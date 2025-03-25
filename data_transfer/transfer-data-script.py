import os
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_transfer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 환경 변수 로드
load_dotenv()

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

def check_columns_exist(cursor, table_name, columns):
    """테이블에 특정 컬럼들이 존재하는지 확인"""
    cursor.execute(f"SHOW COLUMNS FROM {table_name}")
    existing_columns = [row['Field'] for row in cursor.fetchall()]
    
    missing_columns = [col for col in columns if col not in existing_columns]
    return missing_columns

def add_columns(cursor, table_name, columns_to_add):
    """테이블에 새 컬럼 추가"""
    for column_name in columns_to_add:
        # TEXT 타입으로 컬럼 추가 (긴 텍스트 데이터 저장 가능)
        query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} TEXT"
        logger.info(f"컬럼 추가 쿼리: {query}")
        cursor.execute(query)
    
    logger.info(f"{table_name} 테이블에 {len(columns_to_add)}개 컬럼 추가 완료")

def get_common_item_seq(cursor):
    """unified_medicines와 drug_identification 테이블 간 공통 item_seq 찾기"""
    cursor.execute("SELECT item_seq FROM unified_medicines WHERE item_seq IS NOT NULL")
    unified_seq = set([row['item_seq'] for row in cursor.fetchall() if row['item_seq']])
    
    cursor.execute("SELECT item_seq FROM drug_identification WHERE item_seq IS NOT NULL")
    drug_seq = set([row['item_seq'] for row in cursor.fetchall() if row['item_seq']])
    
    common_seq = unified_seq.intersection(drug_seq)
    logger.info(f"두 테이블 간 공통 item_seq: {len(common_seq)}개")
    
    return list(common_seq)

def transfer_data(cursor, common_item_seq, columns_to_transfer):
    """unified_medicines에서 drug_identification으로 데이터 전송"""
    total_count = len(common_item_seq)
    updated_count = 0
    error_count = 0
    
    # 한 번에 처리할 item_seq 개수 (배치 처리)
    batch_size = 100
    
    for i in range(0, total_count, batch_size):
        batch = common_item_seq[i:i+batch_size]
        batch_str = "', '".join(batch)
        
        try:
            # unified_medicines 테이블에서 데이터 가져오기
            query = f"""
            SELECT item_seq, {', '.join(columns_to_transfer)}
            FROM unified_medicines
            WHERE item_seq IN ('{batch_str}')
            """
            cursor.execute(query)
            source_data = cursor.fetchall()
            
            if source_data:
                # 각 행마다 drug_identification 테이블 업데이트
                for row in source_data:
                    item_seq = row['item_seq']
                    
                    update_parts = []
                    update_values = []
                    
                    # NULL이 아닌 컬럼만 업데이트
                    for col in columns_to_transfer:
                        if row[col] is not None:
                            update_parts.append(f"{col} = %s")
                            update_values.append(row[col])
                    
                    if update_parts and update_values:
                        update_query = f"""
                        UPDATE drug_identification
                        SET {', '.join(update_parts)}
                        WHERE item_seq = %s
                        """
                        update_values.append(item_seq)
                        
                        cursor.execute(update_query, update_values)
                        updated_count += 1
            
            if i % 500 == 0 or i + batch_size >= total_count:
                logger.info(f"진행 상황: {min(i + batch_size, total_count)}/{total_count} 처리 중...")
                
        except Exception as e:
            logger.error(f"배치 {i}~{i+batch_size} 처리 중 오류 발생: {str(e)}")
            error_count += 1
    
    logger.info(f"데이터 전송 완료: {updated_count}개 업데이트, {error_count}개 오류")
    return updated_count, error_count

def main():
    """메인 함수"""
    logger.info("약품 데이터 전송 프로세스 시작")
    
    # 전송할 컬럼 목록
    columns_to_transfer = [
        'atpn_qesitm',         # 주의사항
        'intrc_qesitm',        # 상호작용
        'se_qesitm',           # 부작용
        'deposit_method_qesitm', # 보관방법
        'efcy_qesitm',         # 효능효과
        'use_method_qesitm',   # 용법용량
        'atpn_warn_qesitm'     # 경고
    ]
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. drug_identification 테이블에 필요한 컬럼이 있는지 확인
            missing_columns = check_columns_exist(cursor, 'drug_identification', columns_to_transfer)
            
            if missing_columns:
                # 2. 없는 컬럼 추가
                logger.info(f"drug_identification 테이블에 추가해야 할 컬럼: {missing_columns}")
                add_columns(cursor, 'drug_identification', missing_columns)
                conn.commit()
            else:
                logger.info("drug_identification 테이블에 이미 모든 필요한 컬럼이 존재합니다.")
            
            # 3. 두 테이블 간 공통 item_seq 값 찾기
            common_item_seq = get_common_item_seq(cursor)
            
            if common_item_seq:
                # 4. 데이터 전송
                logger.info(f"{len(common_item_seq)}개 약품에 대해 데이터 전송 시작...")
                updated, errors = transfer_data(cursor, common_item_seq, columns_to_transfer)
                
                # 5. 변경사항 커밋
                conn.commit()
                logger.info(f"트랜잭션 커밋 완료: {updated}개 업데이트됨, {errors}개 오류 발생")
            else:
                logger.warning("두 테이블 간 공통 item_seq가 없습니다. 데이터 전송을 건너뜁니다.")
                
    except Exception as e:
        logger.error(f"오류 발생: {str(e)}")
        conn.rollback()
        logger.info("트랜잭션 롤백됨")
    finally:
        conn.close()
        logger.info("데이터베이스 연결 종료")
    
    logger.info("약품 데이터 전송 프로세스 완료")

if __name__ == "__main__":
    main()