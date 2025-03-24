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

# MySQL 인스턴스 초기화
mysql = MySQL(app)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='app.log'
)
logger = logging.getLogger('app')

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
# 데이터베이스 관련 함수
#---------------------------------------------------
def get_medicine_shapes():
    """의약품 모양 목록 가져오기"""
    conn = mysql.connection
    try:
        with conn.cursor(MySQLdb.cursors.DictCursor) as cursor:
            query = """
            SELECT DISTINCT drug_shape 
            FROM medicine_shapes 
            WHERE drug_shape IS NOT NULL AND drug_shape != '' 
            ORDER BY drug_shape
            """
            cursor.execute(query)
            shapes = cursor.fetchall()
            return [shape['drug_shape'] for shape in shapes] if shapes else []
    except Exception as e:
        logger.error(f"의약품 모양 목록 조회 오류: {e}")
        return []

def get_medicine_colors():
    """의약품 색상 목록 가져오기"""
    conn = mysql.connection
    try:
        with conn.cursor(MySQLdb.cursors.DictCursor) as cursor:
            query = """
            SELECT DISTINCT color_class1 
            FROM medicine_shapes 
            WHERE color_class1 IS NOT NULL AND color_class1 != '' 
            ORDER BY color_class1
            """
            cursor.execute(query)
            colors = cursor.fetchall()
            return [color['color_class1'] for color in colors] if colors else []
    except Exception as e:
        logger.error(f"의약품 색상 목록 조회 오류: {e}")
        return []

def search_medicines_in_db(params):
    """데이터베이스에서 의약품 검색"""
    conn = mysql.connection
    try:
        with conn.cursor(MySQLdb.cursors.DictCursor) as cursor:
            base_query = """
            SELECT m.id, m.item_seq, m.item_name, m.entp_name, m.class_name, 
                   ms.drug_shape, ms.color_class1, ms.print_front, ms.print_back,
                   mi.item_image
            FROM medicines m
            LEFT JOIN medicine_shapes ms ON m.id = ms.medicine_id
            LEFT JOIN medicine_images mi ON m.id = mi.medicine_id
            WHERE 1=1
            """
            
            query_params = []
            
            # 검색 파라미터 처리
            if 'item_name' in params and params['item_name']:
                base_query += " AND m.item_name LIKE %s"
                query_params.append(f"%{params['item_name']}%")
            
            if 'drug_shape' in params and params['drug_shape']:
                base_query += " AND ms.drug_shape = %s"
                query_params.append(params['drug_shape'])
            
            if 'color_class1' in params and params['color_class1']:
                base_query += " AND ms.color_class1 = %s"
                query_params.append(params['color_class1'])
            
            if 'print_front' in params and params['print_front']:
                base_query += " AND (ms.print_front LIKE %s OR ms.print_back LIKE %s)"
                query_params.append(f"%{params['print_front']}%")
                query_params.append(f"%{params['print_front']}%")
            
            base_query += " ORDER BY m.item_name LIMIT 100"
            
            cursor.execute(base_query, query_params)
            results = cursor.fetchall()
            
            return results
    except Exception as e:
        logger.error(f"의약품 검색 오류: {e}")
        return []

def get_medicine_detail_from_db(medicine_id):
    """데이터베이스에서 의약품 상세 정보 가져오기"""
    conn = mysql.connection
    try:
        with conn.cursor(MySQLdb.cursors.DictCursor) as cursor:
            # 기본 정보
            base_query = """
            SELECT m.*, ms.*, mi.item_image
            FROM medicines m
            LEFT JOIN medicine_shapes ms ON m.id = ms.medicine_id
            LEFT JOIN medicine_images mi ON m.id = mi.medicine_id
            WHERE m.id = %s
            """
            cursor.execute(base_query, (medicine_id,))
            medicine = cursor.fetchone()
            
            if not medicine:
                return None
            
            # 용법/용량 정보
            usage_query = """
            SELECT * FROM medicine_usage
            WHERE medicine_id = %s
            """
            cursor.execute(usage_query, (medicine_id,))
            usage = cursor.fetchone()
            
            # 성분 정보
            component_query = """
            SELECT * FROM medicine_components
            WHERE medicine_id = %s
            """
            cursor.execute(component_query, (medicine_id,))
            components = cursor.fetchall()
            
            # 병용금기 정보
            dur_query = """
            SELECT * FROM medicine_dur_usjnt
            WHERE medicine_id = %s
            """
            cursor.execute(dur_query, (medicine_id,))
            dur_info = cursor.fetchall()
            
            # 통합 결과
            result = {
                'basic': medicine,
                'usage': usage,
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
    # 로그인 여부 확인
    if 'loggedin' in session:
        # 로그인한 경우 메인 검색 페이지로 이동
        # 의약품 모양과 색상 목록 가져오기
        shapes = get_medicine_shapes()
        colors = get_medicine_colors()
        
        return render_template('index.html', username=session['username'], shapes=shapes, colors=colors)
    # 로그인하지 않은 경우 로그인 페이지로 리디렉션
    return redirect(url_for('login'))

@app.route('/search', methods=['GET', 'POST'])
def search():
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        # POST 요청에서 검색 파라미터 가져오기
        search_params = {
            'item_name': request.form.get('item_name', ''),
            'drug_shape': request.form.get('drug_shape', ''),
            'color_class1': request.form.get('color_class1', ''),
            'print_front': request.form.get('print_front', '')
        }
    else:
        # GET 요청에서 검색 파라미터 가져오기
        search_params = {
            'item_name': request.args.get('item_name', ''),
            'drug_shape': request.args.get('drug_shape', ''),
            'color_class1': request.args.get('color_class1', ''),
            'print_front': request.args.get('print_front', '')
        }
    
    # 검색 실행 - 데이터베이스에서 먼저 검색
    results = search_medicines_in_db(search_params)
    
    # 결과가 없으면 API에서 실시간 검색
    if not results:
        try:
            # API 파라미터 매핑
            api_params = {}
            if search_params['item_name']:
                api_params['item_name'] = search_params['item_name']
            if search_params['drug_shape']:
                api_params['drug_shape'] = search_params['drug_shape']
            if search_params['color_class1']:
                api_params['color_class1'] = search_params['color_class1']
            if search_params['print_front']:
                api_params['print_front'] = search_params['print_front']
                
            # API 호출
            api_results = search_medicines_by_shape(api_params)
            if api_results and api_results['items']:
                # API 결과 형식을 DB 결과 형식으로 변환
                results = []
                for item in api_results['items']:
                    results.append({
                        'id': None,  # API 결과는 DB ID가 없음
                        'item_seq': item.get('ITEM_SEQ', ''),
                        'item_name': item.get('ITEM_NAME', ''),
                        'entp_name': item.get('ENTP_NAME', ''),
                        'drug_shape': item.get('DRUG_SHAPE', ''),
                        'color_class1': item.get('COLOR_CLASS1', ''),
                        'print_front': item.get('PRINT_FRONT', ''),
                        'print_back': item.get('PRINT_BACK', ''),
                        'item_image': item.get('ITEM_IMAGE', '')
                    })
        except Exception as e:
            logger.error(f"API 검색 오류: {e}")
    
    # 의약품 모양과 색상 목록 가져오기
    shapes = get_medicine_shapes()
    colors = get_medicine_colors()
    
    return render_template(
        'search_results.html', 
        results=results, 
        params=search_params,
        shapes=shapes,
        colors=colors,
        username=session.get('username', '')
    )

@app.route('/medicine/<int:medicine_id>')
def medicine_detail(medicine_id):
    if 'loggedin' not in session:
        return redirect(url_for('login'))
        
    # 의약품 상세 정보 가져오기
    medicine = get_medicine_detail_from_db(medicine_id)
    
    # DB에 정보가 없는 경우 API에서 정보 가져오기
    if not medicine and 'item_seq' in request.args:
        try:
            item_seq = request.args['item_seq']
            # API에서 상세 정보 가져오기
            basic_info = get_medicine_detail(item_seq)
            dur_info = get_dur_info(item_seq)
            components = get_medicine_components(item_seq)
            
            if basic_info:
                # API 결과를 DB 결과 형식으로 변환
                medicine = {
                    'basic': {
                        'item_name': basic_info.get('itemName', ''),
                        'entp_name': basic_info.get('entpName', ''),
                        'item_image': basic_info.get('itemImage', '')
                    },
                    'usage': {
                        'efcy_qesitm': basic_info.get('efcyQesitm', ''),
                        'use_method_qesitm': basic_info.get('useMethodQesitm', ''),
                        'atpn_warn_qesitm': basic_info.get('atpnWarnQesitm', ''),
                        'atpn_qesitm': basic_info.get('atpnQesitm', ''),
                        'intrc_qesitm': basic_info.get('intrcQesitm', ''),
                        'se_qesitm': basic_info.get('seQesitm', ''),
                        'deposit_method_qesitm': basic_info.get('depositMethodQesitm', '')
                    },
                    'components': components,
                    'dur_info': dur_info
                }
        except Exception as e:
            logger.error(f"API 상세 정보 조회 오류: {e}")
    
    if not medicine:
        return redirect(url_for('index'))
    
    return render_template('medicine_detail.html', medicine=medicine, username=session.get('username', ''))

#---------------------------------------------------
# 라우트 - API 호출
#---------------------------------------------------
@app.route('/api/search', methods=['GET'])
def api_search():
    if 'loggedin' not in session:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
        
    # API 검색 엔드포인트
    search_params = {
        'item_name': request.args.get('item_name', ''),
        'drug_shape': request.args.get('drug_shape', ''),
        'color_class1': request.args.get('color_class1', ''),
        'print_front': request.args.get('print_front', '')
    }
    
    # 데이터베이스에서 검색
    results = search_medicines_in_db(search_params)
    
    # 결과가 없으면 API에서 검색
    if not results:
        try:
            # API 파라미터 매핑
            api_params = {}
            if search_params['item_name']:
                api_params['item_name'] = search_params['item_name']
            if search_params['drug_shape']:
                api_params['drug_shape'] = search_params['drug_shape']
            if search_params['color_class1']:
                api_params['color_class1'] = search_params['color_class1']
            if search_params['print_front']:
                api_params['print_front'] = search_params['print_front']
                
            # API 호출
            api_results = search_medicines_by_shape(api_params)
            if api_results and api_results['items']:
                # API 결과 형식을 DB 결과 형식으로 변환
                results = []
                for item in api_results['items']:
                    results.append({
                        'id': None,  # API 결과는 DB ID가 없음
                        'item_seq': item.get('ITEM_SEQ', ''),
                        'item_name': item.get('ITEM_NAME', ''),
                        'entp_name': item.get('ENTP_NAME', ''),
                        'drug_shape': item.get('DRUG_SHAPE', ''),
                        'color_class1': item.get('COLOR_CLASS1', ''),
                        'print_front': item.get('PRINT_FRONT', ''),
                        'print_back': item.get('PRINT_BACK', ''),
                        'item_image': item.get('ITEM_IMAGE', '')
                    })
        except Exception as e:
            logger.error(f"API 검색 오류: {e}")
            return jsonify({'success': False, 'message': f"API 검색 오류: {str(e)}"}), 500
    
    return jsonify({
        'success': True,
        'count': len(results),
        'results': results
    })

@app.route('/api/medicine/<int:medicine_id>', methods=['GET'])
def api_medicine_detail(medicine_id):
    if 'loggedin' not in session:
        return jsonify({'success': False, 'message': '로그인이 필요합니다.'}), 401
        
    # API 상세 정보 엔드포인트
    medicine = get_medicine_detail_from_db(medicine_id)
    
    if not medicine:
        return jsonify({
            'success': False,
            'message': '의약품을 찾을 수 없습니다.'
        }), 404
    
    return jsonify({
        'success': True,
        'medicine': medicine
    })

#---------------------------------------------------
# 라우트 - 로그인/회원가입
#---------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    # 로그인 폼 제출 처리
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']
        
        # MySQL 커서 생성
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        
        # 사용자 정보 가져오기
        user = cursor.fetchone()
        
        # 로그인 정보 검증
        if user and check_password_hash(user['password'], password):
            # 로그인 성공, 세션 생성
            session['loggedin'] = True
            session['id'] = user['id']
            session['username'] = user['username']
            
            # 메인 페이지로 리디렉션
            return redirect(url_for('index'))
        else:
            # 로그인 실패
            flash('잘못된 사용자 이름/비밀번호입니다!')
    
    # 로그인 페이지 렌더링
    return render_template('login.html')

@app.route('/logout')
def logout():
    # 세션에서 사용자 정보 제거
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    
    # 로그인 페이지로 리디렉션
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    # 회원가입 폼 제출 처리
    if request.method == 'POST':
        # 폼 데이터 가져오기
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        age = request.form['age']
        ssn = request.form['ssn']  # 주민등록번호
        phone = request.form['phone']
        height = request.form['height']
        weight = request.form['weight']
        
        # MySQL 커서 생성
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # 사용자 이름 중복 확인
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        account = cursor.fetchone()
        
        # 폼 유효성 검사
        if account:
            flash('이미 존재하는 계정입니다!')
        elif not re.match(r'[A-Za-z0-9]+', username):
            flash('사용자 이름은 문자와 숫자만 포함해야 합니다!')
        elif not username or not password or not name or not age or not ssn or not phone:
            flash('양식을 작성해주세요!')
        else:
            # 비밀번호 해싱
            hashed_password = generate_password_hash(password)
            
            # 새 사용자 추가
            cursor.execute('INSERT INTO users (username, password, name, age, ssn, phone, height, weight) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                           (username, hashed_password, name, age, ssn, phone, height, weight))
            mysql.connection.commit()
            
            flash('성공적으로 등록되었습니다!')
            return redirect(url_for('login'))
    
    # 회원가입 페이지 렌더링
    return render_template('register.html')

#---------------------------------------------------
# 메인 함수
#---------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)