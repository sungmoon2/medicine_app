import pandas as pd

# CSV 파일 로드
file_path = 'null_values_data.csv'  # CSV 파일 경로
df = pd.read_csv(file_path)

# 데이터프레임 컬럼 확인
print("데이터프레임의 컬럼:")
print(df.columns)

# 'source_api' 컬럼이 없다면 다른 방법으로 null 값을 분석
if 'source_api' not in df.columns:
    print("'source_api' 컬럼이 존재하지 않으므로 다른 방식으로 null 값 분석을 진행합니다.")
    
    # 전체 데이터에서 null 값이 많은 컬럼 확인
    null_info = df.isnull().sum()  # 각 컬럼별 null 값 개수
    print("각 컬럼의 null 값 개수:")
    print(null_info)
    
    # null 값이 많은 상위 10개 컬럼 출력
    null_columns = null_info[null_info > 0].sort_values(ascending=False).head(10)
    print("null 값이 많은 상위 10개 컬럼:")
    print(null_columns)
    
    # 특정 컬럼에 대해서만 null 값 확인 (예: item_name)
    column_name_with_null = "item_name"  # 분석할 컬럼 지정
    if column_name_with_null in df.columns:
        null_in_column = df[column_name_with_null].isnull().sum()
        print(f"{column_name_with_null} 컬럼의 null 값 개수: {null_in_column}")
    else:
        print(f"{column_name_with_null} 컬럼은 데이터프레임에 존재하지 않습니다.")

    # 특정 API에서 받아온 데이터의 null 값 분석 (source_api 컬럼이 없으므로 다른 방법)
    # 예시로 'gnl_nm_cd' 컬럼에서 null 값이 있는 데이터 분석
    column_name_with_null = "gnl_nm_cd"  # 예시로 다른 컬럼을 지정
    if column_name_with_null in df.columns:
        null_in_column = df[column_name_with_null].isnull().sum()
        print(f"{column_name_with_null} 컬럼의 null 값 개수: {null_in_column}")
    else:
        print(f"{column_name_with_null} 컬럼은 데이터프레임에 존재하지 않습니다.")
else:
    print("'source_api' 컬럼이 존재하므로 해당 컬럼을 사용하여 null 값을 분석합니다.")
    
    # 'source_api' 컬럼에서 각 API별 null 값 개수 확인
    api_null_info = df.groupby('source_api')['item_name'].apply(lambda x: x.isnull().sum())
    print("각 API별 'item_name' 컬럼에서 null 값 개수:")
    print(api_null_info)

    # 'source_api' 컬럼에서 null 값이 많은 API 분석
    api_null_info_sorted = api_null_info.sort_values(ascending=False)
    print("null 값이 많은 상위 API들:")
    print(api_null_info_sorted)
