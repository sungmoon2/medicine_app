import os
import google.generativeai as genai
from dotenv import load_dotenv
import pymysql
from pymysql.cursors import DictCursor

# 환경 변수 로드
load_dotenv()

# Gemini API 초기화
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# 사용 가능한 모델 확인 - 로깅 목적
try:
    models = genai.list_models()
    available_models = [model.name for model in models]
    print(f"사용 가능한 모델: {available_models}")
except Exception as e:
    print(f"모델 목록 조회 오류: {str(e)}")

# 가용 모델 리스트 (출력된 목록에서 확인된 모델들)
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
        print(f"{model_name} 모델 로드 시도 중...")
        model = genai.GenerativeModel(model_name)
        print(f"{model_name} 모델 로드 성공!")
        break  # 성공하면 반복 중단
    except Exception as e:
        print(f"{model_name} 모델 로드 실패: {str(e)}")

# 모든 모델 로드 실패 시
if model is None:
    print("경고: 모든 모델 로드 실패. 기본 검색 기능만 사용합니다.")

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
        다음 의약품 검색 질문을 분석하여 아래 정보를 추출하세요:
        - 약품명 또는 관련 키워드
        - 효능 또는 용도
        - 약품 형태 (정제, 캡슐 등)
        - 색상 정보
        - 모양 정보
        - 제조사 정보
        
        추출된 정보를 JSON 형식으로 반환하세요. 해당 정보가 없으면 null로 표시하세요.
        """
        
        # system role 없이 단일 프롬프트로 전송
        combined_prompt = f"{system_prompt}\n\n질문: {query}\n\n분석 결과:"
        
        try:
            response = model.generate_content(combined_prompt)
        except Exception as e:
            print(f"모델 호출 오류: {str(e)}")
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
            else:
                # 파싱 실패 시 기본 검색 파라미터
                search_params = {
                    "item_name": query,
                    "efficacy": None,
                    "form": None,
                    "color": None,
                    "shape": None,
                    "manufacturer": None
                }
        except:
            # JSON 파싱 오류 시 기본 검색 파라미터
            search_params = {
                "item_name": query,
                "efficacy": None,
                "form": None,
                "color": None,
                "shape": None,
                "manufacturer": None
            }
            
        # 3. 검색 쿼리 구성
        query_parts = []
        params = []
        
        if search_params.get("item_name"):
            query_parts.append("(item_name LIKE %s OR item_eng_name LIKE %s)")
            name_param = f"%{search_params['item_name']}%"
            params.extend([name_param, name_param])
            
        if search_params.get("manufacturer"):
            query_parts.append("entp_name LIKE %s")
            params.append(f"%{search_params['manufacturer']}%")
            
        if search_params.get("efficacy"):
            query_parts.append("(class_name LIKE %s OR efcy_qesitm LIKE %s)")
            efficacy_param = f"%{search_params['efficacy']}%"
            params.extend([efficacy_param, efficacy_param])
            
        if search_params.get("form"):
            query_parts.append("form_code_name LIKE %s")
            params.append(f"%{search_params['form']}%")
            
        if search_params.get("color"):
            query_parts.append("color_class1 LIKE %s")
            params.append(f"%{search_params['color']}%")
            
        if search_params.get("shape"):
            query_parts.append("drug_shape LIKE %s")
            params.append(f"%{search_params['shape']}%")
            
        # 검색 조건이 없는 경우
        if not query_parts:
            # 전체 텍스트 검색으로 fallback
            query_parts.append("(item_name LIKE %s OR class_name LIKE %s OR chart LIKE %s)")
            fallback_param = f"%{query}%"
            params.extend([fallback_param, fallback_param, fallback_param])
            
        # 4. DB 쿼리 실행
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                where_clause = " AND ".join(query_parts)
                sql = f"""
                SELECT id, item_name, item_eng_name, entp_name, chart, 
                       class_name, class_no, etc_otc_name, drug_shape, color_class1,
                       form_code_name, item_image 
                FROM drug_identification 
                WHERE {where_clause}
                LIMIT 10
                """
                
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
                    
                    # AI 요약 생성
                    summary_prompt = f"""
                    다음은 사용자 질문 "{query}"에 대한 검색 결과입니다:
                    {result_items}
                    
                    이 검색 결과를 사용자에게 친절하게 요약해주세요. 
                    검색 결과가 사용자의 질문과 얼마나 관련이 있는지,
                    어떤 특징을 가진 약품들이 검색되었는지 설명해주세요.
                    """
                    
                    summary_response = model.generate_content(summary_prompt)
                    ai_summary = summary_response.text
                else:
                    ai_summary = f"죄송합니다. '{query}'에 대한 검색 결과가 없습니다. 다른 검색어로 시도해보세요."
                
                return {
                    "success": True,
                    "results": results,
                    "ai_summary": ai_summary,
                    "search_params": search_params
                }
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"AI 검색 오류: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "message": "AI 검색 중 오류가 발생했습니다."
        }