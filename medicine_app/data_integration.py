# medicine_app/data_integration.py
import requests
import xml.etree.ElementTree as ET
import pymysql
import time
import logging
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='data_integration.log'
)
logger = logging.getLogger('data_integration')

# API 키 설정
API_KEY = os.getenv('OPEN_API_KEY')
ENCODED_API_KEY = requests.utils.quote(API_KEY) if API_KEY else ''

# 데이터베이스 연결 설정
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'db': os.getenv('DB_NAME', 'medicine_db'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# API 기본 URL
API_BASE_URL = 'http://apis.data.go.kr/1471000/MdcinGrnIdntfcAPIService/getMdcinGrnIdntfcList'

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

def collect_pill_data(page_no=1, num_of_rows=100):
    """의약품 낱알 정보 수집"""
    params = {
        'serviceKey': ENCODED_API_KEY,
        'pageNo': page_no,
        'numOfRows': num_of_rows,
        'type': 'xml'
    }
    
    xml_data = fetch_api_data(API_BASE_URL, params)
    if not xml_data:
        return None
    
    root = parse_xml_response(xml_data)
    if root is None:
        return None
    
    items = []
    for item in root.findall('.//item'):
        pill_data = {}
        for child in item:
            pill_data[child.tag] = child.text
        items.append(pill_data)
    
    total_count = int(root.find('.//totalCount').text) if root.find('.//totalCount') is not None else 0
    
    return {
        'items': items,
        'total_count': total_count
    }

def db_connection():
    """데이터베이스 연결"""
    try:
        connection = pymysql.connect(**DB_CONFIG)
        return connection
    except Exception as e:
        logger.error(f"데이터베이스 연결 오류: {e}")
        return None

def initialize_database():
    """데이터베이스 테이블 초기화"""
    conn = db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cursor:
            # medicines 테이블 생성
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS medicines (
                id INT AUTO_INCREMENT PRIMARY KEY,
                item_seq VARCHAR(20) NOT NULL UNIQUE COMMENT '품목일련번호',
                item_name VARCHAR(500) NOT NULL COMMENT '품목명',
                item_eng_name VARCHAR(500) COMMENT '제품영문명',
                entp_seq VARCHAR(20) COMMENT '업체일련번호',
                entp_name VARCHAR(200) COMMENT '업체명',
                chart VARCHAR(1000) COMMENT '성상',
                class_no VARCHAR(50) COMMENT '분류번호',
                class_name VARCHAR(200) COMMENT '분류명',
                etc_otc_name VARCHAR(100) COMMENT '전문/일반',
                item_permit_date VARCHAR(20) COMMENT '품목허가일자',
                form_code_name VARCHAR(100) COMMENT '제형코드이름',
                edi_code VARCHAR(20) COMMENT '보험코드',
                change_date VARCHAR(20) COMMENT '변경일자',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_item_name (item_name),
                INDEX idx_entp_name (entp_name)
            )
            """)
            
            # medicine_shapes 테이블 생성
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS medicine_shapes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                medicine_id INT NOT NULL,
                drug_shape VARCHAR(100) COMMENT '의약품모양',
                color_class1 VARCHAR(100) COMMENT '색깔(앞)',
                color_class2 VARCHAR(100) COMMENT '색깔(뒤)',
                line_front VARCHAR(100) COMMENT '분할선(앞)',
                line_back VARCHAR(100) COMMENT '분할선(뒤)',
                print_front VARCHAR(100) COMMENT '표시(앞)',
                print_back VARCHAR(100) COMMENT '표시(뒤)',
                leng_long DECIMAL(6,2) COMMENT '크기(장축)',
                leng_short DECIMAL(6,2) COMMENT '크기(단축)',
                thick DECIMAL(6,2) COMMENT '크기(두께)',
                mark_code_front VARCHAR(200) COMMENT '마크코드(앞)',
                mark_code_back VARCHAR(200) COMMENT '마크코드(뒤)',
                mark_code_front_anal VARCHAR(500) COMMENT '마크내용(앞)',
                mark_code_back_anal VARCHAR(500) COMMENT '마크내용(뒤)',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
            )
            """)
            
            # medicine_images 테이블 생성
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS medicine_images (
                id INT AUTO_INCREMENT PRIMARY KEY,
                medicine_id INT NOT NULL,
                item_image VARCHAR(500) COMMENT '제품이미지',
                mark_code_front_img VARCHAR(500) COMMENT '마크이미지(앞)',
                mark_code_back_img VARCHAR(500) COMMENT '마크이미지(뒤)',
                img_regist_ts VARCHAR(20) COMMENT '이미지 생성일',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
            )
            """)
            
            # medicine_usage 테이블 생성
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS medicine_usage (
                id INT AUTO_INCREMENT PRIMARY KEY,
                medicine_id INT NOT NULL,
                efcy_qesitm MEDIUMTEXT COMMENT '효능',
                use_method_qesitm MEDIUMTEXT COMMENT '사용법',
                atpn_warn_qesitm MEDIUMTEXT COMMENT '주의사항경고',
                atpn_qesitm MEDIUMTEXT COMMENT '주의사항',
                intrc_qesitm MEDIUMTEXT COMMENT '상호작용',
                se_qesitm MEDIUMTEXT COMMENT '부작용',
                deposit_method_qesitm MEDIUMTEXT COMMENT '보관법',
                open_de VARCHAR(10) COMMENT '공개일자',
                update_de VARCHAR(10) COMMENT '수정일자',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
            )
            """)
            
            # medicine_dur_usjnt 테이블 생성
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS medicine_dur_usjnt (
                id INT AUTO_INCREMENT PRIMARY KEY,
                medicine_id INT NOT NULL,
                mixture_item_seq VARCHAR(20) COMMENT '병용금기 품목일련번호',
                mixture_item_name VARCHAR(500) COMMENT '병용금기 품목명',
                mixture_entp_name VARCHAR(200) COMMENT '병용금기 업체명',
                contraindiction_level VARCHAR(50) COMMENT '금기등급',
                contraindiction_content MEDIUMTEXT COMMENT '금기내용',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
            )
            """)
            
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"데이터베이스 초기화 오류: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def insert_medicine_data(pill_data):
    """의약품 데이터 삽입"""
    conn = db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cursor:
            # 1. medicines 테이블에 데이터 삽입
            check_sql = "SELECT id FROM medicines WHERE item_seq = %s"
            cursor.execute(check_sql, (pill_data.get('ITEM_SEQ', '')))
            existing = cursor.fetchone()
            
            medicine_id = None
            
            if existing:
                # 이미 존재하면 ID 가져오기
                medicine_id = existing['id']
            else:
                # 새로 삽입
                insert_sql = """
                INSERT INTO medicines (
                    item_seq, item_name, item_eng_name, entp_name, chart, 
                    class_no, class_name, etc_otc_name, item_permit_date, 
                    form_code_name, edi_code
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_sql, (
                    pill_data.get('ITEM_SEQ', ''),
                    pill_data.get('ITEM_NAME', ''),
                    pill_data.get('ITEM_ENG_NAME', ''),
                    pill_data.get('ENTP_NAME', ''),
                    pill_data.get('CHART', ''),
                    pill_data.get('CLASS_NO', ''),
                    pill_data.get('CLASS_NAME', ''),
                    pill_data.get('ETC_OTC_NAME', ''),
                    pill_data.get('ITEM_PERMIT_DATE', ''),
                    pill_data.get('FORM_CODE_NAME', ''),
                    pill_data.get('EDI_CODE', '')
                ))
                
                medicine_id = cursor.lastrowid
            
            if medicine_id:
                # 2. medicine_shapes 테이블에 데이터 삽입
                check_sql = "SELECT id FROM medicine_shapes WHERE medicine_id = %s"
                cursor.execute(check_sql, (medicine_id))
                existing = cursor.fetchone()
                
                if existing:
                    # 업데이트
                    update_sql = """
                    UPDATE medicine_shapes SET
                        drug_shape = %s,
                        color_class1 = %s,
                        color_class2 = %s,
                        line_front = %s,
                        line_back = %s,
                        print_front = %s,
                        print_back = %s,
                        leng_long = %s,
                        leng_short = %s,
                        thick = %s,
                        mark_code_front = %s,
                        mark_code_back = %s,
                        mark_code_front_anal = %s,
                        mark_code_back_anal = %s
                    WHERE id = %s
                    """
                    cursor.execute(update_sql, (
                        pill_data.get('DRUG_SHAPE', ''),
                        pill_data.get('COLOR_CLASS1', ''),
                        pill_data.get('COLOR_CLASS2', ''),
                        pill_data.get('LINE_FRONT', ''),
                        pill_data.get('LINE_BACK', ''),
                        pill_data.get('PRINT_FRONT', ''),
                        pill_data.get('PRINT_BACK', ''),
                        pill_data.get('LENG_LONG', None),
                        pill_data.get('LENG_SHORT', None),
                        pill_data.get('THICK', None),
                        pill_data.get('MARK_CODE_FRONT', ''),
                        pill_data.get('MARK_CODE_BACK', ''),
                        pill_data.get('MARK_CODE_FRONT_ANAL', ''),
                        pill_data.get('MARK_CODE_BACK_ANAL', ''),
                        existing['id']
                    ))
                else:
                    # 삽입
                    insert_sql = """
                    INSERT INTO medicine_shapes (
                        medicine_id, drug_shape, color_class1, color_class2, 
                        line_front, line_back, print_front, print_back, 
                        leng_long, leng_short, thick, mark_code_front, mark_code_back,
                        mark_code_front_anal, mark_code_back_anal
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_sql, (
                        medicine_id,
                        pill_data.get('DRUG_SHAPE', ''),
                        pill_data.get('COLOR_CLASS1', ''),
                        pill_data.get('COLOR_CLASS2', ''),
                        pill_data.get('LINE_FRONT', ''),
                        pill_data.get('LINE_BACK', ''),
                        pill_data.get('PRINT_FRONT', ''),
                        pill_data.get('PRINT_BACK', ''),
                        pill_data.get('LENG_LONG', None),
                        pill_data.get('LENG_SHORT', None),
                        pill_data.get('THICK', None),
                        pill_data.get('MARK_CODE_FRONT', ''),
                        pill_data.get('MARK_CODE_BACK', ''),
                        pill_data.get('MARK_CODE_FRONT_ANAL', ''),
                        pill_data.get('MARK_CODE_BACK_ANAL', '')
                    ))
                
                # 3. medicine_images 테이블에 데이터 삽입
                check_sql = "SELECT id FROM medicine_images WHERE medicine_id = %s"
                cursor.execute(check_sql, (medicine_id))
                existing = cursor.fetchone()
                
                if existing:
                    # 업데이트
                    update_sql = """
                    UPDATE medicine_images SET
                        item_image = %s,
                        mark_code_front_img = %s,
                        mark_code_back_img = %s,
                        img_regist_ts = %s
                    WHERE id = %s
                    """
                    cursor.execute(update_sql, (
                        pill_data.get('ITEM_IMAGE', ''),
                        pill_data.get('MARK_CODE_FRONT_IMG', ''),
                        pill_data.get('MARK_CODE_BACK_IMG', ''),
                        pill_data.get('IMG_REGIST_TS', ''),
                        existing['id']
                    ))
                else:
                    # 삽입
                    insert_sql = """
                    INSERT INTO medicine_images (
                        medicine_id, item_image, mark_code_front_img, 
                        mark_code_back_img, img_regist_ts
                    ) VALUES (%s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_sql, (
                        medicine_id,
                        pill_data.get('ITEM_IMAGE', ''),
                        pill_data.get('MARK_CODE_FRONT_IMG', ''),
                        pill_data.get('MARK_CODE_BACK_IMG', ''),
                        pill_data.get('IMG_REGIST_TS', '')
                    ))
            
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"의약품 데이터 삽입 오류: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    """메인 함수"""
    logger.info("데이터 통합 프로세스 시작")
    
    # 데이터베이스 초기화
    if not initialize_database():
        logger.error("데이터베이스 초기화 실패")
        return
    
    # 샘플 데이터 페이지 1-5까지 조회 (각 페이지당 100개)
    for page in range(1, 6):
        logger.info(f"페이지 {page} 데이터 수집 중...")
        
        data = collect_pill_data(page_no=page, num_of_rows=100)
        if not data:
            logger.error(f"페이지 {page} 데이터 수집 실패")
            continue
        
        items = data['items']
        logger.info(f"페이지 {page}에서 {len(items)}개 항목 수집됨")
        
        # 데이터 저장
        success_count = 0
        for item in items:
            if insert_medicine_data(item):
                success_count += 1
            
            # API 호출 간 짧은 지연
            time.sleep(0.1)
        
        logger.info(f"페이지 {page}에서 {success_count}/{len(items)}개 항목 저장 성공")
        
        # 페이지 간 지연
        time.sleep(1)
    
    logger.info("데이터 통합 프로세스 완료")

if __name__ == "__main__":
    main()