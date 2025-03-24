import pymysql
import logging
import os
import sys
from dotenv import load_dotenv
import colorama
from colorama import Fore, Style
import time
import re

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='data_migration_fix.log',
    encoding='utf-8'
)
logger = logging.getLogger('data_migration_fix')

# 콘솔 출력을 위한 핸들러 추가
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(console_handler)
colorama.init(autoreset=True)  # Windows 콘솔 색상 지원

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

def migrate_atpn_data():
    """주의사항 데이터를 중심으로 한 마이그레이션"""
    conn = db_connection()
    logger.info(f"{Fore.GREEN}주의사항 데이터 중심 마이그레이션 시작...{Style.RESET_ALL}")
    
    try:
        with conn.cursor() as cursor:
            # 1. medicine_usage 필드 데이터 상태 확인
            cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN LENGTH(efcy_qesitm) > 0 THEN 1 ELSE 0 END) as efcy_count,
                SUM(CASE WHEN LENGTH(use_method_qesitm) > 0 THEN 1 ELSE 0 END) as use_count,
                SUM(CASE WHEN LENGTH(atpn_qesitm) > 0 THEN 1 ELSE 0 END) as atpn_count,
                SUM(CASE WHEN LENGTH(atpn_warn_qesitm) > 0 THEN 1 ELSE 0 END) as warn_count,
                SUM(CASE WHEN LENGTH(intrc_qesitm) > 0 THEN 1 ELSE 0 END) as intrc_count,
                SUM(CASE WHEN LENGTH(se_qesitm) > 0 THEN 1 ELSE 0 END) as se_count,
                SUM(CASE WHEN LENGTH(deposit_method_qesitm) > 0 THEN 1 ELSE 0 END) as deposit_count
            FROM medicine_usage
            """)
            field_stats = cursor.fetchone()
            logger.info(f"medicine_usage 테이블 데이터 통계:")
            logger.info(f"  총 항목: {field_stats['total']}개")
            logger.info(f"  효능효과 있음: {field_stats['efcy_count']}개 ({field_stats['efcy_count']/field_stats['total']*100:.1f}% 있음)")
            logger.info(f"  용법용량 있음: {field_stats['use_count']}개 ({field_stats['use_count']/field_stats['total']*100:.1f}% 있음)")
            logger.info(f"  주의사항 있음: {field_stats['atpn_count']}개 ({field_stats['atpn_count']/field_stats['total']*100:.1f}% 있음)")
            logger.info(f"  경고 있음: {field_stats['warn_count']}개 ({field_stats['warn_count']/field_stats['total']*100:.1f}% 있음)")
            logger.info(f"  상호작용 있음: {field_stats['intrc_count']}개 ({field_stats['intrc_count']/field_stats['total']*100:.1f}% 있음)")
            logger.info(f"  부작용 있음: {field_stats['se_count']}개 ({field_stats['se_count']/field_stats['total']*100:.1f}% 있음)")
            logger.info(f"  보관법 있음: {field_stats['deposit_count']}개 ({field_stats['deposit_count']/field_stats['total']*100:.1f}% 있음)")
            
            # 2. 중복 항목 확인
            cursor.execute("""
            SELECT item_seq, COUNT(*) as cnt 
            FROM integrated_drug_info 
            WHERE item_seq IS NOT NULL 
            GROUP BY item_seq 
            HAVING COUNT(*) > 1 
            LIMIT 10
            """)
            
            duplicates = cursor.fetchall()
            if duplicates:
                logger.info(f"통합 테이블 중복 항목 샘플 ({len(duplicates)}개):")
                for dup in duplicates:
                    logger.info(f"  item_seq={dup['item_seq']}, 중복 수={dup['cnt']}")
            
            # 3. medicine_id 매핑
            # 먼저 item_seq로 매핑
            cursor.execute("""
            UPDATE integrated_drug_info i
            JOIN medicines m ON i.item_seq = m.item_seq
            SET i.medicine_id = m.id
            WHERE i.medicine_id IS NULL AND i.item_seq IS NOT NULL AND m.item_seq IS NOT NULL
            """)
            
            item_seq_mapped = cursor.rowcount
            logger.info(f"medicine_id 매핑 (item_seq 기준): {item_seq_mapped}개 항목")
            
            # 4. 주의사항 데이터 마이그레이션
            # medicine_usage에서 available_fields 목록에 있는 필드 중 실제로 데이터가 있는 필드 추출
            available_fields = ['atpn_qesitm', 'atpn_warn_qesitm', 'intrc_qesitm', 'se_qesitm', 'deposit_method_qesitm']
            
            # 필드별 데이터 마이그레이션
            for field in available_fields:
                cursor.execute(f"""
                UPDATE integrated_drug_info i
                JOIN medicine_usage mu ON i.medicine_id = mu.medicine_id
                SET i.{field} = mu.{field}
                WHERE i.medicine_id IS NOT NULL AND LENGTH(mu.{field}) > 0
                """)
                
                rows_updated = cursor.rowcount
                logger.info(f"{field} 데이터 마이그레이션: {rows_updated}개 항목")
            
            # 5. 예시 데이터 확인
            cursor.execute("""
            SELECT i.id, i.item_name, LENGTH(i.atpn_qesitm) as atpn_len
            FROM integrated_drug_info i
            WHERE LENGTH(i.atpn_qesitm) > 0
            ORDER BY atpn_len DESC
            LIMIT 5
            """)
            
            examples = cursor.fetchall()
            if examples:
                logger.info("주의사항 데이터 예시:")
                for ex in examples:
                    logger.info(f"  id={ex['id']}, item_name={ex['item_name']}, 주의사항 길이={ex['atpn_len']}")
            
            # 6. 데이터베이스 커밋
            conn.commit()
            
            # 7. 최종 통계
            cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN medicine_id IS NOT NULL THEN 1 ELSE 0 END) as with_medicine_id,
                SUM(CASE WHEN LENGTH(atpn_qesitm) > 0 THEN 1 ELSE 0 END) as with_atpn,
                SUM(CASE WHEN LENGTH(atpn_warn_qesitm) > 0 THEN 1 ELSE 0 END) as with_warn,
                SUM(CASE WHEN LENGTH(intrc_qesitm) > 0 THEN 1 ELSE 0 END) as with_intrc,
                SUM(CASE WHEN LENGTH(se_qesitm) > 0 THEN 1 ELSE 0 END) as with_se,
                SUM(CASE WHEN LENGTH(deposit_method_qesitm) > 0 THEN 1 ELSE 0 END) as with_deposit
            FROM integrated_drug_info
            """)
            
            final_stats = cursor.fetchone()
            logger.info(f"{Fore.GREEN}마이그레이션 완료. 최종 통계:{Style.RESET_ALL}")
            logger.info(f"  총 항목: {final_stats['total']}개")
            logger.info(f"  medicine_id 매핑됨: {final_stats['with_medicine_id']}개 ({final_stats['with_medicine_id']/final_stats['total']*100:.1f}%)")
            logger.info(f"  주의사항 있음: {final_stats['with_atpn']}개 ({final_stats['with_atpn']/final_stats['total']*100:.1f}%)")
            logger.info(f"  경고 있음: {final_stats['with_warn']}개 ({final_stats['with_warn']/final_stats['total']*100:.1f}%)")
            logger.info(f"  상호작용 있음: {final_stats['with_intrc']}개 ({final_stats['with_intrc']/final_stats['total']*100:.1f}%)")
            logger.info(f"  부작용 있음: {final_stats['with_se']}개 ({final_stats['with_se']/final_stats['total']*100:.1f}%)")
            logger.info(f"  보관법 있음: {final_stats['with_deposit']}개 ({final_stats['with_deposit']/final_stats['total']*100:.1f}%)")
            
    except Exception as e:
        logger.error(f"주의사항 데이터 마이그레이션 오류: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("주의사항 데이터 중심 마이그레이션 시작")
    try:
        migrate_atpn_data()
        print("주의사항 데이터 중심 마이그레이션 완료")
    except Exception as e:
        print(f"오류 발생: {e}")
        logger.error(f"오류 발생: {e}", exc_info=True)