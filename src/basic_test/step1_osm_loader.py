"""
Step 1: OSM 데이터 로드
- 이미 파싱된 seoul-walking.pkl에서 홍대 지역만 추출
- 훨씬 빠름 (전체 PBF 파싱 불필요)
"""
import os
import pickle
import networkx as nx
from collections import defaultdict
from shapely.geometry import LineString, Point

# Configuration
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SRC_DIR, 'data')

# 이미 파싱된 서울 전체 그래프
SEOUL_PKL = os.path.join(DATA_DIR, 'seoul-walking.pkl')

# 홍대 지역 BBOX (넓게 설정)
# [서쪽(min_lon), 남쪽(min_lat), 동쪽(max_lon), 북쪽(max_lat)]
HONGDAE_BBOX = [126.895, 37.540, 126.960, 37.580]


def load_seoul_graph():
    """서울 전체 그래프 로드"""
    print(f"\n[1] Loading seoul-walking.pkl...")
    with open(SEOUL_PKL, 'rb') as f:
        G = pickle.load(f)
    print(f"    Total nodes: {G.number_of_nodes():,}")
    print(f"    Total edges: {G.number_of_edges():,}")
    return G


def filter_by_bbox(G, bbox):
    """BBOX로 노드/엣지 필터링"""
    print(f"\n[2] Filtering by BBOX: {bbox}")

    min_lon, min_lat, max_lon, max_lat = bbox

    # BBOX 내 노드 찾기
    nodes_in_bbox = []
    for node, data in G.nodes(data=True):
        if 'x' in data and 'y' in data:
            x, y = data['x'], data['y']
            if min_lon <= x <= max_lon and min_lat <= y <= max_lat:
                nodes_in_bbox.append(node)

    print(f"    Nodes in BBOX: {len(nodes_in_bbox):,}")

    # 서브그래프 생성
    G_sub = G.subgraph(nodes_in_bbox).copy()
    print(f"    Subgraph nodes: {G_sub.number_of_nodes():,}")
    print(f"    Subgraph edges: {G_sub.number_of_edges():,}")

    return G_sub


def extract_geo_features(G):
    """엣지에서 지리 피처 추출 (녹지 점수용 - 현재는 빈 데이터)"""
    # 참고: seoul-walking.pkl에는 도로 데이터만 있고 건물/공원 데이터는 없음
    # 녹지 점수는 OSM에서 별도로 추출하거나, 0으로 설정
    geo_features = {
        'parks': [],
        'natural': [],
        'landuse': [],
        'waterways': [],
        'buildings': [],
    }
    return geo_features


def print_highway_stats(G):
    """Highway 타입 통계 출력"""
    print(f"\n[3] Highway type statistics:")
    highway_counts = defaultdict(int)

    for u, v, data in G.edges(data=True):
        hw = data.get('highway', 'unknown')
        if isinstance(hw, list):
            hw = hw[0]
        highway_counts[hw] += 1

    for hw, count in sorted(highway_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"    - {hw}: {count:,}")


def main():
    print("=" * 60)
    print(" Step 1: OSM 데이터 로드 (seoul-walking.pkl 기반)")
    print("=" * 60)

    # 출력 디렉토리 생성
    os.makedirs(DATA_DIR, exist_ok=True)

    # 1. 서울 전체 그래프 로드
    G_seoul = load_seoul_graph()

    # 2. 홍대 지역 필터링
    G = filter_by_bbox(G_seoul, HONGDAE_BBOX)

    # 메모리 해제
    del G_seoul

    # 3. 통계 출력
    print_highway_stats(G)

    # 4. 지리 피처 (현재는 빈 데이터)
    geo_features = extract_geo_features(G)

    # 5. 결과 저장
    print(f"\n[4] Saving results...")

    graph_path = os.path.join(DATA_DIR, 'hongdae-osm-network.pkl')
    with open(graph_path, 'wb') as f:
        pickle.dump(G, f)
    print(f"    [OK] Graph: {graph_path}")

    geo_path = os.path.join(DATA_DIR, 'hongdae-geo-features.pkl')
    with open(geo_path, 'wb') as f:
        pickle.dump(geo_features, f)
    print(f"    [OK] Geo features: {geo_path}")

    print("\n" + "=" * 60)
    print(" [OK] Step 1 Complete!")
    print("=" * 60)

    return G, geo_features


if __name__ == "__main__":
    main()
