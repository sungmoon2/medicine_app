import os
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv
import pandas as pd
from tabulate import tabulate

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

def find_common_item_seq():
    """unified_medicines와 drug_identification 테이블 간 공통 item_seq 찾기"""
    print("두 테이블 간 공통 item_seq 검색을 시작합니다...")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 두 테이블에서 item_seq 값 가져오기
            print("1. unified_medicines 테이블에서 item_seq 값 가져오기...")
            cursor.execute("SELECT item_seq FROM unified_medicines")
            unified_seq = set([row['item_seq'] for row in cursor.fetchall() if row['item_seq']])
            
            print(f"   - unified_medicines 테이블에서 {len(unified_seq)}개의 item_seq 값을 찾았습니다.")
            
            print("2. drug_identification 테이블에서 item_seq 값 가져오기...")
            cursor.execute("SELECT item_seq FROM drug_identification")
            drug_seq = set([row['item_seq'] for row in cursor.fetchall() if row['item_seq']])
            
            print(f"   - drug_identification 테이블에서 {len(drug_seq)}개의 item_seq 값을 찾았습니다.")
            
            # 두 세트의 교집합 찾기
            common_seq = unified_seq.intersection(drug_seq)
            
            print(f"3. 두 테이블에 공통으로 존재하는 item_seq 값은 {len(common_seq)}개입니다.")
            
            # 공통 item_seq에 대한 상세 정보 가져오기
            if common_seq:
                # 공통 item_seq 목록 문자열로 변환
                seq_list = "', '".join(common_seq)
                
                print("4. 공통 item_seq에 대한 상세 정보를 가져옵니다...")
                
                query = f"""
                SELECT 
                    u.item_seq, u.item_name AS unified_name, d.item_name AS drug_name,
                    u.entp_name AS unified_manufacturer, d.entp_name AS drug_manufacturer,
                    u.class_name AS unified_class, d.class_name AS drug_class
                FROM unified_medicines u
                JOIN drug_identification d ON u.item_seq = d.item_seq
                WHERE u.item_seq IN ('{seq_list}')
                LIMIT 50
                """
                
                cursor.execute(query)
                common_data = cursor.fetchall()
                
                # 결과를 판다스 데이터프레임으로 변환
                df = pd.DataFrame(common_data)
                
                # 결과 출력
                print("\n공통 item_seq에 대한 샘플 데이터 (최대 50개):")
                print(tabulate(df, headers='keys', tablefmt='psql', showindex=False))
                
                # 결과를 CSV 파일로 저장
                output_csv = 'common_item_seq_data.csv'
                df.to_csv(output_csv, index=False, encoding='utf-8-sig')
                print(f"\n모든 공통 데이터가 '{output_csv}' 파일로 저장되었습니다.")
                
                return common_seq, df
            else:
                print("공통 item_seq 값이 없습니다.")
                return common_seq, None
                
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        return set(), None
    finally:
        conn.close()

def find_unique_items_in_each_table():
    """각 테이블에만 존재하는 item_seq 찾기"""
    print("\n각 테이블에만 존재하는 item_seq 분석을 시작합니다...")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 두 테이블에서 item_seq 값 가져오기
            cursor.execute("SELECT item_seq FROM unified_medicines")
            unified_seq = set([row['item_seq'] for row in cursor.fetchall() if row['item_seq']])
            
            cursor.execute("SELECT item_seq FROM drug_identification")
            drug_seq = set([row['item_seq'] for row in cursor.fetchall() if row['item_seq']])
            
            # 각 테이블에만 존재하는 item_seq 찾기
            only_in_unified = unified_seq - drug_seq
            only_in_drug = drug_seq - unified_seq
            
            print(f"1. unified_medicines 테이블에만 존재하는 item_seq: {len(only_in_unified)}개")
            print(f"2. drug_identification 테이블에만 존재하는 item_seq: {len(only_in_drug)}개")
            
            return only_in_unified, only_in_drug
                
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        return set(), set()
    finally:
        conn.close()

def analyze_sample_items():
    """각 테이블에서 샘플 데이터 분석"""
    print("\n각 테이블의 샘플 데이터를 분석합니다...")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # unified_medicines 테이블에서 샘플 데이터 가져오기
            print("1. unified_medicines 테이블 샘플 데이터:")
            cursor.execute("""
                SELECT item_seq, item_name, entp_name, class_name 
                FROM unified_medicines 
                WHERE item_seq IS NOT NULL
                LIMIT 5
            """)
            unified_samples = cursor.fetchall()
            
            unified_df = pd.DataFrame(unified_samples)
            print(tabulate(unified_df, headers='keys', tablefmt='psql', showindex=False))
            
            # drug_identification 테이블에서 샘플 데이터 가져오기
            print("\n2. drug_identification 테이블 샘플 데이터:")
            cursor.execute("""
                SELECT item_seq, item_name, entp_name, class_name 
                FROM drug_identification 
                WHERE item_seq IS NOT NULL
                LIMIT 5
            """)
            drug_samples = cursor.fetchall()
            
            drug_df = pd.DataFrame(drug_samples)
            print(tabulate(drug_df, headers='keys', tablefmt='psql', showindex=False))
            
    except Exception as e:
        print(f"오류 발생: {str(e)}")
    finally:
        conn.close()

def analyze_column_existence():
    """각 테이블의 컬럼 존재 여부 확인"""
    print("\n각 테이블의 컬럼 구조를 분석합니다...")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # unified_medicines 테이블 컬럼 확인
            cursor.execute("SHOW COLUMNS FROM unified_medicines")
            unified_columns = [row['Field'] for row in cursor.fetchall()]
            
            # drug_identification 테이블 컬럼 확인
            cursor.execute("SHOW COLUMNS FROM drug_identification")
            drug_columns = [row['Field'] for row in cursor.fetchall()]
            
            # 공통 컬럼과 각 테이블에만 있는 컬럼 확인
            common_columns = set(unified_columns).intersection(set(drug_columns))
            only_in_unified = set(unified_columns) - set(drug_columns)
            only_in_drug = set(drug_columns) - set(unified_columns)
            
            print(f"1. 두 테이블에 공통으로 존재하는 컬럼: {len(common_columns)}개")
            print(", ".join(sorted(common_columns)))
            
            print(f"\n2. unified_medicines 테이블에만 존재하는 컬럼: {len(only_in_unified)}개")
            if only_in_unified:
                print(", ".join(sorted(only_in_unified)))
            
            print(f"\n3. drug_identification 테이블에만 존재하는 컬럼: {len(only_in_drug)}개")
            if only_in_drug:
                print(", ".join(sorted(only_in_drug)))
            
    except Exception as e:
        print(f"오류 발생: {str(e)}")
    finally:
        conn.close()

def main():
    """메인 함수"""
    print("===== 의약품 데이터베이스 테이블 비교 분석 =====\n")
    
    # 1. 테이블 구조 분석
    analyze_column_existence()
    
    # 2. 샘플 데이터 확인
    analyze_sample_items()
    
    # 3. 공통 item_seq 찾기
    common_seq, common_data = find_common_item_seq()
    
    # 4. 각 테이블에만 존재하는 item_seq 찾기
    only_in_unified, only_in_drug = find_unique_items_in_each_table()
    
    # 5. 결과 요약
    print("\n===== 분석 결과 요약 =====")
    print(f"1. 공통 item_seq 수: {len(common_seq)}개")
    print(f"2. unified_medicines 테이블에만 존재하는 item_seq: {len(only_in_unified)}개")
    print(f"3. drug_identification 테이블에만 존재하는 item_seq: {len(only_in_drug)}개")
    
    print("\n분석이 완료되었습니다.")

if __name__ == "__main__":
    main()