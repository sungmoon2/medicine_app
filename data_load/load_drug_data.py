import requests
import xml.etree.ElementTree as ET
import pymysql
import time
import logging
import os
import sys
from dotenv import load_dotenv
import colorama
from colorama import Fore, Style
import json
colorama.init(autoreset=True)  # Windows 콘솔 색상 지원

# 환경 변수 로드
load_dotenv()

# 로깅 설정 개선 - UTF-8 인코딩 명시
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='data_load.log',
    encoding='utf-8'  # 명시적으로 UTF-8 인코딩 지정
)
logger = logging.getLogger('data_load')

# 콘솔 출력을 위한 핸들러 추가
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(console_handler)

def format_api_log(api_name, page_no, total_pages, item_index, total_items, item_name):
    """API 데이터 로드 진행 상황을 포맷팅하는 함수"""
    return (
        f"{Fore.GREEN}API {Fore.RED}{api_name}{Style.RESET_ALL}, "
        f"페이지 {Fore.BLUE}{page_no}/{total_pages}{Style.RESET_ALL}, "
        f"항목 {Fore.BLUE}{item_index}/{total_items}{Style.RESET_ALL} "
        f"처리 중: {item_name}"
    )

# API 키 설정
API_KEY = os.getenv('OPEN_API_KEY')
if not API_KEY:
    logger.error("API 키가 설정되지 않았습니다. .env 파일에 OPEN_API_KEY를 확인하세요.")
    sys.exit(1)

# 데이터베이스 연결 설정
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', '1234'),
    'db': os.getenv('DB_NAME', 'medicine_db'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# API URL을 Dictionary로 변경 (set이 아님)
API_URLS = {
    '의약품개요정보': 'http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList',
    '의약품 낱알식별 정보': 'http://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService01/getMdcinGrnIdntfcInfoList01',
    '의약품성분약효정보': 'http://apis.data.go.kr/B551182/msupCmpnMeftInfoService/getMajorCmpnNmCdList', # 데이터 로드 1개도 안됨.
    '성분별 1일 최대투여량 정보': 'http://apis.data.go.kr/1471000/DayMaxDosgQyByIngdService/getDayMaxDosgQyByIngdInq'
}

# API 별 데이터 테이블 매핑
API_TABLE_MAPPING = {
    '의약품 낱알식별 정보': 'drug_identification',
    '의약품성분약효정보': 'drug_component_efficacy',
    '성분별 1일 최대투여량 정보': 'drug_component_dosage'
}

# 체크포인트 파일 경로
CHECKPOINT_FILE = "data_load_checkpoint.json"

def save_checkpoint(api_key, page_no, processed_count):
    """진행 상황 저장"""
    checkpoint_data = {
        'api_key': api_key,
        'page_no': page_no,
        'processed_count': processed_count,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"체크포인트 저장: API={api_key}, 페이지={page_no}, 처리항목={processed_count}")

def load_checkpoint():
    """저장된 진행 상황 로드"""
    if not os.path.exists(CHECKPOINT_FILE):
        return None
    
    try:
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"체크포인트 로드 오류: {e}")
        return None

def db_connection():
    """데이터베이스 연결 및 오류 시 재시도"""
    max_retries = 3
    retry_delay = 3  # 초
    
    for attempt in range(max_retries):
        try:
            connection = pymysql.connect(**DB_CONFIG)
            return connection
        except Exception as e:
            logger.error(f"데이터베이스 연결 오류 (시도 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                logger.info(f"{retry_delay}초 후 재시도...")
                time.sleep(retry_delay)
            else:
                logger.critical("데이터베이스 연결 실패. 프로그램을 종료합니다.")
                sys.exit(1)

def fetch_drug_data(api_key, page_no=1, num_of_rows=100):
    """의약품 정보 가져오기"""
    if api_key not in API_URLS:
        logger.error(f"알 수 없는 API 키: {api_key}")
        return None
    
    url = API_URLS[api_key]
    
    params = {
        'serviceKey': API_KEY,
        'pageNo': page_no,
        'numOfRows': num_of_rows,
        'type': 'xml'
    }
    
    # 재시도 로직 강화
    max_retries = 5
    retry_delay = 2  # 초
    exponential_backoff = True  # 지수 백오프 사용
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"API 요청: {url}, 페이지={page_no}, 행={num_of_rows}")
            response = requests.get(url, params=params, timeout=30)  # 30초 타임아웃 추가
            
            # 응답 코드 로깅
            logger.debug(f"응답 상태 코드: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    root = ET.fromstring(response.text)
                    
                    # 결과 코드 확인
                    result_code_elem = root.find('.//resultCode')
                    if result_code_elem is not None and result_code_elem.text != '00':
                        result_msg_elem = root.find('.//resultMsg')
                        result_msg = result_msg_elem.text if result_msg_elem is not None else '알 수 없는 오류'
                        logger.error(f"API 오류: {result_code_elem.text} - {result_msg}")
                        return None
                    
                    # 항목 추출
                    items = []
                    for item in root.findall('.//item'):
                        drug_data = {}
                        for child in item:
                            drug_data[child.tag] = child.text
                        items.append(drug_data)
                    
                    # 전체 결과 수
                    total_count_elem = root.find('.//totalCount')
                    count = int(total_count_elem.text) if total_count_elem is not None else 0
                    
                    logger.info(f"API {api_key} - 페이지 {page_no}/{(count + num_of_rows - 1) // num_of_rows} - {len(items)}개 항목 가져옴")
                    
                    return {
                        'items': items,
                        'total_count': count
                    }
                except ET.ParseError as e:
                    logger.error(f"XML 파싱 오류: {e}")
                    logger.debug(f"응답 내용: {response.text[:500]}...")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"XML 파싱 재시도 {attempt+1}/{max_retries}...")
                    else:
                        return None
            elif response.status_code == 429:  # Too Many Requests
                logger.warning(f"API 요청 제한 (429): 페이지 {page_no} - 재시도 {attempt+1}/{max_retries}")
                time.sleep(retry_delay * 5)  # 429 오류 시 더 오래 대기
                continue
            else:
                logger.error(f"API 요청 실패: 상태 코드 {response.status_code} - 재시도 {attempt+1}/{max_retries}")
                logger.debug(f"응답 내용: {response.text[:500]}...")
        except requests.exceptions.RequestException as e:
            logger.error(f"네트워크 오류: {e} - 재시도 {attempt+1}/{max_retries}")
        
        # 지수 백오프를 사용한 재시도 지연
        if exponential_backoff:
            sleep_time = retry_delay * (2 ** attempt)  # 지수적으로 증가
            logger.info(f"{sleep_time}초 후 재시도...")
            time.sleep(sleep_time)
        else:
            logger.info(f"{retry_delay}초 후 재시도...")
            time.sleep(retry_delay)
    
    logger.error(f"최대 재시도 횟수 초과: API {api_key}, 페이지 {page_no}")
    return None
def ensure_tables_exist():
    """새로운 데이터베이스 테이블 구조 확인 및 생성"""
    conn = db_connection()
    
    try:
        with conn.cursor() as cursor:
            # 1. 식품의약품안전처_의약품 낱알식별 정보 테이블
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS drug_identification (
                id INT AUTO_INCREMENT PRIMARY KEY,
                item_seq VARCHAR(100) COMMENT '품목일련번호',
                item_name VARCHAR(500) COMMENT '품목명',
                entp_seq VARCHAR(100) COMMENT '업체일련번호',
                entp_name VARCHAR(300) COMMENT '업체명',
                chart TEXT COMMENT '성상',
                item_image TEXT COMMENT '큰제품이미지',
                print_front VARCHAR(255) COMMENT '표시(앞)',
                print_back VARCHAR(255) COMMENT '표시(뒤)',
                drug_shape VARCHAR(100) COMMENT '의약품모양',
                color_class1 VARCHAR(100) COMMENT '색깔(앞)',
                color_class2 VARCHAR(100) COMMENT '색깔(뒤)',
                line_front VARCHAR(100) COMMENT '분할선(앞)',
                line_back VARCHAR(100) COMMENT '분할선(뒤)',
                leng_long VARCHAR(50) COMMENT '크기(장축)',
                leng_short VARCHAR(50) COMMENT '크기(단축)',
                thick VARCHAR(50) COMMENT '크기(두께)',
                img_regist_ts VARCHAR(100) COMMENT '약학정보원 이미지 생성일',
                class_no VARCHAR(100) COMMENT '분류번호',
                class_name VARCHAR(300) COMMENT '분류명',
                etc_otc_name VARCHAR(100) COMMENT '전문/일반',
                item_permit_date VARCHAR(100) COMMENT '품목허가일자',
                form_code_name VARCHAR(200) COMMENT '제형코드이름',
                mark_code_front_anal TEXT COMMENT '마크내용(앞)',
                mark_code_back_anal TEXT COMMENT '마크내용(뒤)',
                mark_code_front_img TEXT COMMENT '마크이미지(앞)',
                mark_code_back_img TEXT COMMENT '마크이미지(뒤)',
                change_date VARCHAR(100) COMMENT '변경일자',
                mark_code_front VARCHAR(255) COMMENT '마크코드(앞)',
                mark_code_back VARCHAR(255) COMMENT '마크코드(뒤)',
                item_eng_name VARCHAR(500) COMMENT '제품영문명',
                edi_code VARCHAR(100) COMMENT '보험코드',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '데이터 생성일',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '데이터 수정일',
                INDEX idx_item_seq (item_seq),
                INDEX idx_item_name (item_name(255)),
                INDEX idx_edi_code (edi_code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='식품의약품안전처_의약품 낱알식별 정보'
            """)
            
            # 2. 식품의약품안전처_의약품성분약효정보 테이블
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS drug_component_efficacy (
                id INT AUTO_INCREMENT PRIMARY KEY,
                div_nm VARCHAR(400) COMMENT '분류명',
                fomn_tp_nm VARCHAR(100) COMMENT '제형구분명',
                gnl_nm VARCHAR(400) NOT NULL COMMENT '일반명',
                gnl_nm_cd VARCHAR(9) NOT NULL COMMENT '일반명코드',
                injc_pth_nm VARCHAR(100) COMMENT '투여경로명',
                iqty_txt VARCHAR(1000) COMMENT '함량내용',
                meft_div_no VARCHAR(3) COMMENT '약효분류번호',
                unit VARCHAR(70) COMMENT '단위',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '데이터 생성일',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '데이터 수정일',
                INDEX idx_gnl_nm_cd (gnl_nm_cd),
                INDEX idx_meft_div_no (meft_div_no)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='식품의약품안전처_의약품성분약효정보'
            """)
            
            # 3. 건강보험심사평가원_의약품성분약효정보 테이블
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS drug_component_dosage (
                id INT AUTO_INCREMENT PRIMARY KEY,
                cpnt_cd VARCHAR(100) NOT NULL COMMENT '성분코드',
                drug_cpnt_kor_nm VARCHAR(500) NOT NULL COMMENT '성분명(한글)',
                drug_cpnt_eng_nm VARCHAR(500) COMMENT '성분명(영문)',
                foml_cd VARCHAR(100) COMMENT '제형코드',
                foml_nm VARCHAR(300) COMMENT '제형명',
                dosage_route_code VARCHAR(100) COMMENT '투여경로',
                day_max_dosg_qy_unit VARCHAR(100) COMMENT '투여단위',
                day_max_dosg_qy DECIMAL(20,6) COMMENT '1일최대투여량',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '데이터 생성일',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '데이터 수정일',
                INDEX idx_cpnt_cd (cpnt_cd),
                INDEX idx_drug_cpnt_kor_nm (drug_cpnt_kor_nm(255))
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='건강보험심사평가원_의약품성분약효정보'
            """)
            
            # 4. 추가적으로 의약품 데이터를 통합적으로 관리하기 위한 관계 테이블
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS drug_relation (
                id INT AUTO_INCREMENT PRIMARY KEY,
                item_seq VARCHAR(100) COMMENT '품목일련번호(drug_identification 참조)',
                gnl_nm_cd VARCHAR(9) COMMENT '일반명코드(drug_component_efficacy 참조)',
                cpnt_cd VARCHAR(100) COMMENT '성분코드(drug_component_dosage 참조)',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '데이터 생성일',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '데이터 수정일',
                INDEX idx_item_seq (item_seq),
                INDEX idx_gnl_nm_cd (gnl_nm_cd),
                INDEX idx_cpnt_cd (cpnt_cd)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='의약품 데이터 관계 테이블'
            """)
            
            conn.commit()
            logger.info("새로운 데이터베이스 테이블 확인/생성 완료")
    except Exception as e:
        logger.error(f"테이블 생성 오류: {e}")
        conn.rollback()
    finally:
        conn.close()

def insert_drug_data(drug_data, api_key=None):
    """새로운 테이블 구조에 맞게 의약품 데이터 삽입"""
    
    # 재시도 설정
    max_retries = 3
    retry_delay = 1
    
    # API 응답 필드를 DB 필드로 매핑 (대문자/소문자 모두 고려)
    field_mappings = {
        '의약품 낱알식별 정보': {
            'item_seq': ['ITEM_SEQ', 'itemSeq', 'item_seq'],
            'item_name': ['ITEM_NAME', 'itemName'],
            'entp_seq': ['ENTP_SEQ', 'entpSeq'],
            'entp_name': ['ENTP_NAME', 'entpName'],
            'chart': ['CHART', 'chart'],
            'item_image': ['ITEM_IMAGE', 'itemImage'],
            'print_front': ['PRINT_FRONT', 'printFront'],
            'print_back': ['PRINT_BACK', 'printBack'],
            'drug_shape': ['DRUG_SHAPE', 'drugShape'],
            'color_class1': ['COLOR_CLASS1', 'colorClass1', 'COLOR_CLASS', 'colorClass'],
            'color_class2': ['COLOR_CLASS2', 'colorClass2'],
            'line_front': ['LINE_FRONT', 'lineFront'],
            'line_back': ['LINE_BACK', 'lineBack'],
            'leng_long': ['LENG_LONG', 'lengLong'],
            'leng_short': ['LENG_SHORT', 'lengShort'],
            'thick': ['THICK', 'thick'],
            'img_regist_ts': ['IMG_REGIST_TS', 'imgRegistTs'],
            'class_no': ['CLASS_NO', 'classNo'],
            'class_name': ['CLASS_NAME', 'className'],
            'etc_otc_name': ['ETC_OTC_NAME', 'etcOtcName'],
            'item_permit_date': ['ITEM_PERMIT_DATE', 'itemPermitDate'],
            'form_code_name': ['FORM_CODE_NAME', 'formCodeName'],
            'mark_code_front_anal': ['MARK_CODE_FRONT_ANAL', 'markCodeFrontAnal'],
            'mark_code_back_anal': ['MARK_CODE_BACK_ANAL', 'markCodeBackAnal'],
            'mark_code_front_img': ['MARK_CODE_FRONT_IMG', 'markCodeFrontImg'],
            'mark_code_back_img': ['MARK_CODE_BACK_IMG', 'markCodeBackImg'],
            'change_date': ['CHANGE_DATE', 'changeDate'],
            'mark_code_front': ['MARK_CODE_FRONT', 'markCodeFront'],
            'mark_code_back': ['MARK_CODE_BACK', 'markCodeBack'],
            'item_eng_name': ['ITEM_ENG_NAME', 'itemEngName'],
            'edi_code': ['EDI_CODE', 'ediCode']
        },
        '의약품성분약효정보': {
            'div_nm': ['divNm', 'DIV_NM'],
            'fomn_tp_nm': ['fomnTpNm', 'FOMN_TP_NM'],
            'gnl_nm': ['gnlNm', 'GNL_NM'],
            'gnl_nm_cd': ['gnlNmCd', 'GNL_NM_CD'],
            'injc_pth_nm': ['injcPthNm', 'INJC_PTH_NM'],
            'iqty_txt': ['iqtyTxt', 'IQTY_TXT'],
            'meft_div_no': ['meftDivNo', 'MEFT_DIV_NO'],
            'unit': ['unit', 'UNIT']
        },
        '성분별 1일 최대투여량 정보': {
            'cpnt_cd': ['CPNT_CD', 'cpntCd'],
            'drug_cpnt_kor_nm': ['DRUG_CPNT_KOR_NM', 'drugCpntKorNm'],
            'drug_cpnt_eng_nm': ['DRUG_CPNT_ENG_NM', 'drugCpntEngNm'],
            'foml_cd': ['FOML_CD', 'fomlCd'],
            'foml_nm': ['FOML_NM', 'fomlNm'],
            'dosage_route_code': ['DOSAGE_ROUTE_CODE', 'dosageRouteCode'],
            'day_max_dosg_qy_unit': ['DAY_MAX_DOSG_QY_UNIT', 'dayMaxDosgQyUnit'],
            'day_max_dosg_qy': ['DAY_MAX_DOSG_QY', 'dayMaxDosgQy']
        }
    }
    
    # 값 가져오기 함수
    def get_field_value(data, field_key, api_key):
        if api_key in field_mappings and field_key in field_mappings[api_key]:
            for possible_field in field_mappings[api_key][field_key]:
                if possible_field in data and data[possible_field] is not None:
                    return data[possible_field]
        return None
    
    # 식별자 확인
    primary_identifier = None
    table_name = API_TABLE_MAPPING.get(api_key)
    
    if api_key == '의약품 낱알식별 정보':
        primary_identifier = get_field_value(drug_data, 'item_seq', api_key)
        id_field = 'item_seq'
    elif api_key == '의약품성분약효정보':
        primary_identifier = get_field_value(drug_data, 'gnl_nm_cd', api_key)
        id_field = 'gnl_nm_cd'
    elif api_key == '성분별 1일 최대투여량 정보':
        primary_identifier = get_field_value(drug_data, 'cpnt_cd', api_key)
        id_field = 'cpnt_cd'
    
    if not primary_identifier or not table_name:
        logger.warning(f"API {api_key}: 식별자 또는 테이블 매핑 없음 - 건너뜀")
        if api_key and api_key in field_mappings:
            available_fields = list(drug_data.keys())
            logger.debug(f"가용 필드: {available_fields}")
        return False
    
    # 로그 출력
    logger.debug(f"테이블: {table_name}, 식별자: {id_field}={primary_identifier}")
    
    # DB 삽입 로직
    for attempt in range(max_retries):
        conn = db_connection()
        try:
            with conn.cursor() as cursor:
                # 기존 레코드 확인
                check_sql = f"SELECT id FROM {table_name} WHERE {id_field} = %s"
                cursor.execute(check_sql, (primary_identifier,))
                existing = cursor.fetchone()
                
                # 필드와 값 수집
                fields = []
                values = []
                placeholders = []
                update_parts = []
                
                # API에 따라 다른 필드 매핑 사용
                if api_key in field_mappings:
                    for db_field, api_fields in field_mappings[api_key].items():
                        value = get_field_value(drug_data, db_field, api_key)
                        if value is not None:
                            fields.append(db_field)
                            values.append(value)
                            placeholders.append('%s')
                            update_parts.append(f"{db_field} = %s")
                
                if not fields:
                    logger.warning(f"API {api_key}: 유효한 필드 없음 - 건너뜀")
                    return False
                
                if existing:
                    # 업데이트
                    id_val = existing['id']
                    if update_parts:
                        update_sql = f"UPDATE {table_name} SET {', '.join(update_parts)}, updated_at = CURRENT_TIMESTAMP WHERE id = %s"
                        cursor.execute(update_sql, values + [id_val])
                        logger.debug(f"레코드 업데이트: {table_name} id={id_val}")
                else:
                    # 삽입
                    insert_sql = f"INSERT INTO {table_name} ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
                    cursor.execute(insert_sql, values)
                    logger.debug(f"새 레코드 삽입: {table_name}")
                    
                    # 성공적으로 삽입한 경우 drug_relation 테이블에도 추가
                    if cursor.lastrowid:
                        # 관계 테이블에 연결 정보 저장 (해당하는 경우)
                        if api_key == '의약품 낱알식별 정보':
                            relation_sql = "INSERT INTO drug_relation (item_seq) VALUES (%s) ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP"
                            cursor.execute(relation_sql, (primary_identifier,))
                        elif api_key == '의약품성분약효정보':
                            relation_sql = "INSERT INTO drug_relation (gnl_nm_cd) VALUES (%s) ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP"
                            cursor.execute(relation_sql, (primary_identifier,))
                        elif api_key == '성분별 1일 최대투여량 정보':
                            relation_sql = "INSERT INTO drug_relation (cpnt_cd) VALUES (%s) ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP"
                            cursor.execute(relation_sql, (primary_identifier,))
                
                conn.commit()
                return True
        except Exception as e:
            conn.rollback()
            logger.error(f"데이터 삽입 오류 (시도 {attempt+1}/{max_retries}): {e}")
            
            if attempt < max_retries - 1:
                logger.info(f"{retry_delay}초 후 재시도...")
                time.sleep(retry_delay)
            else:
                logger.error(f"데이터 삽입 최대 재시도 초과: {primary_identifier}")
                return False
        finally:
            conn.close()
    
    return False

def process_all_api_data():
    """모든 API 데이터 처리"""
    # 체크포인트 로드
    checkpoint = load_checkpoint()
    
    # 처리할 API 목록 - 새로운 테이블 구조에 맞는 API만 처리
    api_keys = list(API_TABLE_MAPPING.keys())
    
    # 체크포인트에서 시작점 결정
    start_api_idx = 0
    start_page = 1
    processed_count = 0
    
    if checkpoint:
        # 이전에 처리 중이던 API 찾기
        if checkpoint['api_key'] in api_keys:
            start_api_idx = api_keys.index(checkpoint['api_key'])
            start_page = checkpoint['page_no']
            processed_count = checkpoint['processed_count']
            logger.info(f"체크포인트에서 다시 시작: API={checkpoint['api_key']}, 페이지={start_page}, 처리항목={processed_count}")
    
    total_processed = processed_count
    success_count = 0
    
    # API 순회
    for api_idx in range(start_api_idx, len(api_keys)):
        current_api = api_keys[api_idx]
        logger.info(f"API {current_api} 처리 시작")
        
        # 첫 페이지 가져오기
        current_page = start_page if api_idx == start_api_idx else 1
        
        # 첫 페이지 로드
        first_page_data = fetch_drug_data(current_api, page_no=current_page, num_of_rows=100)
        if not first_page_data:
            logger.error(f"API {current_api}에서 첫 페이지 로드 실패, 다음 API로 이동")
            continue
        
        total_count = first_page_data['total_count']
        total_pages = (total_count + 99) // 100  # 올림 나눗셈
        
        logger.info(f"API {current_api}: 총 {total_count}개 항목, {total_pages}개 페이지")
        
        # 첫 페이지 처리
        api_success_count = 0
        
        # 첫 페이지부터 처리
        logger.info(f"API {current_api}: 페이지 {current_page}/{total_pages} 처리 중...")

        page_data = first_page_data
        
        for i, item in enumerate(page_data['items']):
            item_name = item.get('itemName', '') or item.get('ITEM_NAME', '') or item.get('gnlNm', '') or item.get('DRUG_CPNT_KOR_NM', '') or f"항목 {i+1}"
            
            # 기존 로그 출력 유지
            logger.info(f"항목 {i+1}/{len(page_data['items'])} 처리 중: {item_name}")
            
            # 새로운 컬러 로그 추가
            colored_log = format_api_log(
                current_api, 
                current_page, 
                total_pages, 
                i+1, 
                len(page_data['items']), 
                item_name
            )
            logger.info(colored_log)
            
            # 필드 확인 로깅 추가
            if i == 0:  # 각 페이지의 첫 항목에 대해서만
                logger.info(f"API {current_api}: 응답 필드: {list(item.keys())}")
            
            if insert_drug_data(item, current_api):
                api_success_count += 1
                success_count += 1
            
            total_processed += 1
            
            # 주기적으로 체크포인트 저장
            if total_processed % 10 == 0:
                save_checkpoint(current_api, current_page, total_processed)
        
        logger.info(f"API {current_api}: 페이지 {current_page} - {api_success_count}/{len(first_page_data['items'])} 항목 저장 완료")
        
        # 나머지 페이지 처리
        for page_no in range(current_page + 1, total_pages + 1):
            logger.info(f"API {current_api}: 페이지 {page_no}/{total_pages} 처리 중...")
            
            # 페이지 데이터 가져오기
            page_data = fetch_drug_data(current_api, page_no=page_no, num_of_rows=100)
            if not page_data:
                logger.error(f"API {current_api}: 페이지 {page_no} 데이터 가져오기 실패, 다음 페이지로 이동")
                # 체크포인트 업데이트
                save_checkpoint(current_api, page_no, total_processed)
                continue
            
            # 페이지 항목 처리
            page_success = 0
            for i, item in enumerate(page_data['items']):
                item_name = item.get('itemName', '') or item.get('ITEM_NAME', '') or item.get('gnlNm', '') or item.get('DRUG_CPNT_KOR_NM', '') or f"항목 {i+1}"
                logger.info(f"항목 {i+1}/{len(page_data['items'])} 처리 중: {item_name}")
                
                # 컬러 로그 추가
                colored_log = format_api_log(
                    current_api, 
                    page_no, 
                    total_pages, 
                    i+1, 
                    len(page_data['items']), 
                    item_name
                )
                logger.info(colored_log)
                
                if insert_drug_data(item, current_api):
                    page_success += 1
                    api_success_count += 1
                    success_count += 1
                
                total_processed += 1
                
                # 주기적으로 체크포인트 저장
                if total_processed % 10 == 0:
                    save_checkpoint(current_api, page_no, total_processed)
            
            logger.info(f"API {current_api}: 페이지 {page_no} - {page_success}/{len(page_data['items'])} 항목 저장 완료")
            
            # 페이지 완료 후 체크포인트 업데이트
            save_checkpoint(current_api, page_no + 1, total_processed)
            
            # API 요청 간 짧은 지연
            time.sleep(0.5)
        
        # API 완료 후 로깅
        logger.info(f"API {current_api} 처리 완료: 총 {api_success_count}/{total_count} 항목 저장")
        
        # 다음 API로 이동할 때 체크포인트 업데이트
        if api_idx < len(api_keys) - 1:
            save_checkpoint(api_keys[api_idx + 1], 1, total_processed)
        
        # API 간 지연
        time.sleep(1)
    
    # 모든 처리 완료 후 체크포인트 파일 제거
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
    
    logger.info(f"모든 API 처리 완료: 총 {success_count}/{total_processed} 항목 저장 성공")

def main():
    """메인 함수"""
    logger.info("데이터 로드 시작")
    
    # 데이터베이스 테이블 확인/생성
    ensure_tables_exist()
    
    # 모든 API 데이터 처리
    process_all_api_data()
    
    logger.info("데이터 로드 완료")

if __name__ == "__main__":
    print("프로그램 시작")
    try:
        main()
        print("프로그램 종료")
    except Exception as e:
        print(f"오류 발생: {e}")
        logger.error(f"오류 발생: {e}", exc_info=True)