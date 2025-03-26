import sqlite3
import mysql.connector
import os
from tqdm import tqdm
import logging
import sys
from datetime import datetime
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('migration')

def migrate_sqlite_to_mysql():
    """
    SQLite 데이터베이스에서 MySQL로 데이터를 마이그레이션합니다.
    설정은 .env 파일에서 로드됩니다.
    """
    # .env 파일 로드
    load_dotenv()
    
    # 환경 변수에서 설정 가져오기
    sqlite_db_path = os.environ.get("SQLITE_DB_PATH", "api_medicine.db")
    mysql_host = os.environ.get("MYSQL_HOST", "localhost")
    mysql_user = os.environ.get("MYSQL_USER", "")
    mysql_password = os.environ.get("MYSQL_PASSWORD", "")
    mysql_database = os.environ.get("MYSQL_DATABASE", "")
    mysql_port = int(os.environ.get("MYSQL_PORT", "3306"))
    clear_existing = os.environ.get("CLEAR_EXISTING_TABLE", "false").lower() == "true"
    
    # 필요한 설정이 있는지 확인
    if not mysql_user or not mysql_database:
        logger.error("MySQL 사용자 이름과 데이터베이스는 필수입니다. .env 파일을 확인하세요.")
        return
    
    # MySQL 설정
    mysql_config = {
        'host': mysql_host,
        'user': mysql_user,
        'password': mysql_password,
        'database': mysql_database,
        'port': mysql_port,
        'charset': 'utf8mb4',
        'use_unicode': True,
        'get_warnings': True
    }
    
    start_time = datetime.now()
    logger.info(f"마이그레이션 시작: {start_time}")
    logger.info(f"소스 SQLite DB: {sqlite_db_path}")
    logger.info(f"MySQL 데이터베이스: {mysql_database}@{mysql_host}")
    
    # SQLite 연결
    if not os.path.exists(sqlite_db_path):
        logger.error(f"SQLite 데이터베이스 파일이 존재하지 않습니다: {sqlite_db_path}")
        return
    
    try:
        sqlite_conn = sqlite3.connect(sqlite_db_path)
        sqlite_cursor = sqlite_conn.cursor()
        
        # 테이블명 확인
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = sqlite_cursor.fetchall()
        
        if not tables:
            logger.error("SQLite 데이터베이스에 테이블이 없습니다.")
            return
        
        logger.info(f"SQLite 데이터베이스 테이블: {[table[0] for table in tables]}")
        
        # 마이그레이션할 소스 테이블 결정 (기본값: api_medicine)
        source_table = 'api_medicine'
        if 'api_medicine' in [table[0] for table in tables]:
            source_table = 'api_medicine'
        
        logger.info(f"소스 테이블: {source_table}")
        
        # 데이터 확인
        sqlite_cursor.execute(f"SELECT COUNT(*) FROM {source_table}")
        count = sqlite_cursor.fetchone()[0]
        
        if count == 0:
            logger.warning(f"소스 테이블 {source_table}에 데이터가 없습니다.")
            return
        
        logger.info(f"마이그레이션할 레코드 수: {count}")
        
        # 컬럼 정보 가져오기
        sqlite_cursor.execute(f"PRAGMA table_info({source_table})")
        columns_info = sqlite_cursor.fetchall()
        column_names = [col[1] for col in columns_info]
        
        logger.info(f"소스 테이블의 컬럼: {column_names}")
        
        # MySQL 연결
        try:
            mysql_conn = mysql.connector.connect(**mysql_config)
            mysql_cursor = mysql_conn.cursor()
            
            # 목적지 테이블 존재 여부 확인
            mysql_cursor.execute(f"SHOW TABLES LIKE 'api_medicine'")
            table_exists = mysql_cursor.fetchone()
            
            if not table_exists:
                logger.warning("MySQL에 api_medicine 테이블이 없습니다. 테이블을 생성합니다.")
                
                # MySQL 테이블 생성 쿼리
                create_table_query = """
                CREATE TABLE api_medicine (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    item_seq VARCHAR(100),
                    item_name VARCHAR(500),
                    entp_seq VARCHAR(100),
                    entp_name VARCHAR(300),
                    chart TEXT,
                    item_image TEXT,
                    print_front VARCHAR(255),
                    print_back VARCHAR(255),
                    drug_shape VARCHAR(100),
                    color_class1 VARCHAR(100),
                    color_class2 VARCHAR(100),
                    line_front VARCHAR(100),
                    line_back VARCHAR(100),
                    leng_long VARCHAR(50),
                    leng_short VARCHAR(50),
                    thick VARCHAR(50),
                    img_regist_ts VARCHAR(100),
                    class_no VARCHAR(100),
                    class_name VARCHAR(300),
                    etc_otc_name VARCHAR(100),
                    item_permit_date VARCHAR(100),
                    form_code_name VARCHAR(200),
                    mark_code_front_anal TEXT,
                    mark_code_back_anal TEXT,
                    mark_code_front_img TEXT,
                    mark_code_back_img TEXT,
                    change_date VARCHAR(100),
                    mark_code_front VARCHAR(255),
                    mark_code_back VARCHAR(255),
                    item_eng_name VARCHAR(500),
                    edi_code VARCHAR(100),
                    atpn_qesitm TEXT,
                    intrc_qesitm TEXT,
                    se_qesitm TEXT,
                    deposit_method_qesitm TEXT,
                    efcy_qesitm TEXT,
                    use_method_qesitm TEXT,
                    atpn_warn_qesitm TEXT,
                    caution_details TEXT,
                    url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    data_hash VARCHAR(32)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
                """
                mysql_cursor.execute(create_table_query)
                
                # 인덱스 생성
                mysql_cursor.execute("CREATE INDEX idx_url ON api_medicine (url(255))")
                mysql_cursor.execute("CREATE INDEX idx_item_name ON api_medicine (item_name(255))")
                mysql_cursor.execute("CREATE INDEX idx_data_hash ON api_medicine (data_hash)")
                
                mysql_conn.commit()
                logger.info("MySQL에 api_medicine 테이블 생성 완료")
            elif clear_existing:
                # 기존 테이블 비우기 (환경 변수 설정에 따라)
                mysql_cursor.execute("TRUNCATE TABLE api_medicine")
                mysql_conn.commit()
                logger.info("MySQL의 api_medicine 테이블을 비웠습니다.")
            else:
                logger.info("기존 api_medicine 테이블을 유지합니다. 중복 데이터는 건너뛰게 됩니다.")
            
            # 데이터 마이그레이션
            batch_size = int(os.environ.get("BATCH_SIZE", "100"))  # 한 번에 처리할 레코드 수
            total_batches = (count + batch_size - 1) // batch_size
            
            with tqdm(total=count, desc="데이터 마이그레이션") as pbar:
                for offset in range(0, count, batch_size):
                    # SQLite에서 데이터 읽기
                    sqlite_cursor.execute(f"SELECT * FROM {source_table} LIMIT {batch_size} OFFSET {offset}")
                    records = sqlite_cursor.fetchall()
                    
                    if not records:
                        break
                    
                    # 컬럼 이름을 제외하고 id 필드는 제외 (MySQL에서 자동 생성)
                    mysql_columns = [col for col in column_names if col != 'id']
                    
                    # 인덱스 조정 (id 필드 제외)
                    record_indexes = [i for i, col in enumerate(column_names) if col != 'id']
                    
                    # 데이터 변환
                    mysql_records = []
                    for record in records:
                        # id를 제외한 필드만 선택
                        mysql_record = [record[i] for i in record_indexes]
                        mysql_records.append(mysql_record)
                    
                    if mysql_records:
                        # MySQL에 데이터 삽입
                        placeholders = ', '.join(['%s'] * len(mysql_columns))
                        columns_str = ', '.join(mysql_columns)
                        
                        # 중복 방지를 위한 INSERT IGNORE 사용 (선택적)
                        insert_query = f"INSERT IGNORE INTO api_medicine ({columns_str}) VALUES ({placeholders})"
                        
                        mysql_cursor.executemany(insert_query, mysql_records)
                        mysql_conn.commit()
                    
                    # 진행 상황 업데이트
                    pbar.update(len(records))
            
            # 결과 확인
            mysql_cursor.execute("SELECT COUNT(*) FROM api_medicine")
            mysql_count = mysql_cursor.fetchone()[0]
            
            logger.info(f"마이그레이션 완료: {mysql_count}/{count} 레코드 전송됨")
            
            end_time = datetime.now()
            logger.info(f"마이그레이션 종료: {end_time}")
            logger.info(f"소요 시간: {end_time - start_time}")
            
        except mysql.connector.Error as err:
            logger.error(f"MySQL 오류: {err}")
        finally:
            if 'mysql_conn' in locals() and mysql_conn.is_connected():
                mysql_cursor.close()
                mysql_conn.close()
                logger.info("MySQL 연결 종료")
                
    except sqlite3.Error as err:
        logger.error(f"SQLite 오류: {err}")
    finally:
        if 'sqlite_conn' in locals():
            sqlite_conn.close()
            logger.info("SQLite 연결 종료")

if __name__ == "__main__":
    # .env 파일이 있는지 확인
    if not os.path.exists('.env'):
        # .env 파일 예시 생성
        with open('.env.example', 'w') as f:
            f.write("""# SQLite 데이터베이스 설정
SQLITE_DB_PATH=api_medicine.db

# MySQL 데이터베이스 설정
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=your_database

# 마이그레이션 설정
CLEAR_EXISTING_TABLE=false
BATCH_SIZE=100
""")
        logger.error(".env 파일이 없습니다. .env.example 파일을 참고하여 .env 파일을 생성하세요.")
        sys.exit(1)
    
    # 마이그레이션 실행
    migrate_sqlite_to_mysql()