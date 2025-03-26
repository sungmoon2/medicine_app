import sqlite3
import mysql.connector
from mysql.connector import Error
import os
import time
from tqdm import tqdm
import datetime
import configparser
import re

print(f"현재 작업 디렉토리: {os.getcwd()}")

def check_sqlite_schema():
    """SQLite 데이터베이스의 테이블 스키마를 디버깅하는 함수"""
    # SQLite 데이터베이스 연결
    sqlite_db_path = 'medicine.db'
    
    try:
        # SQLite 연결
        sqlite_conn = sqlite3.connect(sqlite_db_path)
        sqlite_cursor = sqlite_conn.cursor()
        
        # 테이블 목록 확인
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = sqlite_cursor.fetchall()
        print("테이블 목록:")
        for table in tables:
            print(f"테이블: {table[0]}")
        
        return tables
        
    except sqlite3.Error as e:
        print(f"SQLite 데이터베이스 오류: {e}")
        return []
    
    finally:
        # 연결 종료
        if 'sqlite_conn' in locals() and sqlite_conn:
            sqlite_conn.close()
            print("SQLite 데이터베이스 연결 종료")

def migrate_sqlite_to_mysql():
    # 설정 파일 생성 (처음 실행 시)
    if not os.path.exists('db_config.ini'):
        create_config_file()
        print("설정 파일(db_config.ini)이 생성되었습니다. 파일을 열어 MySQL 연결 정보를 입력한 후 다시 실행하세요.")
        return
    
    # 설정 파일 읽기
    config = configparser.ConfigParser()
    config.read('db_config.ini')
    
    # MySQL 연결 정보
    mysql_config = {
        'host': config['mysql']['host'],
        'user': config['mysql']['user'],
        'password': config['mysql']['password'],
        'database': config['mysql']['database']
    }
    
    # SQLite 파일 경로
    sqlite_db_path = config['sqlite']['db_path']
    
    # 파일 존재 확인
    if not os.path.exists(sqlite_db_path):
        print(f"오류: SQLite 데이터베이스 파일({sqlite_db_path})을 찾을 수 없습니다.")
        return
    
    try:
        # SQLite 연결
        sqlite_conn = sqlite3.connect(sqlite_db_path)
        sqlite_cursor = sqlite_conn.cursor()
        
        # 테이블 목록 확인
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = sqlite_cursor.fetchall()
        
        # 마이그레이션할 테이블 찾기
        source_table = None
        for table in tables:
            table_name = table[0]
            if table_name not in ['sqlite_sequence'] and not table_name.startswith('sqlite_'):
                source_table = table_name
                break
        
        if not source_table:
            print("마이그레이션할 테이블을 찾을 수 없습니다.")
            return
        
        # 대상 테이블 이름 (MySQL)
        target_table = 'api_medicine'
        
        # MySQL 연결
        mysql_conn = mysql.connector.connect(**mysql_config)
        mysql_cursor = mysql_conn.cursor()
        
        print(f"SQLite DB({source_table})와 MySQL DB({target_table})에 연결되었습니다.")
        
        # SQLite에서 테이블 구조 가져오기
        sqlite_cursor.execute(f"PRAGMA table_info({source_table})")
        columns_info = sqlite_cursor.fetchall()
        
        # 컬럼 정보 디버깅
        print("컬럼 정보:")
        for col in columns_info:
            print(f"컬럼: {col[1]}, 타입: {col[2]}")
        
        # 컬럼 정보 추출
        column_definitions = []
        for col in columns_info:
            col_name = col[1]
            col_type = col[2]
            
            # SQLite 타입을 MySQL 타입으로 변환
            if "INTEGER PRIMARY KEY" in col_type.upper():
                mysql_type = "INT AUTO_INCREMENT PRIMARY KEY"
            elif col_type.upper() in ["INTEGER", "INT"]:
                mysql_type = "INT"
            elif col_type.upper() == "TEXT":
                mysql_type = "TEXT"
            elif "VARCHAR" in col_type.upper():
                # 괄호 안의 숫자 추출
                size_match = re.search(r'\((\d+)\)', col_type)
                size = size_match.group(1) if size_match else "255"
                mysql_type = f"VARCHAR({size})"
            elif col_type.upper() == "TIMESTAMP":
                mysql_type = "TIMESTAMP"
            elif col_type.upper() in ["FLOAT", "REAL"]:
                mysql_type = "FLOAT"
            else:
                mysql_type = "TEXT"
            
            column_definitions.append(f"`{col_name}` {mysql_type}")
        
        # 빈 컬럼 정의가 있는지 확인
        filtered_column_definitions = [defn for defn in column_definitions if defn.strip()]
        if not filtered_column_definitions:
            print("오류: 유효한 컬럼 정의가 없습니다.")
            return
        
        # MySQL에서 테이블 생성
        try:
            # 이미 테이블이 있는지 확인 후 DROP
            mysql_cursor.execute(f"SHOW TABLES LIKE '{target_table}'")
            if mysql_cursor.fetchone():
                confirm = input(f"{target_table} 테이블이 이미 존재합니다. 덮어쓰시겠습니까? (y/n): ")
                if confirm.lower() == 'y':
                    mysql_cursor.execute(f"DROP TABLE {target_table}")
                    print("기존 테이블을 삭제했습니다.")
                else:
                    print("마이그레이션을 취소합니다.")
                    return
            
            # 테이블 생성 쿼리 만들기
            create_table_sql = f"CREATE TABLE `{target_table}` ({', '.join(filtered_column_definitions)})"
            print(f"실행할 SQL 쿼리: {create_table_sql}")
            
            mysql_cursor.execute(create_table_sql)
            mysql_conn.commit()
            print(f"MySQL에 {target_table} 테이블을 생성했습니다.")
            
            # 인덱스 생성 시도 (조건부)
            try:
                # item_name에 인덱스 생성
                if 'item_name' in [col[1] for col in columns_info]:
                    mysql_cursor.execute(f"CREATE INDEX idx_item_name ON `{target_table}`(`item_name`(255))")
                    mysql_conn.commit()
                    print("item_name 인덱스 생성 완료")
            except Error as e:
                print(f"인덱스 생성 중 오류 (무시됨): {e}")

        except Error as e:
            print(f"테이블 생성 중 오류 발생: {e}")
            return
        
        # SQLite에서 데이터 가져오기
        sqlite_cursor.execute(f"SELECT * FROM {source_table}")
        rows = sqlite_cursor.fetchall()
        total_rows = len(rows)
        
        print(f"총 {total_rows}개의 데이터를 마이그레이션합니다.")
        
        # 컬럼 이름 목록 가져오기
        sqlite_cursor.execute(f"PRAGMA table_info({source_table})")
        column_names = [column[1] for column in sqlite_cursor.fetchall()]
        
        print(f"컬럼 이름: {column_names}")

        # MySQL에 데이터 삽입
        placeholders = ', '.join(['%s'] * len(column_names))
        insert_query = f"INSERT INTO `{target_table}` ({', '.join(['`'+col+'`' for col in column_names])}) VALUES ({placeholders})"
        
        print(f"삽입 쿼리: {insert_query}")
        
        # 배치 처리 설정
        batch_size = 1000
        batches = [rows[i:i+batch_size] for i in range(0, len(rows), batch_size)]
        
        start_time = time.time()
        progress_bar = tqdm(total=total_rows, desc="데이터 마이그레이션", unit="행")
        
        for batch in batches:
            try:
                mysql_cursor.executemany(insert_query, batch)
                mysql_conn.commit()
                progress_bar.update(len(batch))
            except Error as e:
                print(f"\n데이터 삽입 중 오류 발생: {e}")
                mysql_conn.rollback()
        
        progress_bar.close()
        end_time = time.time()
        
        # MySQL에서 행 수 확인
        mysql_cursor.execute(f"SELECT COUNT(*) FROM {target_table}")
        mysql_count = mysql_cursor.fetchone()[0]
        
        print(f"\n마이그레이션 완료: SQLite {total_rows}행 -> MySQL {mysql_count}행")
        print(f"소요 시간: {end_time - start_time:.2f}초")
        
        if mysql_count < total_rows:
            print(f"주의: {total_rows - mysql_count}개의 행이 마이그레이션되지 않았습니다.")
        
    except Error as e:
        print(f"데이터베이스 오류: {e}")
    
    finally:
        # 연결 종료
        if 'sqlite_conn' in locals() and sqlite_conn:
            sqlite_conn.close()
            
        if 'mysql_conn' in locals() and mysql_conn:
            mysql_conn.close()
        
        print("데이터베이스 연결이 닫혔습니다.")

def add_hash_column_to_medicines_table():
    """
    medicines 테이블에 item_hash 컬럼 추가를 위한 마이그레이션 함수
    """
    conn = sqlite3.connect('medicine.db')
    cursor = conn.cursor()
    
    try:
        # item_hash 컬럼 추가
        cursor.execute('''
        ALTER TABLE medicines 
        ADD COLUMN item_hash VARCHAR(32)
        ''')
        
        # 기존 데이터에 대한 해시값 생성 및 업데이트
        cursor.execute('SELECT id, item_name, company_name, drug_shape FROM medicines')
        for row in cursor.fetchall():
            medicine_data = {
                'item_name': row[1],
                'company_name': row[2],
                'drug_shape': row[3]
            }
            medicine_hash = generate_medicine_hash(medicine_data)
            
            cursor.execute(
                'UPDATE medicines SET item_hash = ? WHERE id = ?', 
                (medicine_hash, row[0])
            )
        
        # 인덱스 생성
        cursor.execute(
            'CREATE UNIQUE INDEX IF NOT EXISTS idx_item_hash ON medicines (item_hash)'
        )
        
        conn.commit()
        logger.info("medicines 테이블 마이그레이션 완료")
    
    except sqlite3.OperationalError as e:
        # 이미 컬럼이 존재하는 경우 무시
        if "duplicate column name" in str(e):
            logger.info("item_hash 컬럼이 이미 존재합니다.")
        else:
            logger.error(f"마이그레이션 중 오류: {e}")
    
    finally:
        conn.close()


def create_config_file():
    """초기 설정 파일 생성"""
    config = configparser.ConfigParser()
    
    config['sqlite'] = {
        'db_path': 'medicine.db'  # SQLite 데이터베이스 파일 경로
    }
    
    config['mysql'] = {
        'host': 'localhost',
        'user': 'root',
        'password': '1234',
        'database': 'medicine_db'
    }
    
    with open('db_config.ini', 'w') as f:
        config.write(f)

if __name__ == "__main__":
    print("SQLite에서 MySQL로 약품 데이터 마이그레이션 도구")
    print("=" * 50)
    
    # 마이그레이션 실행
    migrate_sqlite_to_mysql()