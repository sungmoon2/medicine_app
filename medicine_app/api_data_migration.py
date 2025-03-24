import json
import mysql.connector
import csv

# MySQL 연결 설정
conn = mysql.connector.connect(
    host="localhost",   # 실제 사용 중인 호스트명으로 변경
    user="root",   # MySQL 사용자 이름
    password="1234",  # MySQL 비밀번호
    database="medicine_db"  # 데이터베이스 이름
)

if conn.is_connected():
    print("MySQL에 연결되었습니다.")
else:
    print("MySQL 연결 실패")
    exit(1)

# 커서 생성
cursor = conn.cursor(dictionary=True)  # 결과를 딕셔너리 형태로 가져옴

# 테이블과 컬럼 목록 조회
cursor.execute("DESCRIBE integrated_drug_info;")
columns = cursor.fetchall()

# 각 컬럼에서 NULL 값이 있는 데이터를 찾기 위한 쿼리 생성
null_columns = []  # NULL 값이 있을 수 있는 컬럼을 저장할 리스트
for column in columns:
    if column['Null'] == 'YES':  # NULL 허용 컬럼인 경우
        null_columns.append(column['Field'])

# CSV 파일로 데이터를 저장하는 함수
def save_to_csv(data, column_names, file_name):
    # CSV 파일로 저장
    with open(file_name, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=column_names)
        writer.writeheader()  # 헤더 작성
        for row in data:
            writer.writerow(row)  # 각 행을 CSV에 작성

# NULL 값이 있는 데이터 조회
try:
    # NULL 값이 있는 컬럼들을 기준으로 데이터를 조회
    all_null_data = []  # 모든 NULL 데이터를 저장할 리스트
    for column in null_columns:
        query = f"SELECT * FROM integrated_drug_info WHERE {column} IS NULL"
        cursor.execute(query)
        results = cursor.fetchall()

        # 결과가 있을 경우
        if results:
            print(f"컬럼 '{column}'에서 NULL 값을 가진 데이터:")
            all_null_data.extend(results)  # NULL 값을 가진 데이터를 모두 리스트에 추가
        else:
            print(f"컬럼 '{column}'에서 NULL 값이 없습니다.")
    
    # NULL 값을 가진 데이터를 CSV로 저장
    if all_null_data:
        print("CSV 파일로 저장 중...")
        save_to_csv(all_null_data, column_names=[column['Field'] for column in columns], file_name='null_values_data.csv')
        print("CSV 파일로 저장이 완료되었습니다.")
    else:
        print("NULL 값을 가진 데이터가 없습니다.")

except mysql.connector.Error as err:
    print(f"오류 발생: {err}")

finally:
    # 연결 종료
    cursor.close()
    conn.close()
