import pymysql
import logging
import os
import sys
from dotenv import load_dotenv
import colorama
from colorama import Fore, Style
import time

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='data_migration.log',
    encoding='utf-8'
)
logger = logging.getLogger('data_migration')

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

def create_integrated_table():
    """통합 약품 정보 테이블 생성"""
    conn = db_connection()
    logger.info(f"{Fore.GREEN}통합 테이블 생성 시작...{Style.RESET_ALL}")
    
    try:
        with conn.cursor() as cursor:
            # 통합 테이블 생성 SQL
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS integrated_drug_info (
                id INT AUTO_INCREMENT PRIMARY KEY,
                medicine_id INT COMMENT '약품 기본 ID (medicine_usage 테이블 참조)',
                
                -- 기본 식별자 (각 API에서 가져온 식별자)
                item_seq VARCHAR(100) COMMENT '품목일련번호(drug_identification)',
                gnl_nm_cd VARCHAR(9) COMMENT '일반명코드(drug_component_efficacy)',
                cpnt_cd VARCHAR(100) COMMENT '성분코드(drug_component_dosage)',
                edi_code VARCHAR(100) COMMENT '보험코드',
                
                -- 기본 정보
                item_name VARCHAR(500) COMMENT '품목명(한글)',
                item_eng_name VARCHAR(500) COMMENT '품목명(영문)',
                entp_name VARCHAR(300) COMMENT '제조/수입사',
                
                -- 분류 정보
                class_no VARCHAR(100) COMMENT '분류번호',
                class_name VARCHAR(300) COMMENT '분류명',
                etc_otc_name VARCHAR(100) COMMENT '전문/일반',
                meft_div_no VARCHAR(3) COMMENT '약효분류번호',
                
                -- 성분 정보 
                drug_cpnt_kor_nm VARCHAR(500) COMMENT '주성분명(한글)',
                drug_cpnt_eng_nm VARCHAR(500) COMMENT '주성분명(영문)',
                gnl_nm VARCHAR(400) COMMENT '일반명',
                
                -- 용량 정보
                iqty_txt VARCHAR(1000) COMMENT '함량내용',
                day_max_dosg_qy DECIMAL(20,6) COMMENT '1일최대투여량',
                day_max_dosg_qy_unit VARCHAR(100) COMMENT '투여단위',
                
                -- 외형 정보
                drug_shape VARCHAR(100) COMMENT '의약품모양',
                color_class1 VARCHAR(100) COMMENT '색깔(앞)',
                color_class2 VARCHAR(100) COMMENT '색깔(뒤)',
                print_front VARCHAR(255) COMMENT '표시(앞)',
                print_back VARCHAR(255) COMMENT '표시(뒤)',
                leng_long VARCHAR(50) COMMENT '크기(장축)',
                leng_short VARCHAR(50) COMMENT '크기(단축)',
                
                -- 이미지 정보
                item_image TEXT COMMENT '제품이미지',
                mark_code_front_img TEXT COMMENT '마크이미지(앞)',
                mark_code_back_img TEXT COMMENT '마크이미지(뒤)',
                
                -- 제형 정보
                form_code_name VARCHAR(200) COMMENT '제형코드이름',
                foml_nm VARCHAR(300) COMMENT '제형명',
                fomn_tp_nm VARCHAR(100) COMMENT '제형구분명',
                
                -- 투여 정보
                injc_pth_nm VARCHAR(100) COMMENT '투여경로명',
                dosage_route_code VARCHAR(100) COMMENT '투여경로코드',
                
                -- 기타 상세 정보
                chart TEXT COMMENT '성상(외관 및 성질에 대한 설명)',
                
                -- medicine_usage 테이블에서 추가된 필드
                efcy_qesitm TEXT COMMENT '효능효과',
                use_method_qesitm TEXT COMMENT '사용법',
                atpn_warn_qesitm TEXT COMMENT '주의사항경고',
                atpn_qesitm TEXT COMMENT '주의사항',
                intrc_qesitm TEXT COMMENT '상호작용',
                se_qesitm TEXT COMMENT '부작용',
                deposit_method_qesitm TEXT COMMENT '보관법',
                
                -- 기존 필드
                usage_instructions TEXT COMMENT '용법용량 설명',
                side_effects TEXT COMMENT '부작용 정보',
                precautions TEXT COMMENT '주의사항',
                interactions TEXT COMMENT '상호작용',
                
                -- 메타 정보
                item_permit_date VARCHAR(100) COMMENT '품목허가일자',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '데이터 생성일',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '데이터 수정일',
                
                -- 인덱스 추가
                INDEX idx_medicine_id (medicine_id),
                INDEX idx_item_seq (item_seq),
                INDEX idx_item_name (item_name(255)),
                INDEX idx_gnl_nm_cd (gnl_nm_cd),
                INDEX idx_cpnt_cd (cpnt_cd),
                INDEX idx_edi_code (edi_code),
                INDEX idx_drug_shape (drug_shape),
                INDEX idx_class_no (class_no),
                INDEX idx_etc_otc (etc_otc_name),
                INDEX idx_drug_cpnt_kor_nm (drug_cpnt_kor_nm(255)),
                
                -- 전문검색용 전체텍스트 인덱스
                FULLTEXT idx_fulltext_search (
                    item_name, item_eng_name, drug_cpnt_kor_nm, chart, 
                    efcy_qesitm, use_method_qesitm, atpn_warn_qesitm, atpn_qesitm,
                    intrc_qesitm, se_qesitm, deposit_method_qesitm
                )
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='통합 약품 정보'
            """)
            
            conn.commit()
            logger.info(f"{Fore.BLUE}통합 테이블 생성 완료{Style.RESET_ALL}")
    except Exception as e:
        logger.error(f"통합 테이블 생성 오류: {e}")
        conn.rollback()
    finally:
        conn.close()

def migrate_data():
    """기존 테이블에서 통합 테이블로 데이터 마이그레이션"""
    conn = db_connection()
    logger.info(f"{Fore.GREEN}데이터 마이그레이션 시작...{Style.RESET_ALL}")
    
    try:
        with conn.cursor() as cursor:
            # 1. 기존 테이블의 데이터 통계 확인
            cursor.execute("SELECT COUNT(*) as cnt FROM drug_identification")
            id_count = cursor.fetchone()['cnt']
            
            cursor.execute("SELECT COUNT(*) as cnt FROM drug_component_efficacy")
            eff_count = cursor.fetchone()['cnt']
            
            cursor.execute("SELECT COUNT(*) as cnt FROM drug_component_dosage")
            dos_count = cursor.fetchone()['cnt']
            
            logger.info(f"약품 낱알식별 정보: {id_count}개 항목")
            logger.info(f"약품 성분약효 정보: {eff_count}개 항목")
            logger.info(f"약품 성분별 최대투여량 정보: {dos_count}개 항목")
            
            # 2. 테이블 비우기 (마이그레이션 재실행 시 데이터 중복 방지)
            cursor.execute("TRUNCATE TABLE integrated_drug_info")
            logger.info("통합 테이블 초기화 완료")
            
            # 3. drug_relation 테이블을 기준으로 통합 마이그레이션
            total_migrated = 0
            batch_size = 1000
            offset = 0
            
            while True:
                # drug_relation 테이블에서 배치 단위로 데이터 가져오기
                cursor.execute(f"""
                SELECT * FROM drug_relation
                LIMIT {batch_size} OFFSET {offset}
                """)
                
                relations = cursor.fetchall()
                if not relations:
                    break
                
                for relation in relations:
                    item_seq = relation.get('item_seq')
                    gnl_nm_cd = relation.get('gnl_nm_cd')
                    cpnt_cd = relation.get('cpnt_cd')
                    
                    # 통합 데이터 구성을 위한 딕셔너리
                    integrated_data = {
                        'item_seq': item_seq,
                        'gnl_nm_cd': gnl_nm_cd,
                        'cpnt_cd': cpnt_cd
                    }
                    
                    # drug_identification 테이블에서 데이터 가져오기
                    if item_seq:
                        cursor.execute("SELECT * FROM drug_identification WHERE item_seq = %s", (item_seq,))
                        ident_data = cursor.fetchone()
                        if ident_data:
                            # 필요한 항목 통합 데이터에 추가
                            for field in ['item_name', 'item_eng_name', 'entp_name', 'class_no', 'class_name', 
                                         'etc_otc_name', 'drug_shape', 'color_class1', 'color_class2', 
                                         'print_front', 'print_back', 'leng_long', 'leng_short', 
                                         'item_image', 'mark_code_front_img', 'mark_code_back_img',
                                         'form_code_name', 'chart', 'item_permit_date', 'edi_code']:
                                if field in ident_data and ident_data[field]:
                                    integrated_data[field] = ident_data[field]
                    
                    # drug_component_efficacy 테이블에서 데이터 가져오기
                    if gnl_nm_cd:
                        cursor.execute("SELECT * FROM drug_component_efficacy WHERE gnl_nm_cd = %s", (gnl_nm_cd,))
                        efficacy_data = cursor.fetchone()
                        if efficacy_data:
                            # 필요한 항목 통합 데이터에 추가
                            for field in ['gnl_nm', 'meft_div_no', 'fomn_tp_nm', 'injc_pth_nm', 'iqty_txt']:
                                if field in efficacy_data and efficacy_data[field]:
                                    integrated_data[field] = efficacy_data[field]
                    
                    # drug_component_dosage 테이블에서 데이터 가져오기
                    if cpnt_cd:
                        cursor.execute("SELECT * FROM drug_component_dosage WHERE cpnt_cd = %s", (cpnt_cd,))
                        dosage_data = cursor.fetchone()
                        if dosage_data:
                            # 필요한 항목 통합 데이터에 추가
                            for field in ['drug_cpnt_kor_nm', 'drug_cpnt_eng_nm', 'foml_nm', 
                                         'dosage_route_code', 'day_max_dosg_qy', 'day_max_dosg_qy_unit']:
                                if field in dosage_data and dosage_data[field]:
                                    integrated_data[field] = dosage_data[field]
                    
                    # 데이터가 최소한 하나의 식별자를 가지고 있을 때만 삽입
                    if integrated_data.get('item_seq') or integrated_data.get('gnl_nm_cd') or integrated_data.get('cpnt_cd'):
                        # 필드와 값 준비
                        fields = []
                        values = []
                        placeholders = []
                        
                        for field, value in integrated_data.items():
                            if value is not None:
                                fields.append(field)
                                values.append(value)
                                placeholders.append('%s')
                        
                        # 데이터 삽입
                        if fields:
                            insert_sql = f"INSERT INTO integrated_drug_info ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
                            cursor.execute(insert_sql, values)
                            total_migrated += 1
                            
                            # 진행 상황 로깅
                            if total_migrated % 100 == 0:
                                logger.info(f"{Fore.BLUE}데이터 마이그레이션 진행 중: {total_migrated}개 항목 처리{Style.RESET_ALL}")
                
                # 다음 배치로 이동
                offset += batch_size
                conn.commit()
            
            # 4. 추가로 매핑되지 않은 drug_identification 데이터 처리
            cursor.execute("""
            INSERT INTO integrated_drug_info (item_seq, item_name, item_eng_name, entp_name, class_no, 
                class_name, etc_otc_name, drug_shape, color_class1, color_class2, print_front, 
                print_back, leng_long, leng_short, item_image, mark_code_front_img, mark_code_back_img,
                form_code_name, chart, item_permit_date, edi_code)
            SELECT d.item_seq, d.item_name, d.item_eng_name, d.entp_name, d.class_no, 
                d.class_name, d.etc_otc_name, d.drug_shape, d.color_class1, d.color_class2, d.print_front, 
                d.print_back, d.leng_long, d.leng_short, d.item_image, d.mark_code_front_img, d.mark_code_back_img,
                d.form_code_name, d.chart, d.item_permit_date, d.edi_code
            FROM drug_identification d
            LEFT JOIN integrated_drug_info i ON i.item_seq = d.item_seq
            WHERE i.id IS NULL AND d.item_seq IS NOT NULL
            """)
            added_id = cursor.rowcount
            logger.info(f"추가 약품 식별 정보: {added_id}개 항목 마이그레이션")
            
            # 5. 추가로 매핑되지 않은 drug_component_efficacy 데이터 처리
            cursor.execute("""
            INSERT INTO integrated_drug_info (gnl_nm_cd, gnl_nm, meft_div_no, fomn_tp_nm, injc_pth_nm, iqty_txt)
            SELECT e.gnl_nm_cd, e.gnl_nm, e.meft_div_no, e.fomn_tp_nm, e.injc_pth_nm, e.iqty_txt
            FROM drug_component_efficacy e
            LEFT JOIN integrated_drug_info i ON i.gnl_nm_cd = e.gnl_nm_cd
            WHERE i.id IS NULL AND e.gnl_nm_cd IS NOT NULL
            """)
            added_eff = cursor.rowcount
            logger.info(f"추가 약품 약효 정보: {added_eff}개 항목 마이그레이션")
            
            # 6. 추가로 매핑되지 않은 drug_component_dosage 데이터 처리
            cursor.execute("""
            INSERT INTO integrated_drug_info (cpnt_cd, drug_cpnt_kor_nm, drug_cpnt_eng_nm, foml_nm, 
                                             dosage_route_code, day_max_dosg_qy, day_max_dosg_qy_unit)
            SELECT d.cpnt_cd, d.drug_cpnt_kor_nm, d.drug_cpnt_eng_nm, d.foml_nm, 
                   d.dosage_route_code, d.day_max_dosg_qy, d.day_max_dosg_qy_unit
            FROM drug_component_dosage d
            LEFT JOIN integrated_drug_info i ON i.cpnt_cd = d.cpnt_cd
            WHERE i.id IS NULL AND d.cpnt_cd IS NOT NULL
            """)
            added_dos = cursor.rowcount
            logger.info(f"추가 약품 용량 정보: {added_dos}개 항목 마이그레이션")
            
            conn.commit()
            
            # 7. 약품 사용법 정보(medicine_usage) 데이터 통합
            logger.info(f"{Fore.YELLOW}약품 사용법 정보(medicine_usage) 마이그레이션 시작{Style.RESET_ALL}")
            
            # medicines 테이블과 medicine_usage 테이블이 있는지 확인
            cursor.execute("SHOW TABLES LIKE 'medicines'")
            has_medicines = cursor.fetchone() is not None
            
            cursor.execute("SHOW TABLES LIKE 'medicine_usage'")
            has_medicine_usage = cursor.fetchone() is not None
            
            if has_medicines and has_medicine_usage:
                # 두 테이블 간의 조인 후 통합 테이블 업데이트
                cursor.execute("""
                SELECT COUNT(*) as cnt FROM medicines
                """)
                medicines_count = cursor.fetchone()['cnt']
                
                cursor.execute("""
                SELECT COUNT(*) as cnt FROM medicine_usage
                """)
                usage_count = cursor.fetchone()['cnt']
                
                logger.info(f"기존 테이블 데이터: medicines {medicines_count}개, medicine_usage {usage_count}개")
                
                # medicine_usage 테이블의 필드 정보 가져오기
                cursor.execute("SHOW COLUMNS FROM medicine_usage")
                usage_fields = [row['Field'] for row in cursor.fetchall()]
                
                # 존재하는 필드만 포함시키기 위한 필드 매핑
                usage_field_mapping = {
                    'medicine_id': 'medicine_id',
                    'efcy_qesitm': 'efcy_qesitm',
                    'use_method_qesitm': 'use_method_qesitm',
                    'atpn_warn_qesitm': 'atpn_warn_qesitm',
                    'atpn_qesitm': 'atpn_qesitm',
                    'intrc_qesitm': 'intrc_qesitm',
                    'se_qesitm': 'se_qesitm',
                    'deposit_method_qesitm': 'deposit_method_qesitm'
                }
                
                # 존재하는 필드만 필터링
                valid_usage_fields = [f for f in usage_field_mapping.keys() if f in usage_fields]
                
                if valid_usage_fields:
                    # medicines 테이블의 데이터가 이미 integrated_drug_info에 있는지 확인하고 연결
                    cursor.execute("""
                    SELECT m.id, m.item_seq, m.item_name 
                    FROM medicines m
                    LEFT JOIN integrated_drug_info i ON i.item_seq = m.item_seq
                    WHERE i.id IS NULL
                    LIMIT 10
                    """)
                    
                    unlinked_medicines = cursor.fetchall()
                    if unlinked_medicines:
                        logger.info(f"발견된 연결되지 않은 medicines 데이터: {len(unlinked_medicines)}개 샘플")
                        for med in unlinked_medicines:
                            logger.info(f"  - ID: {med['id']}, item_seq: {med['item_seq']}, item_name: {med['item_name']}")
                    
                    # 통합 테이블 업데이트 - medicine_usage 데이터 통합
                    update_fields = ", ".join([f"{f} = mu.{f}" for f in valid_usage_fields if f != 'medicine_id'])
                    if update_fields:
                        cursor.execute(f"""
                        UPDATE integrated_drug_info i
                        JOIN medicines m ON i.item_seq = m.item_seq
                        JOIN medicine_usage mu ON m.id = mu.medicine_id
                        SET i.medicine_id = mu.medicine_id, {update_fields}
                        """)
                        
                        updated_count = cursor.rowcount
                        logger.info(f"약품 사용법 정보 업데이트: {updated_count}개 항목")
                        
                        # 아직 연결되지 않은 medicine_usage 데이터 삽입
                        cursor.execute(f"""
                        INSERT INTO integrated_drug_info (medicine_id, {', '.join(valid_usage_fields[1:])})
                        SELECT mu.medicine_id, {', '.join(['mu.' + f for f in valid_usage_fields[1:]])}
                        FROM medicine_usage mu
                        LEFT JOIN integrated_drug_info i ON i.medicine_id = mu.medicine_id
                        WHERE i.id IS NULL
                        """)
                        
                        inserted_count = cursor.rowcount
                        logger.info(f"추가 약품 사용법 정보 삽입: {inserted_count}개 항목")
                        
                        conn.commit()
                else:
                    logger.warning("medicine_usage 테이블에 유효한 필드가 없습니다")
            else:
                logger.info("medicines 또는 medicine_usage 테이블이 없습니다")
            
            # 8. 통계 업데이트
            cursor.execute("SELECT COUNT(*) as cnt FROM integrated_drug_info")
            integrated_count = cursor.fetchone()['cnt']
            
            logger.info(f"{Fore.GREEN}데이터 마이그레이션 완료: 총 {integrated_count}개 항목{Style.RESET_ALL}")
            logger.info(f"기존 데이터: 식별 {id_count}개, 약효 {eff_count}개, 용량 {dos_count}개")
            logger.info(f"추가 마이그레이션: 식별 {added_id}개, 약효 {added_eff}개, 용량 {added_dos}개")
            
    except Exception as e:
        logger.error(f"데이터 마이그레이션 오류: {e}")
        conn.rollback()
    finally:
        conn.close()

def main():
    """메인 함수"""
    logger.info(f"{Fore.CYAN}약품 데이터 통합 마이그레이션 시작{Style.RESET_ALL}")
    
    # 1. 통합 테이블 생성
    create_integrated_table()
    
    # 2. 데이터 마이그레이션
    migrate_data()
    
    logger.info(f"{Fore.CYAN}약품 데이터 통합 마이그레이션 완료{Style.RESET_ALL}")

if __name__ == "__main__":
    print("약품 데이터 통합 마이그레이션 시작")
    try:
        main()
        print("약품 데이터 통합 마이그레이션 완료")
    except Exception as e:
        print(f"오류 발생: {e}")
        logger.error(f"오류 발생: {e}", exc_info=True)