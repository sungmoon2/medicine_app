from .client import call_api, parse_xml_response

def search_medicines_by_shape(params=None, page_no=1, num_of_rows=10):
    """
    의약품을 모양, 색상 등으로 검색
    
    Args:
        params: 검색 파라미터 (모양, 색상 등)
        page_no: 페이지 번호
        num_of_rows: 페이지당 결과 수
        
    Returns:
        의약품 목록 또는 오류 시 None
    """
    if params is None:
        params = {}
    
    # 페이징 파라미터 추가
    params['pageNo'] = page_no
    params['numOfRows'] = num_of_rows
    
    # API 호출
    xml_data = call_api('pill_info', params)
    if not xml_data:
        return None
    
    # XML 파싱
    root = parse_xml_response(xml_data)
    if root is None:
        return None
    
    # 결과 추출
    items = []
    for item in root.findall('.//item'):
        medicine_data = {}
        for child in item:
            medicine_data[child.tag] = child.text
        items.append(medicine_data)
    
    # 전체 결과 수 추출
    total_count = int(root.find('.//totalCount').text) if root.find('.//totalCount') is not None else 0
    
    return {
        'items': items,
        'total_count': total_count,
        'page_no': page_no,
        'num_of_rows': num_of_rows
    }

def get_medicine_detail(item_seq):
    """
    의약품 상세 정보 조회
    
    Args:
        item_seq: 품목일련번호
        
    Returns:
        의약품 상세 정보 또는 오류 시 None
    """
    params = {'itemSeq': item_seq}
    
    # API 호출
    xml_data = call_api('medicine_info', params)
    if not xml_data:
        return None
    
    # XML 파싱
    root = parse_xml_response(xml_data)
    if root is None:
        return None
    
    # 결과 추출
    item = root.find('.//item')
    if item is None:
        return None
    
    medicine_data = {}
    for child in item:
        medicine_data[child.tag] = child.text
    
    return medicine_data

def get_dur_info(item_seq, dur_type='usjnt'):
    """
    DUR 정보 조회
    
    Args:
        item_seq: 품목일련번호
        dur_type: DUR 유형 (기본값은 병용금기)
        
    Returns:
        DUR 정보 목록 또는 오류 시 None
    """
    params = {'itemSeq': item_seq}
    
    # API 호출
    endpoint_key = f"dur_{dur_type}"
    xml_data = call_api(endpoint_key, params)
    if not xml_data:
        return None
    
    # XML 파싱
    root = parse_xml_response(xml_data)
    if root is None:
        return None
    
    # 결과 추출
    items = []
    for item in root.findall('.//item'):
        dur_data = {}
        for child in item:
            dur_data[child.tag] = child.text
        items.append(dur_data)
    
    return items

def get_component_info(params=None, page_no=1, num_of_rows=10):
    """
    성분 정보 조회
    
    Args:
        params: 검색 파라미터 (성분코드, 성분명 등)
        page_no: 페이지 번호
        num_of_rows: 페이지당 결과 수
        
    Returns:
        성분 정보 목록 또는 오류 시 None
    """
    if params is None:
        params = {}
    
    # 페이징 파라미터 추가
    params['pageNo'] = page_no
    params['numOfRows'] = num_of_rows
    
    # API 호출
    xml_data = call_api('component_info', params)
    if not xml_data:
        return None
    
    # XML 파싱
    root = parse_xml_response(xml_data)
    if root is None:
        return None
    
    # 결과 추출
    items = []
    for item in root.findall('.//item'):
        component_data = {}
        for child in item:
            component_data[child.tag] = child.text
        items.append(component_data)
    
    # 전체 결과 수 추출
    total_count = int(root.find('.//totalCount').text) if root.find('.//totalCount') is not None else 0
    
    return {
        'items': items,
        'total_count': total_count,
        'page_no': page_no,
        'num_of_rows': num_of_rows
    }