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

# 로깅 설정
colorama.init()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('medicine_crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('medicine_crawler')

class NaverMedicineCrawler:
    def __init__(self, client_id, client_secret, db_path='medicine.db'):
        """
        네이버 API를 이용해 약품 정보를 크롤링하는 클래스
        
        Args:
            client_id: 네이버 개발자 센터에서 발급받은 클라이언트 ID
            client_secret: 네이버 개발자 센터에서 발급받은 클라이언트 시크릿
            db_path: SQLite DB 파일 경로
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.db_path = db_path
        self.init_db()
        
    def init_db(self):
        """데이터베이스 초기화 및 테이블 생성"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 메인 약품 테이블 생성
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS medicines (
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
            caution_details TEXT,  # 새로 추가된 컬럼
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # URL 인덱스 생성 (빠른 중복 검사를 위해)
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_url ON medicines (url)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_item_name ON medicines (item_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_caution_details ON medicines (caution_details)')
        
        conn.commit()
        conn.close()
        
    def search_medicines(self, keyword, display=100, start=1):
        """
        네이버 API를 사용하여 약품 검색
        
        Args:
            keyword: 검색 키워드
            display: 한 번에 가져올 결과 수 (최대 100)
            start: 검색 시작 위치
            
        Returns:
            dict: API 응답 데이터
        """
        encoded_keyword = urllib.parse.quote(f"{keyword} 의약품")
        url = f"https://openapi.naver.com/v1/search/encyc.json?query={encoded_keyword}&display={display}&start={start}"
        
        request = urllib.request.Request(url)
        request.add_header("X-Naver-Client-Id", self.client_id)
        request.add_header("X-Naver-Client-Secret", self.client_secret)
        
        try:
            response = urllib.request.urlopen(request)
            if response.getcode() == 200:
                result = json.loads(response.read().decode('utf-8'))
                return result
            else:
                logger.error(f"API 요청 실패: 응답 코드 {response.getcode()}")
                return None
        except Exception as e:
            logger.error(f"API 요청 중 오류 발생: {e}")
            return None
    
    def fetch_all_medicine_data(self, keywords, max_results_per_keyword=1000):
        """
        여러 키워드에 대해 페이지네이션을 사용하여 모든 약품 데이터 수집
        
        Args:
            keywords: 검색 키워드 리스트
            max_results_per_keyword: 키워드당 최대 결과 수
        """
        total_items = 0
        fetched_items = 0
        skipped_items = 0
        
        # 먼저 각 키워드별 예상 결과 수 확인
        for keyword in keywords:
            try:
                initial_result = self.search_medicines(keyword, display=1, start=1)
                if initial_result and 'total' in initial_result:
                    keyword_total = min(int(initial_result['total']), max_results_per_keyword)
                    total_items += keyword_total
                    logger.info(f"키워드 '{keyword}'에 대한 예상 결과 수: {keyword_total}")
                else:
                    logger.warning(f"키워드 '{keyword}'에 대한 검색 결과가 없거나 API 응답 오류")
            except Exception as e:
                logger.error(f"키워드 '{keyword}' 검색 중 오류: {e}")
        
        logger.info(f"{Fore.BLUE}총 예상 항목 수: {total_items}{Style.RESET_ALL}")
        
        # 메인 프로그레스 바 초기화
        main_progress = tqdm(total=total_items, desc="전체 진행률", unit="항목", 
                             bar_format="{l_bar}%s{bar}%s{r_bar}" % (Fore.GREEN, Style.RESET_ALL))
        
        # 키워드별 데이터 수집
        for keyword in keywords:
            logger.info(f"키워드 '{keyword}' 검색 시작")
            start = 1
            display = 100  # API 최대 허용값
            
            while start <= max_results_per_keyword:
                # API 호출 간 딜레이 (초당 요청 수 제한 방지)
                time.sleep(0.3)
                
                logger.info(f"'{keyword}' 검색 결과 {start}~{start+display-1} 요청 중...")
                result = self.search_medicines(keyword, display=display, start=start)
                
                if not result or 'items' not in result or not result['items']:
                    logger.info(f"'{keyword}'에 대한 추가 결과 없음 또는 마지막 페이지 도달")
                    break
                
                # 약품 데이터 처리
                for item in result['items']:
                    try:
                        # 의약품 정보인지 확인
                        title = BeautifulSoup(item['title'], 'html.parser').get_text()
                        description = BeautifulSoup(item['description'], 'html.parser').get_text()
                        
                        # 의약품 사전 항목인지 확인 (URL에 'medicinedic' 포함 또는 제목에 '정', '캡슐', '주사' 등 포함)
                        is_medicine = ('medicinedic' in item['link'] or 
                                       any(keyword in title for keyword in ['정', '캡슐', '주사', '시럽', '연고', '크림']))
                        
                        if is_medicine:
                            # 중복 검사
                            if self.is_duplicate(item['link'], title):
                                logger.info(f"중복 항목 건너뜀: {title}")
                                skipped_items += 1
                            else:
                                # 상세 페이지에서 정보 가져오기
                                logger.info(f"약품 정보 수집 중: {title} ({item['link']})")
                                medicine_data = self.parse_medicine_detail(item['link'], title)
                                
                                if medicine_data:
                                    # DB에 저장
                                    self.save_medicine_to_db(medicine_data)
                                    fetched_items += 1
                                    logger.info(f"저장 완료: {title}")
                                else:
                                    logger.warning(f"약품 상세 정보를 파싱할 수 없음: {title}")
                        else:
                            logger.debug(f"의약품 항목이 아님, 건너뜀: {title}")
                    except Exception as e:
                        logger.error(f"항목 처리 중 오류: {e}", exc_info=True)
                    
                    # 진행 상황 업데이트
                    main_progress.update(1)
                
                # 다음 페이지로 이동
                start += display
                
                # 결과 수가 display보다 적으면 마지막 페이지
                if len(result['items']) < display:
                    break
        
        main_progress.close()
        logger.info(f"{Fore.BLUE}크롤링 완료: 수집 {fetched_items}개, 중복 건너뜀 {skipped_items}개{Style.RESET_ALL}")
    
    def is_duplicate(self, url, title):
        """URL 또는 제목으로 중복 검사"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # URL로 중복 검사
        cursor.execute("SELECT id FROM medicines WHERE url = ?", (url,))
        url_match = cursor.fetchone()
        
        # 제목으로 중복 검사 (정확히 일치하는 경우만)
        cursor.execute("SELECT id FROM medicines WHERE item_name = ?", (title,))
        title_match = cursor.fetchone()
        
        conn.close()
        
        return bool(url_match or title_match)
    
    def find_medicine_image_url(self, soup, base_url):
        """
        약품 이미지 URL을 다양한 선택자와 패턴으로 찾습니다.
        
        Args:
            soup: BeautifulSoup 객체
            base_url: 기본 URL (상대 경로를 절대 경로로 변환할 때 사용)
        
        Returns:
            str: 찾은 이미지 URL 또는 빈 문자열
        """
        # 이미지를 찾기 위한 다양한 선택자들
        selectors = [
            'div.image_area img',           # 네이버 지식백과 일반적인 이미지 영역
            'div.media_end_content img',     # 네이버 콘텐츠 이미지
            'div.thumb_area img',           # 썸네일 영역
            'div.drug_info_img img',        # 약품 정보 이미지
            'img.drug_image',               # 약품 이미지 클래스
            'div.item_image img',           # 항목 이미지
            'div.med_img img',              # 약품 이미지 영역
            'div.medicinedic_img img',      # 의약품 사전 이미지
            '.medicine-image',              # 약품 이미지 클래스
            '.item-image',                  # 항목 이미지 클래스
            'img[src*="medicinedic"]',      # src 속성에 medicinedic이 포함된 이미지
            'img[src*="drug"]',             # src 속성에 drug이 포함된 이미지
            'img[src*="medicine"]',         # src 속성에 medicine이 포함된 이미지
            'img[alt*="약품"]',              # alt 속성에 "약품"이 포함된 이미지
            'img[alt*="의약품"]',             # alt 속성에 "의약품"이 포함된 이미지
        ]
        
        # 각 선택자에 대해 이미지 찾기 시도
        for selector in selectors:
            img_tag = soup.select_one(selector)
            if img_tag and 'src' in img_tag.attrs:
                img_url = img_tag['src']
                
                # 상대 경로인 경우 절대 경로로 변환
                if not img_url.startswith(('http://', 'https://')):
                    img_url = urllib.parse.urljoin(base_url, img_url)
                
                logger.info(f"이미지 URL 찾음 ({selector}): {img_url}")
                return img_url
        
        # 이미지 태그들을 직접 검사
        all_imgs = soup.find_all('img')
        for img in all_imgs:
            if 'src' not in img.attrs:
                continue
                
            src = img['src']
            # 약품 이미지일 가능성이 높은 패턴 확인
            if any(pattern in src.lower() for pattern in ['drug', 'medi', 'pill', 'pharm', 'item']):
                img_url = src
                if not img_url.startswith(('http://', 'https://')):
                    img_url = urllib.parse.urljoin(base_url, img_url)
                
                logger.info(f"이미지 URL 찾음 (패턴 매칭): {img_url}")
                return img_url
        
        logger.warning(f"이미지 URL을 찾을 수 없음")
        return ""
    
    def parse_medicine_detail(self, url, title):
        """
        약품 상세 페이지에서 정보 파싱
        
        Args:
            url: 약품 상세 페이지 URL
            title: 약품 제목
            
        Returns:
            dict: 파싱된 약품 정보
        """
        try:
            # 기존 로직 유지
            logger.info(f"URL 접속 중: {url}")
            req = urllib.request.Request(url)
            response = urllib.request.urlopen(req)
            html = response.read().decode('utf-8')
            
            soup = BeautifulSoup(html, 'html.parser')
            
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
            
            # 모든 정보 섹션 찾기
            sections = {}
            
            # 업체명, 분류, 구분 정보 찾기
            info_rows = soup.select('table tr')
            for row in info_rows:
                if row.select_one('th') and row.select_one('td'):
                    header = row.select_one('th').get_text().strip()
                    value = row.select_one('td').get_text().strip()
                    
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
                                medicine_data['leng_long'] = re.search(r'[\d\.]+', part).group(0)
                            elif '단축' in part:
                                medicine_data['leng_short'] = re.search(r'[\d\.]+', part).group(0)
                            elif '두께' in part:
                                medicine_data['thick'] = re.search(r'[\d\.]+', part).group(0)
                    elif '식별표기' in header:
                        # 식별표기 분리
                        medicine_data['print_front'] = value
            
            # 목차 찾기를 통해 섹션 추출
            toc = soup.select_one('.toc')
            section_titles = ['성분정보', '효능효과', '용법용량', '저장방법', '사용기간', '사용상의주의사항']
            
            # 각 섹션에 대응하는 내용 추출
            all_headings = soup.select('h2, h3, h4')
            for i, heading in enumerate(all_headings):
                heading_text = heading.get_text().strip()
                
                if any(title in heading_text for title in section_titles):
                    # 다음 헤딩까지의 모든 내용 추출
                    content = []
                    for sibling in heading.next_siblings:
                        if sibling.name in ['h2', 'h3', 'h4']:
                            break
                        if sibling.name:  # 태그가 있는 요소만
                            content.append(str(sibling))
                    
                    # 섹션 내용 저장
                    sections[heading_text] = ''.join(content).strip()
            
            # 사용상의 주의사항 전체 텍스트 추출 (새로운 로직)
            caution_section = soup.find('h2', text=re.compile(r'사용상의\s*주의사항'))
            if caution_section:
                # 사용상의 주의사항 전체 텍스트 추출
                caution_text = self._extract_full_caution_text(caution_section)
                medicine_data['caution_details'] = caution_text
            else:
                medicine_data['caution_details'] = ''
            
            return medicine_data
        
        except Exception as e:
            logger.error(f"상세 페이지 파싱 중 오류: {e}")
            return None
        
    def _extract_full_caution_text(self, caution_section):
        """
        사용상의 주의사항 전체 텍스트 추출
        
        Args:
            caution_section: BeautifulSoup 사용상의 주의사항 섹션 헤더
        
        Returns:
            str: 전체 사용상의 주의사항 텍스트
        """
        try:
            caution_text = []
            current = caution_section.next_sibling
            
            while current and not (current.name in ['h2', 'h3'] and 
                                    re.search(r'(다음\s*절|다음\s*섹션)', current.get_text(strip=True))):
                if current.name and hasattr(current, 'get_text'):
                    text = current.get_text(strip=True)
                    if text:
                        caution_text.append(text)
                current = current.next_sibling
            
            # 추출된 텍스트 정제
            full_text = '\n'.join(caution_text)
            full_text = re.sub(r'\n+', '\n', full_text)  # 연속된 줄바꿈 제거
            
            return full_text.strip()
        
        except Exception as e:
            logger.error(f"사용상의 주의사항 텍스트 추출 중 오류: {e}")
            return ''
    
    def check_medicine_data_completeness(self, medicine_data):
        """약품 데이터의 완전성을 체크하고 로깅"""
        # medicine_data가 반환되기 전에 호출되는 검증 로직
        
        # 필수 필드와 선택적 필드 정의
        required_fields = ['item_name', 'entp_name']
        detail_fields = {
            '기본 정보': ['item_eng_name', 'class_no', 'class_name', 'etc_otc_name', 'chart', 'edi_code'],
            '물리적 특성': ['drug_shape', 'color_class1', 'leng_long', 'leng_short', 'thick', 'print_front', 'print_back'],
            '효능/용법': ['efcy_qesitm', 'use_method_qesitm', 'deposit_method_qesitm'],
            '주의사항': ['atpn_qesitm', 'atpn_warn_qesitm', 'se_qesitm', 'intrc_qesitm']
        }
        
        # 기본 정보 로깅
        logger.info(f"\n{'='*50}")
        logger.info(f"약품 '{medicine_data['item_name']}' 데이터 수집 결과")
        logger.info(f"URL: {medicine_data['url']}")
        
        # 필수 필드 체크
        missing_required = [field for field in required_fields if not medicine_data.get(field)]
        if missing_required:
            logger.warning(f"⚠️ 필수 필드 누락: {', '.join(missing_required)}")
        else:
            logger.info(f"✅ 모든 필수 필드가 수집되었습니다.")
        
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
                
            logger.info(f"{category}: {rate_color}{collected_count}/{total} ({collection_rate:.1f}%){Style.RESET_ALL}")
            
            if missing:
                logger.info(f"  - 미수집 필드: {', '.join(missing)}")
        
        # 전체 수집률
        all_fields = sum([len(fields) for fields in detail_fields.values()]) + len(required_fields)
        filled_fields = sum([1 for field, value in medicine_data.items() if value])
        total_rate = filled_fields / all_fields * 100
        
        if total_rate >= 80:
            total_color = Fore.GREEN
        elif total_rate >= 50:
            total_color = Fore.YELLOW
        else:
            total_color = Fore.RED
        
        logger.info(f"전체 수집률: {total_color}{total_rate:.1f}%{Style.RESET_ALL}")
        logger.info(f"{'='*50}")
        
        return medicine_data
    
    def parse_precautions(self, precautions_html):
        """
        사용상의주의사항 텍스트를 여러 카테고리로 파싱
        
        Args:
            precautions_html: 사용상의주의사항 HTML
            
        Returns:
            dict: 파싱된 주의사항들
        """
        result = {
            'atpn_warn_qesitm': '',  # 경고/투여금기
            'atpn_qesitm': '',       # 일반 주의사항
            'intrc_qesitm': '',      # 상호작용
            'se_qesitm': ''          # 부작용/이상반응
        }
        
        # HTML 텍스트로 변환
        precautions_text = self.clean_html(precautions_html)
        
        # 주요 섹션 패턴 정의
        section_patterns = [
            (r'(?:1\.|[0-9]+\.\s*)?다음\s*환자에게는\s*투여하지\s*말\s*것.*?(?=\d+\.\s|$)', 'atpn_warn_qesitm'),
            (r'(?:2\.|[0-9]+\.\s*)?이상반응.*?(?=\d+\.\s|$)', 'se_qesitm'),
            (r'(?:3\.|[0-9]+\.\s*)?일반적\s*주의.*?(?=\d+\.\s|$)', 'atpn_qesitm'),
            (r'(?:4\.|[0-9]+\.\s*)?상호작용.*?(?=\d+\.\s|$)', 'intrc_qesitm'),
        ]
        
        # 전체 텍스트에서 각 섹션을 순차적으로 추출
        for pattern, field in section_patterns:
            matches = re.search(pattern, precautions_text, re.DOTALL | re.IGNORECASE)
            if matches:
                content = matches.group(0).strip()
                result[field] = content
        
        # 기타 추가 섹션들 처리 (예: 임부/수유부, 소아, 고령자 등)
        other_sections = [
            (r'(?:[0-9]+\.\s*)?임부.*?(?=\d+\.\s|$)', 'atpn_qesitm'),
            (r'(?:[0-9]+\.\s*)?소아.*?(?=\d+\.\s|$)', 'atpn_qesitm'),
            (r'(?:[0-9]+\.\s*)?고령자.*?(?=\d+\.\s|$)', 'atpn_qesitm'),
            (r'(?:[0-9]+\.\s*)?보관.*?(?=\d+\.\s|$)', 'atpn_qesitm')
        ]
        
        for pattern, field in other_sections:
            matches = re.search(pattern, precautions_text, re.DOTALL | re.IGNORECASE)
            if matches:
                content = matches.group(0).strip()
                if result[field]:
                    result[field] += "\n\n" + content
                else:
                    result[field] = content
        
        # 추출되지 않은 나머지 텍스트를 일반 주의사항에 추가
        if not any(result.values()):
            result['atpn_qesitm'] = precautions_text
        
        return result
    
    def clean_html(self, html_text):
        """HTML 태그 제거 및 텍스트 정리"""
        if not html_text:
            return ""
        
        # BeautifulSoup으로 HTML 파싱
        soup = BeautifulSoup(html_text, 'html.parser')
        text = soup.get_text('\n', strip=True)
        
        # 불필요한 text 제거
        text = re.sub(r'\s+', ' ', text)  # 연속된 공백 제거
        text = re.sub(r'(\n\s*)+', '\n', text)  # 연속된 줄바꿈 제거
        
        return text.strip()
    
    def save_medicine_to_db(self, medicine_data):
        """
        약품 정보를 데이터베이스에 저장
        
        Args:
            medicine_data: 약품 정보 딕셔너리
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 컬럼 이름 목록
        columns = list(medicine_data.keys())
        placeholders = ', '.join(['?' for _ in columns])
        column_str = ', '.join(columns)
        
        # 데이터 준비
        values = tuple(medicine_data.get(col, '') for col in columns)
        
        # 삽입 쿼리 실행
        cursor.execute(f"""
        INSERT INTO medicines ({column_str}) 
        VALUES ({placeholders})
        """, values)
        
        conn.commit()
        conn.close()
    
    def validate_data(self, medicine_data):
        """
        데이터 유효성 검증
        
        Args:
            medicine_data: 검증할 약품 데이터
            
        Returns:
            dict: 검증 결과
        """
        result = {
            'is_valid': True,
            'missing_fields': [],
            'empty_fields': []
        }
        
        # 필수 필드 정의
        required_fields = ['item_name', 'entp_name']
        
        # 필수 필드 검증
        for field in required_fields:
            if field not in medicine_data:
                result['is_valid'] = False
                result['missing_fields'].append(field)
            elif not medicine_data[field]:
                result['empty_fields'].append(field)
        
        return result
    def fetch_keyword_data(self, keyword, max_results=1000):
        """
        특정 키워드에 대한 데이터를 수집하고 API 호출 횟수를 반환합니다.
        
        Args:
            keyword: 검색 키워드
            max_results: 최대 결과 수
        
        Returns:
            tuple: (수집된 항목 수, API 호출 횟수)
        """
        fetched_items = 0
        api_calls = 0
        skipped_items = 0
        
        logger.info(f"키워드 '{keyword}' 검색 시작")
        
        # 예상 결과 수 확인 (API 호출 1회)
        try:
            initial_result = self.search_medicines(keyword, display=1, start=1)
            api_calls += 1
            
            if initial_result and 'total' in initial_result:
                keyword_total = min(int(initial_result['total']), max_results)
                logger.info(f"키워드 '{keyword}'에 대한 예상 결과 수: {keyword_total}")
            else:
                logger.warning(f"키워드 '{keyword}'에 대한 검색 결과가 없거나 API 응답 오류")
                return 0, api_calls
        except Exception as e:
            logger.error(f"키워드 '{keyword}' 검색 중 오류: {e}")
            return 0, api_calls
        
        # 결과 페이지네이션
        start = 1
        display = 100  # API 최대 허용값
        
        while start <= max_results:
            # API 호출 간 딜레이
            time.sleep(0.3)
            
            logger.info(f"'{keyword}' 검색 결과 {start}~{start+display-1} 요청 중...")
            result = self.search_medicines(keyword, display=display, start=start)
            api_calls += 1
            
            if not result or 'items' not in result or not result['items']:
                logger.info(f"'{keyword}'에 대한 추가 결과 없음 또는 마지막 페이지 도달")
                break
            
            # 약품 데이터 처리
            for item in result['items']:
                try:
                    # 의약품 정보인지 확인
                    title = BeautifulSoup(item['title'], 'html.parser').get_text()
                    description = BeautifulSoup(item['description'], 'html.parser').get_text()
                    
                    # 의약품 사전 항목인지 확인
                    is_medicine = ('medicinedic' in item['link'] or 
                                any(med_kw in title for med_kw in ['정', '캡슐', '주사', '시럽', '연고', '크림']))
                    
                    if is_medicine:
                        # 중복 검사
                        if self.is_duplicate(item['link'], title):
                            logger.info(f"중복 항목 건너뜀: {title}")
                            skipped_items += 1
                        else:
                            # 상세 페이지에서 정보 가져오기
                            logger.info(f"약품 정보 수집 중: {title} ({item['link']})")
                            medicine_data = self.parse_medicine_detail(item['link'], title)
                            
                            if medicine_data:
                                # DB에 저장
                                self.save_medicine_to_db(medicine_data)
                                fetched_items += 1
                                logger.info(f"저장 완료: {title}")
                            else:
                                logger.warning(f"약품 상세 정보를 파싱할 수 없음: {title}")
                    else:
                        logger.debug(f"의약품 항목이 아님, 건너뜀: {title}")
                except Exception as e:
                    logger.error(f"항목 처리 중 오류: {e}", exc_info=True)
            
            # 다음 페이지로 이동
            start += display
            
            # 결과 수가 display보다 적으면 마지막 페이지
            if len(result['items']) < display:
                break
        
        logger.info(f"키워드 '{keyword}' 검색 완료: {fetched_items}개 수집, {skipped_items}개 중복 건너뜀, API 호출 {api_calls}회")
        return fetched_items, api_calls

def main():
    # 컬러 초기화
    colorama.init(autoreset=True)
    
    # Windows에서 콘솔 출력 인코딩 설정
    import sys
    import io
    import locale

    # 시스템 기본 인코딩 확인
    system_encoding = locale.getpreferredencoding()
    logger.info(f"시스템 기본 인코딩: {system_encoding}")

    # Windows 환경에서 콘솔 출력 인코딩 변경
    if sys.platform.startswith('win'):
        # UTF-8 모드로 설정 (Python 3.7 이상)
        if hasattr(sys, 'setdefaultencoding'):
            sys.setdefaultencoding('utf-8')
        
        # 표준 출력 인코딩 설정
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        logger.info("Windows 환경 UTF-8 출력 모드로 설정함")
    
    # 실행 시작 시간
    start_time = datetime.now()
    
    print(f"{Fore.CYAN}{'='*80}")
    print(f"{Fore.CYAN}네이버 API를 이용한 약품 정보 수집 시작")
    print(f"{Fore.CYAN}실행 시간: {start_time}")
    print(f"{Fore.CYAN}{'='*80}")
    
    # .env 파일 로드
    load_dotenv()
    
    # 환경 변수에서 API 키 가져오기
    client_id = os.environ.get("NAVER_CLIENT_ID")
    client_secret = os.environ.get("NAVER_CLIENT_SECRET")
    db_path = os.environ.get("DB_PATH", "medicine.db")
    
    # .env 파일이 없거나 API 키가 설정되지 않은 경우 생성 안내
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
DB_PATH=medicines.db
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
DB_PATH=medicine.db
"""
            with open('.env', 'w', encoding='utf-8') as f:
                f.write(env_content)
            print(f"{Fore.GREEN}.env 파일이 생성되었습니다. 다음 실행부터는 자동으로 불러옵니다.{Style.RESET_ALL}")
    
    # 크롤러 인스턴스 생성
    crawler = NaverMedicineCrawler(client_id, client_secret, db_path)
    
    # 검색 키워드 리스트
    search_keywords = [
    # 한글 초성 검색 (모든 한글 약품명 포괄)
    "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
    
    # 영문 알파벳 검색 (모든 영문 약품명 포괄)
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", 
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    
    # 숫자 검색 (숫자로 시작하는 약품명 포괄)
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    
    # 의약품 일반 분류
    "의약품", "약품", "전문의약품", "일반의약품", "희귀의약품", "의약외품", "기능성 의약품",
    
    # 제형별 검색 (모든 제형 포괄)
    "정", "캡슐", "주사", "시럽", "연고", "크림", "겔", "패치", "좌제", "분말", "액", "로션",
    "과립", "현탁액", "환", "점안액", "점이액", "스프레이", "흡입제", "투여", "주입", "엑스제",
    "산제", "서방정", "구강붕해정", "경구용", "외용", "설하정", "흡입기", "용액", "필름코팅정",
    
    # 주요 제약사 (국내외 주요 제약회사)
    "동아제약", "유한양행", "녹십자", "한미약품", "종근당", "대웅제약", "일동제약", "보령제약", 
    "SK케미칼", "삼성바이오로직스", "셀트리온", "JW중외제약", "한독", "에이치엘비", "광동제약",
    "경동제약", "부광약품", "현대약품", "동국제약", "제일약품", "삼진제약", "명인제약", "한림제약",
    "씨제이", "건일제약", "대원제약", "동화약품", "바이엘", "화이자", "노바티스", "로슈", "머크",
    "글락소스미스클라인", "아스트라제네카", "사노피", "애브비", "존슨앤존슨", "다케다", "일리릴리",
    "암젠", "길리어드", "태준제약", "신풍제약", "영진약품", "구주제약", "알보젠", "한국앨러간",
    
    # 약물 분류 코드 (ATC 코드 첫 번째 수준)
    "소화관", "혈액", "심혈관계", "피부", "비뇨생식기계", "호르몬", "항감염제", "항암제",
    "근골격계", "신경계", "항기생충제", "호흡기계", "감각기관", "기타", 
    
    # 흔한 약물 성분명
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
    
    # 효능별 분류 (대표적인 치료 효과)
    "진통제", "해열제", "항생제", "소화제", "변비약", "설사약", "고혈압약", "당뇨약", 
    "고지혈증약", "항히스타민제", "항우울제", "수면제", "진정제", "비타민", "철분제",
    "기관지확장제", "스테로이드", "피부질환", "안약", "항암제", "면역억제제", "항응고제",
    "항혈소판제", "이뇨제", "구토억제제", "항경련제", "근육이완제", "항파킨슨제", "피임약",
    "호르몬대체요법", "갑상선약", "전립선약", "항바이러스제", "항진균제", "항결핵제", "골다공증약",
    "관절염약", "통풍약", "편두통약", "천식약", "COPD약", "알레르기약", "치매약", "항정신병약",
    "강장제", "영양제", "소염제", "면역조절제", "구충제", "항구토제", "제산제", "위장약",
    "항경련제", "항간질제", "항균제", "항바이러스제", "항말라리아제", "최면제", "각종 호르몬제",
    
    # 인기 약품 및 브랜드명
    "타이레놀", "게보린", "판콜", "부루펜", "아스피린", "베아제", "백초시럽", "판피린",
    "액티피드", "판콜에이", "신신파스", "제일쿨파스", "캐롤", "텐텐", "이가탄", "센트룸",
    "아로나민", "삐콤씨", "컨디션", "박카스", "인사돌", "쌍화탕", "우루사", "훼스탈",
    "무좀약", "노스카나", "에어탈", "이지엔", "써스펜", "지르텍", "클라리틴", "알레그라",
    "에어미드", "대웅", "한독", "바이엘", "화이자", "한미", "종근당", "일동", "녹십자",
    "유한양행", "보령", "광동", "경동", "부광", "현대", "동국", "제일약품", "삼진", "명인",
    "한림", "씨제이", "건일", "대원", "동화", "정우", "바이탈", "럭스", "데일리",
    
    # 다양한 적응증 및 질환
    "고혈압", "당뇨", "고지혈증", "위염", "역류성식도염", "궤양", "설사", "변비", "알레르기",
    "비염", "아토피", "두통", "편두통", "관절염", "류마티스", "통풍", "골다공증", "골절",
    "요통", "좌골신경통", "디스크", "천식", "기관지염", "폐렴", "결핵", "감기", "독감",
    "인플루엔자", "만성폐쇄성폐질환", "심부전", "부정맥", "협심증", "심근경색", "뇌졸중",
    "동맥경화", "혈전증", "빈혈", "백혈병", "림프종", "전립선염", "전립선비대증", "방광염",
    "요로감염", "신부전", "신장결석", "간염", "간경변", "담석증", "담낭염", "췌장염",
    "갑상선기능항진증", "갑상선기능저하증", "쿠싱증후군", "애디슨병", "당뇨병성신증",
    "당뇨병성망막병증", "당뇨병성신경병증", "우울증", "조울증", "조현병", "불안장애",
    "공황장애", "강박장애", "외상후스트레스장애", "알츠하이머", "파킨슨병", "간질", "발작",
    "불면증", "과다수면증", "피부염", "건선", "여드름", "대상포진", "결핵"
]
    
    # 완료된, 진행 중인 키워드 파일 설정
    COMPLETED_KEYWORDS_FILE = 'completed_keywords.txt'
    IN_PROGRESS_KEYWORDS_FILE = 'in_progress_keywords.txt'

    # 완료된 키워드 로드
    def load_completed_keywords():
        if os.path.exists(COMPLETED_KEYWORDS_FILE):
            with open(COMPLETED_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        return []

    # 진행 중인 키워드 로드
    def load_in_progress_keyword():
        if os.path.exists(IN_PROGRESS_KEYWORDS_FILE):
            with open(IN_PROGRESS_KEYWORDS_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if lines:
                    return lines[0].strip()
        return None

    # 완료된 키워드 저장
    def save_completed_keyword(keyword):
        with open(COMPLETED_KEYWORDS_FILE, 'a', encoding='utf-8') as f:
            f.write(keyword + '\n')

    # 진행 중인 키워드 저장
    def save_in_progress_keyword(keyword):
        with open(IN_PROGRESS_KEYWORDS_FILE, 'w', encoding='utf-8') as f:
            f.write(keyword + '\n')

    # 진행 중인 키워드 제거
    def clear_in_progress_keyword():
        if os.path.exists(IN_PROGRESS_KEYWORDS_FILE):
            os.remove(IN_PROGRESS_KEYWORDS_FILE)

    # 완료된 키워드 로드
    completed_keywords = load_completed_keywords()
    logger.info(f"이미 완료된 키워드: {len(completed_keywords)}개")

    # 진행 중인 키워드 확인
    in_progress_keyword = load_in_progress_keyword()
    if in_progress_keyword:
        logger.info(f"이전에 중단된 키워드 '{in_progress_keyword}'부터 재개합니다.")
        # 진행 중인 키워드가 search_keywords에 없으면 추가
        if in_progress_keyword not in search_keywords:
            search_keywords = [in_progress_keyword] + search_keywords

    # 남은 키워드 필터링
    remaining_keywords = [k for k in search_keywords if k not in completed_keywords]
    logger.info(f"처리할 남은 키워드: {len(remaining_keywords)}개")

    # 진행 중인 키워드가 있으면 맨 앞으로 이동
    if in_progress_keyword and in_progress_keyword in remaining_keywords:
        remaining_keywords.remove(in_progress_keyword)
        remaining_keywords.insert(0, in_progress_keyword)

    # API 호출 카운터 추가
    api_call_counter = 0
    MAX_DAILY_CALLS = 24000  # 여유 있게 설정 (하루 한도 25,000)

    # 데이터 수집 실행 (API 호출 한도 고려)
    try:
        for keyword in remaining_keywords:
            logger.info(f"키워드 '{keyword}' 처리 시작")
            
            # 진행 중인 키워드 표시
            save_in_progress_keyword(keyword)
            
            # 이 키워드에 대한 결과 수집
            fetched_count, api_calls = crawler.fetch_keyword_data(keyword, max_results=1000)
            
            # API 호출 카운터 업데이트
            api_call_counter += api_calls
            logger.info(f"현재까지 API 호출 횟수: {api_call_counter}/{MAX_DAILY_CALLS}")
            
            # 키워드 완료 처리
            save_completed_keyword(keyword)
            clear_in_progress_keyword()
            
            # API 한도 체크
            if api_call_counter >= MAX_DAILY_CALLS:
                logger.warning(f"일일 API 호출 한도에 도달: {api_call_counter}회. 작업 중단.")
                break
    except KeyboardInterrupt:
        logger.warning("사용자에 의해 중단됨")
    except Exception as e:
        logger.error(f"예기치 않은 오류 발생: {e}", exc_info=True)
    
    # 실행 종료 시간
    end_time = datetime.now()
    duration = end_time - start_time
    
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