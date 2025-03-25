import urllib.request
import urllib.parse
import json
import os
import datetime

# 1. 네이버 API 인증 정보
client_id = "u1WaLkN7noyDRj4OiCfV"  # 여기에 발급받은 클라이언트 ID 입력
client_secret = "h33N4vTMpw"  # 여기에 발급받은 클라이언트 시크릿 입력

# 2. 검색어 인코딩
search_term = "모티리톤"
encoded_search_term = urllib.parse.quote(search_term)

# 3. API URL 설정
url = f"https://openapi.naver.com/v1/search/encyc.json?query={encoded_search_term}"

# 4. HTTP 요청 설정
request = urllib.request.Request(url)
request.add_header("X-Naver-Client-Id", client_id)
request.add_header("X-Naver-Client-Secret", client_secret)

try:
    # 5. API 호출 및 결과 처리
    response = urllib.request.urlopen(request)
    rescode = response.getcode()
    
    if rescode == 200:
        # 응답 데이터 읽기 및 파싱
        response_body = response.read()
        result = json.loads(response_body.decode('utf-8'))
        
        # 현재 작업 디렉토리 출력
        current_dir = os.getcwd()
        print(f"현재 작업 디렉토리: {current_dir}")
        
        # 저장할 디렉토리 생성 (없는 경우)
        data_dir = os.path.join(current_dir, "api_data")
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            print(f"데이터 디렉토리 생성됨: {data_dir}")
        
        # 타임스탬프를 파일명에 추가하여 중복 방지
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{search_term}_{timestamp}.json"
        file_path = os.path.join(data_dir, file_name)
        
        # 데이터를 JSON 파일로 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
        
        print(f"\n검색 결과가 다음 위치에 저장되었습니다:")
        print(f"파일 경로: {file_path}")
        
        # 첫 번째 결과 항목 링크 출력 (약품 상세 페이지)
        if result['items'] and len(result['items']) > 0:
            first_item = result['items'][0]
            print(f"\n첫 번째 검색 결과:")
            print(f"제목: {first_item['title'].replace('<b>', '').replace('</b>', '')}")
            print(f"링크: {first_item['link']}")
            print(f"설명: {first_item['description'][:100]}...")
            
            # URL 파싱하여 세부 정보 출력
            from urllib.parse import urlparse
            parsed_url = urlparse(first_item['link'])
            print(f"\n타겟 URL 정보:")
            print(f"스키마: {parsed_url.scheme}")
            print(f"네트워크 위치: {parsed_url.netloc}")
            print(f"경로: {parsed_url.path}")
            print(f"쿼리 매개변수: {parsed_url.query}")
    else:
        print(f"API 호출 실패: 상태 코드 {rescode}")

except Exception as e:
    print(f"오류 발생: {e}")

print("\n처리 완료!")