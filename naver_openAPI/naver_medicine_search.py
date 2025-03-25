import os
import sys
import urllib.request
import json
from bs4 import BeautifulSoup

class NaverMedicineSearch:
    def __init__(self, client_id, client_secret):
        """
        네이버 API 클라이언트 초기화
        
        Args:
            client_id (str): u1WaLkN7noyDRj4OiCfV
            client_secret (str): h33N4vTMpw
        """
        self.client_id = client_id
        self.client_secret = client_secret
        
    def search_medicine(self, query, display=5):
        """
        약품 이름으로 검색하여 백과사전 결과 반환
        
        Args:
            query (str): 검색할 약품 이름
            display (int): 검색 결과 개수 (최대 100)
            
        Returns:
            dict: 검색 결과 JSON 데이터
        """
        encText = urllib.parse.quote(f"{query} 의약품")
        url = f"https://openapi.naver.com/v1/search/encyc?query={encText}&display={display}"
        
        request = urllib.request.Request(url)
        request.add_header("X-Naver-Client-Id", self.client_id)
        request.add_header("X-Naver-Client-Secret", self.client_secret)
        
        try:
            response = urllib.request.urlopen(request)
            rescode = response.getcode()
            
            if rescode == 200:
                response_body = response.read()
                result = json.loads(response_body.decode('utf-8'))
                return result
            else:
                print(f"Error Code: {rescode}")
                return None
        except Exception as e:
            print(f"Exception: {e}")
            return None
    
    def get_medicine_details(self, url):
        """
        약품 상세 페이지 정보 추출 (웹 스크래핑)
        
        Args:
            url (str): 약품 상세 페이지 URL
            
        Returns:
            dict: 약품 상세 정보
        """
        try:
            req = urllib.request.Request(url)
            response = urllib.request.urlopen(req)
            html = response.read().decode('utf-8')
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # 의약품 사전의 경우 상세 정보 추출
            # 참고: 실제 구현 시 HTML 구조에 따라 수정 필요
            medicine_info = {}
            
            # 여기서는 예시 구현입니다. 실제 사이트에 맞게 조정 필요
            title = soup.select_one('h2, h3')
            if title:
                medicine_info['name'] = title.get_text().strip()
            
            info_sections = soup.select('dl.info_section')
            for section in info_sections:
                dt_elements = section.select('dt')
                dd_elements = section.select('dd')
                
                for i in range(len(dt_elements)):
                    if i < len(dd_elements):
                        key = dt_elements[i].get_text().strip()
                        value = dd_elements[i].get_text().strip()
                        medicine_info[key] = value
            
            # 상세 설명 부분 추출
            description = soup.select_one('div.detail_info')
            if description:
                medicine_info['description'] = description.get_text().strip()
                
            return medicine_info
        except Exception as e:
            print(f"Error fetching medicine details: {e}")
            return None

def main():
    # 네이버 개발자 센터에서 발급받은 인증 정보 입력
    client_id = "YOUR_CLIENT_ID"  # 여기에 발급받은 클라이언트 ID 입력
    client_secret = "YOUR_CLIENT_SECRET"  # 여기에 발급받은 클라이언트 시크릿 입력
    
    # 검색할 약품 이름 입력
    search_query = input("검색할 약품 이름을 입력하세요: ")
    
    # 네이버 약품 검색 인스턴스 생성
    medicine_search = NaverMedicineSearch(client_id, client_secret)
    
    # 약품 검색 실행
    search_results = medicine_search.search_medicine(search_query)
    
    if search_results and 'items' in search_results:
        print(f"\n'{search_query}'에 대한 검색 결과: {search_results['total']}개 중 {len(search_results['items'])}개 표시")
        print("=" * 80)
        
        for idx, item in enumerate(search_results['items'], 1):
            # HTML 태그 제거
            title = BeautifulSoup(item['title'], 'html.parser').get_text()
            description = BeautifulSoup(item['description'], 'html.parser').get_text()
            
            print(f"{idx}. {title}")
            print(f"   링크: {item['link']}")
            print(f"   설명: {description}")
            print("-" * 80)
            
            # 첫 번째 결과에 대해 상세 정보 가져오기 (예시)
            if idx == 1:
                print("\n첫 번째 검색결과의 상세 정보:")
                medicine_details = medicine_search.get_medicine_details(item['link'])
                if medicine_details:
                    for key, value in medicine_details.items():
                        print(f"{key}: {value}")
                print("=" * 80)
    else:
        print(f"'{search_query}'에 대한 검색 결과가 없습니다.")

if __name__ == "__main__":
    main()