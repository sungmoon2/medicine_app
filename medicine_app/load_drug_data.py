# medicine_app/load_drug_data.py
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
    filename='data_load.log'
)
logger = logging.getLogger('data_load')

# API 키 설정
API_KEY = os.getenv('OPEN_API_KEY')

# 데이터베이스 연결 설정
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', '1234'),
    'db': os.getenv('DB_NAME', 'medicine_db'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# API URL - 작동이 확인된 URL 사용
API_URL = { 
    'http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList',
    'http://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService01/getMdcinGrnIdntfcInfoList01',
    'http://apis.data.go.kr/B551182/msupCmpnMeftInfoService/getMajorCmpnNmCdList',
    'http://apis.data.go.kr/1471000/DayMaxDosgQyByIngdService/getDayMaxDosgQyByIngdInq'

}
def db_connection():
    """데이터베이스 연결"""
    try:
        connection = pymysql.connect(**DB_CONFIG)
        return connection
    except Exception as e:
        logger.error(f"데이터베이스 연결 오류: {e}")
        return None

def fetch_drug_data(page_no=1, num_of_rows=100):
    """의약품 정보 가져오기"""
    params = {
        'serviceKey': API_KEY,
        'pageNo': page_no,
        'numOfRows': num_of_rows,
        'type': 'xml'
    }
    
    try:
        response = requests.get(API_URL, params=params)
        
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            
            # 결과 코드 확인
            result_code = root.find('.//resultCode')
            if result_code is not None and result_code.text != '00':
                result_msg = root.find('.//resultMsg')
                logger.error(f"API 오류: {result_code.text} - {result_msg.text if result_msg is not None else 'Unknown error'}")
                return None
            
            # 항목 추출
            items = []
            for item in root.findall('.//item'):
                drug_data = {}
                for child in item:
                    drug_data[child.tag] = child.text
                items.append(drug_data)
            
            # 전체 결과 수
            total_count = root.find('.//totalCount')
            count = int(total_count.text) if total_count is not None else 0
            
            return {
                'items': items,
                'total_count': count
            }
        else:
            logger.error(f"API 요청 실패: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"API 요청 예외: {e}")
        return None

def insert_drug_data(drug_data):
    """의약품 데이터 삽입"""
    conn = db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cursor:
            # 1. medicines 테이블에 데이터 삽입
            check_sql = "SELECT id FROM medicines WHERE item_seq = %s"
            cursor.execute(check_sql, (drug_data.get('itemSeq', '')))
            existing = cursor.fetchone()
            
            medicine_id = None
            
            if existing:
                # 이미 존재하면 ID 가져오기
                medicine_id = existing['id']
            else:
                # 새로 삽입
                insert_sql = """
                INSERT INTO medicines (
                    item_seq, item_name, entp_name, chart, class_name, etc_otc_name
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_sql, (
                    drug_data.get('itemSeq', ''),
                    drug_data.get('itemName', ''),
                    drug_data.get('entpName', ''),
                    drug_data.get('chart', ''),
                    drug_data.get('classname', ''),  # API 응답 필드명 확인 필요
                    '일반의약품'  # 이 API는 일반의약품 정보
                ))
                
                medicine_id = cursor.lastrowid
            
            # 2. medicine_usage 테이블에 데이터 삽입
            if medicine_id:
                check_sql = "SELECT id FROM medicine_usage WHERE medicine_id = %s"
                cursor.execute(check_sql, (medicine_id))
                existing = cursor.fetchone()
                
                if existing:
                    # 업데이트
                    update_sql = """
                    UPDATE medicine_usage SET
                        efcy_qesitm = %s,
                        use_method_qesitm = %s
                    WHERE id = %s
                    """
                    cursor.execute(update_sql, (
                        drug_data.get('efcyQesitm', ''),
                        drug_data.get('useMethodQesitm', ''),
                        existing['id']
                    ))
                else:
                    # 삽입
                    insert_sql = """
                    INSERT INTO medicine_usage (
                        medicine_id, efcy_qesitm, use_method_qesitm
                    ) VALUES (%s, %s, %s)
                    """
                    cursor.execute(insert_sql, (
                        medicine_id,
                        drug_data.get('efcyQesitm', ''),
                        drug_data.get('useMethodQesitm', '')
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
    logger.info("데이터 로드 시작")
    
    # 첫 페이지 데이터 가져오기
    first_page = fetch_drug_data(page_no=1, num_of_rows=100)
    if not first_page:
        logger.error("데이터 가져오기 실패")
        return
    
    total_count = first_page['total_count']
    logger.info(f"API에서 제공하는 총 의약품 수: {total_count}개")
    
    # 전체 페이지 수 계산 (한 페이지당 100개 항목)
    total_pages = (total_count + 99) // 100  # 올림 나눗셈
    logger.info(f"총 {total_pages}개 페이지를 처리합니다.")
    
    # 첫 페이지 항목 처리
    success_count = 0
    
    # 첫 페이지 처리
    logger.info(f"페이지 1/{total_pages} 처리 중...")
    for i, item in enumerate(first_page['items']):
        logger.info(f"항목 {i+1}/{len(first_page['items'])} 처리 중: {item.get('itemName', 'N/A')}")
        
        if insert_drug_data(item):
            success_count += 1
    
    logger.info(f"페이지 1: {success_count}/{len(first_page['items'])} 항목 저장 완료")
    
    # 나머지 페이지 처리
    for page_no in range(2, total_pages + 1):
        logger.info(f"페이지 {page_no}/{total_pages} 데이터 가져오기 중...")
        
        # 페이지 데이터 가져오기
        page_data = fetch_drug_data(page_no=page_no, num_of_rows=100)
        if not page_data:
            logger.error(f"페이지 {page_no} 데이터 가져오기 실패")
            continue
        
        # 페이지 항목 처리
        page_success = 0
        for i, item in enumerate(page_data['items']):
            logger.info(f"페이지 {page_no}, 항목 {i+1}/{len(page_data['items'])} 처리 중: {item.get('itemName', 'N/A')}")
            
            if insert_drug_data(item):
                page_success += 1
                success_count += 1
            
            time.sleep(0.1)  # API 호출 간 지연 (부하 줄이기 위해)
        
        logger.info(f"페이지 {page_no}: {page_success}/{len(page_data['items'])} 항목 저장 완료")
        time.sleep(0.5)  # 페이지 간 지연 (부하 줄이기 위해)
    
    logger.info(f"데이터 로드 완료: 총 {success_count}/{total_count}개 항목 저장 성공")

if __name__ == "__main__":
    main()