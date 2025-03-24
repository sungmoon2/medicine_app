# medicine_app/load_drug_data.py
import requests
import xml.etree.ElementTree as ET
import pymysql
import time
import logging
import os
import sys
from dotenv import load_dotenv

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
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

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
    '의약품성분약효정보': 'http://apis.data.go.kr/B551182/msupCmpnMeftInfoService/getMajorCmpnNmCdList',
    '성분별 1일 최대투여량 정보': 'http://apis.data.go.kr/1471000/DayMaxDosgQyByIngdService/getDayMaxDosgQyByIngdInq'
}

# 체크포인트 파일 경로
CHECKPOINT_FILE = "data_load_checkpoint.json"
import json

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
    """데이터베이스 테이블 존재 확인 및 생성"""
    conn = db_connection()
    
    try:
        with conn.cursor() as cursor:
            # medicines 테이블 확인/생성
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS medicines (
                id INT AUTO_INCREMENT PRIMARY KEY,
                item_seq VARCHAR(20) UNIQUE,
                item_name VARCHAR(500) NOT NULL,
                entp_name VARCHAR(200),
                chart TEXT,
                class_name VARCHAR(200),
                etc_otc_name VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            # medicine_usage 테이블 확인/생성
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS medicine_usage (
                id INT AUTO_INCREMENT PRIMARY KEY,
                medicine_id INT NOT NULL,
                efcy_qesitm TEXT,
                use_method_qesitm TEXT,
                atpn_warn_qesitm TEXT,
                atpn_qesitm TEXT,
                intrc_qesitm TEXT,
                se_qesitm TEXT,
                deposit_method_qesitm TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
            
            conn.commit()
            logger.info("데이터베이스 테이블 확인/생성 완료")
    except Exception as e:
        logger.error(f"테이블 생성 오류: {e}")
        conn.rollback()
    finally:
        conn.close()

def insert_drug_data(drug_data, api_key=None):
    """의약품 데이터 삽입 - API별 응답 필드명 처리"""
    
    # 각 API별로 가능한 식별자 필드명
    possible_id_fields = {
        'drug_easy': ['itemSeq'],  # e약은요 API
        'mdcin_grn': ['ITEM_SEQ', 'item_seq'],  # 낱알식별 API
        'major_cmpn': ['gnlNmCd', 'CPNT_CD'],  # 성분약효/1일최대투여량 API
        'day_max_dosg': ['CPNT_CD']  # 1일최대투여량 API
    }
    
    # 모든 가능한 필드명 목록 생성
    all_possible_fields = ['itemSeq', 'ITEM_SEQ', 'item_seq', 'gnlNmCd', 'CPNT_CD']
    
    item_seq = None
    used_field = None
    
    # API별 적합한 필드명 먼저 시도
    if api_key in possible_id_fields:
        for field in possible_id_fields[api_key]:
            if field in drug_data and drug_data[field]:
                item_seq = drug_data[field]
                used_field = field
                logger.info(f"API {api_key}: 식별자 필드 '{field}' 사용")
                break
    
    # 여전히 식별자를 찾지 못했다면 모든 가능한 필드 시도
    if not item_seq:
        for field in all_possible_fields:
            if field in drug_data and drug_data[field]:
                item_seq = drug_data[field]
                used_field = field
                logger.info(f"API {api_key}: 대체 식별자 필드 '{field}' 사용")
                break
    
    # 여전히 식별자가 없다면 로그에 가용 필드 출력
    if not item_seq:
        logger.warning(f"API {api_key}: 식별자 없음. 가용 필드: {list(drug_data.keys())}")
        return False
    
    # 필드명 매핑 추가 (API별 응답 필드를 데이터베이스 필드명으로 변환)
    field_mappings = {
        'drug_easy': {  # e약은요 API
            'name': 'itemName',
            'company': 'entpName',
            'effect': 'efcyQesitm',
            'usage': 'useMethodQesitm'
        },
        'mdcin_grn': {  # 낱알식별 API
            'name': 'ITEM_NAME',
            'company': 'ENTP_NAME',
            'chart': 'CHART',
            'class_name': 'CLASS_NAME'
        },
        'major_cmpn': {  # 성분약효 API
            'name': 'gnlNm',
            'company': 'gnlNmCd'
        }
        # 다른 API들의 매핑도 추가
    }
    
    # 필드 매핑 적용 함수
    def get_field_value(data, field_key, api_key):
        """API별 필드 매핑에 따라 값 가져오기"""
        if api_key in field_mappings and field_key in field_mappings[api_key]:
            mapped_field = field_mappings[api_key][field_key]
            return data.get(mapped_field, '')
        return ''
    
    # DB 삽입 로직은 그대로 두고, 매핑된 값 사용
    for attempt in range(max_retries):
        conn = db_connection()
        try:
            with conn.cursor() as cursor:
                # 1. medicines 테이블에 데이터 삽입
                item_seq = drug_data.get('itemSeq', '')
                if not item_seq:
                    logger.warning("품목일련번호(itemSeq)가 없는 항목 - 건너뜀")
                    return False
                
                check_sql = "SELECT id FROM medicines WHERE item_seq = %s"
                cursor.execute(check_sql, (item_seq,))
                existing = cursor.fetchone()
                
                medicine_id = None
                
                if existing:
                    # 이미 존재하면 ID 가져오기
                    medicine_id = existing['id']
                    logger.debug(f"기존 의약품 발견: ID={medicine_id}, 품목일련번호={item_seq}")
                else:
                    # 새로 삽입
                    insert_sql = """
                    INSERT INTO medicines (
                        item_seq, item_name, entp_name, chart, class_name, etc_otc_name
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_sql, (
                        item_seq,
                        get_field_value(drug_data, 'name', api_key),  # 필드 매핑을 통해 이름을 가져옴
                        get_field_value(drug_data, 'company', api_key),  # 필드 매핑을 통해 업체명을 가져옴
                        get_field_value(drug_data, 'chart', api_key),  # 필드 매핑을 통해 차트를 가져옴
                        get_field_value(drug_data, 'class_name', api_key),  # 필드 매핑을 통해 분류명을 가져옴
                        drug_data.get('etcOtcName', '일반의약품')  # 기본값 설정
                    ))
                    
                    medicine_id = cursor.lastrowid
                    logger.debug(f"새 의약품 추가: ID={medicine_id}, 품목일련번호={item_seq}")
                
                # 2. medicine_usage 테이블에 데이터 삽입
                if medicine_id:
                    check_sql = "SELECT id FROM medicine_usage WHERE medicine_id = %s"
                    cursor.execute(check_sql, (medicine_id,))
                    existing = cursor.fetchone()
                    
                    if existing:
                        # 업데이트
                        update_sql = """
                        UPDATE medicine_usage SET
                            efcy_qesitm = %s,
                            use_method_qesitm = %s,
                            atpn_warn_qesitm = %s,
                            atpn_qesitm = %s,
                            intrc_qesitm = %s,
                            se_qesitm = %s,
                            deposit_method_qesitm = %s
                        WHERE id = %s
                        """
                        cursor.execute(update_sql, (
                            get_field_value(drug_data, 'effect', api_key),  # 필드 매핑을 통해 효과 정보를 가져옴
                            get_field_value(drug_data, 'usage', api_key),  # 필드 매핑을 통해 사용 방법을 가져옴
                            drug_data.get('atpnWarnQesitm', ''),
                            drug_data.get('atpnQesitm', ''),
                            drug_data.get('intrcQesitm', ''),
                            drug_data.get('seQesitm', ''),
                            drug_data.get('depositMethodQesitm', ''),
                            existing['id']
                        ))
                    else:
                        # 삽입
                        insert_sql = """
                        INSERT INTO medicine_usage (
                            medicine_id, efcy_qesitm, use_method_qesitm, 
                            atpn_warn_qesitm, atpn_qesitm, intrc_qesitm,
                            se_qesitm, deposit_method_qesitm
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(insert_sql, (
                            medicine_id,
                            get_field_value(drug_data, 'effect', api_key),  # 필드 매핑을 통해 효과 정보를 가져옴
                            get_field_value(drug_data, 'usage', api_key),  # 필드 매핑을 통해 사용 방법을 가져옴
                            drug_data.get('atpnWarnQesitm', ''),
                            drug_data.get('atpnQesitm', ''),
                            drug_data.get('intrcQesitm', ''),
                            drug_data.get('seQesitm', ''),
                            drug_data.get('depositMethodQesitm', '')
                        ))
                
                conn.commit()
                return True
                
        except Exception as e:
            conn.rollback()
            logger.error(f"의약품 데이터 삽입 오류 (시도 {attempt+1}/{max_retries}): {e}")
            logger.debug(f"문제가 발생한 데이터: {drug_data.get('itemName', '알 수 없음')}")
            
            if attempt < max_retries - 1:
                logger.info(f"{retry_delay}초 후 재시도...")
                time.sleep(retry_delay)
            else:
                logger.error(f"데이터 삽입 최대 재시도 초과: {drug_data.get('itemName', '알 수 없음')}")
                return False
        finally:
            conn.close()
    
    return False


def process_all_api_data():
    """모든 API 데이터 처리"""
    # 체크포인트 로드
    checkpoint = load_checkpoint()
    
    # 처리할 API 목록
    api_keys = list(API_URLS.keys())
    
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
            item_name = item.get('itemName', f"항목 {i+1}")
            logger.info(f"API {current_api}: 항목 {i+1}/{len(page_data['items'])} 처리 중: {item_name}")
            
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
                item_name = item.get('itemName', f"항목 {i+1}")
                logger.info(f"항목 {i+1}/{len(page_data['items'])} 처리 중: {item_name}")
                
                if insert_drug_data(item):
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
    main()