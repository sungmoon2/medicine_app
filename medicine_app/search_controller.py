from flask import Blueprint, render_template, request, current_app
import pymysql
from pymysql.cursors import DictCursor
import math
import logging

# 블루프린트 생성
search_bp = Blueprint('search', __name__)

def get_db_connection():
    """데이터베이스 연결 생성 함수""" 
    return pymysql.connect(
        host=current_app.config.get('DB_HOST', 'localhost'),
        user=current_app.config.get('DB_USER', 'root'),
        password=current_app.config.get('DB_PASSWORD', ''),
        db=current_app.config.get('DB_NAME', 'medicine_db'),
        charset='utf8mb4',
        cursorclass=DictCursor
    )

@search_bp.route('/')
def index():
    """메인 검색 페이지"""
    return render_template('search_form.html')

@search_bp.route('/search')
def search():
    """검색 결과 페이지"""
    # 검색 매개변수 가져오기
    item_name = request.args.get('item_name', '')
    entp_name = request.args.get('entp_name', '')
    symptom = request.args.get('symptom', '')
    etc_otc_name = request.args.get('etc_otc_name', '')
    atpn_keyword = request.args.get('atpn_keyword', '')
    
    # 페이지네이션 매개변수
    page = int(request.args.get('page', 1))
    per_page = 12  # 페이지당 항목 수
    offset = (page - 1) * per_page
    
    # 검색 매개변수 딕셔너리
    search_params = {
        'item_name': item_name,
        'entp_name': entp_name,
        'symptom': symptom,
        'etc_otc_name': etc_otc_name,
        'atpn_keyword': atpn_keyword
    }
    
    # 데이터베이스 연결
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 검색 쿼리 구성
        query_parts = []
        params = []
        
        if item_name:
            query_parts.append("item_name LIKE %s")
            params.append(f"%{item_name}%")
        
        if entp_name:
            query_parts.append("entp_name LIKE %s")
            params.append(f"%{entp_name}%")
        
        if etc_otc_name:
            query_parts.append("etc_otc_name = %s")
            params.append(etc_otc_name)
        
        # 증상 검색은 여러 필드에서 검색
        if symptom:
            # efcy_qesitm(효능효과), atpn_qesitm(주의사항) 등의 필드에서 검색
            # 또는 각 증상에 맞는 특정 약품 분류를 검색할 수도 있음
            symptom_conditions = [
                "efcy_qesitm LIKE %s",
                "atpn_qesitm LIKE %s",
                "chart LIKE %s"
            ]
            query_parts.append("(" + " OR ".join(symptom_conditions) + ")")
            params.extend([f"%{symptom}%"] * len(symptom_conditions))
        
        if atpn_keyword:
            query_parts.append("atpn_qesitm LIKE %s")
            params.append(f"%{atpn_keyword}%")
        
        # 최종 쿼리 구성
        where_clause = " AND ".join(query_parts) if query_parts else "1=1"
        
        # 총 결과 개수 쿼리
        count_query = f"SELECT COUNT(*) as total FROM unified_medicines WHERE {where_clause}"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()['total']
        
        # 총 페이지 수 계산
        total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1
        
        # 결과가 있는 경우만 메인 쿼리 실행
        medicines = []
        if total_count > 0:
            # 메인 검색 쿼리
            query = f"""
            SELECT * FROM unified_medicines 
            WHERE {where_clause}
            ORDER BY item_name
            LIMIT %s OFFSET %s
            """
            cursor.execute(query, params + [per_page, offset])
            medicines = cursor.fetchall()
            
            # 디버깅용 로그
            current_app.logger.info(f"검색 쿼리: {query}")
            current_app.logger.info(f"검색 매개변수: {params + [per_page, offset]}")
            current_app.logger.info(f"결과 개수: {len(medicines)}")
        
        # 결과 렌더링
        return render_template(
            'search_results.html',
            medicines=medicines,
            search_params=search_params,
            current_page=page,
            pages=total_pages
        )
    
    except Exception as e:
        current_app.logger.error(f"검색 오류: {str(e)}")
        return render_template(
            'error.html', 
            error=f"검색 중 오류가 발생했습니다: {str(e)}"
        )
    
    finally:
        if 'conn' in locals():
            conn.close()

@search_bp.route('/medicine/<int:id>')
def medicine_detail(id):
    """의약품 상세 정보 페이지"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 의약품 정보 가져오기
        cursor.execute("SELECT * FROM unified_medicines WHERE id = %s", (id,))
        medicine = cursor.fetchone()
        
        if not medicine:
            return render_template('error.html', error="해당 의약품을 찾을 수 없습니다"), 404
        
        # 관련 의약품 가져오기 (같은 분류의 다른 의약품)
        related_query = """
        SELECT * FROM unified_medicines 
        WHERE class_name = %s AND id != %s
        ORDER BY item_name
        LIMIT 4
        """
        cursor.execute(related_query, (medicine.get('class_name', ''), id))
        related_medicines = cursor.fetchall()
        
        return render_template(
            'medicine_detail.html',
            medicine=medicine,
            related_medicines=related_medicines
        )
    
    except Exception as e:
        current_app.logger.error(f"의약품 상세 정보 오류: {str(e)}")
        return render_template(
            'error.html', 
            error=f"의약품 정보를 가져오는 중 오류가 발생했습니다: {str(e)}"
        )
    
    finally:
        if 'conn' in locals():
            conn.close()

@search_bp.route('/test_search')
def test_search():
    """검색 디버깅을 위한 테스트 라우트"""
    keyword = request.args.get('keyword', '타이레놀')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 디버깅용 직접 검색
        cursor.execute("SELECT * FROM unified_medicines WHERE item_name LIKE %s LIMIT 10", (f"%{keyword}%",))
        medicines = cursor.fetchall()
        
        # 테이블 목록 확인
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        table_list = [list(table.values())[0] for table in tables]
        
        # 통합 테이블 구조 확인
        table_name = "unified_medicines"
        if table_name in table_list:
            cursor.execute(f"DESCRIBE {table_name}")
            columns = cursor.fetchall()
            column_names = [col['Field'] for col in columns]
            
            # 샘플 레코드 확인
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
            sample = cursor.fetchone()
        else:
            columns = []
            column_names = []
            sample = None
        
        # 결과 반환
        return render_template(
            'search_results.html',
            medicines=medicines,
            search_params={'item_name': keyword},
            current_page=1,
            pages=1,
            debug_info={
                'tables': table_list,
                'columns': column_names,
                'sample': sample,
                'query': f"SELECT * FROM unified_medicines WHERE item_name LIKE '%{keyword}%' LIMIT 10",
                'result_count': len(medicines)
            }
        )
    
    except Exception as e:
        current_app.logger.error(f"테스트 검색 오류: {str(e)}")
        return str(e), 500
    
    finally:
        if 'conn' in locals():
            conn.close()

# 앱에 블루프린트 등록하는 방법: app.register_blueprint(search_bp)