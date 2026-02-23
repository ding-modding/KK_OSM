"""
Step 3: Edge 속성 부착 (Feature Enrichment)
- POI를 가장 가까운 Edge에 매핑 (R-tree 인덱스)
- OSM 지리 데이터 기반 녹지 점수 계산
- 보행 적합성 점수 계산
- 테마별 점수 계산
"""
import os
import pickle
import pandas as pd
import numpy as np
from collections import defaultdict
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union

# R-tree 인덱스 (선택적)
try:
    from rtree import index
    HAS_RTREE = True
except ImportError:
    HAS_RTREE = False
    print("Warning: rtree not installed. Using brute-force matching.")

# Configuration
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SRC_DIR, 'data')
GRAPH_PKL = os.path.join(DATA_DIR, 'hongdae-osm-network.pkl')
GEO_PKL = os.path.join(DATA_DIR, 'hongdae-geo-features.pkl')
POI_CSV = os.path.join(DATA_DIR, 'hongdae-poi-classified.csv')
OUTPUT_PKL = os.path.join(DATA_DIR, 'hongdae-enriched.pkl')

# 녹지 점수 설정
GREEN_SCORING = {
    'leisure': {
        'park': 10, 'garden': 8, 'playground': 5, 'nature_reserve': 10,
        'pitch': 3, 'sports_centre': 2,
    },
    'natural': {
        'water': 10, 'wood': 8, 'tree': 5, 'grassland': 7, 'scrub': 4, 'wetland': 6,
    },
    'landuse': {
        'grass': 6, 'forest': 9, 'meadow': 7, 'recreation_ground': 5,
        'village_green': 6, 'orchard': 4,
    },
    'waterway': {
        'river': 10, 'stream': 8, 'canal': 6, 'drain': 2,
    },
}

# 보행 적합성 점수
WALKABILITY_SCORES = {
    'highway': {
        'footway': 10, 'pedestrian': 10, 'path': 9, 'corridor': 9,
        'living_street': 8, 'steps': 6, 'residential': 5, 'service': 4,
        'cycleway': 4, 'track': 3, 'tertiary': 2, 'secondary': 1,
        'primary': 0, 'unclassified': 3,
    },
    'surface': {
        'paving_stones': 5, 'asphalt': 4, 'concrete': 4, 'paved': 4,
        'wood': 3, 'ground': 2, 'unpaved': 1, 'dirt': 1, 'earth': 1,
    },
    'lit': {'yes': 3, 'no': 0, None: 1},
    'sidewalk': {'both': 4, 'left': 2, 'right': 2, 'separate': 3, 'no': 0, None: 1},
    'foot': {'designated': 3, 'yes': 3, 'permissive': 2, 'destination': 1, 'private': 0, 'no': 0, None: 1},
}


def load_data():
    """데이터 로드"""
    print("\n[1] Loading data...")

    # 그래프
    with open(GRAPH_PKL, 'rb') as f:
        G = pickle.load(f)
    print(f"    Graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

    # 지리 데이터
    with open(GEO_PKL, 'rb') as f:
        geo_features = pickle.load(f)
    print(f"    Geo features: {sum(len(v) for v in geo_features.values()):,} total")

    # POI
    df_poi = pd.read_csv(POI_CSV)
    print(f"    POIs: {len(df_poi):,}")

    return G, geo_features, df_poi


def build_spatial_index(G):
    """Edge용 공간 인덱스 생성"""
    print("\n[2] Building spatial index...")

    edge_list = []
    edge_geometries = {}

    for u, v, key, data in G.edges(keys=True, data=True):
        geom = data.get('geometry')
        if geom is None:
            # geometry가 없으면 노드 좌표로 생성
            u_data = G.nodes[u]
            v_data = G.nodes[v]
            if 'x' in u_data and 'y' in u_data and 'x' in v_data and 'y' in v_data:
                geom = LineString([(u_data['x'], u_data['y']), (v_data['x'], v_data['y'])])
            else:
                continue

        edge_id = (u, v, key)
        edge_list.append(edge_id)
        edge_geometries[edge_id] = geom

    print(f"    Valid edges: {len(edge_list):,}")

    if HAS_RTREE:
        idx = index.Index()
        for i, edge_id in enumerate(edge_list):
            geom = edge_geometries[edge_id]
            idx.insert(i, geom.bounds)
        print("    [OK] R-tree index built")
        return idx, edge_list, edge_geometries
    else:
        print("    [OK] Edge list prepared (no R-tree)")
        return None, edge_list, edge_geometries


def prepare_geo_polygons(geo_features):
    """지리 피처를 Polygon으로 변환"""
    print("\n[3] Preparing geo polygons...")

    geo_polygons = {
        'parks': [],
        'natural': [],
        'landuse': [],
        'waterways': [],
    }

    for feature_type in ['parks', 'natural', 'landuse', 'waterways']:
        features = geo_features.get(feature_type, [])
        for feature in features:
            coords = feature.get('coords', [])
            if len(coords) >= 3:
                try:
                    # 폴리곤 생성 (마지막 점이 첫 점과 같지 않으면 닫기)
                    if coords[0] != coords[-1]:
                        coords = coords + [coords[0]]
                    poly = Polygon(coords)
                    if poly.is_valid and not poly.is_empty:
                        geo_polygons[feature_type].append({
                            'geometry': poly,
                            'type': list(feature.keys())[1],  # leisure, natural, etc.
                            'value': list(feature.values())[2] if len(feature) > 2 else '',  # park, water, etc.
                            'name': feature.get('name', ''),
                        })
                except Exception:
                    continue
            elif len(coords) >= 2:
                # LineString으로 처리 (waterway 등)
                try:
                    line = LineString(coords)
                    if line.is_valid and not line.is_empty:
                        # 버퍼로 폴리곤화
                        poly = line.buffer(0.0001)  # ~10m buffer
                        geo_polygons[feature_type].append({
                            'geometry': poly,
                            'type': list(feature.keys())[1],
                            'value': list(feature.values())[2] if len(feature) > 2 else '',
                            'name': feature.get('name', ''),
                        })
                except Exception:
                    continue

    for ft, polys in geo_polygons.items():
        print(f"    {ft}: {len(polys)} polygons")

    return geo_polygons


def calculate_green_score(edge_geom, geo_polygons, radius=0.001):
    """Edge 주변 녹지 점수 계산 (radius in degrees, ~100m)"""
    score = 0
    buffer = edge_geom.buffer(radius)

    # 각 지리 피처와 교차 확인
    for feature_type, polys in geo_polygons.items():
        score_map = GREEN_SCORING.get(feature_type, {})
        for poly_data in polys:
            poly = poly_data['geometry']
            value = poly_data['value']

            if buffer.intersects(poly):
                # 점수 추가
                pts = score_map.get(value, 0)
                score += pts

    return min(score, 30)  # 최대 30점


def calculate_walkability_score(data):
    """Edge의 보행 적합성 점수 계산"""
    score = 0
    max_score = 0

    # Highway type (0-10)
    highway = data.get('highway')
    if highway:
        if isinstance(highway, list):
            highway = highway[0]
        score += WALKABILITY_SCORES['highway'].get(highway, 3)
    max_score += 10

    # Surface (0-5)
    surface = data.get('surface')
    if surface:
        if isinstance(surface, list):
            surface = surface[0]
        score += WALKABILITY_SCORES['surface'].get(surface, 2)
    else:
        score += 2
    max_score += 5

    # Lit (0-3)
    lit = data.get('lit')
    score += WALKABILITY_SCORES['lit'].get(lit, 1)
    max_score += 3

    # Sidewalk (0-4)
    sidewalk = data.get('sidewalk')
    if sidewalk:
        if isinstance(sidewalk, list):
            sidewalk = sidewalk[0]
        score += WALKABILITY_SCORES['sidewalk'].get(sidewalk, 1)
    else:
        score += 1
    max_score += 4

    # Foot (0-3)
    foot = data.get('foot')
    score += WALKABILITY_SCORES['foot'].get(foot, 1)
    max_score += 3

    return round(score / max_score * 10, 2)


def match_pois_to_edges(G, df_poi, spatial_idx, edge_list, edge_geometries):
    """POI를 가장 가까운 Edge에 매핑"""
    print("\n[4] Matching POIs to edges...")

    edge_stores = defaultdict(list)
    search_radius = 0.0005  # ~50m in degrees

    total = len(df_poi)
    matched = 0

    for idx, row in df_poi.iterrows():
        if idx % 1000 == 0 and idx > 0:
            print(f"    Processing {idx:,}/{total:,}...")

        try:
            store_point = Point(float(row['경도']), float(row['위도']))
        except (ValueError, KeyError):
            continue

        # 근접 Edge 탐색
        if HAS_RTREE and spatial_idx is not None:
            bounds = (
                store_point.x - search_radius,
                store_point.y - search_radius,
                store_point.x + search_radius,
                store_point.y + search_radius
            )
            candidate_indices = list(spatial_idx.intersection(bounds))
        else:
            candidate_indices = range(len(edge_list))

        if not candidate_indices:
            continue

        # 최근접 Edge 찾기
        min_distance = float('inf')
        nearest_edge = None

        for i in candidate_indices:
            if i >= len(edge_list):
                continue
            edge_id = edge_list[i]
            geom = edge_geometries[edge_id]

            dist = store_point.distance(geom)
            if dist < min_distance:
                min_distance = dist
                nearest_edge = edge_id

        if nearest_edge is not None and min_distance < search_radius:
            # 테마 파싱
            themes_str = str(row.get('themes', 'other'))
            themes = themes_str.split(',') if themes_str else ['other']

            edge_stores[nearest_edge].append({
                'name': str(row.get('상호명', '')),
                'category': str(row.get('상권업종중분류명', '')),
                'themes': themes,
                'primary_theme': str(row.get('primary_theme', 'other')),
                'distance': min_distance,
                'lat': float(row['위도']),
                'lng': float(row['경도']),
            })
            matched += 1

    print(f"    [OK] Matched {matched:,} POIs to edges")
    return edge_stores


def enrich_edges(G, edge_stores, edge_geometries, geo_polygons):
    """Edge에 모든 속성 추가"""
    print("\n[5] Enriching edges with scores...")

    total_edges = G.number_of_edges()
    processed = 0

    for u, v, key, data in G.edges(keys=True, data=True):
        edge_id = (u, v, key)
        stores = edge_stores.get(edge_id, [])
        geom = edge_geometries.get(edge_id)

        # 1. Store 정보
        G.edges[u, v, key]['stores'] = stores
        G.edges[u, v, key]['store_count'] = len(stores)

        # 2. 테마별 점수 (해당 테마 POI 개수)
        theme_scores = defaultdict(int)
        for store in stores:
            for theme in store.get('themes', []):
                theme_scores[theme] += 1

        G.edges[u, v, key]['cafe_score'] = theme_scores.get('cafe', 0)
        G.edges[u, v, key]['food_score'] = theme_scores.get('food', 0)
        G.edges[u, v, key]['nightlife_score'] = theme_scores.get('nightlife', 0)
        G.edges[u, v, key]['shopping_score'] = theme_scores.get('shopping', 0)

        # 3. 녹지 점수 (OSM 지리 데이터 기반)
        if geom is not None:
            green_score = calculate_green_score(geom, geo_polygons)
        else:
            green_score = 0
        G.edges[u, v, key]['green_score'] = green_score

        # 4. 보행 적합성 점수
        walkability = calculate_walkability_score(data)
        G.edges[u, v, key]['walkability_score'] = walkability

        processed += 1
        if processed % 5000 == 0:
            print(f"    Processed {processed:,}/{total_edges:,} edges...")

    # 통계
    edges_with_stores = sum(1 for u, v, k, d in G.edges(keys=True, data=True) if d.get('store_count', 0) > 0)
    edges_with_green = sum(1 for u, v, k, d in G.edges(keys=True, data=True) if d.get('green_score', 0) > 0)
    avg_walkability = np.mean([d.get('walkability_score', 0) for u, v, k, d in G.edges(keys=True, data=True)])

    print(f"\n    Statistics:")
    print(f"    - Edges with stores: {edges_with_stores:,}")
    print(f"    - Edges with green score: {edges_with_green:,}")
    print(f"    - Avg walkability: {avg_walkability:.2f}")

    return G


def save_enriched_graph(G):
    """결과 저장"""
    print("\n[6] Saving enriched graph...")

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_PKL, 'wb') as f:
        pickle.dump(G, f)

    print(f"    [OK] Saved: {OUTPUT_PKL}")


def main():
    print("=" * 60)
    print(" Step 3: Feature Enrichment")
    print("=" * 60)

    # 1. 데이터 로드
    G, geo_features, df_poi = load_data()

    # 2. 공간 인덱스 생성
    spatial_idx, edge_list, edge_geometries = build_spatial_index(G)

    # 3. 지리 폴리곤 준비
    geo_polygons = prepare_geo_polygons(geo_features)

    # 4. POI-Edge 매칭
    edge_stores = match_pois_to_edges(G, df_poi, spatial_idx, edge_list, edge_geometries)

    # 5. Edge 속성 추가
    G = enrich_edges(G, edge_stores, edge_geometries, geo_polygons)

    # 6. 저장
    save_enriched_graph(G)

    print("\n" + "=" * 60)
    print(" [OK] Step 3 Complete!")
    print("=" * 60)

    return G


if __name__ == "__main__":
    main()
