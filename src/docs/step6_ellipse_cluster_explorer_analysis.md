# Step 6: 타원 기반 POI 클러스터링 탐색기 — 코드 구조 분석

## 개요

`step6_ellipse_cluster_explorer.py`는 홍대 지역의 POI(Point of Interest) 데이터를 **사전 클러스터링**하고, **타원 기반 경로 탐색 기능**이 포함된 단일 HTML 파일을 생성하는 스크립트이다.

**핵심 아이디어**: 출발점과 도착점 사이에 타원을 그리고, 타원 경계 근처의 테마별 POI 클러스터를 경유지로 선택하여 경로를 생성한다.

---

## 실행 흐름 (Pipeline)

```
main()
  │
  ├─ [1] load_data()            ← 데이터 로드 (pkl, csv)
  │     ├─ hongdae-linegraph.pkl   (Line Graph: 도로 네트워크)
  │     ├─ hongdae-enriched.pkl    (Original Graph: 노드/엣지)
  │     └─ hongdae-poi-classified.csv (POI 분류 데이터)
  │
  ├─ [2] prepare_data(L, G, poi_df)  ← 시각화용 데이터 변환
  │     ├─ node_to_roads: 노드 → 도로 매핑
  │     ├─ road_weights: 도로별 길이(가중치)
  │     ├─ road_coords: 도로 좌표 (시각화용)
  │     ├─ nodes_data: 그래프 노드 좌표
  │     ├─ edges_data: 배경 도로 (시각화용)
  │     ├─ adjacency: Line Graph 인접 리스트
  │     ├─ pois_data → pre_cluster_pois() 호출 [3]
  │     └─ pois_by_theme: 테마별 개별 POI (산점도용)
  │
  ├─ [3] pre_cluster_pois()     ← 테마별·줌레벨별 사전 클러스터링
  │     ├─ 테마 5종 × 줌레벨 3단계 = 15세트 클러스터
  │     └─ 방식: grid_cluster() 또는 kmeans_cluster()
  │
  └─ [4] generate_html(data)    ← 모든 데이터를 JSON으로 HTML에 임베딩
        └─ ellipse_cluster_explorer.html 출력
```

---

## 파일 구조

```
src/
├── step6_ellipse_cluster_explorer.py   ← 이 스크립트 (생성기)
├── ellipse_cluster_explorer.html       ← 출력 파일 (브라우저에서 실행)
└── data/
    ├── hongdae-linegraph.pkl           ← Line Graph (경로 탐색용)
    ├── hongdae-enriched.pkl            ← Original Graph (좌표, 도로 정보)
    └── hongdae-poi-classified.csv      ← 분류된 POI 데이터
```

---

## Python 파트 상세 (서버 사이드 — 생성 시 1회 실행)

### 1. 설정 및 상수

| 상수 | 값 | 설명 |
|---|---|---|
| `THEMES` | `['cafe', 'food', 'nightlife', 'shopping', 'green']` | 5개 테마 |
| `THEME_INFO` | dict | 테마별 이름, 색상, 아이콘 |
| `CLUSTERING_METHOD` | `'kmeans'` | 클러스터링 방식 (`'grid'` 또는 `'kmeans'`) |

### 2. 유틸리티 함수

#### `haversine_distance(lat1, lng1, lat2, lng2)` → float (미터)
- 두 좌표 간의 Haversine 거리 계산
- 지구 반지름 6,371,000m 기준

### 3. 클러스터링 함수

#### `grid_cluster(pois, cell_size_meters=100)` → list[dict]
- **O(n)** 그리드 기반 클러스터링
- 위도/경도 공간을 고정 셀로 나누고, 같은 셀의 POI를 하나의 클러스터로 처리
- 필터링: `MIN_POI_COUNT=5` 미만 클러스터 제거
- 반경: `BASE_RADIUS(30) + sqrt(count) * RADIUS_PER_POI(3)`, 최대 `MAX_RADIUS(200)`

#### `kmeans_cluster(pois, k=None, max_k=30)` → list[dict]
- K-Means++ 초기화 + 최대 20회 반복
- K 자동 결정: `max(5, min(sqrt(n/2), max_k))`
- 동일한 반경 공식 적용
- seed=42로 재현성 보장

#### `pre_cluster_pois(pois_data)` → dict
- **핵심 함수**: 테마 5종 × 줌레벨 3단계 = 15세트 클러스터 생성
- 줌레벨별 K값 (KMeans 모드):

| 줌 레벨 | 키 | K 결정 공식 | 용도 |
|---|---|---|---|
| 높은 줌 (17+) | `small` | `min(50, max(10, n//50))` | 많은 작은 클러스터 |
| 중간 줌 (15-16) | `medium` | `min(30, max(5, n//100))` | 중간 클러스터 |
| 낮은 줌 (~14) | `large` | `min(15, max(3, n//200))` | 적은 큰 클러스터 |

### 4. 데이터 로드/변환 함수

#### `load_data()` → (L, G, poi_df)
- `pickle.load`로 Line Graph(L)와 Original Graph(G) 로드
- `pd.read_csv`로 POI 데이터 로드

#### `prepare_data(L, G, poi_df)` → dict
- Line Graph → `road_weights`, `adjacency`, `node_to_roads` 변환
- Original Graph → `nodes_data`, `edges_data`, `road_coords` 변환
- POI CSV → `pois_data` → `pre_cluster_pois()` → `pre_clustered`
- POI를 테마별로 분류 → `pois_by_theme` (산점도용)
- 중심점 좌표 계산

### 5. HTML 생성

#### `generate_html(data)` → void
- Python dict → `json.dumps()` → JS 변수로 HTML에 직접 임베딩
- f-string 기반 단일 HTML 파일 생성
- 외부 의존성: Leaflet.js (CDN), Font Awesome (CDN)

---

## JavaScript 파트 상세 (클라이언트 사이드 — 브라우저에서 실행)

### 1. 임베딩된 데이터 (Python에서 주입)

| 변수 | 타입 | 설명 |
|---|---|---|
| `roadWeights` | `{roadId: {length}}` | 도로별 가중치 |
| `nodeToRoads` | `{nodeId: [roadId]}` | 노드 → 도로 매핑 |
| `roadCoords` | `{roadId: {lat1,lng1,lat2,lng2}}` | 도로 좌표 |
| `nodesData` | `[{id, lat, lng}]` | 그래프 노드 |
| `edgesData` | `[{lat1,lng1,lat2,lng2,highway}]` | 배경 도로 |
| `adjacency` | `{roadId: [roadId]}` | Line Graph 인접 리스트 |
| `preClusteredData` | `{theme: {small,medium,large}}` | 사전 클러스터링 결과 |
| `poisByTheme` | `{theme: [{lat,lng,name}]}` | 테마별 개별 POI |

### 2. 줌 레벨 상수

```
ZOOM_SCATTER = 18  →  개별 POI 산점도 표시
ZOOM_SMALL   = 17  →  small 클러스터
ZOOM_MEDIUM  = 15  →  medium 클러스터
그 이하            →  large 클러스터
```

### 3. 지도 레이어 구조

```
map (Leaflet Map)
├── CartoDB Light 타일 (베이스맵)
├── bgLayer       ← 배경 도로 (회색 선)
├── ellipseLayer  ← 타원 표시 (점선)
├── clusterLayer  ← 클러스터 원 + 라벨 (또는 산점도)
├── routeLayer    ← 경로 표시 (보라색 선)
└── markerLayer   ← 출발/도착/경유지 마커
```

### 4. 상태 관리 (전역 변수)

```javascript
startNode, endNode          // 출발/도착 노드
startMarker, endMarker      // 출발/도착 마커
currentTheme = 'cafe'       // 현재 테마
walkTime = 30               // 이동 시간 (분)
minWalkTime = 10            // 최소 이동 시간
shortestDistance = 0        // 최단 거리
waypoints = []              // 경유지 배열
waypointMarkers = []        // 경유지 마커 배열
currentEllipse = null       // 현재 타원 파라미터
filteredClusters = []       // 필터링된 클러스터
```

### 5. 핵심 함수 흐름

#### (A) 타원 계산 및 표시

```
사용자가 출발/도착 클릭 → updateTimeSliderMin()
                           └→ calculateShortestDistance() → dijkstra()

"클러스터 표시" 클릭 → showClusters()
                        ├→ drawEllipse()
                        │    └→ calculateEllipseParams()
                        │         ├─ 직선거리 / 최단거리 비율로 detourRatio 계산
                        │         ├─ a = adjustedTotalDistance / 2
                        │         ├─ c = straightDistance / 2
                        │         └─ b = sqrt(a² - c²)
                        └→ updateClusterDisplay()
```

#### `calculateEllipseParams(start, end, totalDistance)`
- `totalDistance` = `walkTime * 75` (분 × 75m/분)
- `detourRatio` = `shortestDistance / straightDistance` (1.0~2.0 클램프)
- 타원 장축(a) = `adjustedTotalDistance / 2`, 초점거리(c) = `straightDistance / 2`
- 타원 단축(b) = `sqrt(a² - c²)`

#### `isClusterInEllipse(cluster, ellipse, start, end)`
- **타원 경계 근처만** 표시 (내부 깊숙한 곳 제외)
- `d1 + d2` (두 초점까지 거리 합) 기준:
  - 안쪽 한계: `ellipseBoundary * 0.6` (60% 안쪽은 제외)
  - 바깥 한계: `ellipseBoundary + 80m`

#### (B) 클러스터/산점도 표시

```
updateClusterDisplay()
├─ getClusterLevel() → 'scatter' | 'small' | 'medium' | 'large'
│
├─ [scatter 모드] showScatterPlot()
│    └→ 개별 POI를 circleMarker로 표시
│         └→ 클릭 시 addWaypoint()
│
└─ [cluster 모드]
     ├→ preClusteredData[theme][level] 에서 클러스터 로드
     ├→ isClusterInEllipse()로 필터링
     └→ L.circle + L.divIcon 라벨로 표시
          └→ 클릭 시 addWaypoint()
```

#### (C) 경유지 관리

```
addWaypoint(cluster)
├→ 중복 체크 (좌표 기반 ID)
├→ waypoints 배열에 추가
├→ 번호 마커 생성
└→ updateWaypointUI() → 사이드바 목록 갱신

removeWaypoint(index)
├→ waypoints에서 제거
├→ 마커 제거
├→ updateWaypointMarkers() → 번호 재부여
└→ updateWaypointUI()
```

#### (D) 경로 탐색

```
findRoute()
├→ 경유지를 출발점으로부터 거리 순 정렬
├→ 정차 순서: [출발] → [경유지1] → [경유지2] → ... → [도착]
├→ 각 구간마다 dijkstra() 실행
├→ 도로 좌표로 polyline 시각화
└→ 총 거리/시간/경유지 수 표시
```

#### `dijkstra(startNodeId, endNodeId)`
- Line Graph 기반 Dijkstra 최단 경로
- `nodeToRoads`로 시작/종료 노드에 연결된 도로 ID 조회
- 우선순위 큐: 배열 + sort (간이 구현)
- 가중치: `roadWeights[roadId].length`
- 반환: 도로 ID 배열 (경로)

### 6. 이벤트 핸들러

| 이벤트 | 핸들러 | 동작 |
|---|---|---|
| 지도 클릭 | `map.on('click')` | 첫 클릭=출발, 두번째=도착, 최단거리 계산 |
| 테마 버튼 클릭 | `.theme-btn click` | 테마 변경 + 클러스터 갱신 |
| 시간 슬라이더 | `#timeSlider input` | walkTime 업데이트 (10~120분) |
| 줌 변경 | `map.on('zoomend')` | 줌레벨별 클러스터 재표시 |
| 클러스터 표시 | `#btnShowClusters click` | `showClusters()` |
| 경로 생성 | `#btnFindRoute click` | `findRoute()` |
| 경유지 초기화 | `#btnClearWaypoints click` | `clearWaypoints()` |
| 전체 초기화 | `clearAll()` | 모든 상태 리셋 |

---

## UI 구조

```
┌───────────────────────────────────┬──────────────────┐
│                                   │  Sidebar (380px)  │
│                                   │                  │
│            Leaflet Map            │  ┌─ 헤더 ──────┐ │
│                                   │  │ 타원 클러스터│ │
│   [배경 도로]                      │  │ 탐색기       │ │
│   [타원 점선]                      │  └─────────────┘ │
│   [클러스터 원 / 산점도]           │                  │
│   [경로 선]                        │  ┌─ 출발/도착 ─┐ │
│   [출발·도착·경유지 마커]          │  │ 출발점: ...  │ │
│                                   │  │ 도착점: ...  │ │
│                                   │  └─────────────┘ │
│                                   │                  │
│                                   │  ┌─ 테마 선택 ─┐ │
│                                   │  │ [카페][맛집] │ │
│                                   │  │ [유흥][쇼핑] │ │
│                                   │  │    [녹지]    │ │
│                                   │  │              │ │
│                                   │  │ 시간: ──●── │ │
│                                   │  │  30분        │ │
│                                   │  │ [클러스터표시]│ │
│                                   │  └─────────────┘ │
│                                   │                  │
│                                   │  ┌─ 경유지 ───┐ │
│                                   │  │ 1. 카페(12) │ │
│                                   │  │ 2. 맛집(8)  │ │
│                                   │  │ [경로 생성] │ │
│                                   │  └─────────────┘ │
│                                   │                  │
│                                   │  ┌─ 경로 정보 ─┐ │
│                                   │  │ 거리: 2.3km │ │
│                                   │  │ 시간: 31분  │ │
│                                   │  └─────────────┘ │
│                                   │                  │
│                                   │  [사용법 안내]   │
│                                   │  [전체 초기화]   │
└───────────────────────────────────┴──────────────────┘
```

---

## 사용자 인터랙션 흐름

```
1. 지도 클릭 → 출발점 설정 (녹색 마커)
2. 지도 클릭 → 도착점 설정 (빨강 마커) → 최단거리 자동 계산
3. 테마 선택 (카페/맛집/유흥/쇼핑/녹지)
4. 이동 시간 슬라이더 조정 (타원 크기 결정)
5. "클러스터 표시" 클릭 → 타원 + 클러스터 표시
6. 줌 인/아웃 → 클러스터 해상도 자동 변경
   - 줌 18+: 개별 POI 산점도
   - 줌 17: small 클러스터
   - 줌 15-16: medium 클러스터
   - 줌 ~14: large 클러스터
7. 클러스터/POI 클릭 → 경유지 추가 (주황 번호 마커)
8. "경로 생성" 클릭 → Dijkstra 기반 경유지 순회 경로 표시
```

---

## 데이터 흐름 요약

```
[Python 생성 시]
pkl/csv → load_data() → prepare_data() → pre_cluster_pois()
                                              │
                                    json.dumps()로 HTML에 임베딩
                                              ↓
                              ellipse_cluster_explorer.html

[브라우저 실행 시]
임베딩된 JSON 데이터 → Leaflet 지도 초기화
사용자 입력 → 타원 계산 → 클러스터 필터링 → 경로 탐색 → 시각화
```

---

## 주요 설정값 (수정 포인트)

| 위치 | 변수 | 기본값 | 설명 |
|---|---|---|---|
| Python | `CLUSTERING_METHOD` | `'kmeans'` | 클러스터링 방식 |
| Python | `MIN_POI_COUNT` | `5` | 클러스터 최소 POI 수 |
| Python | `BASE_RADIUS` | `30` | 클러스터 기본 반경 (m) |
| Python | `MAX_RADIUS` | `200` | 클러스터 최대 반경 (m) |
| Python | K값 공식 | `K_SMALL`, `K_MEDIUM`, `K_LARGE` | 줌별 클러스터 수 |
| JS | `ZOOM_SCATTER` | `18` | 산점도 전환 줌 레벨 |
| JS | `ZOOM_SMALL` | `17` | small 클러스터 줌 레벨 |
| JS | `ZOOM_MEDIUM` | `15` | medium 클러스터 줌 레벨 |
| JS | `INNER_MARGIN` | `0.6` | 타원 내부 제외 비율 |
| JS | `OUTER_BUFFER` | `80` | 타원 외부 허용 거리 (m) |
| JS | 보행 속도 | `75 m/분` | 이동 시간 → 거리 변환 |

---

## 외부 의존성

### Python
- `pandas` — CSV 읽기
- `pickle` — 그래프 데이터 직렬화
- `math`, `collections`, `json`, `os` — 표준 라이브러리

### HTML (CDN)
- **Leaflet 1.9.4** — 지도 라이브러리
- **Font Awesome 6.4.0** — 아이콘
- **CartoDB Light** — 베이스맵 타일
