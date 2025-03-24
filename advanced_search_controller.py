from flask import Blueprint, render_template, request, current_app
import pymysql
from pymysql.cursors import DictCursor
import math
import logging

# 블루프린트 생성
advanced_search_bp = Blueprint('advanced_search', __name__)

def get_db_connection():
    """데이터베이스 연결 생성 함수"""
    return pymysql.connect(
        host=current_app.config.get('DB_HOST', 'localhost'),
        user=current_app.config.get('DB_USER', 'root'),
        password=current_app.config.get('DB_PASSWORD', '1234'), #1234 입력하니 오류 해결됨
        db=current_app.config.get('DB_NAME', 'medicine_db'),
        charset='utf8mb4',
        cursorclass=DictCursor,
        auth_plugin_map={'mysql_native_password': 'mysql_native_password'}
    )

@advanced_search_bp.route('/')
def index():
    """고급 검색 페이지"""
    return render_template('advanced_search.html')

@advanced_search_bp.route('/search')
def advanced_search():
    """고급 검색 결과 페이지"""
    # 검색 파라미터 가져오기
    search_params = {
        'item_name': request.args.get('item_name', ''),
        'entp_name': request.args.get('entp_name', ''),
        'drug_shape': request.args.getlist('drug_shape'),
        'colors': request.args.getlist('color'),
        'print_front': request.args.get('print_front', ''),
        'print_back': request.args.get('print_back', ''),
    }
    
    # 페이지네이션 파라미터
    page = int(request.args.get('page', 1))
    per_page = 12
    offset = (page - 1) * per_page
    
    # 데이터베이스 연결
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 검색 쿼리 구성
        query_parts = []
        params = []
        
        # 제품명 검색 (부분 검색)
        if search_params['item_name']:
            query_parts.append("(item_name LIKE %s OR item_eng_name LIKE %s)")
            search_name = f"%{search_params['item_name']}%"
            params.extend([search_name, search_name])
        
        # 제조사 검색 (부분 검색)
        if search_params['entp_name']:
            query_parts.append("entp_name LIKE %s")
            params.append(f"%{search_params['entp_name']}%")
        
        # 모양 검색 (복수 선택 가능)
        if search_params['drug_shape'] and 'all' not in search_params['drug_shape']:
            shape_conditions = " OR ".join(["drug_shape = %s"] * len(search_params['drug_shape']))
            query_parts.append(f"({shape_conditions})")
            params.extend(search_params['drug_shape'])
        
        # 색상 검색 (복수 선택 가능)
        if search_params['colors']:
            color_conditions = " OR ".join(["color_class1 = %s"] * len(search_params['colors']))
            query_parts.append(f"({color_conditions})")
            params.extend(search_params['colors'])
        
        # 앞면 마크 검색
        if search_params['print_front']:
            query_parts.append("(print_front LIKE %s OR mark_code_front LIKE %s)")
            front_mark = f"%{search_params['print_front']}%"
            params.extend([front_mark, front_mark])
        
        # 뒷면 마크 검색
        if search_params['print_back']:
            query_parts.append("(print_back LIKE %s OR mark_code_back LIKE %s)")
            back_mark = f"%{search_params['print_back']}%"
            params.extend([back_mark, back_mark])
            
        # 앞면 분할선 검색
        if 'line_front' in request.args and request.args.get('line_front'):
            line_front_value = request.args.get('line_front')
            
            # + 기호를 선택했을 때 '십자분할선'도 함께 검색
            if line_front_value == '+':
                query_parts.append("(line_front = %s OR line_front LIKE %s)")
                params.append('+')
                params.append('%십자%')
            # 기타를 선택했을 때
            elif line_front_value == '기타':
                query_parts.append("(line_front != '+' AND line_front != '-' AND line_front IS NOT NULL)")
            # 다른 값(예: -)을 선택했을 때
            else:
                query_parts.append("line_front = %s")
                params.append(line_front_value)

        # 뒷면 분할선 검색 (동일한 로직)
        if 'line_back' in request.args and request.args.get('line_back'):
            line_back_value = request.args.get('line_back')
            
            if line_back_value == '+':
                query_parts.append("(line_back = %s OR line_back LIKE %s)")
                params.append('+')
                params.append('%십자%')
            elif line_back_value == '기타':
                query_parts.append("(line_back != '+' AND line_back != '-' AND line_back IS NOT NULL)")
            else:
                query_parts.append("line_back = %s")
                params.append(line_back_value)
        
        # 최종 쿼리 구성
        where_clause = " AND ".join(query_parts) if query_parts else "1=1"
        
        # 총 결과 개수 쿼리
        count_query = f"SELECT COUNT(*) as total FROM drug_identification WHERE {where_clause}"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()['total']
        
        # 총 페이지 수 계산
        total_pages = math.ceil(total_count / per_page) if total_count > 0 else 1
        
        # 결과가 있는 경우만 메인 쿼리 실행
        results = []
        if total_count > 0:
            # 메인 검색 쿼리
            query = f"""
            SELECT * FROM drug_identification 
            WHERE {where_clause}
            ORDER BY item_name
            LIMIT %s OFFSET %s
            """
            cursor.execute(query, params + [per_page, offset])
            results = cursor.fetchall()
        
        # 페이지네이션 URL 구성
        pagination_url = request.base_url + '?' + '&'.join([f"{k}={v}" for k, v in request.args.items() if k != 'page'])
        
        return render_template(
            'advanced_search_results.html',
            results=results,
            total_count=total_count,
            current_page=page,
            total_pages=total_pages,
            search_params=search_params,
            pagination_url=pagination_url
        )
    
    except Exception as e:
        current_app.logger.error(f"고급 검색 오류: {str(e)}")
        return f"검색 중 오류가 발생했습니다: {str(e)}", 500
    
    finally:
        if 'conn' in locals():
            conn.close()