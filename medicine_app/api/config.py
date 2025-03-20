import os
from dotenv import load_dotenv
import requests

# .env 파일에서 환경 변수 로드
load_dotenv()

# API 기본 URL 및 키 설정
API_KEY = os.getenv('OPEN_API_KEY')
ENCODED_API_KEY = requests.utils.quote(API_KEY)

# API 엔드포인트 기본 URL
BASE_URLS = {
    'pill_info': 'http://apis.data.go.kr/1471000/MdcinGrnIdntfcAPIService/getMdcinGrnIdntfcList',
    'medicine_info': 'http://apis.data.go.kr/1471000/DrugInfoService/getDrugInfo',
    'dur_info': 'http://apis.data.go.kr/1471000/DURPrdlstInfoService',
    'component_info': 'http://apis.data.go.kr/1471000/DrugIngrNameService/getIngredientInfoList',
    'daily_dose': 'http://apis.data.go.kr/1471000/MedicDayMaxDoseInfoService/getMedicDayMaxDoseInfo'
}

# DUR 관련 API 엔드포인트
DUR_ENDPOINTS = {
    'usjnt': 'getUsjntTabooInfoList03',     # 병용금기
    'age': 'getSpcifyAgrdeTabooInfoList03', # 특정연령대금기
    'pregnancy': 'getPwnmTabooInfoList03',  # 임부금기
    'capacity': 'getCpctyAtentInfoList03',  # 용량주의
    'period': 'getMdctnPdAtentInfoList03',  # 투여기간주의
    'elderly': 'getOdsnAtentInfoList03',    # 노인주의
    'duplicate': 'getEfcyDplctInfoList03',  # 효능군중복
    'split': 'getSeobangjeongPartitnAtentInfoList03' # 서방정분할주의
}