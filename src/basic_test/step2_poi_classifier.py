"""
Step 2: POI 테마 분류
- 소상공인 CSV 데이터 로드
- 5대 테마로 분류: 녹지(green), 식당(food), 유흥(nightlife), 쇼핑(shopping), 카페(cafe)
"""
import os
import pandas as pd
from collections import Counter

# Configuration
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SRC_DIR, 'data')
STORE_CSV = os.path.join(DATA_DIR, '소상공인시장진흥공단_상가(상권)정보_서울_202510.csv')
OUTPUT_CSV = os.path.join(DATA_DIR, 'hongdae-poi-classified.csv')

# 홍대 지역 BBOX (Step 1과 동일)
HONGDAE_BBOX = [126.895, 37.540, 126.960, 37.580]

# 홍대 지역 필터 키워드 (행정동/도로명)
HONGDAE_KEYWORDS = [
    '서교동', '연남동', '상수동', '합정동', '동교동', '연희동', '망원동', '성산동',
    '홍대', '연남', '상수', '합정', '동교', '망원'
]

# 테마 분류 매핑
THEME_MAPPING = {
    'cafe': {
        'keywords': [
            '커피', '카페', 'coffee', 'cafe', '디저트', '베이커리', '빵', '케이크',
            '제과', '도넛', '마카롱', '와플', '차(茶)', '티하우스', '스터디카페',
            '아이스크림', '빙수', '음료', '쥬스', '스무디'
        ],
        'major_codes': [],  # 대분류 코드
        'middle_names': ['커피', '카페', '디저트', '베이커리', '빵', '차']
    },
    'food': {
        'keywords': [
            '한식', '양식', '일식', '중식', '분식', '패스트푸드', '치킨', '피자',
            '고기', '삼겹살', '갈비', '횟집', '해산물', '국밥', '찌개', '탕',
            '면', '라면', '우동', '파스타', '버거', '샌드위치', '도시락', '뷔페',
            '음식점', '식당', '정식', '백반', '덮밥', '볶음밥', '비빔밥', '냉면',
            '쌀국수', '타코', '브런치', '스테이크', '초밥', '롤', '아시아'
        ],
        'major_codes': ['I2'],  # 음식
        'middle_names': ['한식', '양식', '일식', '중식', '분식', '패스트푸드', '기타 간이', '음식']
    },
    'nightlife': {
        'keywords': [
            '주점', '호프', '바', 'bar', 'pub', '클럽', 'club', '나이트', '노래방',
            '단란주점', '유흥', '라운지', '이자카야', '포차', '와인바', '칵테일'
        ],
        'major_codes': [],
        'middle_names': ['주점', '유흥', '단란', '나이트']
    },
    'shopping': {
        'keywords': [
            '의류', '패션', '옷', '화장품', '잡화', '신발', '가방', '액세서리',
            '안경', '시계', '쥬얼리', '편의점', '마트', '슈퍼', '소매', '상점',
            '매장', '가게', '샵', 'shop', '편집샵', '빈티지', '셀렉트', '부티크'
        ],
        'major_codes': ['D1', 'D2', 'D3', 'D4', 'G2'],  # 소매업
        'middle_names': ['의류', '패션', '화장품', '잡화', '신발', '가방', '소매', '편의점']
    },
    'green': {
        # 녹지 테마는 POI에서는 거의 없음 (OSM 지리 데이터로 보완)
        'keywords': ['공원', '정원', '산책', '녹지', '숲', '자연'],
        'major_codes': [],
        'middle_names': []
    }
}


def load_poi_data():
    """소상공인 데이터 로드"""
    print("\n[1] Loading POI data...")

    # 인코딩 시도
    for encoding in ['cp949', 'utf-8-sig', 'euc-kr', 'utf-8']:
        try:
            df = pd.read_csv(STORE_CSV, encoding=encoding, low_memory=False)
            print(f"    [OK] Loaded with encoding: {encoding}")
            break
        except Exception as e:
            continue
    else:
        raise Exception("Could not load CSV with any encoding!")

    print(f"    Total POIs: {len(df):,}")

    # 컬럼 확인
    print(f"    Columns: {len(df.columns)}")

    return df


def filter_hongdae_area(df):
    """홍대 지역 POI 필터링"""
    print("\n[2] Filtering Hongdae area...")

    # 좌표 컬럼 찾기
    lng_col = lat_col = None
    for col in df.columns:
        if '경도' in col:
            lng_col = col
        if '위도' in col:
            lat_col = col

    if not lng_col or not lat_col:
        raise Exception(f"Could not find coordinate columns!")

    # 좌표를 숫자로 변환
    df[lng_col] = pd.to_numeric(df[lng_col], errors='coerce')
    df[lat_col] = pd.to_numeric(df[lat_col], errors='coerce')

    # 1차 필터: BBOX 기반
    bbox_mask = (
        (df[lng_col] >= HONGDAE_BBOX[0]) & (df[lng_col] <= HONGDAE_BBOX[2]) &
        (df[lat_col] >= HONGDAE_BBOX[1]) & (df[lat_col] <= HONGDAE_BBOX[3])
    )

    # 2차 필터: 키워드 기반 (BBOX 밖이지만 홍대 관련 지역인 경우)
    keyword_mask = pd.Series([False] * len(df))

    for col in ['행정동명', '법정동명', '도로명주소', '지번주소']:
        if col in df.columns:
            for keyword in HONGDAE_KEYWORDS:
                keyword_mask |= df[col].astype(str).str.contains(keyword, na=False)

    # 합집합
    final_mask = bbox_mask | keyword_mask

    df_filtered = df[final_mask].copy()
    df_filtered = df_filtered.dropna(subset=[lng_col, lat_col])

    # 컬럼명 정규화
    df_filtered = df_filtered.rename(columns={lng_col: '경도', lat_col: '위도'})

    print(f"    BBOX filter: {bbox_mask.sum():,}")
    print(f"    Keyword filter: {keyword_mask.sum():,}")
    print(f"    Final filtered: {len(df_filtered):,}")

    return df_filtered


def classify_theme(row):
    """단일 POI의 테마 분류"""
    themes = []

    # 검색 대상 텍스트 조합
    major_name = str(row.get('상권업종대분류명', ''))
    middle_name = str(row.get('상권업종중분류명', ''))
    small_name = str(row.get('상권업종소분류명', ''))
    store_name = str(row.get('상호명', ''))
    major_code = str(row.get('상권업종대분류코드', ''))

    search_text = f"{major_name} {middle_name} {small_name} {store_name}".lower()

    # 각 테마별로 매칭 확인
    for theme, config in THEME_MAPPING.items():
        matched = False

        # 1. 대분류 코드 매칭
        if major_code in config.get('major_codes', []):
            matched = True

        # 2. 중분류명 매칭
        for middle in config.get('middle_names', []):
            if middle in middle_name:
                matched = True
                break

        # 3. 키워드 매칭
        for keyword in config.get('keywords', []):
            if keyword.lower() in search_text:
                matched = True
                break

        if matched:
            themes.append(theme)

    # 테마가 없으면 'other'
    return themes if themes else ['other']


def classify_all_pois(df):
    """모든 POI에 테마 분류 적용"""
    print("\n[3] Classifying POIs by theme...")

    # 테마 분류 적용
    df['themes'] = df.apply(classify_theme, axis=1)
    df['primary_theme'] = df['themes'].apply(lambda x: x[0] if x else 'other')

    # 통계 출력
    theme_counts = Counter()
    for themes in df['themes']:
        for theme in themes:
            theme_counts[theme] += 1

    print("\n    Theme distribution:")
    for theme, count in theme_counts.most_common():
        pct = count / len(df) * 100
        print(f"    - {theme}: {count:,} ({pct:.1f}%)")

    # 업종 대분류별 분포
    if '상권업종대분류명' in df.columns:
        print("\n    Major category distribution (top 10):")
        for cat, count in df['상권업종대분류명'].value_counts().head(10).items():
            print(f"    - {cat}: {count:,}")

    return df


def save_classified_data(df):
    """분류된 데이터 저장"""
    print("\n[4] Saving classified data...")

    # 필요한 컬럼만 선택
    columns_to_keep = [
        '상가업소번호', '상호명', '경도', '위도',
        '상권업종대분류코드', '상권업종대분류명',
        '상권업종중분류코드', '상권업종중분류명',
        '상권업종소분류코드', '상권업종소분류명',
        '시군구명', '행정동명', '법정동명', '도로명주소',
        'themes', 'primary_theme'
    ]

    # 존재하는 컬럼만 선택
    columns_to_keep = [c for c in columns_to_keep if c in df.columns]
    df_output = df[columns_to_keep].copy()

    # themes 리스트를 문자열로 변환
    df_output['themes'] = df_output['themes'].apply(lambda x: ','.join(x))

    # 저장
    os.makedirs(DATA_DIR, exist_ok=True)
    df_output.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
    print(f"    [OK] Saved: {OUTPUT_CSV}")

    return df_output


def main():
    print("=" * 60)
    print(" Step 2: POI 테마 분류")
    print("=" * 60)

    # 1. 데이터 로드
    df = load_poi_data()

    # 2. 홍대 지역 필터링
    df_hongdae = filter_hongdae_area(df)

    # 3. 테마 분류
    df_classified = classify_all_pois(df_hongdae)

    # 4. 저장
    df_output = save_classified_data(df_classified)

    print("\n" + "=" * 60)
    print(" [OK] Step 2 Complete!")
    print("=" * 60)

    return df_output


if __name__ == "__main__":
    main()
