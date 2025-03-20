import os
import shutil

def create_directory(path):
    """디렉토리 생성 함수"""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"디렉토리 생성됨: {path}")
    else:
        print(f"디렉토리가 이미 존재함: {path}")

def create_file(path, content=""):
    """파일 생성 함수"""
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
    
    if not os.path.exists(path):
        with open(path, 'w', encoding='utf-8') as file:
            file.write(content)
        print(f"파일 생성됨: {path}")
    else:
        print(f"파일이 이미 존재함: {path}")

def create_medicine_app_project():
    """의약품 검색 및 관리 웹 애플리케이션 프로젝트 구조 생성"""
    # 프로젝트 루트 디렉토리
    project_dir = "medicine_app"
    
    # 기존 프로젝트 디렉토리가 있으면 확인 후 삭제
    if os.path.exists(project_dir):
        confirm = input(f"'{project_dir}' 디렉토리가 이미 존재합니다. 삭제하고 새로 만드시겠습니까? (y/n): ")
        if confirm.lower() == 'y':
            shutil.rmtree(project_dir)
            print(f"'{project_dir}' 디렉토리가 삭제되었습니다.")
        else:
            print("프로젝트 생성이 취소되었습니다.")
            return
    
    # 디렉토리 구조 생성
    create_directory(project_dir)
    create_directory(os.path.join(project_dir, "static"))
    create_directory(os.path.join(project_dir, "static/css"))
    create_directory(os.path.join(project_dir, "static/js"))
    create_directory(os.path.join(project_dir, "static/img"))
    create_directory(os.path.join(project_dir, "templates"))
    
    # 파일 생성
    create_file(os.path.join(project_dir, "app.py"), """from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# 세션 비밀키 설정
app.secret_key = 'your_secret_key'

# MySQL 연결 설정
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'  # MySQL 사용자명
app.config['MYSQL_PASSWORD'] = 'your_password'  # MySQL 비밀번호
app.config['MYSQL_DB'] = 'medicine_db'  # 데이터베이스 이름

# MySQL 인스턴스 초기화
mysql = MySQL(app)

# 메인 페이지 라우트
@app.route('/')
def index():
    # 로그인 여부 확인
    if 'loggedin' in session:
        # 사용자가 로그인한 경우 메인 페이지 렌더링
        return render_template('index.html', username=session['username'])
    # 로그인하지 않은 경우 로그인 페이지로 리디렉션
    return redirect(url_for('login'))

# 로그인 페이지 라우트
@app.route('/login', methods=['GET', 'POST'])
def login():
    # 로그인 폼 제출 처리
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']
        
        # MySQL 커서 생성
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        
        # 사용자 정보 가져오기
        user = cursor.fetchone()
        
        # 로그인 정보 검증
        if user and check_password_hash(user['password'], password):
            # 로그인 성공, 세션 생성
            session['loggedin'] = True
            session['id'] = user['id']
            session['username'] = user['username']
            
            # 메인 페이지로 리디렉션
            return redirect(url_for('index'))
        else:
            # 로그인 실패
            flash('잘못된 사용자 이름/비밀번호입니다!')
    
    # 로그인 페이지 렌더링
    return render_template('login.html')

# 로그아웃 라우트
@app.route('/logout')
def logout():
    # 세션에서 사용자 정보 제거
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    
    # 로그인 페이지로 리디렉션
    return redirect(url_for('login'))

# 회원가입 페이지 라우트
@app.route('/register', methods=['GET', 'POST'])
def register():
    # 회원가입 폼 제출 처리
    if request.method == 'POST':
        # 폼 데이터 가져오기
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        age = request.form['age']
        ssn = request.form['ssn']  # 주민등록번호
        phone = request.form['phone']
        height = request.form['height']
        weight = request.form['weight']
        
        # MySQL 커서 생성
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        
        # 사용자 이름 중복 확인
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        account = cursor.fetchone()
        
        # 폼 유효성 검사
        if account:
            flash('이미 존재하는 계정입니다!')
        elif not re.match(r'[A-Za-z0-9]+', username):
            flash('사용자 이름은 문자와 숫자만 포함해야 합니다!')
        elif not username or not password or not name or not age or not ssn or not phone:
            flash('양식을 작성해주세요!')
        else:
            # 비밀번호 해싱
            hashed_password = generate_password_hash(password)
            
            # 새 사용자 추가
            cursor.execute('INSERT INTO users (username, password, name, age, ssn, phone, height, weight) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                           (username, hashed_password, name, age, ssn, phone, height, weight))
            mysql.connection.commit()
            
            flash('성공적으로 등록되었습니다!')
            return redirect(url_for('login'))
    
    # 회원가입 페이지 렌더링
    return render_template('register.html')

if __name__ == '__main__':
    app.run(debug=True)
""")
    
    create_file(os.path.join(project_dir, "config.py"), """# 데이터베이스 설정
DATABASE_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'your_password',
    'db': 'medicine_db',
    'charset': 'utf8mb4'
}

# 애플리케이션 설정
SECRET_KEY = 'your_secret_key'
DEBUG = True
""")
    
    create_file(os.path.join(project_dir, "models.py"), """# 데이터베이스 모델링 - 추후 개발 시 사용
class User:
    def __init__(self, id=None, username=None, name=None, age=None, ssn=None, phone=None, height=None, weight=None):
        self.id = id
        self.username = username
        self.name = name
        self.age = age
        self.ssn = ssn
        self.phone = phone
        self.height = height
        self.weight = weight

class Medicine:
    def __init__(self, id=None, name=None, ingredient=None, effect=None, usage_info=None, caution=None, company=None):
        self.id = id
        self.name = name
        self.ingredient = ingredient
        self.effect = effect
        self.usage_info = usage_info
        self.caution = caution
        self.company = company

class UserMedicine:
    def __init__(self, id=None, user_id=None, medicine_id=None, dosage=None, start_date=None, end_date=None, reminder=False, reminder_time=None, notes=None):
        self.id = id
        self.user_id = user_id
        self.medicine_id = medicine_id
        self.dosage = dosage
        self.start_date = start_date
        self.end_date = end_date
        self.reminder = reminder
        self.reminder_time = reminder_time
        self.notes = notes
""")
    
    create_file(os.path.join(project_dir, "routes.py"), """# 라우팅 코드 - 추후 개발 시 app.py에서 분리하여 사용
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

main = Blueprint('main', __name__)
auth = Blueprint('auth', __name__)
medicine = Blueprint('medicine', __name__)

# 메인 라우트
@main.route('/')
def index():
    pass

# 인증 라우트
@auth.route('/login', methods=['GET', 'POST'])
def login():
    pass

@auth.route('/logout')
def logout():
    pass

@auth.route('/register', methods=['GET', 'POST'])
def register():
    pass

# 의약품 관련 라우트
@medicine.route('/search', methods=['GET', 'POST'])
def search():
    pass

@medicine.route('/medicine/<int:id>')
def medicine_detail(id):
    pass

@medicine.route('/my-medicines')
def my_medicines():
    pass
""")
    
    # 템플릿 파일 생성
    create_file(os.path.join(project_dir, "templates/base.html"), """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}의약품 검색 및 관리 시스템{% endblock %}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('index') }}">의약품 검색 시스템</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    {% if session.loggedin %}
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('index') }}">홈</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('logout') }}">로그아웃</a>
                    </li>
                    {% else %}
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('login') }}">로그인</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('register') }}">회원가입</a>
                    </li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        {% with messages = get_flashed_messages() %}
        {% if messages %}
        <div class="alert alert-info">
            {% for message in messages %}
            {{ message }}
            {% endfor %}
        </div>
        {% endif %}
        {% endwith %}

        {% block content %}
        {% endblock %}
    </div>

    <footer class="bg-light py-3 mt-5">
        <div class="container text-center">
            <p class="text-muted">© 2025 의약품 검색 및 관리 시스템</p>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{{ url_for('static', filename='js/script.js') }}"></script>
</body>
</html>
""")
    
    create_file(os.path.join(project_dir, "templates/index.html"), """{% extends 'base.html' %}

{% block title %}메인 페이지 - 의약품 검색 및 관리 시스템{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <div class="card">
            <div class="card-header bg-primary text-white">
                <h2 class="text-center">환영합니다!</h2>
            </div>
            <div class="card-body">
                <h4 class="card-title">{{ username }}님, 안녕하세요!</h4>
                <p class="card-text">의약품 검색 및 관리 시스템에 로그인하셨습니다.</p>
                
                <div class="mt-4">
                    <h5>서비스 안내</h5>
                    <ul>
                        <li>의약품 검색: 이름, 성분, 효능 등으로 의약품 검색</li>
                        <li>내 의약품 관리: 복용 중인 의약품 기록 및 관리</li>
                        <li>복용 일정: 의약품 복용 알림 설정</li>
                        <li>부작용 정보: 의약품 부작용 및 주의사항 확인</li>
                    </ul>
                </div>
                
                <div class="text-center mt-4">
                    <a href="#" class="btn btn-primary me-2">의약품 검색</a>
                    <a href="#" class="btn btn-outline-primary">내 의약품 관리</a>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
""")
    
    create_file(os.path.join(project_dir, "templates/login.html"), """{% extends 'base.html' %}

{% block title %}로그인 - 의약품 검색 및 관리 시스템{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card">
            <div class="card-header bg-primary text-white">
                <h2 class="text-center">로그인</h2>
            </div>
            <div class="card-body">
                <form method="post" action="{{ url_for('login') }}">
                    <div class="mb-3">
                        <label for="username" class="form-label">사용자 아이디</label>
                        <input type="text" class="form-control" id="username" name="username" required>
                    </div>
                    <div class="mb-3">
                        <label for="password" class="form-label">비밀번호</label>
                        <input type="password" class="form-control" id="password" name="password" required>
                    </div>
                    <div class="d-grid">
                        <button type="submit" class="btn btn-primary">로그인</button>
                    </div>
                </form>
                
                <div class="text-center mt-3">
                    <p>계정이 없으신가요? <a href="{{ url_for('register') }}">회원가입</a></p>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
""")
    
    create_file(os.path.join(project_dir, "templates/register.html"), """{% extends 'base.html' %}

{% block title %}회원가입 - 의약품 검색 및 관리 시스템{% endblock %}

{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <div class="card">
            <div class="card-header bg-primary text-white">
                <h2 class="text-center">회원가입</h2>
            </div>
            <div class="card-body">
                <form method="post" action="{{ url_for('register') }}">
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label for="username" class="form-label">사용자 아이디</label>
                            <input type="text" class="form-control" id="username" name="username" required>
                        </div>
                        <div class="col-md-6 mb-3">
                            <label for="password" class="form-label">비밀번호</label>
                            <input type="password" class="form-control" id="password" name="password" required>
                        </div>
                    </div>

                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label for="name" class="form-label">이름</label>
                            <input type="text" class="form-control" id="name" name="name" required>
                        </div>
                        <div class="col-md-6 mb-3">
                            <label for="age" class="form-label">나이</label>
                            <input type="number" class="form-control" id="age" name="age" required>
                        </div>
                    </div>

                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label for="ssn" class="form-label">주민등록번호 (앞 6자리-뒷자리 첫번째자리)</label>
                            <input type="text" class="form-control" id="ssn" name="ssn" placeholder="예: 010430-3" required pattern="[0-9]{6}-[1-4]{1}">
                            <div class="form-text">형식: 생년월일 6자리-성별 1자리</div>
                        </div>
                        <div class="col-md-6 mb-3">
                            <label for="phone" class="form-label">휴대전화번호</label>
                            <input type="tel" class="form-control" id="phone" name="phone" placeholder="예: 010-5577-5471" required pattern="[0-9]{3}-[0-9]{4}-[0-9]{4}">
                            <div class="form-text">형식: 000-0000-0000</div>
                        </div>
                    </div>

                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label for="height" class="form-label">키 (cm)</label>
                            <input type="number" step="0.1" class="form-control" id="height" name="height" required>
                        </div>
                        <div class="col-md-6 mb-3">
                            <label for="weight" class="form-label">몸무게 (kg)</label>
                            <input type="number" step="0.1" class="form-control" id="weight" name="weight" required>
                        </div>
                    </div>

                    <div class="d-grid">
                        <button type="submit" class="btn btn-primary">회원가입</button>
                    </div>
                </form>
                
                <div class="text-center mt-3">
                    <p>이미 계정이 있으신가요? <a href="{{ url_for('login') }}">로그인</a></p>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
""")
    
    # 정적 파일 생성
    create_file(os.path.join(project_dir, "static/css/style.css"), """/* 기본 스타일 */
body {
    font-family: 'Noto Sans KR', sans-serif;
    background-color: #f8f9fa;
    color: #333;
}

/* 카드 스타일 */
.card {
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    margin-bottom: 20px;
}

.card-header {
    border-radius: 10px 10px 0 0 !important;
}

/* 폼 스타일 */
.form-control:focus {
    border-color: #0d6efd;
    box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.25);
}

/* 버튼 스타일 */
.btn-primary {
    background-color: #0d6efd;
    border-color: #0d6efd;
}

.btn-primary:hover {
    background-color: #0b5ed7;
    border-color: #0a58ca;
}

/* 네비게이션 바 스타일 */
.navbar {
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

/* 푸터 스타일 */
footer {
    border-top: 1px solid #e9ecef;
}
""")
    
    create_file(os.path.join(project_dir, "static/js/script.js"), """// 문서가 로드된 후 실행
document.addEventListener('DOMContentLoaded', function() {
    // 주민등록번호 형식 검증
    const ssnInput = document.getElementById('ssn');
    if (ssnInput) {
        ssnInput.addEventListener('input', function(e) {
            let value = e.target.value;
            
            // 하이픈 자동 추가
            if (value.length === 6 && !value.includes('-')) {
                e.target.value = value + '-';
            }
            
            // 주민등록번호 유효성 검사 (간단한 패턴만 체크)
            const ssnPattern = /^[0-9]{6}-[1-4]{1}$/;
            if (value.length >= 8 && !ssnPattern.test(value)) {
                ssnInput.setCustomValidity('올바른 주민등록번호 형식이 아닙니다 (예: 010430-3)');
            } else {
                ssnInput.setCustomValidity('');
            }
        });
    }
    
    // 휴대전화번호 형식 검증
    const phoneInput = document.getElementById('phone');
    if (phoneInput) {
        phoneInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/[^0-9]/g, '');
            
            // 하이픈 자동 추가
            if (value.length > 3 && value.length <= 7) {
                value = value.slice(0, 3) + '-' + value.slice(3);
            } else if (value.length > 7) {
                value = value.slice(0, 3) + '-' + value.slice(3, 7) + '-' + value.slice(7, 11);
            }
            
            e.target.value = value;
            
            // 휴대전화번호 유효성 검사
            const phonePattern = /^[0-9]{3}-[0-9]{4}-[0-9]{4}$/;
            if (value.length >= 13 && !phonePattern.test(value)) {
                phoneInput.setCustomValidity('올바른 휴대전화번호 형식이 아닙니다 (예: 010-5577-5471)');
            } else {
                phoneInput.setCustomValidity('');
            }
        });
    }
    
    // 알림 메시지 자동 숨김
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(function() {
            alert.style.opacity = '0';
            setTimeout(function() {
                alert.style.display = 'none';
            }, 500);
        }, 3000);
    });
});
""")
    
    # MySQL 설정 파일 추가
    create_file(os.path.join(project_dir, "mysql_setup.sql"), """-- 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS medicine_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 데이터베이스 선택
USE medicine_db;

-- 사용자 테이블 생성
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    age INT NOT NULL,
    ssn VARCHAR(8) NOT NULL,  -- 주민등록번호 (앞 6자리-뒷자리 첫번째자리)
    phone VARCHAR(15) NOT NULL,  -- 휴대전화번호
    height DECIMAL(5,2),  -- 키 (cm)
    weight DECIMAL(5,2),  -- 몸무게 (kg)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 의약품 정보 테이블 (추후 개발을 위한 예시)
CREATE TABLE IF NOT EXISTS medicines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    ingredient TEXT,
    effect TEXT,
    usage_info TEXT,
    caution TEXT,
    company VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 사용자 의약품 관리 테이블 (추후 개발을 위한 예시)
CREATE TABLE IF NOT EXISTS user_medicines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    medicine_id INT NOT NULL,
    dosage VARCHAR(100),
    start_date DATE,
    end_date DATE,
    reminder BOOLEAN DEFAULT FALSE,
    reminder_time TIME,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
""")

    # requirements.txt 파일 추가
    create_file(os.path.join(project_dir, "requirements.txt"), """Flask==2.3.3
Flask-MySQLdb==1.0.1
Werkzeug==2.3.7
mysqlclient==2.2.0
""")

    # README.md 파일 추가
    create_file(os.path.join(project_dir, "README.md"), """# 의약품 검색 및 관리 웹 애플리케이션

의약품 검색 및 관리를 위한 웹 애플리케이션입니다.

## 설치 방법

1. 필요한 패키지 설치:
```bash
pip install -r requirements.txt
```

2. MySQL 데이터베이스 설정:
- MySQL Workbench에서 `mysql_setup.sql` 스크립트 실행

3. `config.py` 파일에서 데이터베이스 연결 정보 수정

## 실행 방법

```bash
python app.py
```

## 기능

- 회원가입 및 로그인
- 의약품 검색
- 개인 의약품 관리
- 복용 일정 관리
""")

    print(f"\n프로젝트 '{project_dir}' 구조가 성공적으로 생성되었습니다!")
    print("이제 다음 명령어로 필요한 패키지를 설치할 수 있습니다:")
    print("pip install -r requirements.txt")
    
    print("\n데이터베이스 설정을 위해 MySQL Workbench에서 mysql_setup.sql 파일을 실행하세요.")
    print("\n마지막으로 다음 명령어로 애플리케이션을 실행할 수 있습니다:")
    print("python app.py")

if __name__ == "__main__":
    create_medicine_app_project()