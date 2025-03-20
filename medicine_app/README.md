# 의약품 검색 및 관리 웹 애플리케이션

이 프로젝트는 식품의약품안전처에서 제공하는 공공 API를 활용하여 의약품 정보를 검색하고 관리할 수 있는 웹 애플리케이션입니다.

## 기능

- 의약품 이름, 모양, 색상, 표시(각인) 등으로 의약품 검색
- 의약품 상세 정보 조회 (효능, 용법, 주의사항, 성분 정보 등)
- 병용금기, 특정연령대금기, 임부금기 등 DUR 정보 제공

## 기술 스택

- **백엔드**: Python, Flask
- **데이터베이스**: MySQL
- **프론트엔드**: HTML, CSS, JavaScript, Bootstrap 5
- **API**: 식품의약품안전처 공공데이터 Open API

## 설치 방법

### 필수 요구사항

- Python 3.8 이상
- MySQL 8.0 이상
- 식품의약품안전처 공공데이터포털 API 키

### 설치 과정

1. 저장소 복제
   ```bash
   git clone https://github.com/yourusername/medicine-app.git
   cd medicine-app
   ```

2. 가상 환경 생성 및 활성화
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. 의존성 패키지 설치
   ```bash
   pip install -r requirements.txt
   ```

4. 환경 변수 설정
   - `.env` 파일 생성 후 아래 내용 추가
   ```
   DB_HOST=localhost
   DB_USER=your_mysql_username
   DB_PASSWORD=your_mysql_password
   DB_NAME=medicine_db
   OPEN_API_KEY=your_api_key
   FLASK_SECRET_KEY=your_secret_key
   ```

5. 데이터베이스 설정
   - MySQL Workbench 또는 명령줄에서 `mysql_setup.sql` 실행
   ```bash
   mysql -u username -p < mysql_setup.sql
   ```

6. 데이터 수집 및 통합
   ```bash
   python data_integration.py
   ```

7. 애플리케이션 실행
   ```bash
   python app.py
   ```

8. 웹 브라우저에서 접속
   - http://localhost:5000

## 데이터 구조

이 프로젝트는 다음과 같은 데이터베이스 테이블 구조를 사용합니다:

- `medicines`: 의약품 기본 정보
- `medicine_shapes`: 의약품 모양/색상 정보
- `medicine_images`: 의약품 이미지 정보
- `medicine_usage`: 효능/용법 정보
- `medicine_components`: 성분 정보
- `medicine_dur_*`: DUR 관련 정보 (병용금기, 특정연령대금기 등)

## API 연동

이 애플리케이션은 다음 식품의약품안전처 API를 사용합니다:

1. 의약품 낱알 정보 API
2. 의약품 상세 정보 API
3. DUR 정보 API (병용금기, 특정연령대금기 등)
4. 의약품 성분 정보 API
5. 1일 최대투여량 정보 API

각 API의 데이터를 통합하여 종합적인 의약품 정보 데이터베이스를 구축합니다.

## 프로젝트 구조

```
medicine_app/
│
├── app.py                  # Flask 애플리케이션 메인 파일
├── data_integration.py     # API 데이터 수집 및 통합 스크립트
├── config.py               # 애플리케이션 설정 파일
├── models.py               # 데이터베이스 모델 정의
├── requirements.txt        # 의존성 패키지 목록
├── mysql_setup.sql         # 데이터베이스 설정 스크립트
│
├── static/                 # 정적 파일 디렉토리
│   ├── css/
│   │   └── style.css       # 메인 스타일시트
│   ├── js/
│   │   └── script.js       # 메인 JavaScript 파일
│   └── img/                # 이미지 파일
│
└── templates/              # HTML 템플릿 디렉토리
    ├── index.html          # 메인 검색 페이지
    ├── search_results.html # 검색 결과 페이지
    └── medicine_detail.html # 의약품 상세 정보 페이지
```

## 라이선스

MIT License

## 기여 방법

1. 이 저장소를 포크합니다.
2. 새 기능 브랜치를 생성합니다 (`git checkout -b feature/amazing-feature`).
3. 변경사항을 커밋합니다 (`git commit -m 'Add some amazing feature'`).
4. 브랜치에 푸시합니다 (`git push origin feature/amazing-feature`).
5. Pull Request를 생성합니다.