# medicine_app/test_api_fixed.py
import requests
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# API 키 가져오기
API_KEY = os.getenv('OPEN_API_KEY')
print(f"API 키 존재 여부: {'있음' if API_KEY else '없음'}")
print(f"API 키 (앞부분만): {API_KEY[:10]}..." if API_KEY else "API 키 없음")

# 여러 가능한 API URL을 시도
urls = [
    'http://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService01/getMdcinGrnIdntfcList',
    'http://apis.data.go.kr/1471000/DrbEasyDrugInfoService/getDrbEasyDrugList',
    'http://apis.data.go.kr/1471000/DrugInfoService/getDrugInfo',
    'http://apis.data.go.kr/1471000/MdcinGrnIdntfcAPIService/getMdcinGrnIdntfcList'
]

params = {
    'serviceKey': API_KEY,
    'pageNo': '1',
    'numOfRows': '10',
    'type': 'xml'
}

# 각 URL 시도
for url in urls:
    try:
        print(f"\n{'-'*50}")
        print(f"테스트 URL: {url}")
        print(f"{'-'*50}")
        
        response = requests.get(url, params=params)
        print(f"상태 코드: {response.status_code}")
        
        # 응답 내용 확인
        response_text = response.text[:300] + "..." if len(response.text) > 300 else response.text
        print(f"응답 내용: {response_text}")
        
        if response.status_code == 200:
            print("✓ 요청 성공!")
        else:
            print("✗ 요청 실패")
            
    except Exception as e:
        print(f"요청 오류: {e}")