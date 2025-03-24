from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
import os
import json
import logging
import requests
import xml.etree.ElementTree as ET
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import time
from advanced_search_controller import advanced_search_bp  # 고급 검색 블루프린트 import

# 로그 디렉토리 확인 및 생성
log_dir = os.path.dirname(os.path.abspath('app.log'))
os.makedirs(log_dir, exist_ok=True)

# 환경 변수 로드
load_dotenv()

# 앱 초기화
app = Flask(__name__)

# 세션 비밀키 설정
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your_secret_key')

# MySQL 연결 설정
app.config['MYSQL_HOST'] = os.getenv('DB_HOST', 'localhost')
app.config['MYSQL_USER'] = os.getenv('DB_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.getenv('DB_PASSWORD', 'your_password')
app.config['MYSQL_DB'] = os.getenv('DB_NAME', 'medicine_db')
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

# 데이터베이스 테이블 설정
app.config['DATABASE_TABLE'] = os.getenv('DB_TABLE', 'drug_identification')

# 블루프린트 등록
app.register_blueprint(advanced_search_bp, url_prefix='/advanced')

# MySQL 인스턴스 초기화
mysql = MySQL(app)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log',  # 절대 경로 사용 권장
    filemode='a'  # append 모드로 설정
)
# 콘솔 핸들러 추가
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

logger = logging.getLogger('app')
logger.addHandler(console_handler)

# API 키 설정
API_KEY = os.getenv('OPEN_API_KEY')
ENCODED_API_KEY = requests.utils.quote(API_KEY) if API_KEY else ''

# API 기본 URL 설정
API_BASE_URLS = {
    'drug_info': 'http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList',
    'pill_info': 'http://apis.data.go.kr/1471000/MdcinGrnIdntfcAPIService/getMdcinGrnIdntfcList',
    'medicine_info': 'http://apis.data.go.kr/1471000/DrugInfoService/getDrugInfo',
    'component_info': 'http://apis.data.go.kr/1471000/DrugIngrNameService/getIngredientInfoList',
    'daily_dose': 'http://apis.data.go.kr/1471000/MedicDayMaxDoseInfoService/getMedicDayMaxDoseInfo'
}

# DUR 관련 API 엔드포인트
DUR_ENDPOINTS = {
    'usjnt': 'getUsjntTabooInfoList03',     # 병용금기
    'age': 'getSpcifyAgrdeTabooInfoList03', # 특정연령대금기
    'pregnancy': 'getPwnmTabooInfoList03',  # 임부금기
    'capacity': 'getCpctyAtentInfoList03',  # 용량주의
    'period': 'getMdctnPdAtentInfoList03',  # 투여기간주의
    'elderly': 'getOdsnAtentInfoList03',    # 노인주의
    'duplicate': 'getEfcyDplctInfoList03',  # 효능군중복
    'split': 'getSeobangjeongPartitnAtentInfoList03' # 서방정분할주의
}

#---------------------------------------------------
# API 호출 함수
#---------------------------------------------------
def fetch_api_data(url, params, retries=3, delay=1):
    """API 요청 함수"""
    try:
        for attempt in range(retries):
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                return response.text
            
            logger.warning(f"API 요청 실패: {response.status_code}. 재시도 {attempt+1}/{retries}")
            time.sleep(delay)
        
        logger.error(f"API 요청 실패: 최대 재시도 횟수 초과. URL: {url}")
        return None
    except Exception as e:
        logger.error(f"API 요청 예외 발생: {e}, URL: {url}")
        return None

def parse_xml_response(xml_text):
    """XML 파싱 함수"""
    try:
        root = ET.fromstring(xml_text)
        return root
    except Exception as e:
        logger.error(f"XML 파싱 오류: {e}")
        return None

def call_api(endpoint_key, params=None):
    """API 호출 통합 함수"""
    if params is None:
        params = {}
    
    # 기본 파라미터에 API 키 추가
    params['serviceKey'] = ENCODED_API_KEY
    
    # 데이터 포맷이 지정되지 않은 경우 XML로 설정
    if 'type' not in params:
        params['type'] = 'xml'
        
    # 엔드포인트 URL 결정
    url = None
    if endpoint_key in API_BASE_URLS:
        url = API_BASE_URLS[endpoint_key]
    elif endpoint_key.startswith('dur_'):
        # DUR 관련 API 호출
        dur_type = endpoint_key.split('_')[1]
        if dur_type in DUR_ENDPOINTS:
            url = f"{API_BASE_URLS['dur_info']}/{DUR_ENDPOINTS[dur_type]}"
    
    if url is None:
        logger.error(f"알 수 없는 엔드포인트: {endpoint_key}")
        return None
    
    # API 호출
    xml_data = fetch_api_data(url, params)
    if not xml_data:
        return None
    
    # XML 파싱
    root = parse_xml_response(xml_data)
    return root

#---------------------------------------------------
# 의약품 API 호출 함수
#---------------------------------------------------
def search_medicines_by_shape(params=None, page_no=1, num_of_rows=10):
    """의약품 모양, 색상 등으로 검색"""
    if params is None:
        params = {}
    
    # 페이징 파라미터 추가
    params['pageNo'] = page_no
    params['numOfRows'] = num_of_rows
    
    # API 호출
    root = call_api('pill_info', params)
    if root is None:
        return None
    
    # 결과 추출
    items = []
    for item in root.findall('.//item'):
        medicine_data = {}
        for child in item:
            medicine_data[child.tag] = child.text
        items.append(medicine_data)
    
    # 전체 결과 수 추출
    total_count = int(root.find('.//totalCount').text) if root.find('.//totalCount') is not None else 0
    
    return {
        'items': items,
        'total_count': total_count,
        'page_no': page_no,
        'num_of_rows': num_of_rows
    }
 
def get_medicine_detail(item_seq):
    """의약품 상세 정보 조회"""
    params = {'itemSeq': item_seq}
    
    # API 호출
    root = call_api('medicine_info', params)
    if root is None:
        return None
    
    # 결과 추출
    item = root.find('.//item')
    if item is None:
        return None
    
    medicine_data = {}
    for child in item:
        medicine_data[child.tag] = child.text
    
    return medicine_data

def get_dur_info(item_seq, dur_type='usjnt'):
    """DUR 정보 조회"""
    params = {'itemSeq': item_seq}
    
    # API 호출
    endpoint_key = f"dur_{dur_type}"
    root = call_api(endpoint_key, params)
    if root is None:
        return None
    
    # 결과 추출
    items = []
    for item in root.findall('.//item'):
        dur_data = {}
        for child in item:
            dur_data[child.tag] = child.text
        items.append(dur_data)
    
    return items

def get_medicine_components(item_seq):
    """의약품 성분 정보 조회"""
    # 의약품 성분 정보 조회 로직
    # 실제 API 사용 시 구현 필요
    return []

#---------------------------------------------------
# 검색 및 데이터베이스 관련 함수
#---------------------------------------------------
def highlight_text(text, search_term):
    """검색어를 하이라이트 처리"""
    if not text or not search_term:
        return text
    
    # 대소문자 구분 없이 검색어 찾기
    pattern = re.compile(re.escape(search_term), re.IGNORECASE)
    return pattern.sub(lambda m: f'<span class="highlight">{m.group(0)}</span>', text)

def search_medicines_in_db(search_params, page=1, per_page=12):
    conn = mysql.connection
    try:
        with conn.cursor(MySQLdb.cursors.DictCursor) as cursor:
            base_query = """
            SELECT 
                id, item_seq, item_name, item_eng_name, 
                entp_seq, entp_name, chart, 
                class_no, class_name, etc_otc_name, 
                item_permit_date, form_code_name, 
                efcy_qesitm, se_qesitm
            FROM unified_medicines
            WHERE 1=1
            """
            
            query_params = []
            
            # 제품명 검색 조건
            product_names = search_params.get('product_names', [])
            if product_names:
                product_conditions = []
                for name in product_names:
                    product_conditions.append(
                        "(LOWER(item_name) LIKE LOWER(%s) OR LOWER(item_name) LIKE LOWER(%s))"
                    )
                    query_params.append(f"%{name}%")  # 포함된 경우
                    query_params.append(f"{name}%")   # 시작하는 경우
                
                base_query += " AND (" + " OR ".join(product_conditions) + ")"
            
            # 제조사 검색 조건
            manufacturers = search_params.get('manufacturers', [])
            if manufacturers:
                manufacturer_conditions = []
                for manufacturer in manufacturers:
                    manufacturer_conditions.append("LOWER(entp_name) LIKE LOWER(%s)")
                    query_params.append(f"%{manufacturer}%")
                if manufacturer_conditions:
                    base_query += " AND (" + " OR ".join(manufacturer_conditions) + ")"
            
            # 부작용 검색 조건
            side_effects = search_params.get('side_effects', [])
            if side_effects:
                side_effect_conditions = []
                for side_effect in side_effects:
                    side_effect_conditions.append("LOWER(se_qesitm) LIKE LOWER(%s)")
                    query_params.append(f"%{side_effect}%")
                if side_effect_conditions:
                    base_query += " AND (" + " OR ".join(side_effect_conditions) + ")"
            
            logger.info(f"최종 검색 쿼리: {base_query}")
            logger.info(f"검색 파라미터: {query_params}")

            # 카운트 쿼리 수정
            count_query = f"""
            SELECT COUNT(*) as total 
            FROM (
                {base_query}
            ) as count_subquery
            """

            logger.info(f"카운트 쿼리: {count_query}")
            logger.info(f"카운트 쿼리 파라미터: {query_params}")

            cursor.execute(count_query, query_params)
            total_count = cursor.fetchone()['total']
            
            # 페이지네이션 적용
            offset = (page - 1) * per_page
            paginated_query = base_query + " ORDER BY item_name LIMIT %s OFFSET %s"
            query_params.extend([per_page, offset])
            
            # 메인 쿼리 실행
            cursor.execute(paginated_query, query_params)
            results = cursor.fetchall()
            
            # 검색 결과에 매치 정보 추가
            for result in results:
                # 제품명 매치 하이라이트
                result['matched_name'] = False
                for name in product_names:
                    if name.lower() in result['item_name'].lower():
                        result['item_name'] = highlight_text(result['item_name'], name)
                        result['matched_name'] = True
                        break
                
                # 제조사 매치 하이라이트
                result['matched_manufacturer'] = False
                for manufacturer in manufacturers:
                    if manufacturer.lower() in result['entp_name'].lower():
                        result['entp_name'] = highlight_text(result['entp_name'], manufacturer)
                        result['matched_manufacturer'] = True
                        break
                
                # 부작용 매치 하이라이트
                result['matched_side_effect'] = False
                if result.get('se_qesitm'):
                    for side_effect in side_effects:
                        if side_effect.lower() in result['se_qesitm'].lower():
                            result['se_qesitm'] = highlight_text(result['se_qesitm'], side_effect)
                            result['matched_side_effect'] = True
                            break
            
            return {
                'results': results,
                'total_count': total_count,
                'page': page,
                'per_page': per_page,
                'total_pages': (total_count + per_page - 1) // per_page
            }
    except Exception as e:
        logger.error(f"의약품 검색 오류: {e}")
        return {
            'results': [],
            'total_count': 0,
            'page': page,
            'per_page': per_page,
            'total_pages': 0
        }
    
def get_medicine_detail_from_db(medicine_id):
    """데이터베이스에서 의약품 상세 정보 가져오기"""
    conn = mysql.connection
    try:
        with conn.cursor(MySQLdb.cursors.DictCursor) as cursor:
            # 기본 정보 - LEFT JOIN 제거, unified_medicines 테이블만 사용
            base_query = """
            SELECT *
            FROM drug_identification
            WHERE id = %s
            """
            cursor.execute(base_query, (medicine_id,))
            medicine = cursor.fetchone()
            
            if not medicine:
                return None
            
            # 성분 정보 쿼리 - 테이블 존재 여부 확인 필요
            try:
                component_query = """
                SELECT * FROM medicine_components
                WHERE medicine_id = %s
                """
                cursor.execute(component_query, (medicine_id,))
                components = cursor.fetchall()
            except Exception as e:
                logger.warning(f"성분 정보 조회 실패: {e}")
                components = []
            
            # 병용금기 정보 쿼리 - 테이블 존재 여부 확인 필요
            try:
                dur_query = """
                SELECT * FROM medicine_dur_usjnt
                WHERE medicine_id = %s
                """
                cursor.execute(dur_query, (medicine_id,))
                dur_info = cursor.fetchall()
            except Exception as e:
                logger.warning(f"DUR 정보 조회 실패: {e}")
                dur_info = []
            
            # 통합 결과
            result = {
                'basic': medicine,
                'components': components,
                'dur_info': dur_info
            }
            
            return result
    except Exception as e:
        logger.error(f"의약품 상세 정보 조회 오류: {e}")
        return None

#---------------------------------------------------
# 라우트 - 메인 페이지 및 검색 관련
#---------------------------------------------------
@app.route('/')
def index():
    return redirect(url_for('advanced_search.index'))

@app.route('/search')
def search():
    # 검색 파라미터 가져오기
    product_names = request.args.getlist('product_name')
    manufacturers = request.args.getlist('manufacturer')
    side_effects = request.args.getlist('side_effect')
    
    # 검색 파라미터가 비어있으면 홈으로 리디렉션
    if not product_names and not manufacturers and not side_effects:
        return redirect(url_for('index'))
    
    # 페이지네이션 파라미터
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 12))
    
    # 검색 파라미터 구성
    search_params = {
        'product_names': product_names,
        'manufacturers': manufacturers,
        'side_effects': side_effects
    }
    
    # 데이터베이스에서 검색
    search_result = search_medicines_in_db(search_params, page, per_page)
    
    # 페이지네이션 URL 구성
    pagination_url = url_for('search') + '?'
    url_params = []
    
    for name in product_names:
        url_params.append(f'product_name={name}')
    
    for manufacturer in manufacturers:
        url_params.append(f'manufacturer={manufacturer}')
    
    for side_effect in side_effects:
        url_params.append(f'side_effect={side_effect}')
    
    pagination_url += '&'.join(url_params)
    
    return render_template(
        'search_results.html',
        results=search_result['results'],
        total_count=search_result['total_count'],
        current_page=page,
        per_page=per_page,
        total_pages=search_result['total_pages'],
        pagination_url=pagination_url,
        search_params=search_params
    )

@app.route('/advanced/medicine_detail/<int:medicine_id>')
def medicine_detail(medicine_id):
    # 의약품 상세 정보 가져오기
    medicine = get_medicine_detail_from_db(medicine_id)
    
    if not medicine:
        flash('의약품 정보를 찾을 수 없습니다.', 'error')
        return redirect(url_for('index'))
    
    return render_template('medicine_detail.html', medicine=medicine)

#---------------------------------------------------
# 메인 함수
#---------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)