import pymysql
import logging
import os
import sys
from dotenv import load_dotenv
import time

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='unified_migration.log',
    encoding='utf-8'
)
logger = logging.getLogger('unified_migration')

# 콘솔 출력을 위한 핸들러 추가
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(console_handler)

# 데이터베이스 연결 설정
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', '1234'),
    'db': os.getenv('DB_NAME', 'medicine_db'),
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

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

def create_unified_table():
    """통합 의약품 테이블 생성"""
    conn = db_connection()
    logger.info("통합 의약품 테이블 생성 시작...")
    
    try:
        with conn.cursor() as cursor:
            # 통합 테이블 생성 SQL
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS unified_medicines (
                id INT AUTO_INCREMENT PRIMARY KEY,
                
                -- 이미지 1의 테이블에서 온 필드들
                item_seq VARCHAR(100) COMMENT '품목일련번호',
                item_name VARCHAR(500) COMMENT '품목명',
                item_eng_name VARCHAR(500) COMMENT '영문 품목명',
                entp_seq VARCHAR(100) COMMENT '업체일련번호',
                entp_name VARCHAR(300) COMMENT '업체명',
                chart TEXT COMMENT '성상',
                class_no VARCHAR(100) COMMENT '분류번호',
                class_name VARCHAR(300) COMMENT '분류명',
                etc_otc_name VARCHAR(100) COMMENT '전문/일반',
                item_permit_date VARCHAR(100) COMMENT '품목허가일자',
                form_code_name VARCHAR(200) COMMENT '제형코드이름',
                edi_code VARCHAR(100) COMMENT '보험코드',
                change_date VARCHAR(100) COMMENT '변경일자',
                
                -- 이미지 2의 테이블에서 온 필드들
                medicine_id INT COMMENT '기존 medicine_id',
                efcy_qesitm TEXT COMMENT '효능효과',
                use_method_qesitm TEXT COMMENT '용법용량',
                atpn_warn_qesitm TEXT COMMENT '주의사항경고',
                atpn_qesitm TEXT COMMENT '주의사항',
                intrc_qesitm TEXT COMMENT '상호작용',
                se_qesitm TEXT COMMENT '부작용',
                deposit_method_qesitm TEXT COMMENT '보관법',
                opendate VARCHAR(100) COMMENT '개봉일자',
                updatedate VARCHAR(100) COMMENT '업데이트일자',
                
                -- 메타 정보
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '데이터 생성일',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '데이터 수정일',
                
                -- 인덱스 추가
                INDEX idx_item_seq (item_seq),
                INDEX idx_item_name (item_name(255)),
                INDEX idx_medicine_id (medicine_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='통합 의약품 정보'
            """)
            
            conn.commit()
            logger.info("통합 의약품 테이블 생성 완료")
    except Exception as e:
        logger.error(f"통합 테이블 생성 오류: {e}")
        conn.rollback()
    finally:
        conn.close()

def migrate_data():
    """데이터 마이그레이션"""
    conn = db_connection()
    logger.info("데이터 마이그레이션 시작...")
    
    try:
        with conn.cursor() as cursor:
            # 1. 테이블 존재 여부 확인
            cursor.execute("SHOW TABLES LIKE 'medicines'")
            has_medicines = cursor.fetchone() is not None
            
            cursor.execute("SHOW TABLES LIKE 'medicine_usage'")
            has_medicine_usage = cursor.fetchone() is not None
            
            if not (has_medicines and has_medicine_usage):
                logger.error("필요한 테이블이 없습니다: medicines 또는 medicine_usage")
                return
            
            # 2. 기존 데이터 통계 확인
            cursor.execute("SELECT COUNT(*) as cnt FROM medicines")
            medicines_count = cursor.fetchone()['cnt']
            
            cursor.execute("SELECT COUNT(*) as cnt FROM medicine_usage")
            usage_count = cursor.fetchone()['cnt']
            
            logger.info(f"기존 데이터: medicines={medicines_count}개, medicine_usage={usage_count}개")
            
            # 3. 통합 테이블 초기화
            cursor.execute("TRUNCATE TABLE unified_medicines")
            logger.info("통합 테이블 초기화 완료")
            
            # 4. JOIN을 통해 데이터 이전
            cursor.execute("""
            INSERT INTO unified_medicines (
                item_seq, item_name, item_eng_name, entp_seq, entp_name, chart, 
                class_no, class_name, etc_otc_name, item_permit_date, form_code_name, 
                edi_code, change_date, medicine_id, efcy_qesitm, use_method_qesitm, 
                atpn_warn_qesitm, atpn_qesitm, intrc_qesitm, se_qesitm, deposit_method_qesitm
            )
            SELECT 
                m.item_seq, m.item_name, m.item_eng_name, m.entp_seq, m.entp_name, m.chart,
                m.class_no, m.class_name, m.etc_otc_name, m.item_permit_date, m.form_code_name,
                m.edi_code, m.change_date, mu.medicine_id, mu.efcy_qesitm, mu.use_method_qesitm,
                mu.atpn_warn_qesitm, mu.atpn_qesitm, mu.intrc_qesitm, mu.se_qesitm, mu.deposit_method_qesitm
            FROM 
                medicines m
            JOIN 
                medicine_usage mu ON m.id = mu.medicine_id
            """)
            
            joined_count = cursor.rowcount
            logger.info(f"JOIN을 통한 데이터 이전: {joined_count}개 항목")
            
            # 5. medicine_usage에 매핑되지 않은 medicines 데이터 이전
            cursor.execute("""
            INSERT INTO unified_medicines (
                item_seq, item_name, item_eng_name, entp_seq, entp_name, chart, 
                class_no, class_name, etc_otc_name, item_permit_date, form_code_name, 
                edi_code, change_date
            )
            SELECT 
                m.item_seq, m.item_name, m.item_eng_name, m.entp_seq, m.entp_name, m.chart,
                m.class_no, m.class_name, m.etc_otc_name, m.item_permit_date, m.form_code_name,
                m.edi_code, m.change_date
            FROM 
                medicines m
            LEFT JOIN 
                medicine_usage mu ON m.id = mu.medicine_id
            WHERE 
                mu.medicine_id IS NULL
            """)
            
            medicines_only_count = cursor.rowcount
            logger.info(f"medicines만 있는 데이터 이전: {medicines_only_count}개 항목")
            
            # 6. medicines에 매핑되지 않은 medicine_usage 데이터 이전
            cursor.execute("""
            INSERT INTO unified_medicines (
                medicine_id, efcy_qesitm, use_method_qesitm, 
                atpn_warn_qesitm, atpn_qesitm, intrc_qesitm, se_qesitm, deposit_method_qesitm
            )
            SELECT 
                mu.medicine_id, mu.efcy_qesitm, mu.use_method_qesitm,
                mu.atpn_warn_qesitm, mu.atpn_qesitm, mu.intrc_qesitm, mu.se_qesitm, mu.deposit_method_qesitm
            FROM 
                medicine_usage mu
            LEFT JOIN 
                medicines m ON mu.medicine_id = m.id
            WHERE 
                m.id IS NULL
            """)
            
            usage_only_count = cursor.rowcount
            logger.info(f"medicine_usage만 있는 데이터 이전: {usage_only_count}개 항목")
            
            # 7. 통계 출력
            cursor.execute("SELECT COUNT(*) as cnt FROM unified_medicines")
            unified_count = cursor.fetchone()['cnt']
            
            cursor.execute("SELECT COUNT(*) as cnt FROM unified_medicines WHERE item_seq IS NOT NULL")
            with_item_seq = cursor.fetchone()['cnt']
            
            cursor.execute("SELECT COUNT(*) as cnt FROM unified_medicines WHERE atpn_qesitm IS NOT NULL")
            with_atpn = cursor.fetchone()['cnt']
            
            logger.info(f"통합 테이블 통계:")
            logger.info(f"  총 항목: {unified_count}개")
            logger.info(f"  품목일련번호 있음: {with_item_seq}개 ({with_item_seq/unified_count*100:.1f}%)")
            logger.info(f"  주의사항 있음: {with_atpn}개 ({with_atpn/unified_count*100:.1f}%)")
            
            # 8. 샘플 데이터 확인
            cursor.execute("""
            SELECT id, item_seq, item_name, medicine_id, 
                   LENGTH(atpn_qesitm) as atpn_len
            FROM unified_medicines
            WHERE item_seq IS NOT NULL AND atpn_qesitm IS NOT NULL
            LIMIT 5
            """)
            
            samples = cursor.fetchall()
            if samples:
                logger.info("통합 데이터 샘플:")
                for sample in samples:
                    logger.info(f"  id={sample['id']}, item_seq={sample['item_seq']}, item_name={sample['item_name']}, medicine_id={sample['medicine_id']}, 주의사항 길이={sample['atpn_len']}")
            
            conn.commit()
            logger.info("데이터 마이그레이션 완료")
            
    except Exception as e:
        logger.error(f"데이터 마이그레이션 오류: {e}")
        conn.rollback()
    finally:
        conn.close()

def main():
    """메인 함수"""
    logger.info("의약품 데이터 통합 마이그레이션 시작")
    
    # 1. 통합 테이블 생성
    create_unified_table()
    
    # 2. 데이터 마이그레이션
    migrate_data()
    
    logger.info("의약품 데이터 통합 마이그레이션 완료")

if __name__ == "__main__":
    main()