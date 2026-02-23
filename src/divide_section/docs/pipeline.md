# divide_section 파이프라인

## 실행 순서

```
step1 → step2 → step3
```

---

## Step 1 — OSM 구역 생성 (`step1_osm_loader/osm_loader_from_pkl.py`)

**입력:** `src/data/hongdae-osm-network.pkl` (OSM 네트워크 그래프)

**처리:**
1. pkl에서 OSM 그래프(G) 로드
2. 도로 유형별 버퍼 폭을 다르게 적용해 도로 장벽(barrier) 생성
   - **Macro 도로** (간선: motorway, trunk, primary 등) → 큰 구역 분리
   - **Micro 도로** (Macro + unclassified, residential 등) → 작은 구역 세분화
3. 전체 영역에서 도로 장벽을 빼(difference) 보행 구역 폴리곤 생성
4. Micro 구역에 Macro 구역 ID(`macro_id`) 매핑 (계층 구조)

**출력:**
- `data/hongdae_pedestrian_zones.geojson` — micro 구역 (micro_id, macro_id 포함)
- `data/hongdae_pedestrian_zones_macro.geojson` — macro 구역

---

## Step 2 — POI 공간 매핑 (`step2_zone_data_integration/data_integration.py`)

**입력:**
- `data/hongdae_pedestrian_zones.geojson` (Step 1 출력)
- `data/POI_data.csv` (상호명, 업종 코드/명, 경도/위도)

**처리:**
1. POI CSV를 GeoDataFrame으로 변환 (경도/위도 → Point geometry)
2. Spatial Join (`sjoin`, within 조건)으로 각 POI를 micro 구역에 매핑

**출력:**
- `data/mapped_poi_results.geojson` — POI별 `matched_micro_id` + 업종 분류 컬럼 포함

---

## Step 3 — 밀도 시각화 (`step3_visualization/visualization.py`)

**입력:**
- `data/hongdae_pedestrian_zones.geojson`
- `data/hongdae_pedestrian_zones_macro.geojson`
- `data/mapped_poi_results.geojson` (Step 2 출력)

**처리:**
1. 구역별 면적(m²) 계산 (UTM 투영)
2. 업종 카테고리 계층 구축 (대분류 → 중분류 → 소분류)
3. 선택한 카테고리 기준으로 micro 구역별 POI 밀도 계산
4. 밀도에 비례해 구역 불투명도(alpha) 조정 → matplotlib 인터랙티브 지도 표시

**UI:** 사이드바 버튼으로 카테고리 탐색, Back/이전/다음 페이지, 줌·팬 유지

---

## 데이터 흐름 요약

```
hongdae-osm-network.pkl
        ↓ Step 1
hongdae_pedestrian_zones.geojson  ←→  _macro.geojson
        ↓ Step 2
POI_data.csv + zones → mapped_poi_results.geojson
        ↓ Step 3
인터랙티브 밀도 지도 (matplotlib)
```
