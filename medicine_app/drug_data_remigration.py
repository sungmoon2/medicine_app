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

def fix_medicine_usage_migration():
    """medicine_usage 테이블 데이터를 통합 테이블로 다시 마이그레이션"""
    conn = db_connection()
    logger.info(f"{Fore.GREEN}medicine_usage 테이블 데이터 재마이그레이션 시작...{Style.RESET_ALL}")
    
    try:
        with conn.cursor() as cursor:
            # 1. 테이블 존재 여부 확인
            cursor.execute("SHOW TABLES LIKE 'medicines'")
            has_medicines = cursor.fetchone() is not None
            
            cursor.execute("SHOW TABLES LIKE 'medicine_usage'")
            has_medicine_usage = cursor.fetchone() is not None
            
            cursor.execute("SHOW TABLES LIKE 'integrated_drug_info'")
            has_integrated = cursor.fetchone() is not None
            
            if not (has_medicines and has_medicine_usage and has_integrated):
                logger.error(f"필요한 테이블이 없습니다: medicines={has_medicines}, medicine_usage={has_medicine_usage}, integrated_drug_info={has_integrated}")
                return
            
            # 2. 테이블 데이터 통계 확인
            cursor.execute("SELECT COUNT(*) as cnt FROM medicines")
            medicines_count = cursor.fetchone()['cnt']
            
            cursor.execute("SELECT COUNT(*) as cnt FROM medicine_usage")
            usage_count = cursor.fetchone()['cnt']
            
            cursor.execute("SELECT COUNT(*) as cnt FROM integrated_drug_info")
            integrated_count = cursor.fetchone()['cnt']
            
            logger.info(f"테이블 데이터 통계: medicines={medicines_count}, medicine_usage={usage_count}, integrated_drug_info={integrated_count}")
            
            # 3. medicine_usage 테이블의 필드 존재 여부 확인
            cursor.execute("SHOW COLUMNS FROM medicine_usage")
            usage_fields = [row['Field'] for row in cursor.fetchall()]
            
            # 4. medicines와 medicine_usage 사이의 관계 확인
            cursor.execute("""
            SELECT COUNT(*) as cnt FROM medicines m
            JOIN medicine_usage mu ON m.id = mu.medicine_id
            """)
            relation_count = cursor.fetchone()['cnt']
            logger.info(f"medicine_usage와 medicines 간의 관계 수: {relation_count}")
            
            # 필드 매핑 정의
            target_fields = [
                'medicine_id', 'efcy_qesitm', 'use_method_qesitm', 'atpn_warn_qesitm',
                'atpn_qesitm', 'intrc_qesitm', 'se_qesitm', 'deposit_method_qesitm'
            ]
            
            # 존재하는 필드만 필터링
            valid_fields = [f for f in target_fields if f in usage_fields]
            
            if not valid_fields:
                logger.error("medicine_usage 테이블에 필요한 필드가 없습니다.")
                return
            
            logger.info(f"medicine_usage 유효 필드: {valid_fields}")
            
            # 5. 테이블 별 식별자 확인
            # medicines 테이블의 item_seq 필드 존재 여부 확인
            cursor.execute("SHOW COLUMNS FROM medicines LIKE 'item_seq'")
            has_item_seq = cursor.fetchone() is not None
            
            if not has_item_seq:
                logger.error("medicines 테이블에 item_seq 필드가 없습니다.")
                return
            
            # 6. 통합 테이블의 medicine_usage 관련 필드 초기화
            cursor.execute("""
            UPDATE integrated_drug_info
            SET 
                medicine_id = NULL,
                efcy_qesitm = NULL,
                use_method_qesitm = NULL,
                atpn_warn_qesitm = NULL,
                atpn_qesitm = NULL,
                intrc_qesitm = NULL,
                se_qesitm = NULL,
                deposit_method_qesitm = NULL
            """)
            logger.info(f"통합 테이블의 medicine_usage 관련 필드 초기화: {cursor.rowcount}개 행")
            
            # 7. item_seq를 기준으로 테이블 간 관계 확인
            cursor.execute("""
            SELECT m.id, m.item_seq, i.id as integrated_id
            FROM medicines m
            JOIN integrated_drug_info i ON m.item_seq = i.item_seq
            LIMIT 5
            """)
            
            item_seq_relations = cursor.fetchall()
            if item_seq_relations:
                logger.info(f"medicines와 integrated_drug_info 간의 item_seq 관계 샘플 ({len(item_seq_relations)}개):")
                for rel in item_seq_relations:
                    logger.info(f"  medicines.id={rel['id']}, item_seq={rel['item_seq']}, integrated_id={rel['integrated_id']}")
            else:
                logger.warning("medicines와 integrated_drug_info 간에 item_seq로 연결된 데이터가 없습니다.")
            
            # 8. 동일한 item_seq를 가진 의약품 찾기
            cursor.execute("""
            SELECT 
                i.id as integrated_id,
                i.item_seq,
                i.item_name,
                m.id as medicine_id
            FROM 
                integrated_drug_info i
            JOIN 
                medicines m ON i.item_seq = m.item_seq
            LIMIT 10
            """)
            
            matching_items = cursor.fetchall()
            if matching_items:
                logger.info(f"동일한 item_seq를 가진 의약품 샘플 ({len(matching_items)}개):")
                for item in matching_items:
                    logger.info(f"  integrated_id={item['integrated_id']}, item_seq={item['item_seq']}, item_name={item['item_name']}, medicine_id={item['medicine_id']}")
            else:
                logger.warning("동일한 item_seq를 가진 의약품이 없습니다. 데이터를 확인해주세요.")
            
            # 9. medicine_id 매핑 - item_seq 기준
            cursor.execute("""
            UPDATE integrated_drug_info i
            JOIN medicines m ON i.item_seq = m.item_seq
            SET i.medicine_id = m.id
            """)
            
            medicine_id_mapped = cursor.rowcount
            logger.info(f"medicine_id 매핑 완료 (item_seq 기준): {medicine_id_mapped}개 항목")
            
            # 10. item_name으로 매핑 시도 (item_seq가 없는 경우)
            cursor.execute("""
            UPDATE integrated_drug_info i
            JOIN medicines m ON i.item_name = m.item_name
            SET i.medicine_id = m.id
            WHERE i.medicine_id IS NULL AND i.item_seq IS NULL
            """)
            
            medicine_id_mapped_by_name = cursor.rowcount
            logger.info(f"medicine_id 매핑 완료 (item_name 기준): {medicine_id_mapped_by_name}개 항목")
            
            # 총 매핑된 medicine_id 수 확인
            cursor.execute("SELECT COUNT(*) as cnt FROM integrated_drug_info WHERE medicine_id IS NOT NULL")
            total_mapped = cursor.fetchone()['cnt']
            logger.info(f"총 매핑된 medicine_id: {total_mapped}개")
            
            # 11. medicine_usage 데이터 마이그레이션
            # 필드 목록 생성
            update_fields = ", ".join([f"i.{f} = mu.{f}" for f in valid_fields if f != 'medicine_id'])
            
            # SQL 문 생성 및 실행
            if update_fields:
                update_sql = f"""
                UPDATE integrated_drug_info i
                JOIN medicine_usage mu ON i.medicine_id = mu.medicine_id
                SET {update_fields}
                WHERE i.medicine_id IS NOT NULL
                """
                
                cursor.execute(update_sql)
                usage_updated = cursor.rowcount
                logger.info(f"medicine_usage 데이터 마이그레이션 완료: {usage_updated}개 항목")
            
            # HTML 태그 처리된 텍스트 샘플 확인
            cursor.execute("""
            SELECT item_name, efcy_qesitm, use_method_qesitm
            FROM integrated_drug_info
            WHERE efcy_qesitm IS NOT NULL
            LIMIT 3
            """)
            
            samples = cursor.fetchall()
            if samples:
                logger.info("데이터 샘플 (HTML 태그 포함):")
                for sample in samples:
                    # HTML 태그 제거한 짧은 미리보기
                    efcy_preview = re.sub('<.*?>', '', sample['efcy_qesitm'] or '')[:100] + '...' if sample['efcy_qesitm'] else 'NULL'
                    use_preview = re.sub('<.*?>', '', sample['use_method_qesitm'] or '')[:100] + '...' if sample['use_method_qesitm'] else 'NULL'
                    
                    logger.info(f"  {sample['item_name']}")
                    logger.info(f"    - 효능효과: {efcy_preview}")
                    logger.info(f"    - 용법용량: {use_preview}")
            
            conn.commit()
            logger.info(f"{Fore.GREEN}medicine_usage 데이터 재마이그레이션 완료{Style.RESET_ALL}")
            
            # 통계 출력
            cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN efcy_qesitm IS NOT NULL THEN 1 ELSE 0 END) as with_efcy,
                SUM(CASE WHEN use_method_qesitm IS NOT NULL THEN 1 ELSE 0 END) as with_use,
                SUM(CASE WHEN atpn_qesitm IS NOT NULL THEN 1 ELSE 0 END) as with_atpn,
                SUM(CASE WHEN se_qesitm IS NOT NULL THEN 1 ELSE 0 END) as with_se
            FROM integrated_drug_info
            """)
            
            stats = cursor.fetchone()
            logger.info(f"통합 테이블 통계:")
            logger.info(f"  총 항목: {stats['total']}개")
            logger.info(f"  효능효과 있음: {stats['with_efcy']}개 ({stats['with_efcy']/stats['total']*100:.1f}%)")
            logger.info(f"  용법용량 있음: {stats['with_use']}개 ({stats['with_use']/stats['total']*100:.1f}%)")
            logger.info(f"  주의사항 있음: {stats['with_atpn']}개 ({stats['with_atpn']/stats['total']*100:.1f}%)")
            logger.info(f"  부작용 있음: {stats['with_se']}개 ({stats['with_se']/stats['total']*100:.1f}%)")
            
    except Exception as e:
        logger.error(f"medicine_usage 데이터 재마이그레이션 오류: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("medicine_usage 데이터 재마이그레이션 시작")
    try:
        fix_medicine_usage_migration()
        print("medicine_usage 데이터 재마이그레이션 완료")
    except Exception as e:
        print(f"오류 발생: {e}")
        logger.error(f"오류 발생: {e}", exc_info=True)