import os
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv
import pandas as pd
from tabulate import tabulate
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_verification.log'),
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

def verify_columns_exist(cursor):
    """drug_identification 테이블에 추가된 컬럼 확인"""
    columns_to_check = [
        'atpn_qesitm',         # 주의사항
        'intrc_qesitm',        # 상호작용
        'se_qesitm',           # 부작용
        'deposit_method_qesitm', # 보관방법
        'efcy_qesitm',         # 효능효과
        'use_method_qesitm',   # 용법용량
        'atpn_warn_qesitm'     # 경고
    ]
    
    cursor.execute("SHOW COLUMNS FROM drug_identification")
    existing_columns = [row['Field'] for row in cursor.fetchall()]
    
    verified_columns = [col for col in columns_to_check if col in existing_columns]
    missing_columns = [col for col in columns_to_check if col not in existing_columns]
    
    if verified_columns:
        logger.info(f"drug_identification 테이블에 다음 컬럼이 존재합니다: {', '.join(verified_columns)}")
    
    if missing_columns:
        logger.warning(f"drug_identification 테이블에 다음 컬럼이 누락되었습니다: {', '.join(missing_columns)}")
    
    return verified_columns, missing_columns

def verify_data_transfer(cursor, columns_to_verify):
    """데이터 전송 결과 검증"""
    # 테스트를 위해 최대 5개의 공통 item_seq 가져오기
    cursor.execute("""
    SELECT di.item_seq
    FROM drug_identification di
    JOIN unified_medicines um ON di.item_seq = um.item_seq
    WHERE di.item_seq IS NOT NULL
    LIMIT 5
    """)
    
    sample_item_seqs = [row['item_seq'] for row in cursor.fetchall()]
    if not sample_item_seqs:
        logger.warning("검증할 공통 item_seq가 없습니다.")
        return
    
    logger.info(f"검증을 위해 {len(sample_item_seqs)}개의 샘플 item_seq를 선택했습니다.")
    
    # 샘플 데이터의 컬럼 값 비교
    for item_seq in sample_item_seqs:
        logger.info(f"item_seq={item_seq} 데이터 검증...")
        
        # unified_medicines 데이터 가져오기
        cursor.execute(f"""
        SELECT item_name, {', '.join(columns_to_verify)}
        FROM unified_medicines
        WHERE item_seq = %s
        """, (item_seq,))
        unified_data = cursor.fetchone()
        
        # drug_identification 데이터 가져오기
        cursor.execute(f"""
        SELECT item_name, {', '.join(columns_to_verify)}
        FROM drug_identification
        WHERE item_seq = %s
        """, (item_seq,))
        drug_data = cursor.fetchone()
        
        if unified_data and drug_data:
            # 각 컬럼 값 비교
            comparison_data = []
            all_match = True
            
            # 약품명 추가
            comparison_data.append({
                'item_seq': item_seq,
                'column': 'item_name',
                'unified_value': unified_data['item_name'],
                'drug_value': drug_data['item_name'],
                'match': unified_data['item_name'] == drug_data['item_name']
            })
            
            # 각 컬럼 비교
            for col in columns_to_verify:
                # NULL 값은 빈 문자열로 처리
                unified_val = unified_data[col] if unified_data[col] is not None else ''
                drug_val = drug_data[col] if drug_data[col] is not None else ''
                
                # 값이 같은지 비교
                is_match = unified_val == drug_val
                if not is_match:
                    all_match = False
                
                # 텍스트가 너무 길 경우 요약
                if unified_val and len(unified_val) > 50:
                    unified_val = unified_val[:47] + "..."
                if drug_val and len(drug_val) > 50:
                    drug_val = drug_val[:47] + "..."
                
                comparison_data.append({
                    'item_seq': item_seq,
                    'column': col,
                    'unified_value': unified_val,
                    'drug_value': drug_val,
                    'match': is_match
                })
            
            # 결과를 표로 출력
            df = pd.DataFrame(comparison_data)
            logger.info(f"\n{tabulate(df, headers='keys', tablefmt='psql')}")
            
            if all_match:
                logger.info(f"item_seq={item_seq}의 모든 컬럼 데이터가 일치합니다.")
            else:
                logger.warning(f"item_seq={item_seq}의 일부 컬럼 데이터가 일치하지 않습니다.")
        else:
            logger.warning(f"item_seq={item_seq}에 대해 하나 이상의 테이블에서 데이터를 찾을 수 없습니다.")

def count_non_null_values(cursor, columns):
    """drug_identification 테이블에서 빈 값이 아닌 레코드 개수 확인"""
    results = {}
    
    for col in columns:
        cursor.execute(f"""
        SELECT COUNT(*) as count
        FROM drug_identification
        WHERE {col} IS NOT NULL AND {col} != ''
        """)
        row = cursor.fetchone()
        results[col] = row['count'] if row else 0
    
    # 전체 레코드 수 가져오기
    cursor.execute("SELECT COUNT(*) as total FROM drug_identification")
    total = cursor.fetchone()['total']
    
    # 결과 출력
    logger.info(f"drug_identification 테이블의 총 레코드 수: {total}")
    
    for col, count in results.items():
        percentage = (count / total) * 100 if total > 0 else 0
        logger.info(f"컬럼 '{col}'에서 값이 있는 레코드: {count}개 ({percentage:.2f}%)")
    
    return results, total

def main():
    """메인 함수"""
    logger.info("데이터 전송 검증 프로세스 시작")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 컬럼 존재 여부 확인
            verified_columns, missing_columns = verify_columns_exist(cursor)
            
            if not verified_columns:
                logger.error("검증할 컬럼이 없습니다. 프로세스를 종료합니다.")
                return
            
            # 2. 데이터 전송 검증
            verify_data_transfer(cursor, verified_columns)
            
            # 3. 데이터 채워진 상태 확인
            count_non_null_values(cursor, verified_columns)
            
    except Exception as e:
        logger.error(f"오류 발생: {str(e)}")
    finally:
        conn.close()
        logger.info("데이터베이스 연결 종료")
    
    logger.info("데이터 전송 검증 프로세스 완료")

if __name__ == "__main__":
    main()