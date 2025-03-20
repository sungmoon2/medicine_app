import requests
import logging
import time
import xml.etree.ElementTree as ET
from .config import ENCODED_API_KEY, BASE_URLS, DUR_ENDPOINTS

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='api_client.log'
)
logger = logging.getLogger('api_client')

def call_api(endpoint_key, params=None, retries=3, delay=1):
    """
    API 호출 기본 함수
    
    Args:
        endpoint_key: API 엔드포인트 키
        params: 요청 파라미터 (기본 키 제외)
        retries: 재시도 횟수
        delay: 재시도 간 지연시간(초)
        
    Returns:
        XML 응답 문자열 또는 오류 시 None
    """
    # 기본 파라미터에 API 키 추가
    if params is None:
        params = {}
    
    params['serviceKey'] = ENCODED_API_KEY
    
    # 데이터 포맷이 지정되지 않은 경우 XML로 설정
    if 'type' not in params:
        params['type'] = 'xml'
        
    # 엔드포인트 URL 결정
    url = None
    if endpoint_key in BASE_URLS:
        url = BASE_URLS[endpoint_key]
    elif endpoint_key.startswith('dur_'):
        # DUR 관련 API 호출
        dur_type = endpoint_key.split('_')[1]
        if dur_type in DUR_ENDPOINTS:
            url = f"{BASE_URLS['dur_info']}/{DUR_ENDPOINTS[dur_type]}"
    
    if url is None:
        logger.error(f"알 수 없는 엔드포인트: {endpoint_key}")
        return None
    
    # API 호출 시도
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params)
            
            # 성공 응답 확인
            if response.status_code == 200:
                return response.text
            
            logger.warning(f"API 호출 실패: 상태 코드 {response.status_code}, 재시도 {attempt+1}/{retries}")
            time.sleep(delay)
            
        except Exception as e:
            logger.error(f"API 호출 중 오류 발생: {e}")
            time.sleep(delay)
    
    logger.error(f"API 호출 최대 재시도 횟수 초과: {endpoint_key}")
    return None

def parse_xml_response(xml_text):
    """
    XML 응답을 파싱하여 Python 객체로 변환
    
    Args:
        xml_text: XML 형식의 문자열
        
    Returns:
        ElementTree 객체 또는 파싱 오류 시 None
    """
    try:
        root = ET.fromstring(xml_text)
        return root
    except Exception as e:
        logger.error(f"XML 파싱 오류: {e}")
        return None