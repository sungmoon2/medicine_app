# 라우팅 코드 - 추후 개발 시 app.py에서 분리하여 사용
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
