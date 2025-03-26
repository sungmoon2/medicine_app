import os
import re
import json
import time
import sqlite3
import logging
import urllib.parse
import urllib.request
from datetime import datetime
import sys
import io
import locale
from tqdm import tqdm
import colorama
from colorama import Fore, Back, Style
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import concurrent.futures
import hashlib
import requests
import asyncio
import aiohttp
import functools
from typing import Dict, List, Tuple, Optional, Any, Union

# 로깅 설정
colorama.init(autoreset=True)

def setup_logging(log_file='medicine_crawler.log', console_level=logging.INFO, file_level=logging.DEBUG):
    """
    로깅 시스템 설정
    
    Args:
        log_file: 로그 파일 경로
        console_level: 콘솔에 표시할 로그 레벨
        file_level: 파일에 저장할 로그 레벨
    
    Returns:
        logging.Logger: 설정된 로거 객체
    """
    logger = logging.getLogger('medicine_crawler')
    logger.setLevel(logging.DEBUG)  # 로거 자체는 모든 메시지를 처리할 수 있도록 설정
    
    # 포매터 설정
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 파일 핸들러 설정
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    
    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    
    # 기존 핸들러 제거 (중복 방지)
    if logger.handlers:
        logger.handlers = []
    
    # 핸들러 추가
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# 설정 및 상수
class Config:
    """애플리케이션 설정 및 상수를 관리하는 클래스"""
    
    # API 설정
    DEFAULT_SEARCH_DISPLAY = 20  # 한 번에 가져올 결과 수 (최대 100)
    API_DELAY = 0.3  # API 호출 간 딜레이 (초)
    MAX_DAILY_API_CALLS = 24000  # 일일 최대 API 호출 수 (여유있게 설정, 실제 한도는 25,000)
    
    # 데이터베이스 설정
    DEFAULT_DB_PATH = 'api_medicine.db'
    DB_TABLES = {
        'api_medicine': '''
        CREATE TABLE IF NOT EXISTS api_medicine (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            url TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_hash TEXT
        )
        ''',
        'api_calls': '''
        CREATE TABLE IF NOT EXISTS api_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        '''
    }
    
    # 키워드 파일 설정
    COMPLETED_KEYWORDS_FILE = 'completed_keywords.txt'
    IN_PROGRESS_KEYWORDS_FILE = 'in_progress_keywords.txt'
    FAILED_KEYWORDS_FILE = 'failed_keywords.txt'
    
    # 의약품 식별 패턴
    MEDICINE_URL_PATTERNS = ['medicinedic', 'drug', 'medicine', 'pill', 'pharm']
    MEDICINE_TITLE_PATTERNS = ['정', '캡슐', '주사', '시럽', '연고', '크림', '겔', '패치', '좌제', '분말', 
                               '주', '서방정', '액', '과립', 'tab', 'cap', 'inj', 'amp', 'powder']
    
    # 검색 결과 필터링을 위한 불용어
    STOPWORDS = ['추천', '이벤트', '광고', '판매', '구매', '쇼핑몰', '최저가']
    
    # 이미지 다운로드 설정
    ENABLE_IMAGE_DOWNLOAD = True
    IMAGES_DIR = 'medicine_images'
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # 병렬 처리 설정
    MAX_WORKERS = 4  # 병렬 처리에 사용할 최대 워커 수

def init_environment():
    """
    실행 환경 초기화 (인코딩, 콘솔 설정 등)
    """
    # Windows 환경에서 콘솔 출력 인코딩 변경
    if sys.platform.startswith('win'):
        # UTF-8 모드로 설정 (Python 3.7 이상)
        if hasattr(sys, 'setdefaultencoding'):
            sys.setdefaultencoding('utf-8')
        
        # 표준 출력 인코딩 설정
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    # 이미지 디렉토리 생성
    if Config.ENABLE_IMAGE_DOWNLOAD and not os.path.exists(Config.IMAGES_DIR):
        os.makedirs(Config.IMAGES_DIR)
    
    # 로딩 정보 출력
    start_time = datetime.now()
    print(f"{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}네이버 API를 이용한 약품 정보 수집 시작")
    print(f"{Fore.CYAN}실행 시간: {start_time}")
    print(f"{Fore.CYAN}{'='*80}")
    
    return start_time

def load_env_configuration():
    """
    환경 설정 로드 및 API 키 준비
    
    Returns:
        tuple: (client_id, client_secret, db_path) 튜플
    """
    # .env 파일 로드
    load_dotenv()
    
    # 환경 변수에서 설정 가져오기
    client_id = os.environ.get("NAVER_CLIENT_ID")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET")
    db_path = os.environ.get("DB_PATH", Config.DEFAULT_DB_PATH)
    
    # API 키가 없는 경우 처리
    if not client_id or not client_secret:
        print(f"{Fore.YELLOW}.env 파일이 없거나 API 키가 설정되지 않았습니다.")
        print(f"현재 작업 디렉토리에 .env 파일을 생성하고 다음 내용을 추가하세요:")
        print(f"{Fore.GREEN}NAVER_CLIENT_ID=네이버_API_클라이언트_ID")
        print(f"NAVER_CLIENT_SECRET=네이버_API_클라이언트_시크릿{Style.RESET_ALL}")
        
        # .env 파일 예시 생성
        env_example = """# 네이버 API 인증 정보
NAVER_CLIENT_ID=YOUR_CLIENT_ID
NAVER_CLIENT_SECRET=YOUR_CLIENT_SECRET

# 데이터베이스 설정
DB_PATH=api_medicine.db

# 병렬 처리 설정 (선택사항)
MAX_WORKERS=4

# 이미지 다운로드 설정 (선택사항)
ENABLE_IMAGE_DOWNLOAD=True
IMAGES_DIR=medicine_images
"""
        with open('.env.example', 'w', encoding='utf-8') as f:
            f.write(env_example)
        
        print(f"{Fore.YELLOW}.env.example 파일이 생성되었습니다. 이 파일을 .env로 복사하고 API 키를 입력하세요.")
        
        # 사용자 입력 받기 (대체 방법)
        print(f"{Fore.CYAN}또는 직접 API 키를 입력하세요:")
        client_id = input("네이버 API 클라이언트 ID: ")
        client_secret = input("네이버 API 클라이언트 시크릿: ")
        
        # 입력받은 정보로 .env 파일 생성
        if client_id and client_secret:
            env_content = f"""NAVER_CLIENT_ID={client_id}
NAVER_CLIENT_SECRET={client_secret}
DB_PATH={Config.DEFAULT_DB_PATH}
"""
            with open('.env', 'w', encoding='utf-8') as f:
                f.write(env_content)
            print(f"{Fore.GREEN}.env 파일이 생성되었습니다. 다음 실행부터는 자동으로 불러옵니다.{Style.RESET_ALL}")
    
    return client_id, client_secret, db_path

# 키워드 파일 관리 함수들
def load_completed_keywords():
    """완료된 키워드 목록 로드"""
    if os.path.exists(Config.COMPLETED_KEYWORDS_FILE):
        with open(Config.COMPLETED_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    return []

def load_in_progress_keyword():
    """진행 중인 키워드 로드"""
    if os.path.exists(Config.IN_PROGRESS_KEYWORDS_FILE):
        with open(Config.IN_PROGRESS_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if lines:
                return lines[0].strip()
    return None

def load_failed_keywords():
    """실패한 키워드 목록 로드"""
    if os.path.exists(Config.FAILED_KEYWORDS_FILE):
        with open(Config.FAILED_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    return []

def save_completed_keyword(keyword):
    """완료된 키워드 저장"""
    with open(Config.COMPLETED_KEYWORDS_FILE, 'a', encoding='utf-8') as f:
        f.write(keyword + '\n')

def save_in_progress_keyword(keyword):
    """진행 중인 키워드 저장"""
    with open(Config.IN_PROGRESS_KEYWORDS_FILE, 'w', encoding='utf-8') as f:
        f.write(keyword + '\n')

def save_failed_keyword(keyword, reason=None):
    """실패한 키워드 저장"""
    with open(Config.FAILED_KEYWORDS_FILE, 'a', encoding='utf-8') as f:
        if reason:
            f.write(f"{keyword} # {reason}\n")
        else:
            f.write(keyword + '\n')

def clear_in_progress_keyword():
    """진행 중인 키워드 제거"""
    if os.path.exists(Config.IN_PROGRESS_KEYWORDS_FILE):
        os.remove(Config.IN_PROGRESS_KEYWORDS_FILE)

# 데코레이터: 재시도 메커니즘
def retry(max_tries=3, delay_seconds=1, backoff_factor=2, exceptions=(Exception,)):
    """
    함수 실행 실패 시 재시도하는 데코레이터
    
    Args:
        max_tries: 최대 시도 횟수
        delay_seconds: 재시도 간 대기 시간 (초)
        backoff_factor: 대기 시간 증가 계수
        exceptions: 재시도할 예외 유형 튜플
    
    Returns:
        decorator: 재시도 데코레이터
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            mtries, mdelay = max_tries, delay_seconds
            last_exception = None
            
            while mtries > 0:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    mtries -= 1
                    if mtries == 0:
                        break
                        
                    time.sleep(mdelay)
                    mdelay *= backoff_factor
            
            # 모든 재시도 실패 시 마지막 예외 발생
            if last_exception:
                raise last_exception
        return wrapper
    return decorator

# 헬퍼 함수
def generate_data_hash(data_dict):
    """
    데이터 사전에서 해시값 생성
    
    Args:
        data_dict: 해시를 생성할 데이터 사전
    
    Returns:
        str: 데이터의 MD5 해시값
    """
    # 핵심 필드만 추출하여 정렬
    key_fields = sorted([
        f"{k}:{str(v)}" for k, v in data_dict.items() 
        if k not in ['created_at', 'updated_at', 'id', 'data_hash']
    ])
    
    # 정렬된 필드를 문자열로 연결하고 해시 생성
    data_str = '||'.join(key_fields)
    return hashlib.md5(data_str.encode('utf-8')).hexdigest()

def generate_comprehensive_keywords():
    """
    포괄적인 검색 키워드 생성
    
    Returns:
        list: 검색에 사용할 키워드 리스트
    """
    keywords = []
    
    # 한글 초성 검색 (모든 한글 약품명 포괄)
    keywords.extend(["ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"])
    
    # 영문 알파벳 검색 (모든 영문 약품명 포괄)
    keywords.extend(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    
    # 숫자 검색 (숫자로 시작하는 약품명 포괄)
    keywords.extend([str(i) for i in range(10)])
    
    # 의약품 일반 분류
    keywords.extend([
        "의약품", "약품", "전문의약품", "일반의약품", "희귀의약품", "의약외품", "기능성 의약품",
        "처방약", "비처방약", "OTC", "제네릭", "오리지널"
    ])
    
    # 제형별 검색 (모든 제형 포괄)
    form_keywords = [
        "정", "캡슐", "주사", "시럽", "연고", "크림", "겔", "패치", "좌제", "분말", "액", "로션",
        "과립", "현탁액", "환", "점안액", "점이액", "스프레이", "흡입제", "투여", "주입", "엑스제",
        "산제", "서방정", "구강붕해정", "경구용", "외용", "설하정", "흡입기", "용액", "필름코팅정",
        "질정", "점착제", "경피제", "좌약", "트로키정", "시럽제", "건조주사제", "서스펜션", "에멀젼"
    ]
    keywords.extend(form_keywords)
    
    # 주요 제약사 (국내외 주요 제약회사)
    pharma_companies = [
        "동아제약", "유한양행", "녹십자", "한미약품", "종근당", "대웅제약", "일동제약", "보령제약", 
        "SK케미칼", "삼성바이오로직스", "셀트리온", "JW중외제약", "한독", "에이치엘비", "광동제약",
        "경동제약", "부광약품", "현대약품", "동국제약", "제일약품", "삼진제약", "명인제약", "한림제약",
        "씨제이", "건일제약", "대원제약", "동화약품", "바이엘", "화이자", "노바티스", "로슈", "머크",
        "글락소스미스클라인", "아스트라제네카", "사노피", "애브비", "존슨앤존슨", "다케다", "일리릴리",
        "암젠", "길리어드", "태준제약", "신풍제약", "영진약품", "구주제약", "알보젠", "한국앨러간",
        "GSK", "MSD", "아스텔라스", "화이트", "한국오츠카", "한국얀센", "한국릴리", "한국베링거",
        "대한약품", "동구약품", "동성제약", "삼일제약", "삼천당제약", "신일제약", "안국약품", 
        "영풍제약", "오스틴제약", "우리제약", "유영제약", "일성신약", "한국유나이티드제약", 
        "한국콜마", "한국화이자업존", "한국노바티스", "한국아스트라제네카", "현대약품", "휴온스", "환인제약"
    ]
    keywords.extend(pharma_companies)
    
    # 약물 분류 코드 (ATC 코드 첫 번째 수준)
    atc_classes = [
        "소화관", "혈액", "심혈관계", "피부", "비뇨생식기계", "호르몬", "항감염제", "항암제",
        "근골격계", "신경계", "항기생충제", "호흡기계", "감각기관", "기타", "당뇨병치료제", 
        "고혈압약", "고지혈증약", "항우울제", "항히스타민제", "진해거담제", "항경련제", "항궤양제",
        "항정신병약", "면역억제제", "비스테로이드성소염제", "항응고제", "혈소판응집억제제",
        "마약성진통제", "비마약성진통제", "항파킨슨제", "치매치료제", "골다공증치료제"
    ]
    keywords.extend(atc_classes)
    
    # 흔한 약물 성분명 (확장)
    active_ingredients = [
        "아세트아미노펜", "디클로페낙", "아스피린", "이부프로펜", "메트포르민", "아토바스타틴",
        "로수바스타틴", "암로디핀", "발사르탄", "로페라미드", "세티리진", "레보세티리진",
        "모티리톤", "라니티딘", "오메프라졸", "판토프라졸", "란소프라졸", "메포민", "글리메피리드",
        "심바스타틴", "프라바스타틴", "에제티미브", "로사르탄", "텔미사르탄", "올메사르탄",
        "카르베딜롤", "비소프롤롤", "독사조신", "프로프라놀롤", "아테놀롤", "클로피도그렐",
        "와파린", "플루옥세틴", "에스시탈로프람", "파록세틴", "벤라팍신", "디아제팜", "알프라졸람",
        "로라제팜", "졸피뎀", "클로나제팜", "레보도파", "세레콕시브", "메로페넴", "레보플록사신",
        "시프로플록사신", "독시사이클린", "아목시실린", "세팔렉신", "세프트리악손", "아지트로마이신",
        "클래리스로마이신", "페니실린", "플루코나졸", "레비티라세탐", "가바펜틴", "프레가발린",
        "라모트리진", "발프로산", "토피라메이트", "미들라제팜", "니페디핀", "실데나필", "타다라필",
        "올란자핀", "퀘티아핀", "리스페리돈", "팔리페리돈", "세르트랄린", "밀나시프란", "아리피프라졸",
        "리튬", "라미프릴", "에날라프릴", "리시노프릴", "테르비나핀", "이트라코나졸", "케토코나졸",
        "메트로니다졸", "티카그렐러", "메트롤", "에놀", "티몰롤", "도네페질", "메만틴", "갈란타민",
        "리바스티그민", "트라마돌", "코데인", "카바마제핀", "나부메톤", "네비보롤", "덱사메타손", 
        "둘록세틴", "디곡신", "에피네프린", "인도메타신", "인슐린", "하이드로코르티손", "할로페리돌",
        "부데소니드", "부프로피온", "스피로놀락톤", "시메티딘", "소마트로핀", "수니티닙", "파모티딘",
        "펜토바르비탈", "조피클론", "피나스테리드", "피오글리타존", "히드로클로로티아지드"
    ]
    keywords.extend(active_ingredients)
    
    # 효능별 분류 (대표적인 치료 효과)
    therapeutic_effects = [
        "진통제", "해열제", "항생제", "소화제", "변비약", "설사약", "고혈압약", "당뇨약", 
        "고지혈증약", "항히스타민제", "항우울제", "수면제", "진정제", "비타민", "철분제",
        "기관지확장제", "스테로이드", "피부질환", "안약", "항암제", "면역억제제", "항응고제",
        "항혈소판제", "이뇨제", "구토억제제", "항경련제", "근육이완제", "항파킨슨제", "피임약",
        "호르몬대체요법", "갑상선약", "전립선약", "항바이러스제", "항진균제", "항결핵제", "골다공증약",
        "관절염약", "통풍약", "편두통약", "천식약", "COPD약", "알레르기약", "치매약", "항정신병약",
        "강장제", "영양제", "소염제", "면역조절제", "구충제", "항구토제", "제산제", "위장약",
        "최면제", "각종 호르몬제", "발기부전치료제", "탈모치료제", "여드름치료제"
    ]
    keywords.extend(therapeutic_effects)
    
    # 인기 약품 및 브랜드명
    popular_brands = [
        "타이레놀", "게보린", "판콜", "부루펜", "아스피린", "베아제", "백초시럽", "판피린",
        "액티피드", "판콜에이", "신신파스", "제일쿨파스", "캐롤", "텐텐", "이가탄", "센트룸",
        "아로나민", "삐콤씨", "컨디션", "박카스", "인사돌", "우루사", "훼스탈",
        "무좀약", "노스카나", "에어탈", "이지엔", "써스펜", "지르텍", "클라리틴", "알레그라",
        "에어미드", "아스피린프로텍트", "노바스크", "코자", "리피토", "크레스토", "포시가",
        "자누비아", "트라젠타", "넥시움", "부광유니펜", "독클라", "징코에프", "활명수", "까스활명수",
        "니코틴엘", "스포라녹스", "쎄레브렉스", "큐란", "스리반", "알닥톤", "루센티스", "하보니",
        "소발디", "테세오스", "레토프릴", "쿨쿨정", "아드빌", "브루펜", "펜잘", "이지엔6", 
        "탁센", "디스롤정", "나린펜정", "펜잘스피드", "복합마취크림", "개비스콘", "가스모틴", 
        "모사프리드", "둘코락스", "듀파락", "마그밀", "베너픽스", "지렐정", "멕클리짓", 
        "프로맥", "덱실란트", "레가론", "에세푸릴"
    ]
    keywords.extend(popular_brands)
    
    # 질환명 (확장)
    diseases = [
        "고혈압", "당뇨", "고지혈증", "위염", "역류성식도염", "궤양", "설사", "변비", "알레르기",
        "비염", "아토피", "두통", "편두통", "관절염", "류마티스", "통풍", "골다공증", "골절",
        "요통", "좌골신경통", "디스크", "천식", "기관지염", "폐렴", "결핵", "감기", "독감",
        "인플루엔자", "만성폐쇄성폐질환", "심부전", "부정맥", "협심증", "심근경색", "뇌졸중",
        "동맥경화", "혈전증", "빈혈", "백혈병", "림프종", "전립선염", "전립선비대증", "방광염",
        "요로감염", "신부전", "신장결석", "간염", "간경변", "담석증", "담낭염", "췌장염",
        "갑상선기능항진증", "갑상선기능저하증", "쿠싱증후군", "애디슨병", "당뇨병성신증",
        "당뇨병성망막병증", "당뇨병성신경병증", "우울증", "조울증", "조현병", "불안장애",
        "공황장애", "강박장애", "외상후스트레스장애", "알츠하이머", "파킨슨병", "간질", "발작",
        "불면증", "과다수면증", "피부염", "건선", "여드름", "대상포진", "결핵", "암", "뇌종양",
        "폐암", "간암", "위암", "대장암", "췌장암", "유방암", "전립선암", "방광암", "난소암",
        "자궁경부암", "백혈병", "임파선암", "피부암", "폐암", "간암", "위암", "대장암", "췌장암", "유방암", "전립선암", "방광암", "난소암",
        "자궁경부암", "백혈병", "임파선암", "피부암", "뇌경색", "뇌출혈", "동맥경화증", "심근경색",
        "협심증", "심부전", "심장판막질환", "대동맥류", "혈관염", "레이노증후군", "버거병"
    ]
    keywords.extend(diseases)
    
    # 약리작용 및 분류 관련 키워드 추가
    pharmacological_keywords = [
        "ACE억제제", "ARB", "NSAID", "PPI", "SSRI", "SNRI", "TCA", "alpha차단제", "beta차단제", 
        "COX2억제제", "DPP4억제제", "SGLT2억제제", "TNF알파억제제", "칼슘통로차단제", "스타틴계열", 
        "항전간제", "항우울제", "항정신병약", "항응고제", "항혈소판제", "면역억제제", "마약성진통제", 
        "비마약성진통제", "프로바이오틱스", "면역조절제", "항바이러스제", "항균제", "항진균제"
    ]
    keywords.extend(pharmacological_keywords)
    
    # 투여 용량 관련 키워드
    dosage_keywords = [
        "5mg", "10mg", "20mg", "25mg", "30mg", "40mg", "50mg", "100mg", "250mg", "500mg",
        "1g", "2g", "5g", "10g", "15g", "20g", "0.5mg", "0.25mg", "1mg", "2mg", "3mg", "4mg",
        "75mg", "150mg", "200mg", "300mg", "400mg", "600mg", "800mg", "1000mg"
    ]
    keywords.extend(dosage_keywords)
    
    # 희귀/전문성 질환 관련 의약품
    rare_disease_meds = [
        "항암제", "면역억제제", "면역조절제", "항레트로바이러스제", "항파킨슨제", "항리슈만편모충제", 
        "항트리파노소마약", "항말라리아제", "항진균제", "항결핵제", "항바이러스제", "희귀질환치료제", 
        "낭포성섬유증", "근위축성측삭경화증", "다발성경화증", "재생불량성빈혈", "혈우병", "폐동맥고혈압", 
        "폼페병", "고셔병", "패브리병", "윌슨병", "척수성근위축증", "크론병", "궤양성대장염", "건선", 
        "류마티스관절염", "강직성척추염", "에이즈치료제", "항응고제", "호르몬대체요법", "조현병치료제"
    ]
    keywords.extend(rare_disease_meds)
    
    # 증상 및 질환별 키워드 보강
    symptom_keywords = [
        "두통약", "감기약", "소화제", "진통제", "치질약", "항생제", "항히스타민제", "비염약", 
        "피부염약", "무좀약", "변비약", "설사약", "구토억제제", "멀미약", "수면제", "근육이완제",
        "관절염약", "천식약", "고혈압약", "당뇨약", "콜레스테롤약", "골다공증약", "갑상선약",
        "간질환약", "파킨슨약", "알츠하이머약", "우울증약", "조현병약", "간질약", "전립선약",
        "발기부전약", "피임약", "여성호르몬제", "갱년기약", "통풍약", "비만약", "금연보조제"
    ]
    keywords.extend(symptom_keywords)
    
    # 의약품 기술 및 제형 관련 추가 키워드
    tech_keywords = [
        "서방형", "지속형", "방출조절", "다층정", "이중정", "용해도증가", "생체이용률", 
        "약물전달시스템", "생물학적동등성", "약물상호작용", "약물대사", "정밀의료"
    ]
    keywords.extend(tech_keywords)
    
    # 중복 제거
    unique_keywords = list(set(keywords))
    
    return unique_keywords

class NaverAPIClient:
    """
    네이버 Open API 호출을 담당하는 클라이언트 클래스
    """
    def __init__(self, client_id, client_secret, db_conn, logger):
        """
        네이버 API 클라이언트 초기화
        
        Args:
            client_id: 네이버 개발자 센터에서 발급받은 클라이언트 ID
            client_secret: 네이버 개발자 센터에서 발급받은 클라이언트 시크릿
            db_conn: SQLite 데이터베이스 연결 객체
            logger: 로깅 객체
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.db_conn = db_conn
        self.logger = logger
        self.today_api_calls = self._load_today_api_calls()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def _load_today_api_calls(self):
        """오늘의 API 호출 횟수 로드"""
        cursor = self.db_conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute(
            "SELECT count FROM api_calls WHERE date = ? ORDER BY id DESC LIMIT 1", 
            (today,)
        )
        result = cursor.fetchone()
        
        if result:
            return result[0]
        else:
            # 오늘 첫 API 호출이면 레코드 생성
            cursor.execute(
                "INSERT INTO api_calls (date, count) VALUES (?, 0)",
                (today,)
            )
            self.db_conn.commit()
            return 0
    
    def _update_api_call_count(self, count=1):
        """
        API 호출 횟수 업데이트
        
        Args:
            count: 증가시킬 호출 횟수
        
        Returns:
            int: 업데이트 후 오늘의 총 API 호출 횟수
        """
        self.today_api_calls += count
        
        cursor = self.db_conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute(
            "UPDATE api_calls SET count = ? WHERE date = ?",
            (self.today_api_calls, today)
        )
        self.db_conn.commit()
        
        return self.today_api_calls
    
    def check_api_limit(self):
        """
        API 호출 한도에 도달했는지 확인
        
        Returns:
            bool: API 호출 한도에 도달했으면 True, 아니면 False
        """
        return self.today_api_calls >= Config.MAX_DAILY_API_CALLS
    
    @retry(max_tries=5, delay_seconds=2, backoff_factor=2, exceptions=(requests.RequestException, urllib.error.URLError))
    def search_medicine(self, keyword, display=None, start=1):
        """
        네이버 API를 사용하여 약품 검색
        
        Args:
            keyword: 검색 키워드
            display: 한 번에 가져올 결과 수 (최대 100)
            start: 검색 시작 위치
            
        Returns:
            dict: API 응답 데이터 또는 None (에러 발생 시)
        """
        if display is None:
            display = Config.DEFAULT_SEARCH_DISPLAY
        
        # API 한도 체크
        if self.check_api_limit():
            self.logger.warning(f"일일 API 호출 한도({Config.MAX_DAILY_API_CALLS}회)에 도달했습니다.")
            return None
        
        encoded_keyword = urllib.parse.quote(f"{keyword} 의약품")
        url = f"https://openapi.naver.com/v1/search/encyc.json?query={encoded_keyword}&display={display}&start={start}"
        
        self.logger.info(f"API 요청 시작: URL={url}, 키워드='{keyword}', 결과 수={display}, 시작 위치={start}")
        
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret
        }
        
        try:
            self.logger.debug(f"API 요청 헤더: {headers}")
            response = self.session.get(url, headers=headers, timeout=10)
            
            self.logger.info(f"API 응답 상태 코드: {response.status_code}")
            self.logger.debug(f"API 응답 헤더: {dict(response.headers)}")
            
            # 응답 내용 일부 로깅 (너무 길지 않게)
            response_preview = response.text[:500] + ('...' if len(response.text) > 500 else '')
            self.logger.debug(f"API 응답 내용 미리보기: {response_preview}")
            
            response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
            
            try:
                result = response.json()
                
                # 결과 정보 로깅
                if 'total' in result:
                    self.logger.info(f"API 검색 결과: 총 {result['total']}개 항목 중 {len(result.get('items', []))}개 반환됨")
                else:
                    self.logger.warning(f"API 응답에 'total' 필드가 없음: {result.keys()}")
                
                # API 호출 카운터 업데이트
                self._update_api_call_count()
                return result
            except json.JSONDecodeError as e:
                self.logger.error(f"API 응답을 JSON으로 파싱할 수 없음: {e}")
                self.logger.error(f"원본 응답: {response.text}")
                raise
                
        except requests.RequestException as e:
            self.logger.error(f"API 요청 중 오류 발생: {e}")
            
            # 오류 상세 정보 로깅
            if hasattr(e, 'response') and e.response is not None:
                self.logger.error(f"오류 상태 코드: {e.response.status_code}")
                self.logger.error(f"오류 응답 헤더: {dict(e.response.headers)}")
                self.logger.error(f"오류 응답 내용: {e.response.text}")
            
            raise
    
    @retry(max_tries=3, delay_seconds=1, exceptions=(requests.RequestException,))
    def get_html_content(self, url):
        """
        주어진 URL에서 HTML 내용 가져오기
        
        Args:
            url: 가져올 웹페이지 URL
            
        Returns:
            str: 웹페이지 HTML 내용 또는 None (에러 발생 시)
        """
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            self.logger.error(f"URL 접속 중 오류 발생: {e}")
            raise
    
    @retry(max_tries=3, delay_seconds=1, exceptions=(requests.RequestException,))
    def download_image(self, image_url, medicine_name):
        """
        이미지 URL에서 이미지 다운로드
        
        Args:
            image_url: 이미지 URL
            medicine_name: 약품 이름 (파일명 생성용)
            
        Returns:
            str: 로컬에 저장된 이미지 경로 또는 원본 URL (실패 시)
        """
        if not Config.ENABLE_IMAGE_DOWNLOAD:
            return image_url
        
        if not image_url:
            return None
        
        try:
            # 파일명에 사용할 수 없는 문자 제거
            safe_name = re.sub(r'[\\/*?:"<>|]', "", medicine_name)
            # URL의 해시값 추가하여 고유한 파일명 생성
            hash_suffix = hashlib.md5(image_url.encode()).hexdigest()[:8]
            file_ext = os.path.splitext(image_url.split('?')[0])[1] or '.jpg'
            file_name = f"{safe_name}_{hash_suffix}{file_ext}"
            file_path = os.path.join(Config.IMAGES_DIR, file_name)
            
            # 이미 다운로드된 파일이면 해당 경로 반환
            if os.path.exists(file_path):
                return file_path
            
            # 이미지 다운로드
            response = self.session.get(image_url, stream=True, timeout=10)
            response.raise_for_status()
            
            # 콘텐츠 길이 확인
            content_length = int(response.headers.get('Content-Length', 0))
            if content_length > Config.MAX_IMAGE_SIZE:
                self.logger.warning(f"이미지 크기가 너무 큼: {content_length} bytes, 최대 허용: {Config.MAX_IMAGE_SIZE} bytes")
                return image_url
            
            # 파일 저장
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            self.logger.info(f"이미지 다운로드 완료: {file_path}")
            return file_path
        
        except Exception as e:
            self.logger.error(f"이미지 다운로드 중 오류 발생: {e}")
            return image_url

    async def search_medicine_async(self, keyword, display=None, start=1):
        """
        네이버 API를 사용하여 약품 검색 (비동기 버전)
        
        Args:
            keyword: 검색 키워드
            display: 한 번에 가져올 결과 수 (최대 100)
            start: 검색 시작 위치
            
        Returns:
            dict: API 응답 데이터 또는 None (에러 발생 시)
        """
        if display is None:
            display = Config.DEFAULT_SEARCH_DISPLAY
        
        # API 한도 체크
        if self.check_api_limit():
            self.logger.warning(f"일일 API 호출 한도({Config.MAX_DAILY_API_CALLS}회)에 도달했습니다.")
            return None
        
        encoded_keyword = urllib.parse.quote(f"{keyword} 의약품")
        url = f"https://openapi.naver.com/v1/search/encyc.json?query={encoded_keyword}&display={display}&start={start}"
        
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        result = await response.json()
                        # API 호출 카운터 업데이트
                        self._update_api_call_count()
                        return result
                    else:
                        error_text = await response.text()
                        self.logger.error(f"API 요청 실패: 응답 코드 {response.status}, 응답: {error_text}")
                        return None
            except Exception as e:
                self.logger.error(f"비동기 API 요청 중 오류 발생: {e}")
                return None


class SearchManager:
    """
    약품 검색 및 처리를 관리하는 클래스
    """
    def __init__(self, api_client, db_manager, parser, logger):
        """
        검색 관리자 초기화
        
        Args:
            api_client: NaverAPIClient 인스턴스
            db_manager: DatabaseManager 인스턴스
            parser: MedicineParser 인스턴스
            logger: 로그 객체
        """
        self.api_client = api_client
        self.db_manager = db_manager
        self.parser = parser
        self.logger = logger
    
    def is_medicine_item(self, item):
        """
        검색 결과 항목이 구체적인 의약품인지 확인
        """
        # BeautifulSoup을 사용하여 HTML 태그 제거
        title = BeautifulSoup(item['title'], 'html.parser').get_text()
        description = BeautifulSoup(item['description'], 'html.parser').get_text()
        
        # 제약회사 관련 패턴 대폭 확장
        company_patterns = [
            '제약', '약품(주)', '바이오', '파마', '약국', '의약품 제조', 
            '(주)', '주식회사', '바이오택', '팜', '제약회사', '케미칼',
            '바이오로직스', '생명과학', '헬스케어', '바이오사이언스',
            '메디칼', '메디컬', '헬스', '제약사', '테라퓨틱스', '약업',
            '약품', '의약', '의약품', '제약업', '바이오제약', '생명공학',
            '약품공업', '제약공업', '팜텍', '바이오팜', '신약', '생물약품'
        ]
        
        # 의약품이 아닌 일반 용어 패턴
        term_patterns = [
            '합성의약품', '생물의약품', '약학', '약사', '의약품 분류', 
            '의약품 허가', '의약품 개발', '의약품 정의', '의약품이란',
            '제네릭', '오리지널', '백신', '약전', '약품학', '약리학',
            '바이오시밀러', '의약품 안전', '의약품 부작용', '의약품 관리',
            '처방의약품', '일반의약품', '전문의약품', '의약품 유통',
            '의약품산업', '약물', '약물학', '의약품 심사', '의약품 표시기재'
        ]
        
        # 제약회사 확인 - 제목에 회사 관련 패턴이 있는지
        for pattern in company_patterns:
            if pattern in title:
                self.logger.debug(f"제약회사 패턴 '{pattern}'이 포함된 항목 제외: {title}")
                return False
        
        # 일반 용어 확인 - 제목이 의약품 관련 용어인지
        for pattern in term_patterns:
            if pattern in title:
                self.logger.debug(f"일반 용어 패턴 '{pattern}'이 포함된 항목 제외: {title}")
                return False
        
        # 의약품 URL 확인 - medicinedic이 URL에 포함된 항목만 허용
        if 'medicinedic' in item['link'].lower():
            return True
        
        # 명확한 의약품 형태 확인
        medicine_forms = ['정', '캡슐', '주사', '시럽', '연고', '크림', '겔', '패치', 
                        '좌제', '분말', '액', '주', '서방정', '구강정', '액상', '세립',
                        '분말', '과립']
        
        # 제목 끝에 의약품 형태가 있는지 확인
        for form in medicine_forms:
            if title.endswith(form) or re.search(r'\d+' + form + r'$', title):
                return True
        
        # 특정 의약품 식별 패턴 (예: "OO정 100mg", "OO캡슐 500mg")
        if re.search(r'\d+\s*mg|\d+\s*mcg|\d+\s*g', title) and any(form in title for form in medicine_forms):
            return True
        
        # 설명에 의약품 핵심 키워드가 모두 포함되는지 확인
        essential_keywords = ['효능', '용법', '성분']
        if all(keyword in description for keyword in essential_keywords):
            return True
        
        # 기본적으로 제외 (확실한 의약품 패턴이 발견되지 않으면)
        return False
    
    def pre_validate_medicine_page(self, html_content, url):
        """
        HTML 내용을 사전 분석하여 실제 의약품 페이지인지 확인
        
        Args:
            html_content: HTML 내용
            url: 페이지 URL
                
        Returns:
            bool: 의약품 페이지면 True, 아니면 False
        """
        # URL 패턴으로 빠른 확인
        if 'medicinedic' in url.lower():
            return True
            
        # HTML 파싱
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출
        title_elements = soup.select('h2.title, h3.title, h1.title, .article_header h2, .main_title')
        
        if title_elements:
            title = title_elements[0].get_text().strip()
            
            # 제약회사 이름 패턴 확인
            company_keywords = ['제약', '(주)', '바이오', '파마', '약품', '바이오택', '생명과학']
            if any(keyword in title for keyword in company_keywords):
                self.logger.info(f"제약회사 관련 페이지로 판단: {title}")
                return False
        
        # 의약품 관련 주요 섹션 검색
        medicine_sections = ['효능효과', '용법용량', '성분', '주의사항', '저장방법', '사용상 주의사항']
        
        # 최소 2개 이상의 섹션이 존재해야 함
        section_count = 0
        for section in medicine_sections:
            if soup.find(text=re.compile(section)):
                section_count += 1
        
        if section_count >= 2:
            return True
        
        # 테이블 구조 분석 (의약품 정보는 주로 테이블 형태)
        tables = soup.select('table')
        for table in tables:
            rows = table.select('tr')
            for row in rows:
                if row.select('th') and row.select('td'):
                    header = row.select_one('th').get_text().strip()
                    # 의약품 특성 관련 헤더 확인
                    if any(term in header for term in ['성분', '효능', '용법', '분류', '제형', '성상']):
                        section_count += 1
        
        return section_count >= 2
        
    def filter_duplicates(self, items):
        """
        중복 항목 필터링
        
        Args:
            items: 검색 결과 항목 리스트
            
        Returns:
            list: 중복이 제거된 항목 리스트
        """
        filtered_items = []
        seen_urls = set()
        seen_titles = set()
        
        for item in items:
            title = BeautifulSoup(item['title'], 'html.parser').get_text()
            url = item['link']
            
            # URL이나 제목이 이미 처리된 경우 건너뜀
            if url in seen_urls or title in seen_titles:
                continue
            
            # 데이터베이스에 이미 있는지 확인
            if self.db_manager.is_duplicate(url, title):
                continue
            
            # 중복 체크 세트에 추가
            seen_urls.add(url)
            seen_titles.add(title)
            filtered_items.append(item)
        
        return filtered_items
    
    def process_search_item(self, item):
        """
        하나의 검색 결과 항목 처리
        
        Args:
            item: 처리할 검색 결과 항목
            
        Returns:
            bool: 성공적으로 처리되면 True, 아니면 False
        """
        try:
            title = BeautifulSoup(item['title'], 'html.parser').get_text()
            url = item['link']
            
            self.logger.info(f"약품 정보 수집 중: {title} ({url})")
            
            # HTML 내용 가져오기
            html_content = self.api_client.get_html_content(url)
            if not html_content:
                self.logger.warning(f"HTML 내용을 가져올 수 없음: {url}")
                return False
            
            # HTML 파싱
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 의약품 정보 파싱
            medicine_data = self.parser.parse_medicine_detail(soup, url, title)
            if not medicine_data:
                self.logger.warning(f"약품 정보를 파싱할 수 없음: {title}")
                return False
            
            # 데이터 검증
            validation_result = self.parser.validate_medicine_data(medicine_data)
            if not validation_result['is_valid']:
                self.logger.warning(f"약품 데이터 유효성 검사 실패: {title}, 이유: {validation_result['reason']}")
                return False
            
            # 이미지가 있으면 다운로드
            if medicine_data.get('item_image'):
                local_image_path = self.api_client.download_image(
                    medicine_data['item_image'], 
                    medicine_data['item_name']
                )
                if local_image_path:
                    medicine_data['item_image'] = local_image_path
            
            # 데이터 해시 생성
            medicine_data['data_hash'] = generate_data_hash(medicine_data)
            
            # 데이터베이스에 저장
            result = self.db_manager.save_medicine_to_db(medicine_data)
            if result:
                self.logger.info(f"약품 정보 저장 완료: {title}")
                return True
            else:
                self.logger.warning(f"약품 정보 저장 실패: {title}")
                return False
                
        except Exception as e:
            self.logger.error(f"검색 항목 처리 중 오류 발생: {str(e)}", exc_info=True)
            return False
    
    def process_search_results(self, search_results):
        """
        검색 결과 처리
        
        Args:
            search_results: 검색 결과 항목 리스트
            
        Returns:
            tuple: (처리된 항목 수, 의약품 항목 수, 중복 항목 수)
        """
        if not search_results or 'items' not in search_results or not search_results['items']:
            return 0, 0, 0
        
        total_items = len(search_results['items'])
        medicine_items = []
        
        # 의약품 항목 필터링
        for item in search_results['items']:
            if self.is_medicine_item(item):
                medicine_items.append(item)
        
        # 중복 항목 필터링
        filtered_items = self.filter_duplicates(medicine_items)
        
        # 결과 처리
        processed_count = 0
        for item in filtered_items:
            success = self.process_search_item(item)
            if success:
                processed_count += 1
        
        return processed_count, len(medicine_items), len(medicine_items) - len(filtered_items)
    
    def fetch_keyword_data(self, keyword, max_results=1000):
        """
        특정 키워드에 대한 데이터 수집
        
        Args:
            keyword: 검색 키워드
            max_results: 최대 결과 수
            
        Returns:
            tuple: (수집된 항목 수, API 호출 횟수)
        """
        fetched_items = 0
        api_calls = 0
        
        self.logger.info(f"키워드 '{keyword}' 검색 시작")
        
        # 예상 결과 수 확인 (API 호출 1회)
        initial_result = self.api_client.search_medicine(keyword, display=1, start=1)
        api_calls += 1
        
        if not initial_result or 'total' not in initial_result:
            self.logger.warning(f"키워드 '{keyword}'에 대한 검색 결과가 없거나 API 응답 오류")
            return 0, api_calls
        
        keyword_total = min(int(initial_result['total']), max_results)
        self.logger.info(f"키워드 '{keyword}'에 대한 예상 결과 수: {keyword_total}")
        
        # 결과 페이지네이션
        start = 1
        display = Config.DEFAULT_SEARCH_DISPLAY
        
        while start <= max_results and not self.api_client.check_api_limit():
            # API 호출 간 딜레이
            time.sleep(Config.API_DELAY)
            
            self.logger.info(f"'{keyword}' 검색 결과 {start}~{start+display-1} 요청 중...")
            result = self.api_client.search_medicine(keyword, display=display, start=start)
            api_calls += 1
            
            if not result or 'items' not in result or not result['items']:
                self.logger.info(f"'{keyword}'에 대한 추가 결과 없음 또는 마지막 페이지 도달")
                break
            
            # 검색 결과 처리
            processed, medicine_count, duplicate_count = self.process_search_results(result)
            fetched_items += processed
            
            self.logger.info(
                f"처리 완료: {processed}개 항목 추가, {medicine_count}개 의약품 항목 감지, {duplicate_count}개 중복 항목 건너뜀"
            )
            
            # 다음 페이지로 이동
            start += display
            
            # 결과 수가 display보다 적으면 마지막 페이지
            if len(result['items']) < display:
                break
        
        self.logger.info(f"키워드 '{keyword}' 검색 완료: {fetched_items}개 수집, API 호출 {api_calls}회")
        return fetched_items, api_calls
    
    async def fetch_keyword_data_async(self, keyword, max_results=1000):
        """
        특정 키워드에 대한 데이터 수집 (비동기 버전)
        
        Args:
            keyword: 검색 키워드
            max_results: 최대 결과 수
            
        Returns:
            tuple: (수집된 항목 수, API 호출 횟수)
        """
        fetched_items = 0
        api_calls = 0
        
        self.logger.info(f"[Async] 키워드 '{keyword}' 검색 시작")
        
        # 예상 결과 수 확인 (API 호출 1회)
        initial_result = await self.api_client.search_medicine_async(keyword, display=1, start=1)
        api_calls += 1
        
        if not initial_result or 'total' not in initial_result:
            self.logger.warning(f"[Async] 키워드 '{keyword}'에 대한 검색 결과가 없거나 API 응답 오류")
            return 0, api_calls
        
        keyword_total = min(int(initial_result['total']), max_results)
        self.logger.info(f"[Async] 키워드 '{keyword}'에 대한 예상 결과 수: {keyword_total}")
        
        # 결과 페이지네이션
        tasks = []
        for start in range(1, min(keyword_total + 1, max_results + 1), Config.DEFAULT_SEARCH_DISPLAY):
            # API 한도 체크
            if self.api_client.check_api_limit():
                break
                
            # 작업 추가
            tasks.append(self.api_client.search_medicine_async(
                keyword, 
                display=Config.DEFAULT_SEARCH_DISPLAY, 
                start=start
            ))
            
            # API 호출 횟수 업데이트
            api_calls += 1
            
            # 동시 요청이 너무 많지 않도록 작업 배치 처리
            if len(tasks) >= 5:  # 최대 5개 요청 동시 처리
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Exception):
                        self.logger.error(f"[Async] API 요청 실패: {result}")
                        continue
                        
                    if not result or 'items' not in result or not result['items']:
                        continue
                        
                    # 검색 결과 처리 (비동기 함수에서는 동기 함수 호출에 주의)
                    processed, medicine_count, duplicate_count = self.process_search_results(result)
                    fetched_items += processed
                
                # 작업 목록 초기화
                tasks = []
                
                # API 딜레이
                await asyncio.sleep(Config.API_DELAY)
        
        # 남은 작업 처리
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    self.logger.error(f"[Async] API 요청 실패: {result}")
                    continue
                    
                if not result or 'items' not in result or not result['items']:
                    continue
                    
                processed, medicine_count, duplicate_count = self.process_search_results(result)
                fetched_items += processed
        
        self.logger.info(f"[Async] 키워드 '{keyword}' 검색 완료: {fetched_items}개 수집, API 호출 {api_calls}회")
        return fetched_items, api_calls
    
class MedicineParser:
    """
    의약품 정보 파싱을 담당하는 클래스
    """
    def __init__(self, logger):
        """
        의약품 파서 초기화
        
        Args:
            logger: 로깅 객체
        """
        self.logger = logger
    
    def find_medicine_image_url(self, soup, base_url):
        """
        약품 이미지 URL을 다양한 선택자와 패턴으로 찾기
        
        Args:
            soup: BeautifulSoup 객체
            base_url: 기본 URL (상대 경로를 절대 경로로 변환할 때 사용)
        
        Returns:
            str: 찾은 이미지 URL 또는 빈 문자열
        """
        # 이미지를 찾기 위한 선택자들 (우선순위 순)
        selectors = [
            'div.medicinedic_img img',      # 의약품 사전 이미지
            'div.image_area img',           # 네이버 지식백과 일반적인 이미지 영역
            'div.img_box img',              # 이미지 박스
            'div.thumb_area img',           # 썸네일 영역
            'div.drug_info_img img',        # 약품 정보 이미지
            'img.drug_image',               # 약품 이미지 클래스
            'div.item_image img',           # 항목 이미지
            'div.med_img img',              # 약품 이미지 영역
            '.medicine-image',              # 약품 이미지 클래스
            '.item-image',                  # 항목 이미지 클래스
            'div.media_end_content img',    # 네이버 콘텐츠 이미지
            'div.figure_area img',          # 그림 영역
            'div.center_img img',           # 중앙 이미지
            'div.medi_wrap img',            # 약품 래퍼 영역
            'div.medi_img img',             # 약품 이미지 영역
            'div.article_body img',         # 본문 이미지
        ]
        
        # 이미지 속성 추가 패턴
        img_attr_patterns = [
            {'src': ['medicinedic', 'drug', 'medicine', 'pill', 'pharm']},
            {'alt': ['약품', '의약품', '정', '캡슐', '주사']},
            {'class': ['drug', 'medicine', 'pill', 'pharm', 'item']}
        ]
        
        # 각 선택자에 대해 이미지 찾기 시도
        for selector in selectors:
            img_tag = soup.select_one(selector)
            if img_tag and 'src' in img_tag.attrs:
                img_url = img_tag['src']
                
                # 상대 경로인 경우 절대 경로로 변환
                if not img_url.startswith(('http://', 'https://')):
                    img_url = urllib.parse.urljoin(base_url, img_url)
                
                self.logger.info(f"이미지 URL 찾음 ({selector}): {img_url}")
                return img_url
        
        # 모든 이미지 태그 검사
        all_imgs = soup.find_all('img')
        
        # 약품 이미지 패턴에 맞는 이미지 찾기
        for img in all_imgs:
            if 'src' not in img.attrs:
                continue
                
            src = img['src']
            
            # 속성 패턴 검사
            for attr_pattern in img_attr_patterns:
                for attr, patterns in attr_pattern.items():
                    if attr in img.attrs:
                        attr_value = img[attr].lower()
                        if any(pattern in attr_value for pattern in patterns):
                            img_url = src
                            if not img_url.startswith(('http://', 'https://')):
                                img_url = urllib.parse.urljoin(base_url, img_url)
                            
                            self.logger.info(f"이미지 URL 찾음 (속성 패턴 매칭): {img_url}")
                            return img_url
            
            # 약품 이미지일 가능성이 높은 패턴 확인
            if any(pattern in src.lower() for pattern in ['drug', 'medi', 'pill', 'pharm', 'item']):
                img_url = src
                if not img_url.startswith(('http://', 'https://')):
                    img_url = urllib.parse.urljoin(base_url, img_url)
                
                self.logger.info(f"이미지 URL 찾음 (URL 패턴 매칭): {img_url}")
                return img_url
        
        # 이미지 크기를 기반으로 메인 이미지를 추정
        main_image = None
        main_image_area = 0
        
        for img in all_imgs:
            if 'src' not in img.attrs:
                continue
                
            # 광고, 아이콘 등 작은 이미지 제외
            width = int(img.get('width', '0').replace('px', '').strip() or '0')
            height = int(img.get('height', '0').replace('px', '').strip() or '0')
            
            # 너비와 높이를 가져올 수 없으면 style 속성에서 추출 시도
            if width == 0 or height == 0:
                style = img.get('style', '')
                width_match = re.search(r'width\s*:\s*(\d+)px', style)
                height_match = re.search(r'height\s*:\s*(\d+)px', style)
                
                width = int(width_match.group(1)) if width_match else 0
                height = int(height_match.group(1)) if height_match else 0
            
            # 면적 계산
            area = width * height
            
            # 최소 크기 이상이고 현재까지 찾은 이미지보다 큰 경우 갱신
            if area > 10000 and area > main_image_area:  # 최소 100x100 이상
                main_image_area = area
                main_image = img
        
        # 가장 큰 이미지 반환
        if main_image and 'src' in main_image.attrs:
            img_url = main_image['src']
            if not img_url.startswith(('http://', 'https://')):
                img_url = urllib.parse.urljoin(base_url, img_url)
            
            self.logger.info(f"이미지 URL 찾음 (크기 기반): {img_url}")
            return img_url
        
        self.logger.warning(f"이미지 URL을 찾을 수 없음")
        return ""
    
    def clean_html(self, html_text):
        """
        HTML 태그 제거 및 텍스트 정리
        
        Args:
            html_text: 정리할 HTML 텍스트
        
        Returns:
            str: 정리된 텍스트
        """
        if not html_text:
            return ""
        
        # BeautifulSoup으로 HTML 파싱
        soup = BeautifulSoup(html_text, 'html.parser')
        
        # 모든 script, style 태그 제거
        for tag in soup(['script', 'style']):
            tag.decompose()
        
        # 텍스트 추출 및 정리
        text = soup.get_text('\n', strip=True)
        
        # 불필요한 공백 제거
        text = re.sub(r'\s+', ' ', text)  # 연속된 공백 제거
        text = re.sub(r'(\n\s*)+', '\n', text)  # 연속된 줄바꿈 제거
        
        return text.strip()
    
    def parse_medicine_detail(self, soup, url, title):
        """
        약품 상세 페이지에서 정보 파싱
        
        Args:
            soup: BeautifulSoup 객체
            url: 약품 상세 페이지 URL
            title: 약품 제목
            
        Returns:
            dict: 파싱된 약품 정보 또는 None (실패 시)
        """
        try:
            self.logger.info(f"약품 '{title}' 상세 정보 파싱 시작")
            
            # 기본 정보 초기화
            medicine_data = {
                'item_name': title,
                'item_eng_name': '',
                'entp_name': '',
                'chart': '',
                'class_no': '',
                'class_name': '',
                'etc_otc_name': '',
                'form_code_name': '',
                'drug_shape': '',
                'color_class1': '',
                'leng_long': '',
                'leng_short': '',
                'thick': '',
                'print_front': '',
                'print_back': '',
                'edi_code': '',
                'efcy_qesitm': '',
                'use_method_qesitm': '',
                'deposit_method_qesitm': '',
                'atpn_qesitm': '',
                'atpn_warn_qesitm': '',
                'se_qesitm': '',
                'intrc_qesitm': '',
                'caution_details': '',
                'url': url
            }
            
            # 이미지 URL 찾기
            image_url = self.find_medicine_image_url(soup, url)
            if image_url:
                medicine_data['item_image'] = image_url
            
            # 영문명 찾기
            eng_name_match = re.search(r'\[(.*?)\]', title)
            if eng_name_match:
                medicine_data['item_eng_name'] = eng_name_match.group(1).strip()
            
            # 모든 테이블 검색하여 정보 추출
            tables = soup.select('table')
            for table in tables:
                rows = table.select('tr')
                for row in rows:
                    if row.select_one('th') and row.select_one('td'):
                        header = row.select_one('th').get_text().strip()
                        value = row.select_one('td').get_text().strip()
                        
                        # 헤더에 따라 적절한 필드 매핑
                        if '업체명' in header:
                            medicine_data['entp_name'] = value
                        elif '분류' in header:
                            # 분류 코드와 이름 분리 (예: "[02390]기타의 소화기관용약")
                            class_match = re.search(r'\[(.*?)\](.*)', value)
                            if class_match:
                                medicine_data['class_no'] = class_match.group(1).strip()
                                medicine_data['class_name'] = class_match.group(2).strip()
                            else:
                                medicine_data['class_name'] = value
                        elif '구분' in header:
                            medicine_data['etc_otc_name'] = value
                        elif '성상' in header:
                            medicine_data['chart'] = value
                        elif '제형' in header:
                            medicine_data['form_code_name'] = value
                        elif '보험코드' in header:
                            medicine_data['edi_code'] = value
                        elif '모양' in header:
                            medicine_data['drug_shape'] = value
                        elif '색깔' in header or '색상' in header:
                            medicine_data['color_class1'] = value
                        elif '크기' in header:
                            size_parts = value.split(',')
                            for part in size_parts:
                                if '장축' in part:
                                    length_match = re.search(r'[\d\.]+', part)
                                    if length_match:
                                        medicine_data['leng_long'] = length_match.group(0)
                                elif '단축' in part:
                                    width_match = re.search(r'[\d\.]+', part)
                                    if width_match:
                                        medicine_data['leng_short'] = width_match.group(0)
                                elif '두께' in part:
                                    thick_match = re.search(r'[\d\.]+', part)
                                    if thick_match:
                                        medicine_data['thick'] = thick_match.group(0)
                        elif '식별표기' in header:
                            # 식별표기 분리
                            medicine_data['print_front'] = value
            
            # 목차 찾기
            toc = soup.select_one('.toc')
            section_titles = ['성분정보', '효능효과', '용법용량', '저장방법', '사용기간', '사용상의주의사항']
            
            # 각 섹션에 대응하는 내용 추출
            for title in section_titles:
                section_heading = soup.find(lambda tag: tag.name in ['h2', 'h3', 'h4'] and title in tag.get_text())
                if section_heading:
                    section_content = []
                    current = section_heading.next_sibling
                    
                    # 다음 제목까지의 모든 내용 추출
                    while current and not (current.name in ['h2', 'h3', 'h4'] and any(t in current.get_text() for t in section_titles)):
                        if hasattr(current, 'name'):
                            section_content.append(str(current))
                        current = current.next_sibling
                    
                    content = ''.join(section_content).strip()
                    
                    # 섹션별 매핑
                    if title == '효능효과':
                        medicine_data['efcy_qesitm'] = self.clean_html(content)
                    elif title == '용법용량':
                        medicine_data['use_method_qesitm'] = self.clean_html(content)
                    elif title == '저장방법':
                        medicine_data['deposit_method_qesitm'] = self.clean_html(content)
                    elif title == '사용상의주의사항':
                        # 전체 사용상의 주의사항 저장
                        medicine_data['caution_details'] = self.clean_html(content)
            
            # 사용상의 주의사항이 있으면 섹션 파싱
            if medicine_data['caution_details']:
                precaution_sections = self.parse_precautions(medicine_data['caution_details'])
                medicine_data.update(precaution_sections)
            
            return self.check_medicine_data_completeness(medicine_data)
            
        except Exception as e:
            self.logger.error(f"상세 페이지 파싱 중 오류: {str(e)}", exc_info=True)
            return None
    
    def parse_precautions(self, precautions_text):
        """
        사용상의주의사항 텍스트를 여러 카테고리로 파싱
        
        Args:
            precautions_text: 사용상의주의사항 텍스트
            
        Returns:
            dict: 파싱된 주의사항
        """
        result = {
            'atpn_warn_qesitm': '',  # 경고/투여금기
            'atpn_qesitm': '',       # 일반 주의사항
            'intrc_qesitm': '',      # 상호작용
            'se_qesitm': ''          # 부작용/이상반응
        }
        
        if not precautions_text:
            return result
        
        # 텍스트 정규화
        text = re.sub(r'\s+', ' ', precautions_text)
        
        # 주요 섹션 패턴 정의
        section_patterns = [
            # 경고/투여금기
            (r'(?:1\.|[0-9]+\.\s*)?다음\s*환자에게는\s*투여하지\s*말\s*것.*?(?=\d+\.\s|$)', 'atpn_warn_qesitm'),
            # 이상반응/부작용
            (r'(?:2\.|[0-9]+\.\s*)?이상반응.*?(?=\d+\.\s|$)', 'se_qesitm'),
            # 일반적 주의
            (r'(?:3\.|[0-9]+\.\s*)?일반적\s*주의.*?(?=\d+\.\s|$)', 'atpn_qesitm'),
            # 상호작용
            (r'(?:4\.|[0-9]+\.\s*)?상호작용.*?(?=\d+\.\s|$)', 'intrc_qesitm'),
        ]
        
        # 전체 텍스트에서 각 섹션을 순차적으로 추출
        for pattern, field in section_patterns:
            matches = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if matches:
                content = matches.group(0).strip()
                result[field] = content
        
        # 기타 추가 섹션들 처리
        other_sections = [
            (r'(?:[0-9]+\.\s*)?임부.*?(?=\d+\.\s|$)', 'atpn_qesitm'),
            (r'(?:[0-9]+\.\s*)?소아.*?(?=\d+\.\s|$)', 'atpn_qesitm'),
            (r'(?:[0-9]+\.\s*)?고령자.*?(?=\d+\.\s|$)', 'atpn_qesitm'),
            (r'(?:[0-9]+\.\s*)?보관.*?(?=\d+\.\s|$)', 'atpn_qesitm')
        ]
        
        for pattern, field in other_sections:
            matches = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if matches:
                content = matches.group(0).strip()
                # 이미 내용이 있으면 추가
                if result[field]:
                    result[field] += "\n\n" + content
                else:
                    result[field] = content
        
        # 일반 주의사항이 비어있고 다른 항목도 모두 비어있으면
        # 전체 내용을 일반 주의사항으로 설정
        if not any(result.values()):
            result['atpn_qesitm'] = text
        
        return result
    
    def check_medicine_data_completeness(self, medicine_data):
        """
        약품 데이터의 완전성을 체크하고 로깅
        
        Args:
            medicine_data: 검증할 약품 데이터
            
        Returns:
            dict: 검증 결과가 포함된 약품 데이터
        """
        # 필수 필드와 선택적 필드 정의
        required_fields = ['item_name', 'url']
        detail_fields = {
            '기본 정보': ['item_eng_name', 'entp_name', 'class_no', 'class_name', 'etc_otc_name', 'chart', 'edi_code'],
            '물리적 특성': ['drug_shape', 'color_class1', 'leng_long', 'leng_short', 'thick', 'print_front', 'print_back', 'item_image'],
            '효능/용법': ['efcy_qesitm', 'use_method_qesitm', 'deposit_method_qesitm'],
            '주의사항': ['atpn_qesitm', 'atpn_warn_qesitm', 'se_qesitm', 'intrc_qesitm', 'caution_details']
        }
        
        # 기본 정보 로깅
        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"약품 '{medicine_data['item_name']}' 데이터 수집 결과")
        self.logger.info(f"URL: {medicine_data['url']}")
        
        # 필수 필드 체크
        missing_required = [field for field in required_fields if not medicine_data.get(field)]
        if missing_required:
            self.logger.warning(f"⚠️ 필수 필드 누락: {', '.join(missing_required)}")
        else:
            self.logger.info(f"✅ 모든 필수 필드가 수집되었습니다.")
        
        # 카테고리별 필드 체크
        for category, fields in detail_fields.items():
            collected = []
            missing = []
            
            for field in fields:
                if medicine_data.get(field):
                    collected.append(field)
                else:
                    missing.append(field)
            
            total = len(fields)
            collected_count = len(collected)
            
            # 수집률 계산 및 색상 적용
            collection_rate = collected_count / total * 100
            if collection_rate >= 80:
                rate_color = Fore.GREEN
            elif collection_rate >= 50:
                rate_color = Fore.YELLOW
            else:
                rate_color = Fore.RED
                
            self.logger.info(f"{category}: {rate_color}{collected_count}/{total} ({collection_rate:.1f}%){Style.RESET_ALL}")
            
            if missing:
                self.logger.info(f"  - 미수집 필드: {', '.join(missing)}")
        
        # 전체 수집률
        all_fields = sum([len(fields) for fields in detail_fields.values()]) + len(required_fields)
        filled_fields = sum([1 for field, value in medicine_data.items() if value and field in required_fields + sum(detail_fields.values(), [])])
        total_rate = filled_fields / all_fields * 100
        
        if total_rate >= 80:
            total_color = Fore.GREEN
        elif total_rate >= 50:
            total_color = Fore.YELLOW
        else:
            total_color = Fore.RED
        
        self.logger.info(f"전체 수집률: {total_color}{total_rate:.1f}%{Style.RESET_ALL}")
        self.logger.info(f"{'='*50}")
        
        return medicine_data
    
    def validate_medicine_data(self, medicine_data):
        """
        약품 데이터 유효성 검증
        
        Args:
            medicine_data: 검증할 약품 데이터
            
        Returns:
            dict: 검증 결과
        """
        result = {
            'is_valid': True,
            'reason': '',
            'missing_fields': [],
            'empty_fields': [],
            'quality_score': 0
        }
        
        # 필수 필드 정의
        required_fields = ['item_name', 'url']
        
        # 중요 필드 정의 (있으면 가산점)
        important_fields = [
            'entp_name', 'class_name', 'etc_otc_name', 'item_image',
            'efcy_qesitm', 'use_method_qesitm', 'caution_details'
        ]
        
        # 필수 필드 검증
        for field in required_fields:
            if field not in medicine_data:
                result['is_valid'] = False
                result['missing_fields'].append(field)
            elif not medicine_data[field]:
                result['empty_fields'].append(field)
        
        # 필수 필드가 누락됐으면 유효하지 않음
        if result['missing_fields']:
            result['is_valid'] = False
            result['reason'] = f"필수 필드 누락: {', '.join(result['missing_fields'])}"
            return result
        
        # 최소한의 중요 정보가 있는지 확인
        present_important_fields = [f for f in important_fields if medicine_data.get(f)]
        quality_score = len(present_important_fields) / len(important_fields) * 100
        
        result['quality_score'] = quality_score
        
        # 품질 점수가 너무 낮으면 유효하지 않음
        if quality_score < 30:  # 30% 미만일 경우
            result['is_valid'] = False
            result['reason'] = f"데이터 품질 점수가 너무 낮음: {quality_score:.1f}%"
        
        # 기본 정보가 전혀 없으면 유효하지 않음
        if not any([medicine_data.get(f) for f in ['entp_name', 'class_name', 'etc_otc_name']]):
            result['is_valid'] = False
            result['reason'] = "기본 약품 정보가 전혀 없음"
        
        # 효능/용법/주의사항 정보가 전혀 없으면 유효하지 않음
        if not any([medicine_data.get(f) for f in ['efcy_qesitm', 'use_method_qesitm', 'caution_details']]):
            result['is_valid'] = False
            result['reason'] = "효능, 용법, 주의사항 정보가 전혀 없음"
        
        return result
    
class DatabaseManager:
    """
    데이터베이스 관리를 담당하는 클래스
    """
    def __init__(self, db_path, logger):
        """
        데이터베이스 관리자 초기화
        
        Args:
            db_path: SQLite DB 파일 경로
            logger: 로깅 객체
        """
        self.db_path = db_path
        self.logger = logger
        self.init_db()
    
    def init_db(self):
        """
        데이터베이스 초기화 및 테이블 생성
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        self.logger.info(f"데이터베이스 연결 완료: {self.db_path}")
        
        # 테이블 정보 확인 로깅
        self.logger.debug("SQLite 마스터 테이블 조회 중...")
        cursor.execute("SELECT name, type FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        self.logger.info(f"데이터베이스 내 테이블 목록: {[table[0] for table in tables]}")
        
        # 각 테이블 생성 또는 확인
        for table_name, table_schema in Config.DB_TABLES.items():
            # 테이블 존재 여부 확인
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            if cursor.fetchone():
                self.logger.info(f"테이블 '{table_name}' 이미 존재함")
                
                # 컬럼 정보 조회
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]
                self.logger.info(f"테이블 '{table_name}' 컬럼 목록: {column_names}")
                
                # 필요한 컬럼 추가
                missing_columns = []
                if table_name == 'api_medicine':
                    if 'data_hash' not in column_names:
                        missing_columns.append(('data_hash', 'TEXT'))
                    if 'caution_details' not in column_names:
                        missing_columns.append(('caution_details', 'TEXT'))
                
                # 누락된 컬럼 추가
                for col_name, col_type in missing_columns:
                    try:
                        self.logger.info(f"테이블 '{table_name}'에 컬럼 '{col_name}' 추가 시도")
                        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
                        self.logger.info(f"컬럼 '{col_name}' 추가 완료")
                    except sqlite3.OperationalError as e:
                        self.logger.error(f"컬럼 '{col_name}' 추가 실패: {e}")
            else:
                # 테이블이 없으면 생성
                try:
                    self.logger.info(f"테이블 '{table_name}' 생성 시도")
                    cursor.execute(table_schema)
                    self.logger.info(f"테이블 '{table_name}' 생성 완료")
                except sqlite3.OperationalError as e:
                    self.logger.error(f"테이블 '{table_name}' 생성 실패: {e}")
        
        # 인덱스 생성 시도
        try:
            self.logger.info("인덱스 생성 시도")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_medicine'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(api_medicine)")
                columns = [col[1] for col in cursor.fetchall()]
                
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_url ON api_medicine (url)')
                self.logger.info("URL 인덱스 생성 완료")
                
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_item_name ON api_medicine (item_name)')
                self.logger.info("item_name 인덱스 생성 완료")
                
                if 'data_hash' in columns:
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_data_hash ON api_medicine (data_hash)')
                    self.logger.info("data_hash 인덱스 생성 완료")
                else:
                    self.logger.warning("data_hash 컬럼이 없어 인덱스 생성 생략")
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_calls'")
            if cursor.fetchone():
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_api_calls_date ON api_calls (date)')
                self.logger.info("api_calls_date 인덱스 생성 완료")
        except sqlite3.OperationalError as e:
            self.logger.error(f"인덱스 생성 중 오류 발생: {e}")
        
        conn.commit()
        conn.close()
        
        self.logger.info("데이터베이스 초기화 완료")
    
    def get_connection(self):
        """
        데이터베이스 연결 객체 반환
        
        Returns:
            sqlite3.Connection: SQLite 연결 객체
        """
        return sqlite3.connect(self.db_path)
    
    def get_tables_info(self):
        """
        데이터베이스 테이블 정보 조회
        
        Returns:
            dict: 테이블별 레코드 수
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.logger.info("데이터베이스 테이블 정보 조회 시작")
        
        # 먼저 DB에 실제로 어떤 테이블이 있는지 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        actual_tables = [row[0] for row in cursor.fetchall()]
        self.logger.info(f"데이터베이스에 실제 존재하는 테이블: {actual_tables}")
        
        result = {}
        
        # 각 테이블의 레코드 수 조회
        for table_name in Config.DB_TABLES.keys():
            try:
                self.logger.debug(f"테이블 '{table_name}' 레코드 수 조회 시도")
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                result[table_name] = count
                self.logger.info(f"테이블 '{table_name}'의 레코드 수: {count}")
            except sqlite3.OperationalError as e:
                self.logger.error(f"테이블 '{table_name}' 레코드 수 조회 실패: {e}")
                result[table_name] = 0
        
        conn.close()
        self.logger.info("데이터베이스 테이블 정보 조회 완료")
        return result
    
    def is_duplicate(self, url, title=None):
        """
        URL 또는 제목으로 중복 검사
        
        Args:
            url: 약품 상세 페이지 URL
            title: 약품 제목 (선택적)
            
        Returns:
            bool: 중복이면 True, 아니면 False
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # URL로 중복 검사
        cursor.execute("SELECT id FROM api_medicine WHERE url = ?", (url,))
        url_match = cursor.fetchone()
        
        # URL 매치가 있으면 바로 중복으로 판단
        if url_match:
            conn.close()
            return True
        
        # 제목이 제공된 경우, 제목으로 중복 검사
        if title:
            # 정확히 일치하는 경우
            cursor.execute("SELECT id FROM api_medicine WHERE item_name = ?", (title,))
            exact_title_match = cursor.fetchone()
            
            if exact_title_match:
                conn.close()
                return True
            
            # 유사 제목 검사 (제목에 대괄호나 소괄호가 포함된 경우)
            base_title = re.sub(r'\[.*?\]|\(.*?\)', '', title).strip()
            if base_title != title and len(base_title) > 3:  # 기본 제목이 최소 4자 이상인 경우만
                # LIKE 연산자를 사용한 유사 검색
                cursor.execute("SELECT id FROM api_medicine WHERE item_name LIKE ?", (f"%{base_title}%",))
                similar_title_match = cursor.fetchone()
                
                if similar_title_match:
                    conn.close()
                    return True
        
        conn.close()
        return False
    
    def is_content_duplicate(self, data_hash):
        """
        데이터 해시를 사용한 콘텐츠 중복 검사
        
        Args:
            data_hash: 약품 데이터의 해시값
            
        Returns:
            bool: 중복이면 True, 아니면 False
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM api_medicine WHERE data_hash = ?", (data_hash,))
        hash_match = cursor.fetchone()
        
        conn.close()
        return bool(hash_match)
    
    def save_medicine_to_db(self, medicine_data):
        """
        약품 정보를 데이터베이스에 저장
        
        Args:
            medicine_data: 약품 정보 딕셔너리
            
        Returns:
            bool: 성공적으로 저장되면 True, 아니면 False
        """
        try:
            # 데이터 해시 확인 (해시가 없으면 새로 생성)
            if 'data_hash' not in medicine_data:
                medicine_data['data_hash'] = generate_data_hash(medicine_data)
            
            # 해시로 콘텐츠 중복 검사
            if self.is_content_duplicate(medicine_data['data_hash']):
                self.logger.info(f"콘텐츠 중복으로 건너뜀: {medicine_data['item_name']}")
                return False
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 컬럼 이름 목록
            columns = [key for key in medicine_data.keys()]
            placeholders = ', '.join(['?' for _ in columns])
            column_str = ', '.join(columns)
            
            # 데이터 준비
            values = tuple(medicine_data.get(col, '') for col in columns)
            
            # 삽입 쿼리 실행
            cursor.execute(f"""
            INSERT INTO api_medicine ({column_str}) 
            VALUES ({placeholders})
            """, values)
            
            conn.commit()
            
            # 삽입된 row ID 확인
            inserted_id = cursor.lastrowid
            conn.close()
            
            self.logger.info(f"약품 정보 저장 완료 (ID: {inserted_id}): {medicine_data['item_name']}")
            return True
            
        except Exception as e:
            self.logger.error(f"약품 정보 저장 중 오류: {str(e)}", exc_info=True)
            return False
    
    def update_medicine_in_db(self, medicine_id, update_data):
        """
        기존 약품 정보 업데이트
        
        Args:
            medicine_id: 업데이트할 약품의 ID
            update_data: 업데이트할 필드와 값 딕셔너리
            
        Returns:
            bool: 성공적으로 업데이트되면 True, 아니면 False
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 업데이트 쿼리 생성
            set_clause = ', '.join([f"{key} = ?" for key in update_data.keys()])
            values = list(update_data.values())
            values.append(medicine_id)  # WHERE 절의 ID에 대한 값
            
            # 업데이트 시간 추가
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            set_clause += ", updated_at = ?"
            values.append(now)
            
            # 쿼리 실행
            cursor.execute(f"""
            UPDATE api_medicine 
            SET {set_clause}
            WHERE id = ?
            """, values)
            
            conn.commit()
            
            # 업데이트 성공 여부 확인
            if cursor.rowcount > 0:
                self.logger.info(f"약품 정보 업데이트 완료 (ID: {medicine_id})")
                result = True
            else:
                self.logger.warning(f"약품 정보 업데이트 실패 (ID: {medicine_id}): 해당 ID를 찾을 수 없음")
                result = False
            
            conn.close()
            return result
            
        except Exception as e:
            self.logger.error(f"약품 정보 업데이트 중 오류: {str(e)}", exc_info=True)
            return False
    
    def get_medicine_by_id(self, medicine_id):
        """
        ID로 약품 정보 조회
        
        Args:
            medicine_id: 조회할 약품의 ID
            
        Returns:
            dict: 약품 정보 또는 None (찾지 못한 경우)
        """
        try:
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row  # 컬럼명으로 접근 가능하게 설정
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM api_medicine WHERE id = ?", (medicine_id,))
            row = cursor.fetchone()
            
            conn.close()
            
            if row:
                # sqlite3.Row 객체를 딕셔너리로 변환
                return {key: row[key] for key in row.keys()}
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"약품 정보 조회 중 오류: {str(e)}", exc_info=True)
            return None
    
    def get_medicine_by_name(self, name, limit=10):
        """
        이름으로 약품 정보 검색
        
        Args:
            name: 검색할 약품 이름 (부분 일치)
            limit: 반환할 최대 결과 수
            
        Returns:
            list: 약품 정보 목록
        """
        try:
            conn = self.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM api_medicine WHERE item_name LIKE ? ORDER BY id DESC LIMIT ?", 
                (f"%{name}%", limit)
            )
            rows = cursor.fetchall()
            
            conn.close()
            
            # sqlite3.Row 객체를 딕셔너리로 변환
            return [{key: row[key] for key in row.keys()} for row in rows]
                
        except Exception as e:
            self.logger.error(f"약품 이름 검색 중 오류: {str(e)}", exc_info=True)
            return []
    
    def get_medicine_stats(self):
        """
        약품 데이터 통계 정보 조회
        
        Returns:
            dict: 통계 정보
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 총 약품 수
            cursor.execute("SELECT COUNT(*) FROM api_medicine")
            total_count = cursor.fetchone()[0]
            
            # 제약사별 약품 수 (상위 10개)
            cursor.execute("""
                SELECT entp_name, COUNT(*) as count 
                FROM api_medicine 
                WHERE entp_name != '' 
                GROUP BY entp_name 
                ORDER BY count DESC 
                LIMIT 10
            """)
            companies = cursor.fetchall()
            
            # 분류별 약품 수 (상위 10개)
            cursor.execute("""
                SELECT class_name, COUNT(*) as count 
                FROM api_medicine 
                WHERE class_name != '' 
                GROUP BY class_name 
                ORDER BY count DESC 
                LIMIT 10
            """)
            categories = cursor.fetchall()
            
            # 제형별 약품 수
            cursor.execute("""
                SELECT form_code_name, COUNT(*) as count 
                FROM api_medicine 
                WHERE form_code_name != '' 
                GROUP BY form_code_name 
                ORDER BY count DESC 
                LIMIT 10
            """)
            forms = cursor.fetchall()
            
            # 날짜별 추가된 약품 수 (최근 10일)
            cursor.execute("""
                SELECT substr(created_at, 1, 10) as date, COUNT(*) as count 
                FROM api_medicine 
                GROUP BY date 
                ORDER BY date DESC 
                LIMIT 10
            """)
            daily_added = cursor.fetchall()
            
            conn.close()
            
            return {
                'total_count': total_count,
                'companies': companies,
                'categories': categories,
                'forms': forms,
                'daily_added': daily_added
            }
                
        except Exception as e:
            self.logger.error(f"약품 통계 조회 중 오류: {str(e)}", exc_info=True)
            return {
                'total_count': 0,
                'companies': [],
                'categories': [],
                'forms': [],
                'daily_added': []
            }
    
    def delete_medicine(self, medicine_id):
        """
        약품 정보 삭제
        
        Args:
            medicine_id: 삭제할 약품의 ID
            
        Returns:
            bool: 성공적으로 삭제되면 True, 아니면 False
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM api_medicine WHERE id = ?", (medicine_id,))
            
            conn.commit()
            
            # 삭제 성공 여부 확인
            if cursor.rowcount > 0:
                self.logger.info(f"약품 정보 삭제 완료 (ID: {medicine_id})")
                result = True
            else:
                self.logger.warning(f"약품 정보 삭제 실패 (ID: {medicine_id}): 해당 ID를 찾을 수 없음")
                result = False
            
            conn.close()
            return result
                
        except Exception as e:
            self.logger.error(f"약품 정보 삭제 중 오류: {str(e)}", exc_info=True)
            return False
    
    def vacuum_database(self):
        """
        데이터베이스 최적화 (VACUUM)
        
        Returns:
            bool: 성공적으로 최적화되면 True, 아니면 False
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # SQLite VACUUM 실행
            cursor.execute("VACUUM")
            
            conn.close()
            
            self.logger.info(f"데이터베이스 최적화 완료: {self.db_path}")
            return True
                
        except Exception as e:
            self.logger.error(f"데이터베이스 최적화 중 오류: {str(e)}", exc_info=True)
            return False
        
class NaverMedicineCrawler:
    """
    네이버 의약품 크롤링을 총괄하는 클래스
    """
    def __init__(self, client_id, client_secret, db_path=None):
        """
        네이버 의약품 크롤러 초기화
        
        Args:
            client_id: 네이버 API 클라이언트 ID
            client_secret: 네이버 API 클라이언트 시크릿
            db_path: 데이터베이스 파일 경로 (기본값: Config.DEFAULT_DB_PATH)
        """
        # 로거 설정
        self.logger = setup_logging()
        
        # 데이터베이스 경로 설정
        self.db_path = db_path or Config.DEFAULT_DB_PATH
        
        # 컴포넌트 초기화
        self.db_manager = DatabaseManager(self.db_path, self.logger)
        self.db_conn = self.db_manager.get_connection()
        self.api_client = NaverAPIClient(client_id, client_secret, self.db_conn, self.logger)
        self.parser = MedicineParser(self.logger)
        self.search_manager = SearchManager(self.api_client, self.db_manager, self.parser, self.logger)
        
        # 통계 카운터
        self.stats = {
            'total_items': 0,
            'fetched_items': 0,
            'skipped_items': 0,
            'api_calls': 0,
            'failed_items': 0
        }
        
        self.logger.info("네이버 의약품 크롤러 초기화 완료")
    
    def __del__(self):
        """소멸자: 리소스 정리"""
        try:
            if hasattr(self, 'db_conn') and self.db_conn:
                self.db_conn.close()
        except Exception:
            pass
    
    def fetch_all_medicine_data(self, keywords=None, max_results_per_keyword=1000, use_async=False):
        """
        여러 키워드에 대해 페이지네이션을 사용하여 모든 약품 데이터 수집
        
        Args:
            keywords: 검색 키워드 리스트 (None이면 자동 생성)
            max_results_per_keyword: 키워드당 최대 결과 수
            use_async: 비동기 방식 사용 여부
        """
        # 키워드가 제공되지 않으면 포괄적인 키워드 생성
        if keywords is None:
            keywords = generate_comprehensive_keywords()
        
        # 키워드 파일 관리
        completed_keywords = load_completed_keywords()
        in_progress_keyword = load_in_progress_keyword()
        failed_keywords = load_failed_keywords()
        
        self.logger.info(f"이미 완료된 키워드: {len(completed_keywords)}개")
        self.logger.info(f"실패한 키워드: {len(failed_keywords)}개")
        
        # 진행 중인 키워드 확인
        if in_progress_keyword:
            self.logger.info(f"이전에 중단된 키워드 '{in_progress_keyword}'부터 재개합니다.")
            # 진행 중인 키워드가 keywords에 없으면 추가
            if in_progress_keyword not in keywords:
                keywords = [in_progress_keyword] + keywords
        
        # 남은 키워드 필터링
        remaining_keywords = [k for k in keywords if k not in completed_keywords and k not in failed_keywords]
        self.logger.info(f"처리할 남은 키워드: {len(remaining_keywords)}개")
        
        # 진행 중인 키워드가 있으면 맨 앞으로 이동
        if in_progress_keyword and in_progress_keyword in remaining_keywords:
            remaining_keywords.remove(in_progress_keyword)
            remaining_keywords.insert(0, in_progress_keyword)
        
        # 통계 초기화
        self.stats = {
            'total_items': 0,
            'fetched_items': 0,
            'skipped_items': 0,
            'api_calls': 0,
            'failed_items': 0
        }
        
        # 메인 프로그레스 바 초기화
        main_progress = tqdm(total=len(remaining_keywords), desc="키워드 진행률", unit="키워드",
                            bar_format="{l_bar}%s{bar}%s{r_bar}" % (Fore.GREEN, Style.RESET_ALL))
        
        # 키워드별 데이터 수집
        try:
            if use_async:
                # 비동기 실행이 요청된 경우 asyncio 이벤트 루프 생성
                loop = asyncio.get_event_loop()
                loop.run_until_complete(self._process_keywords_async(remaining_keywords, max_results_per_keyword, main_progress))
            else:
                # 동기 방식 실행
                self._process_keywords(remaining_keywords, max_results_per_keyword, main_progress)
        except KeyboardInterrupt:
            self.logger.warning("사용자에 의해 중단됨")
        except Exception as e:
            self.logger.error(f"예기치 않은 오류 발생: {e}", exc_info=True)
        finally:
            main_progress.close()
            
            # 결과 요약 출력
            self._print_summary()
    
    def _process_keywords(self, keywords, max_results_per_keyword, progress_bar):
        """
        키워드 목록 처리 (동기 방식)
        
        Args:
            keywords: 처리할 키워드 목록
            max_results_per_keyword: 키워드당 최대 결과 수
            progress_bar: tqdm 프로그레스 바 객체
        """
        self.logger.info(f"키워드 처리 시작: 총 {len(keywords)}개 키워드")
        
        for idx, keyword in enumerate(keywords):
            self.logger.info(f"키워드 '{keyword}' 처리 시작 ({idx+1}/{len(keywords)})")
            
            # 진행 중인 키워드 표시
            save_in_progress_keyword(keyword)
            self.logger.debug(f"키워드 '{keyword}'를 진행 중으로 표시")
            
            try:
                # 키워드 오류 횟수 초기화
                error_count = 0
                max_errors = 3  # 최대 허용 오류 횟수
                
                while error_count < max_errors:
                    try:
                        self.logger.info(f"키워드 '{keyword}' 검색 시도 중...")
                        # 이 키워드에 대한 결과 수집
                        fetched_count, api_calls = self.search_manager.fetch_keyword_data(keyword, max_results_per_keyword)
                        
                        self.logger.info(f"키워드 '{keyword}' 검색 성공: {fetched_count}개 항목 수집, API 호출 {api_calls}회")
                        break  # 성공하면 반복 종료
                    except requests.HTTPError as e:
                        if "500" in str(e):  # 500 오류인 경우
                            error_count += 1
                            self.logger.warning(f"키워드 '{keyword}' 처리 중 서버 오류(500) 발생, 재시도 ({error_count}/{max_errors})")
                            
                            if error_count >= max_errors:
                                self.logger.error(f"키워드 '{keyword}' 최대 오류 횟수({max_errors}회) 초과")
                                raise
                                
                            # 재시도 전 대기
                            wait_time = 5 * error_count  # 오류 횟수에 따라 대기 시간 증가
                            self.logger.info(f"{wait_time}초 대기 후 재시도...")
                            time.sleep(wait_time)
                        else:
                            self.logger.error(f"키워드 '{keyword}' 처리 중 HTTP 오류 발생: {e}")
                            raise
                
                # 통계 업데이트
                self.stats['fetched_items'] += fetched_count
                self.stats['api_calls'] += api_calls
                
                self.logger.info(f"키워드 '{keyword}' 처리 완료")
                
                # 키워드 완료 처리
                save_completed_keyword(keyword)
                clear_in_progress_keyword()
                self.logger.debug(f"키워드 '{keyword}'를 완료 처리함")
                
                # API 한도 체크
                if self.api_client.check_api_limit():
                    self.logger.warning(f"일일 API 호출 한도에 도달: {self.api_client.today_api_calls}회. 작업 중단.")
                    break
            except Exception as e:
                self.logger.error(f"키워드 '{keyword}' 처리 중 오류 발생: {e}", exc_info=True)
                
                # 예외 유형별 상세 로깅
                if isinstance(e, requests.HTTPError):
                    self.logger.error(f"HTTP 오류 상세 정보: {str(e)}")
                elif isinstance(e, requests.ConnectionError):
                    self.logger.error("네트워크 연결 오류")
                elif isinstance(e, requests.Timeout):
                    self.logger.error("요청 시간 초과")
                elif isinstance(e, json.JSONDecodeError):
                    self.logger.error("JSON 파싱 오류")
                elif isinstance(e, sqlite3.Error):
                    self.logger.error(f"데이터베이스 오류: {str(e)}")
                
                save_failed_keyword(keyword, str(e))
                self.stats['failed_items'] += 1
                self.logger.info(f"키워드 '{keyword}'를 실패 처리함")
            finally:
                # 프로그레스 바 업데이트
                progress_bar.update(1)
                progress_bar.set_postfix({"수집": self.stats['fetched_items'], "API호출": self.stats['api_calls']})
                self.logger.debug(f"프로그레스 바 업데이트: {idx+1}/{len(keywords)}")
        
    async def _process_keywords_async(self, keywords, max_results_per_keyword, progress_bar):
        """
        키워드 목록 처리 (비동기 방식)
        
        Args:
            keywords: 처리할 키워드 목록
            max_results_per_keyword: 키워드당 최대 결과 수
            progress_bar: tqdm 프로그레스 바 객체
        """
        # 병렬 처리 수 제한
        semaphore = asyncio.Semaphore(Config.MAX_WORKERS)
        
        async def process_keyword(keyword):
            async with semaphore:
                self.logger.info(f"[Async] 키워드 '{keyword}' 처리 시작")
                
                try:
                    # 이 키워드에 대한 결과 수집
                    fetched_count, api_calls = await self.search_manager.fetch_keyword_data_async(keyword, max_results_per_keyword)
                    
                    # 통계 업데이트
                    self.stats['fetched_items'] += fetched_count
                    self.stats['api_calls'] += api_calls
                    
                    self.logger.info(f"[Async] 키워드 '{keyword}' 완료: {fetched_count}개 항목 수집, API 호출 {api_calls}회")
                    
                    # 키워드 완료 처리
                    save_completed_keyword(keyword)
                    
                    # API 한도 체크
                    if self.api_client.check_api_limit():
                        self.logger.warning(f"[Async] 일일 API 호출 한도에 도달: {self.api_client.today_api_calls}회.")
                        return False
                    
                    return True
                except Exception as e:
                    self.logger.error(f"[Async] 키워드 '{keyword}' 처리 중 오류 발생: {e}", exc_info=True)
                    save_failed_keyword(keyword, str(e))
                    self.stats['failed_items'] += 1
                    return False
                finally:
                    # 프로그레스 바 업데이트
                    progress_bar.update(1)
                    progress_bar.set_postfix({"수집": self.stats['fetched_items'], "API호출": self.stats['api_calls']})
        
        # 초기에 진행 중인 키워드 표시
        if keywords:
            save_in_progress_keyword(keywords[0])
        
        # 태스크 생성 및 실행
        tasks = []
        for keyword in keywords:
            if self.api_client.check_api_limit():
                self.logger.warning(f"[Async] 일일 API 호출 한도에 도달: {self.api_client.today_api_calls}회. 추가 태스크 생성 중단.")
                break
                
            task = asyncio.create_task(process_keyword(keyword))
            tasks.append(task)
        
        # 모든 태스크 완료 대기
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 진행 중인 키워드 표시 제거
        clear_in_progress_keyword()
        
        # 예외 확인
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self.logger.error(f"[Async] 키워드 처리 중 예외 발생: {result}")
    
    def _print_summary(self):
        """
        크롤링 결과 요약 출력
        """
        print(f"{Fore.CYAN}{'='*80}")
        print(f"{Fore.CYAN}크롤링 결과 요약")
        print(f"{Fore.CYAN}{'='*80}")
        print(f"총 수집 항목: {Fore.GREEN}{self.stats['fetched_items']}개{Style.RESET_ALL}")
        print(f"총 API 호출: {Fore.YELLOW}{self.stats['api_calls']}회{Style.RESET_ALL}")
        print(f"건너뛴 항목: {Fore.BLUE}{self.stats['skipped_items']}개{Style.RESET_ALL}")
        print(f"실패한 항목: {Fore.RED}{self.stats['failed_items']}개{Style.RESET_ALL}")
        
        # 데이터베이스 통계 출력
        db_stats = self.db_manager.get_tables_info()
        print(f"\n{Fore.CYAN}데이터베이스 통계")
        for table, count in db_stats.items():
            print(f"{table}: {Fore.GREEN}{count}개 레코드{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
    
    def fetch_single_medicine(self, url, title=None):
        """
        단일 약품 정보 수집
        
        Args:
            url: 약품 상세 페이지 URL
            title: 약품 제목 (옵션)
            
        Returns:
            dict: 수집된 약품 정보 또는 None (실패 시)
        """
        self.logger.info(f"단일 약품 정보 수집 시작: {url}")
        
        # 중복 체크
        if self.db_manager.is_duplicate(url, title):
            self.logger.info(f"이미 존재하는 약품, 건너뜀: {url}")
            return None
        
        try:
            # HTML 내용 가져오기
            html_content = self.api_client.get_html_content(url)
            if not html_content:
                self.logger.warning(f"HTML 내용을 가져올 수 없음: {url}")
                return None
            
            # HTML 파싱
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 제목이 제공되지 않았다면 페이지에서 추출
            if not title:
                title_element = soup.select_one('h2.title, h3.title, h1, .article_header h2, .article_title')
                if title_element:
                    title = title_element.get_text().strip()
                else:
                    title = url.split('/')[-1]  # URL의 마지막 부분을 제목으로 사용
            
            # 의약품 정보 파싱
            medicine_data = self.parser.parse_medicine_detail(soup, url, title)
            if not medicine_data:
                self.logger.warning(f"약품 정보를 파싱할 수 없음: {url}")
                return None
            
            # 데이터 검증
            validation_result = self.parser.validate_medicine_data(medicine_data)
            if not validation_result['is_valid']:
                self.logger.warning(f"약품 데이터 유효성 검사 실패: {url}, 이유: {validation_result['reason']}")
                return None
            
            # 이미지가 있으면 다운로드
            if medicine_data.get('item_image'):
                local_image_path = self.api_client.download_image(
                    medicine_data['item_image'], 
                    medicine_data['item_name']
                )
                if local_image_path:
                    medicine_data['item_image'] = local_image_path
            
            # 데이터 해시 생성
            medicine_data['data_hash'] = generate_data_hash(medicine_data)
            
            # 데이터베이스에 저장
            result = self.db_manager.save_medicine_to_db(medicine_data)
            if result:
                self.logger.info(f"약품 정보 저장 완료: {title}")
                return medicine_data
            else:
                self.logger.warning(f"약품 정보 저장 실패: {title}")
                return None
                
        except Exception as e:
            self.logger.error(f"단일 약품 정보 수집 중 오류 발생: {e}", exc_info=True)
            return None
    
    def export_medicine_to_csv(self, output_file='api_medicine_export.csv'):
        """
        수집된 약품 정보를 CSV 파일로 내보내기
        
        Args:
            output_file: 출력 CSV 파일 경로
            
        Returns:
            bool: 성공적으로 내보내면 True, 아니면 False
        """
        import csv
        
        try:
            conn = self.db_manager.get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 필수 출력 컬럼 정의
            essential_columns = [
                'id', 'item_name', 'item_eng_name', 'entp_name', 'class_no', 'class_name',
                'etc_otc_name', 'chart', 'drug_shape', 'color_class1', 'item_image', 
                'efcy_qesitm', 'use_method_qesitm', 'deposit_method_qesitm', 
                'caution_details', 'url', 'created_at'
            ]
            
            # 모든 약품 데이터 조회
            cursor.execute("SELECT * FROM api_medicine ORDER BY id")
            rows = cursor.fetchall()
            
            if not rows:
                self.logger.warning("내보낼 약품 데이터가 없습니다.")
                return False
            
            # 모든 컬럼 가져오기
            columns = [column[0] for column in cursor.description]
            
            # CSV 파일 생성
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)
                
                # 헤더 작성
                writer.writerow(columns)
                
                # 데이터 작성
                for row in rows:
                    writer.writerow([row[column] for column in columns])
            
            conn.close()
            
            self.logger.info(f"약품 데이터 내보내기 완료: {output_file}, {len(rows)}개 레코드")
            return True
            
        except Exception as e:
            self.logger.error(f"약품 데이터 내보내기 중 오류 발생: {e}", exc_info=True)
            return False


def main():
    """메인 함수"""
    # 환경 초기화
    start_time = init_environment()
    
    # 로거 설정
    logger = setup_logging()
    logger.info("프로그램 시작")
    
    # 시스템 정보 로깅
    logger.info(f"Python 버전: {sys.version}")
    logger.info(f"운영체제: {sys.platform}")
    logger.info(f"작업 디렉토리: {os.getcwd()}")
    
    # 환경 설정 로드
    client_id, client_secret, db_path = load_env_configuration()
    logger.info(f"설정 로드 완료: DB 경로={db_path}")
    
    if not client_id or not client_secret:
        logger.error("API 키가 설정되지 않았습니다. 프로그램을 종료합니다.")
        print(f"{Fore.RED}API 키가 설정되지 않았습니다. 프로그램을 종료합니다.{Style.RESET_ALL}")
        return
    
    # 명령줄 인자 처리
    import argparse
    parser = argparse.ArgumentParser(description='네이버 의약품 정보 크롤러')
    parser.add_argument('--url', help='단일 약품 URL 수집')
    parser.add_argument('--keyword', help='특정 키워드로 검색')
    parser.add_argument('--max', type=int, default=1000, help='키워드당 최대 결과 수')
    parser.add_argument('--async', action='store_true', help='비동기 방식 사용')
    parser.add_argument('--export', help='수집된 데이터를 CSV 파일로 내보내기')
    parser.add_argument('--stats', action='store_true', help='데이터베이스 통계 표시')
    
    args = parser.parse_args()
    logger.info(f"명령줄 인자: {vars(args)}")
    
    try:
        # 크롤러 인스턴스 생성
        logger.info("크롤러 인스턴스 생성 시작")
        crawler = NaverMedicineCrawler(client_id, client_secret, db_path)
        logger.info("크롤러 인스턴스 생성 완료")
        
        # 단일 URL 수집
        if args.url:
            logger.info(f"단일 URL 수집 시작: {args.url}")
            medicine_data = crawler.fetch_single_medicine(args.url)
            if medicine_data:
                logger.info(f"약품 정보 수집 성공: {medicine_data['item_name']}")
                print(f"{Fore.GREEN}약품 정보 수집 성공: {medicine_data['item_name']}{Style.RESET_ALL}")
            else:
                logger.error(f"약품 정보 수집 실패: {args.url}")
                print(f"{Fore.RED}약품 정보 수집 실패{Style.RESET_ALL}")
        
        # 특정 키워드 검색
        elif args.keyword:
            logger.info(f"키워드 검색 시작: {args.keyword}, 최대 결과 수: {args.max}, 비동기: {getattr(args, 'async', False)}")
            crawler.fetch_all_medicine_data(
                keywords=[args.keyword], 
                max_results_per_keyword=args.max,
                use_async=getattr(args, 'async', False)
            )
        
        # 데이터 내보내기
        elif args.export:
            logger.info(f"데이터 내보내기 시작: {args.export}")
            if crawler.export_medicine_to_csv(args.export):
                logger.info(f"데이터 내보내기 완료: {args.export}")
                print(f"{Fore.GREEN}데이터 내보내기 완료: {args.export}{Style.RESET_ALL}")
            else:
                logger.error(f"데이터 내보내기 실패: {args.export}")
                print(f"{Fore.RED}데이터 내보내기 실패{Style.RESET_ALL}")
        
        # 데이터베이스 통계
        elif args.stats:
            logger.info("데이터베이스 통계 조회 시작")
            stats = crawler.db_manager.get_medicine_stats()
            logger.info(f"데이터베이스 통계: 총 약품 수={stats['total_count']}")
            
            # 콘솔에 통계 출력
            print(f"{Fore.CYAN}{'='*80}")
            print(f"{Fore.CYAN}데이터베이스 통계")
            print(f"{Fore.CYAN}{'='*80}")
            print(f"총 약품 수: {Fore.GREEN}{stats['total_count']}개{Style.RESET_ALL}")
            
            # 나머지 통계 출력 코드...
        
        # 기본: 모든 키워드로 수집
        else:
            logger.info(f"전체 키워드 수집 시작: 최대 결과 수={args.max}, 비동기={getattr(args, 'async', False)}")
            crawler.fetch_all_medicine_data(
                max_results_per_keyword=args.max,
                use_async=getattr(args, 'async', False)
            )
    except Exception as e:
        logger.critical(f"프로그램 실행 중 심각한 오류 발생: {e}", exc_info=True)
        print(f"{Fore.RED}오류 발생: {e}{Style.RESET_ALL}")
    
    # 실행 종료 시간
    end_time = datetime.now()
    duration = end_time - start_time
    
    logger.info(f"프로그램 종료: 시작={start_time}, 종료={end_time}, 소요 시간={duration}")
    
    print(f"{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}약품 정보 수집 완료")
    print(f"{Fore.CYAN}시작 시간: {start_time}")
    print(f"{Fore.CYAN}종료 시간: {end_time}")
    print(f"{Fore.CYAN}소요 시간: {duration}")
    print(f"{Fore.CYAN}로그 파일: {os.path.abspath('medicine_crawler.log')}")
    print(f"{Fore.CYAN}데이터베이스 파일: {os.path.abspath(db_path)}")
    print(f"{Fore.CYAN}{'='*80}")


if __name__ == "__main__":
    main()