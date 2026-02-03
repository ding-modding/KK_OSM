# OSMProject - 홍대 타원 클러스터 경로 탐색기

OpenStreetMap 데이터와 소상공인 POI 데이터를 활용하여 테마별 산책 경로를 탐색하는 시스템입니다.

## 📋 프로젝트 개요

사용자가 출발점과 도착점을 선택하면, 두 점을 초점으로 하는 **타원 영역** 내의 POI(카페, 맛집 등)를 클러스터링하여 표시합니다. 
사용자는 원하는 클러스터를 경유지로 선택하고, 최단거리 경로를 생성할 수 있습니다.

### 주요 기능

- **타원 영역 탐색**: 시작점↔도착점을 초점으로, 이동 시간에 따른 타원 범위 설정
- **테마별 POI 클러스터링**: 카페, 맛집, 유흥, 쇼핑, 녹지 5개 테마
- **줌 레벨 기반 표시**: 줌아웃 시 큰 클러스터, 줌인 시 세밀한 클러스터
- **경유지 선택 및 경로 생성**: 클러스터 클릭으로 경유지 추가, 최단경로 자동 계산

---

## 🗂️ 파일 구조

```
OSMProject/
├── src/
│   ├── main_pipeline.py              # 전체 파이프라인 실행
│   ├── step1_osm_loader.py           # OSM 데이터 로드
│   ├── step2_poi_classifier.py       # POI 테마 분류
│   ├── step3_feature_enricher.py     # 도로에 POI 정보 연결
│   ├── step4_linegraph_builder.py    # 라인 그래프 변환
│   ├── step5_route_visualizer.py     # 기본 경로 시각화
│   ├── step5_route_visualizer_v2.py  # K-diverse 경로 시각화
│   ├── step6_ellipse_cluster_explorer.py  # ⭐ 타원 클러스터 탐색기 생성
│   ├── ellipse_cluster_explorer.html # 생성된 HTML 파일
│   ├── algorithms/
│   │   ├── k_diverse_paths.py        # K개 다양한 경로 알고리즘
│   │   └── time_based_walk.py        # 시간 기반 산책 알고리즘
│   └── data/
│       ├── hongdae-poi-classified.csv    # 분류된 POI 데이터
│       ├── hongdae-enriched.pkl          # 도로 그래프 (POI 연결됨)
│       ├── hongdae-linegraph.pkl         # 라인 그래프
│       └── 소상공인시장진흥공단_*.csv     # 원본 POI 데이터
├── requirements.txt
└── README.md
```

---

## 🚀 실행 방법

### 1. 환경 설정

```bash
# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 데이터 파이프라인 실행 (최초 1회)

```bash
cd src
python main_pipeline.py
```

### 3. 타원 클러스터 탐색기 생성

```bash
python src/step6_ellipse_cluster_explorer.py
```

### 4. HTML 파일 열기

`src/ellipse_cluster_explorer.html`을 브라우저에서 열어 사용합니다.

---

## 🔧 개발자 가이드 - 알고리즘 수정 포인트

### 1. 클러스터링 해상도 조정

**파일**: `src/step6_ellipse_cluster_explorer.py`

```python
# pre_cluster_pois() 함수 내부 (약 110~115줄)
# ============================================================
# 클러스터링 해상도 설정 (수정 가능)
# ============================================================
CELL_SIZE_SMALL = 150    # 높은 줌 레벨용 (미터)
CELL_SIZE_MEDIUM = 300   # 중간 줌 레벨용 (미터)
CELL_SIZE_LARGE = 500    # 낮은 줌 레벨용 (미터)
```

- **값이 클수록**: 클러스터 수 감소, 개별 클러스터 크기 증가
- **값이 작을수록**: 클러스터 수 증가, 더 세밀한 표시

### 2. 줌 레벨 ↔ 클러스터 크기 매핑

**파일**: `src/step6_ellipse_cluster_explorer.py` (HTML 템플릿 내 JavaScript)

```javascript
// updateVisualizationByZoom() 함수
// ============================================================
// 줌 레벨별 클러스터 크기 매핑 (수정 가능)
// ============================================================
const ZOOM_THRESHOLD_LARGE = 15;   // 이하: large 클러스터
const ZOOM_THRESHOLD_MEDIUM = 16;  // 이하: medium 클러스터
// 그 이상: small 클러스터
```

### 3. 타원 크기 보정 (우회 비율)

**파일**: `src/step6_ellipse_cluster_explorer.py` (HTML 템플릿 내 JavaScript)

```javascript
// calculateEllipseParams() 함수
// ============================================================
// 도로 네트워크 우회 비율 (수정 가능)
// ============================================================
// 실제 도로 거리 / 직선 거리 비율
// 값이 클수록 타원이 작아짐 (보수적)
// 값이 작을수록 타원이 커짐 (여유로움)
detourRatio = Math.max(1.0, Math.min(detourRatio, 2.0));
```

### 4. POI 테마 분류 기준

**파일**: `src/step2_poi_classifier.py`

```python
# THEME_MAPPING 딕셔너리 (약 30~60줄)
THEME_MAPPING = {
    'cafe': {
        'keywords': ['커피', '카페', 'coffee', ...],
        'major_codes': [],
        'middle_names': ['커피', '카페', ...]
    },
    'food': {
        'keywords': ['한식', '양식', '치킨', ...],
        'major_codes': ['I2'],  # 음식업 대분류 코드
        ...
    },
    # ... 다른 테마들
}
```

### 5. 최단경로 알고리즘

**파일**: `src/step6_ellipse_cluster_explorer.py` (HTML 템플릿 내 JavaScript)

```javascript
// dijkstra() 함수
// 현재: 단순 거리 기반 최단경로
// 수정 가능: 테마 점수 가중치 적용

// 예시: 테마 가중치 적용
const weight = w.length * (1 - 0.5 * themeScore);  // 테마 점수 높으면 가중치 감소
```

### 6. 경유지 순서 최적화

**파일**: `src/step6_ellipse_cluster_explorer.py` (HTML 템플릿 내 JavaScript)

```javascript
// findRoute() 함수 내 waypointNodes 정렬
// 현재: 시작점에서의 직선 거리순 정렬
// 수정 가능: TSP(외판원 문제) 알고리즘으로 최적 순서 계산

waypointNodes.sort((a, b) => a.distFromStart - b.distFromStart);
```

---

## 📊 데이터 흐름

```
┌─────────────────┐     ┌──────────────────┐
│  OSM 데이터     │────▶│ step1_osm_loader │
│ (seoul-*.pkl)   │     └────────┬─────────┘
└─────────────────┘              │
                                 ▼
┌─────────────────┐     ┌────────────────────┐
│  소상공인 CSV   │────▶│ step2_poi_classifier│
└─────────────────┘     └────────┬───────────┘
                                 │
                                 ▼
                        ┌────────────────────┐
                        │ step3_feature_     │
                        │     enricher       │
                        └────────┬───────────┘
                                 │
                                 ▼
                        ┌────────────────────┐
                        │ step4_linegraph_   │
                        │     builder        │
                        └────────┬───────────┘
                                 │
                                 ▼
┌───────────────────────────────────────────────────┐
│              step6_ellipse_cluster_explorer       │
│  ┌─────────────────────────────────────────────┐ │
│  │ 1. 데이터 로드 (PKL, CSV)                    │ │
│  │ 2. 테마별 사전 클러스터링 (Grid-based)       │ │
│  │ 3. HTML 템플릿 생성 (JavaScript 포함)        │ │
│  └─────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────┘
                                 │
                                 ▼
                   ┌───────────────────────────┐
                   │ ellipse_cluster_explorer  │
                   │         .html             │
                   └───────────────────────────┘
```

---

## 🧮 핵심 알고리즘

### 1. 그리드 기반 클러스터링 (Grid Clustering)

- **복잡도**: O(n) - DBSCAN의 O(n²)보다 훨씬 빠름
- **원리**: 위도/경도를 고정 크기 셀로 나누고, 각 셀을 하나의 클러스터로 처리

```python
def grid_cluster(pois, cell_size_meters=100):
    # 위도 1도 ≈ 111.32km
    lat_cell = cell_size_meters / 111320
    # 경도는 위도에 따라 다름
    lng_cell = cell_size_meters / (111320 * cos(center_lat))
    
    # O(n): 각 POI를 셀에 할당
    for poi in pois:
        cell = (int(poi.lat / lat_cell), int(poi.lng / lng_cell))
        grid[cell].append(poi)
```

### 2. 타원 영역 계산

- **타원의 정의**: 두 초점(시작점, 도착점)까지의 거리 합이 일정한 점들의 집합
- **2a**: 총 이동 가능 거리 (걷는 시간 × 75m/분)
- **우회 비율 보정**: 실제 도로 거리 / 직선 거리로 타원 크기 조정

```javascript
// 타원 내부 판정
function isPointInEllipse(lat, lng, start, end, a) {
    const d1 = distance(lat, lng, start.lat, start.lng);
    const d2 = distance(lat, lng, end.lat, end.lng);
    return (d1 + d2) <= (a * 2);  // 거리 합 ≤ 2a
}
```

### 3. 최단경로 (Dijkstra)

- 라인 그래프 기반 경로 탐색
- 현재 거리만 고려, 테마 가중치 미적용 (수정 가능)

---

## 📝 라이선스

MIT License

---

## 🤝 기여 방법

1. Fork 후 feature 브랜치 생성
2. 알고리즘 수정 시 `개발자 가이드` 섹션의 해당 부분 참고
3. 테스트 후 Pull Request 생성
