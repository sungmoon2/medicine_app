import os
import google.generativeai as genai
from dotenv import load_dotenv
import pymysql
from pymysql.cursors import DictCursor
import re
import logging

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gemini API 초기화
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# 가용 모델 리스트
gemini_models = [
    'models/gemini-1.5-pro',
    'models/gemini-1.5-flash',
    'models/gemini-1.5-flash-8b',
    'models/gemini-pro-vision'
]

# 모델 로드 시도
model = None
for model_name in gemini_models:
    try:
        logger.info(f"{model_name} 모델 로드 시도 중...")
        model = genai.GenerativeModel(model_name)
        logger.info(f"{model_name} 모델 로드 성공!")
        break  # 성공하면 반복 중단
    except Exception as e:
        logger.error(f"{model_name} 모델 로드 실패: {str(e)}")

# 모든 모델 로드 실패 시
if model is None:
    logger.warning("경고: 모든 모델 로드 실패. 기본 검색 기능만 사용합니다.")

def get_db_connection():
    """데이터베이스 연결 생성 함수"""
    return pymysql.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'root'),
        password=os.getenv('DB_PASSWORD', '1234'),
        db=os.getenv('DB_NAME', 'medicine_db'),
        charset='utf8mb4',
        cursorclass=DictCursor
    )

def ai_search_medicine(query):
    """AI를 활용한 의약품 검색 함수"""
    try:
        # 1. 시스템 프롬프트와 사용자 질의를 하나의 프롬프트로 합침
        system_prompt = """
        당신은 의약품 정보를 검색하는 봇입니다.
        사용자의 자연어 검색 질문을 분석하여 다음과 같은 정보를 추출하세요:
        
        1. 약품명 또는 관련 키워드
        2. 효능 또는 용도 (두통, 감기, 소화 등)
        3. 증상 (열, 통증, 피로 등)
        4. 약품 형태 (정제, 캡슐 등)
        5. 색상 정보
        6. 모양 정보
        7. 제조사 정보
        
        추출된 정보를 JSON 형식으로 반환하고, 각 필드에 다음과 같이 추출하세요:
        
        {
            "item_name": "약품명 키워드",
            "efficacy": "효능이나 용도 키워드",
            "symptom": "증상 키워드", 
            "form": "약품 형태",
            "color": "색상 정보",
            "shape": "모양 정보",
            "manufacturer": "제조사 정보"
        }
        
        해당 정보가 없으면 null로 표시하세요.
        효능이나 증상 관련 단어는 매우 중요하므로 반드시 추출하세요.
        예를 들어:
        - "두통에 좋은 약 찾아줘" → {"efficacy": "진통제", "symptom": "두통"} 등으로 추출
        - "소화가 잘 안될 때 먹는 약" → {"efficacy": "소화제", "symptom": "소화불량"} 등으로 추출
        """
        
        # system role 없이 단일 프롬프트로 전송
        combined_prompt = f"{system_prompt}\n\n질문: {query}\n\n분석 결과:"
        
        try:
            response = model.generate_content(combined_prompt)
        except Exception as e:
            logger.error(f"모델 호출 오류: {str(e)}")
            # 다른 형식으로 다시 시도
            response = model.generate_content({
                "contents": [{"parts": [{"text": combined_prompt}]}]
            })
        
        # 2. 응답 텍스트를 파싱하여 검색 파라미터 추출
        import json
        try:
            text_response = response.text
            # JSON 형식 데이터 추출
            if '{' in text_response and '}' in text_response:
                json_str = text_response[text_response.find('{'):text_response.rfind('}')+1]
                search_params = json.loads(json_str)
                logger.info(f"AI 추출 검색 파라미터: {search_params}")
            else:
                # 파싱 실패 시 기본 검색 파라미터
                search_params = {
                    "item_name": query,
                    "efficacy": None,
                    "symptom": None,
                    "form": None,
                    "color": None,
                    "shape": None,
                    "manufacturer": None
                }
        except Exception as json_err:
            logger.error(f"JSON 파싱 오류: {json_err}")
            # JSON 파싱 오류 시 기본 검색 파라미터
            search_params = {
                "item_name": query,
                "efficacy": None,
                "symptom": None,
                "form": None,
                "color": None,
                "shape": None,
                "manufacturer": None
            }
        
        # 3. 검색 쿼리 구성 (퍼지 검색 로직으로 개선)
        all_search_terms = []  # 모든 검색어를 수집
        
        # 효능/용도와 증상 정보를 활용한 검색 로직 추가
        efficacy_keywords = search_params.get("efficacy")
        symptom_keywords = search_params.get("symptom")
        
        # 효능 키워드로 확장 검색
        if efficacy_keywords:
            # 효능 관련 동의어 추가
            efficacy_mapping = {
                "진통": ["진통", "통증완화", "페인", "통증", "두통", "편두통", "해열", "소염"],
                "소화": ["소화", "소화불량", "위장", "속쓰림", "위산", "위통", "소화제"],
                "감기": ["감기", "기침", "코감기", "콧물", "인후통", "비염", "감기약"],
                "알레르기": ["알레르기", "알러지", "항히스타민", "가려움"],
                "수면": ["수면", "불면", "불면증", "수면제", "수면유도"],
                "영양제": ["영양", "비타민", "미네랄", "종합영양"]
            }
            
            # 효능 키워드 확장
            expanded_efficacy_terms = [efficacy_keywords]
            for category, terms in efficacy_mapping.items():
                for term in terms:
                    if term in efficacy_keywords.lower():
                        expanded_efficacy_terms.extend(terms)
                        break
            
            # 중복 제거
            expanded_efficacy_terms = list(set(expanded_efficacy_terms))
            all_search_terms.extend(expanded_efficacy_terms)
        
        # 증상 키워드로 검색
        if symptom_keywords:
            # 증상 동의어 매핑
            symptom_mapping = {
                "두통": ["두통", "편두통", "머리 아픔", "머리통증"],
                "소화불량": ["소화불량", "속쓰림", "소화 안됨", "더부룩", "속 불편"],
                "감기": ["감기", "콧물", "기침", "인후통", "코막힘"],
                "알레르기": ["알레르기", "알러지", "가려움", "두드러기"]
            }
            
            expanded_symptom_terms = [symptom_keywords]
            for category, terms in symptom_mapping.items():
                for term in terms:
                    if term in symptom_keywords.lower():
                        expanded_symptom_terms.extend(terms)
                        break
            
            expanded_symptom_terms = list(set(expanded_symptom_terms))
            all_search_terms.extend(expanded_symptom_terms)
        
        # 약품명 추가
        if search_params.get("item_name") and search_params.get("item_name") != query:
            all_search_terms.append(search_params.get("item_name"))
            
        # 제조사 추가
        if search_params.get("manufacturer"):
            all_search_terms.append(search_params.get("manufacturer"))
            
        # 형태 추가    
        if search_params.get("form"):
            all_search_terms.append(search_params.get("form"))
            
        # 색상 추가
        if search_params.get("color"):
            all_search_terms.append(search_params.get("color"))
            
        # 모양 추가
        if search_params.get("shape"):
            all_search_terms.append(search_params.get("shape"))
        
        # 원본 쿼리 자체도 검색어로 추가
        all_search_terms.append(query)
        
        # 검색어가 없는 경우
        if not all_search_terms:
            all_search_terms = [query]  # 원본 쿼리를 그대로 사용
            
        # 중복 제거
        all_search_terms = list(set(all_search_terms))
        
        # 단일 OR 쿼리로 구성 (더 많은 결과를 얻기 위해)
        or_conditions = []
        params = []
        
        for term in all_search_terms:
            or_conditions.append("(item_name LIKE %s OR class_name LIKE %s OR chart LIKE %s)")
            params.extend([f"%{term}%", f"%{term}%", f"%{term}%"])
        
        # 쿼리 로깅
        logger.info(f"검색 키워드: {all_search_terms}")
        logger.info(f"검색 조건: {or_conditions}")
        logger.info(f"검색 파라미터: {params}")
        
        # 4. DB 쿼리 실행
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                where_clause = " OR ".join(or_conditions)  # OR로 조건 연결 (더 많은 결과)
                sql = f"""
                SELECT id, item_name, item_eng_name, entp_name, chart, 
                       class_name, class_no, etc_otc_name, drug_shape, color_class1,
                       form_code_name, item_image 
                FROM drug_identification 
                WHERE {where_clause}
                LIMIT 10
                """
                
                logger.info(f"실행 SQL: {sql}")
                cursor.execute(sql, params)
                results = cursor.fetchall()
                
                # 5. AI에게 결과 요약 요청
                if results:
                    result_summary = f"검색 결과 {len(results)}개가 발견되었습니다."
                    
                    # 결과의 첫 3개 항목만 요약에 포함
                    result_items = []
                    for idx, r in enumerate(results[:3]):
                        item = {
                            "name": r["item_name"],
                            "manufacturer": r["entp_name"],
                            "class": r["class_name"] if r["class_name"] else "정보 없음",
                            "shape": r["drug_shape"] if r["drug_shape"] else "정보 없음",
                            "color": r["color_class1"] if r["color_class1"] else "정보 없음", 
                            "description": r["chart"] if r["chart"] else "정보 없음"
                        }
                        result_items.append(item)
                    
                    # AI 요약 생성 (프롬프트 개선)
                    summary_prompt = f"""
                    다음은 사용자 질문 "{query}"에 대한 검색 결과입니다:
                    {result_items}
                    
                    이 검색 결과를 사용자에게 친절하게 요약해주세요.
                    원래 사용자 질문과 결과의 연관성을 먼저 설명하고,
                    검색된 약품들의 주요 정보와 효능에 대해 쉽게 설명해주세요.
                    약사처럼 전문적이고 신뢰성 있게 정보를 제공하되, 
                    이것은 단순히 검색 결과일 뿐 실제 의학적 조언이 아님을 알려주세요.
                    """
                    
                    summary_response = model.generate_content(summary_prompt)
                    ai_summary = summary_response.text
                else:
                    # 검색어와 함께 대안 제시
                    alternatives = ["진통제", "소화제", "감기약", "알레르기약", "비타민"]
                    ai_summary = f"죄송합니다. '{query}'에 대한 검색 결과가 없습니다. 다른 검색어나 표현으로 시도해보세요. 예를 들어, '{alternatives[0]}'나 '{alternatives[1]}' 등의 키워드로 검색해보세요."
                
                return {
                    "success": True,
                    "results": results,
                    "ai_summary": ai_summary,
                    "search_params": search_params,
                    "query": query
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"AI 검색 오류: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "AI 검색 중 오류가 발생했습니다."
        }