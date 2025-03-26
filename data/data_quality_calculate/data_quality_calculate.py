import os
import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from tabulate import tabulate
import logging
import time
import json
from collections import defaultdict

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_quality_assessment.log'),
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

def check_table_existence(cursor, table_name):
    """테이블 존재 여부 확인"""
    cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
    return cursor.fetchone() is not None

def define_column_weights():
    """검색 및 표시에 중요한 컬럼들의 가중치 정의"""
    
    # 1순위 (필수 검색 요소): 높은 가중치
    # 2순위 (물리적 특성 검색): 중간 가중치
    # 3순위 (상세 정보 검색): 낮은 가중치
    
    column_weights = {
        # 1순위: 필수 검색 요소 (각 10점)
        'item_name': 10,         # 제품명
        'entp_name': 10,         # 제조사
        'class_name': 10,        # 분류명
        'efcy_qesitm': 10,       # 효능효과
        
        # 2순위: 물리적 특성 검색 (각 7점)
        'drug_shape': 7,         # 모양
        'color_class1': 7,       # 색상
        'form_code_name': 7,     # 제형
        'print_front': 7,        # 각인/표시(앞)
        'print_back': 7,         # 각인/표시(뒤)
        
        # 3순위: 상세 정보 검색 (각 5점)
        'chart': 5,              # 성상
        'se_qesitm': 5,          # 부작용
        'atpn_qesitm': 5,        # 주의사항
        'use_method_qesitm': 5,  # 용법용량
        'item_eng_name': 5,      # 영문 제품명
        
        # 추가 정보 (각 3점)
        'deposit_method_qesitm': 3,  # 보관방법
        'intrc_qesitm': 3,           # 상호작용
        'atpn_warn_qesitm': 3,       # 경고
        'class_no': 3,               # 분류번호
        'item_seq': 3,               # 품목기준코드
        'edi_code': 3,               # 보험코드
        
        # 물리적 특성 추가 정보 (각 2점)
        'drug_shape_code': 2,    # 모양 코드
        'color_class2': 2,       # 부색상
        'leng_long': 2,          # 길이
        'leng_short': 2,         # 너비
        'thick': 2,              # 두께
        'weight': 2,             # 무게
        'line_front': 2,         # 앞면 분할선
        'line_back': 2,          # 뒷면 분할선
        'mark_code_front': 2,    # 앞면 마크코드
        'mark_code_back': 2,     # 뒷면 마크코드
        'etc_otc_name': 2,       # 전문/일반
    }
    
    return column_weights

def get_max_possible_score(column_weights):
    """최대 가능 점수 계산"""
    return sum(column_weights.values())

def calculate_score_threshold(column_weights):
    """최소 필요 점수 임계치 계산"""
    # 1순위 컬럼 합계 (모든 필수 요소)
    priority1_sum = column_weights['item_name'] + column_weights['entp_name'] + \
                   column_weights['class_name'] + column_weights['efcy_qesitm']
    
    # 2순위 컬럼 중 일부 합계 (중요 물리적 특성)
    priority2_partial = column_weights['drug_shape'] + column_weights['color_class1']
    
    # 3순위 컬럼 중 일부 합계 (주요 상세 정보)
    priority3_partial = column_weights['chart'] + column_weights['se_qesitm']
    
    # 임계치: 1순위 모두 + 2순위 일부 + 3순위 일부
    threshold = priority1_sum + priority2_partial + priority3_partial
    
    # 임계점수 그룹화
    thresholds = {
        'excellent': int(get_max_possible_score(column_weights) * 0.9),  # 90% 이상
        'good': int(get_max_possible_score(column_weights) * 0.75),      # 75% 이상
        'average': int(get_max_possible_score(column_weights) * 0.6),    # 60% 이상
        'minimum': threshold                                            # 기본 임계치
    }
    
    return thresholds

def get_column_list(cursor, table_name):
    """테이블 컬럼 목록 가져오기"""
    cursor.execute(f"SHOW COLUMNS FROM {table_name}")
    columns = [row['Field'] for row in cursor.fetchall()]
    return columns

def calculate_quality_scores(cursor, table_name, column_weights, batch_size=1000):
    """데이터 품질 점수 계산"""
    # 테이블 컬럼 확인
    table_columns = get_column_list(cursor, table_name)
    
    # 테이블에 있는 가중치 컬럼 필터링
    valid_columns = [col for col in column_weights.keys() if col in table_columns]
    
    # 레코드 총 개수 파악
    cursor.execute(f"SELECT COUNT(*) as total FROM {table_name}")
    total_records = cursor.fetchone()['total']
    logger.info(f"{table_name} 테이블에 총 {total_records}개 레코드가 있습니다.")
    
    # 결과 저장 변수
    all_scores = []
    quality_stats = defaultdict(int)
    processed = 0
    start_time = time.time()
    
    # 점수 임계치 설정
    thresholds = calculate_score_threshold(column_weights)
    logger.info(f"점수 임계치 - 최우수: {thresholds['excellent']}, 우수: {thresholds['good']}, "
                f"평균: {thresholds['average']}, 최소: {thresholds['minimum']}")
    
    # 각 레코드 점수 계산 (배치 처리)
    for offset in range(0, total_records, batch_size):
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {batch_size} OFFSET {offset}")
        records = cursor.fetchall()
        
        for record in records:
            # 빈 값이 아닌 컬럼에 대해서만 점수 부여
            record_score = 0
            non_empty_columns = []
            
            for column in valid_columns:
                # NULL이 아니고 빈 문자열이 아닌 경우에만 점수 추가
                if record[column] is not None and (not isinstance(record[column], str) or record[column].strip()):
                    record_score += column_weights[column]
                    non_empty_columns.append(column)
            
            # 점수에 따른 품질 등급 분류
            if record_score >= thresholds['excellent']:
                quality_level = 'excellent'
            elif record_score >= thresholds['good']:
                quality_level = 'good'
            elif record_score >= thresholds['average']:
                quality_level = 'average'
            elif record_score >= thresholds['minimum']:
                quality_level = 'minimum'
            else:
                quality_level = 'poor'
            
            quality_stats[quality_level] += 1
            
            # 레코드 정보와 점수 저장
            all_scores.append({
                'id': record.get('id'),
                'item_seq': record.get('item_seq'),
                'item_name': record.get('item_name'),
                'score': record_score,
                'quality_level': quality_level,
                'filled_columns': len(non_empty_columns),
                'total_columns': len(valid_columns),
                'percentage_filled': round(len(non_empty_columns) / len(valid_columns) * 100, 2)
            })
        
        processed += len(records)
        elapsed = time.time() - start_time
        records_per_sec = processed / elapsed if elapsed > 0 else 0
        eta = (total_records - processed) / records_per_sec if records_per_sec > 0 else 0
        
        logger.info(f"처리 중... {processed}/{total_records} ({processed/total_records*100:.2f}%) "
                   f"- {records_per_sec:.1f} 레코드/초 - 남은 시간: {eta:.1f}초")
    
    # 등급별 통계
    logger.info("\n품질 등급 통계:")
    for level, count in quality_stats.items():
        percentage = count / total_records * 100
        logger.info(f"- {level}: {count}개 ({percentage:.2f}%)")
    
    return all_scores, quality_stats

def analyze_empty_fields(cursor, table_name, column_weights):
    """각 컬럼별 빈 값 비율 분석"""
    # 테이블 컬럼 확인
    table_columns = get_column_list(cursor, table_name)
    
    # 테이블에 있는 가중치 컬럼 필터링
    valid_columns = [col for col in column_weights.keys() if col in table_columns]
    
    # 테이블 총 레코드 수 파악
    cursor.execute(f"SELECT COUNT(*) as total FROM {table_name}")
    total_records = cursor.fetchone()['total']
    
    # 각 컬럼별 비어있지 않은 레코드 수 계산
    column_stats = []
    
    for column in valid_columns:
        cursor.execute(f"""
        SELECT COUNT(*) as count 
        FROM {table_name} 
        WHERE {column} IS NOT NULL AND ({column} != '' OR NOT {column} REGEXP '^\\\\s*$')
        """)
        non_empty_count = cursor.fetchone()['count']
        filled_percentage = (non_empty_count / total_records * 100) if total_records > 0 else 0
        
        column_stats.append({
            'column': column,
            'non_empty_count': non_empty_count,
            'filled_percentage': round(filled_percentage, 2),
            'weight': column_weights[column],
            'importance': 'High' if column_weights[column] >= 8 else ('Medium' if column_weights[column] >= 5 else 'Low')
        })
    
    # 중요도(가중치) 및 채워진 비율 기준으로 정렬
    column_stats.sort(key=lambda x: (-x['weight'], -x['filled_percentage']))
    
    return column_stats

def save_results_to_file(all_scores, column_stats, quality_stats, max_score, thresholds):
    """분석 결과를 파일로 저장"""
    # 결과 디렉토리 생성
    os.makedirs('results', exist_ok=True)
    
    # 1. 전체 품질 점수 저장 (상위 1000개)
    df_scores = pd.DataFrame(all_scores)
    df_scores.sort_values(by='score', ascending=False, inplace=True)
    df_scores.head(1000).to_csv('results/quality_scores_top1000.csv', index=False)
    
    # 2. 컬럼별 통계 저장
    df_columns = pd.DataFrame(column_stats)
    df_columns.to_csv('results/column_statistics.csv', index=False)
    
    # 3. 품질 등급 통계 저장
    quality_data = []
    for level, count in quality_stats.items():
        quality_data.append({
            'quality_level': level,
            'count': count,
            'percentage': count / len(all_scores) * 100 if all_scores else 0
        })
    df_quality = pd.DataFrame(quality_data)
    df_quality.to_csv('results/quality_level_statistics.csv', index=False)
    
    # 4. 요약 정보 JSON 저장
    summary = {
        'total_records': len(all_scores),
        'max_possible_score': max_score,
        'thresholds': thresholds,
        'quality_distribution': {level: count for level, count in quality_stats.items()},
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }
    
    with open('results/analysis_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    logger.info(f"분석 결과가 'results' 디렉토리에 저장되었습니다.")

def print_quality_summary(all_scores, column_stats, quality_stats, max_score, thresholds):
    """품질 평가 요약 출력"""
    # 상위 10개 고품질 레코드 표시
    top_records = sorted(all_scores, key=lambda x: -x['score'])[:10]
    
    logger.info("\n=== 품질 평가 요약 ===")
    logger.info(f"총 {len(all_scores)}개 레코드 평가 완료")
    logger.info(f"최대 가능 점수: {max_score}")
    logger.info(f"점수 임계치 - 최우수: {thresholds['excellent']}, 우수: {thresholds['good']}, "
               f"평균: {thresholds['average']}, 최소: {thresholds['minimum']}")
    
    logger.info("\n--- 품질 등급 분포 ---")
    for level, count in quality_stats.items():
        percentage = count / len(all_scores) * 100 if all_scores else 0
        logger.info(f"{level}: {count}개 ({percentage:.2f}%)")
    
    logger.info("\n--- 상위 10개 고품질 레코드 ---")
    df_top = pd.DataFrame(top_records)
    logger.info("\n" + tabulate(df_top, headers='keys', tablefmt='psql'))
    
    logger.info("\n--- 중요 컬럼 통계 (상위 15개) ---")
    df_cols = pd.DataFrame(column_stats[:15])
    logger.info("\n" + tabulate(df_cols, headers='keys', tablefmt='psql'))

def main():
    """메인 함수"""
    logger.info("의약품 데이터 품질 평가 시작")
    
    # 가중치 정의
    column_weights = define_column_weights()
    
    # 최대 가능 점수 및 임계치 계산
    max_score = get_max_possible_score(column_weights)
    thresholds = calculate_score_threshold(column_weights)
    
    # 데이터베이스 연결
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 테이블 존재 확인
            table_name = "integrated_drug_info"  # 대상 테이블
            if not check_table_existence(cursor, table_name):
                logger.error(f"{table_name} 테이블이 존재하지 않습니다.")
                return
            
            # 1. 컬럼별 비어있는 데이터 분석
            logger.info(f"{table_name} 테이블의 컬럼별 데이터 완성도 분석 중...")
            column_stats = analyze_empty_fields(cursor, table_name, column_weights)
            
            # 2. 개별 레코드 품질 점수 계산
            logger.info(f"{table_name} 테이블의 레코드별 품질 점수 계산 중...")
            all_scores, quality_stats = calculate_quality_scores(cursor, table_name, column_weights)
            
            # 3. 품질 평가 요약 출력
            print_quality_summary(all_scores, column_stats, quality_stats, max_score, thresholds)
            
            # 4. 결과 저장
            save_results_to_file(all_scores, column_stats, quality_stats, max_score, thresholds)
            
    except Exception as e:
        logger.error(f"오류 발생: {str(e)}")
    finally:
        conn.close()
        logger.info("데이터베이스 연결 종료")
    
    logger.info("의약품 데이터 품질 평가 완료")

if __name__ == "__main__":
    main()