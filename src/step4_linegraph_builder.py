"""
Step 4: Line Graph 변환
- 원본 그래프 G (노드=교차점, 간선=도로)를 Line Graph L(G)로 변환
- Line Graph에서: 노드=도로(원본 Edge), 간선=도로 연결 관계
- 회전 각도 정보 추가
"""
import os
import pickle
import math
import networkx as nx
from collections import defaultdict

# Configuration
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SRC_DIR, 'data')
INPUT_PKL = os.path.join(DATA_DIR, 'hongdae-enriched.pkl')
OUTPUT_PKL = os.path.join(DATA_DIR, 'hongdae-linegraph.pkl')


def load_enriched_graph():
    """Enriched 그래프 로드"""
    print("\n[1] Loading enriched graph...")

    with open(INPUT_PKL, 'rb') as f:
        G = pickle.load(f)

    print(f"    Nodes: {G.number_of_nodes():,}")
    print(f"    Edges: {G.number_of_edges():,}")

    return G


def calculate_bearing(lon1, lat1, lon2, lat2):
    """두 좌표 사이의 방위각 계산 (degrees)"""
    # Convert to radians
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    lon_diff = math.radians(lon2 - lon1)

    x = math.sin(lon_diff) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(lon_diff)

    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360  # Normalize to 0-360


def get_edge_bearing(G, u, v):
    """Edge의 방위각 계산"""
    u_data = G.nodes.get(u, {})
    v_data = G.nodes.get(v, {})

    if 'x' not in u_data or 'y' not in u_data or 'x' not in v_data or 'y' not in v_data:
        return None

    return calculate_bearing(u_data['x'], u_data['y'], v_data['x'], v_data['y'])


def calculate_turn_angle(bearing1, bearing2):
    """두 방위각 사이의 회전 각도 계산 (-180 ~ 180)"""
    if bearing1 is None or bearing2 is None:
        return 0

    diff = bearing2 - bearing1

    # Normalize to -180 ~ 180
    while diff > 180:
        diff -= 360
    while diff < -180:
        diff += 360

    return diff


def classify_turn(angle):
    """회전 각도를 분류"""
    abs_angle = abs(angle)

    if abs_angle <= 30:
        return 'straight'
    elif abs_angle <= 60:
        return 'slight_left' if angle < 0 else 'slight_right'
    elif abs_angle <= 120:
        return 'left' if angle < 0 else 'right'
    elif abs_angle <= 150:
        return 'sharp_left' if angle < 0 else 'sharp_right'
    else:
        return 'u_turn'


def build_line_graph(G):
    """원본 그래프를 Line Graph로 변환"""
    print("\n[2] Building Line Graph...")

    # MultiDiGraph의 경우 edge를 (u, v, key)로 식별
    # Line Graph의 노드는 원본 Edge, 간선은 연결된 Edge 쌍

    L = nx.DiGraph()

    # 1. 원본 Edge를 Line Graph 노드로 추가
    print("    Creating nodes from edges...")
    edge_count = 0

    for u, v, key, data in G.edges(keys=True, data=True):
        # Line Graph 노드 ID: 문자열로 변환 (튜플은 JSON 직렬화 문제)
        node_id = f"{u}_{v}_{key}"

        # 원본 Edge 데이터를 노드 속성으로 복사
        node_attrs = {
            'original_edge': (u, v, key),
            'source': u,
            'target': v,
            'edge_key': key,
        }

        # 모든 Edge 속성 복사
        for attr_key, attr_value in data.items():
            # geometry는 직렬화 문제가 있을 수 있으므로 별도 처리
            if attr_key == 'geometry':
                node_attrs['geometry'] = attr_value
                # 좌표도 추출
                if attr_value is not None:
                    coords = list(attr_value.coords)
                    node_attrs['start_coord'] = coords[0] if coords else None
                    node_attrs['end_coord'] = coords[-1] if coords else None
            else:
                node_attrs[attr_key] = attr_value

        # 방위각 계산
        bearing = get_edge_bearing(G, u, v)
        node_attrs['bearing'] = bearing

        L.add_node(node_id, **node_attrs)
        edge_count += 1

    print(f"    Created {edge_count:,} nodes")

    # 2. 연결된 Edge 쌍을 Line Graph 간선으로 추가
    print("    Creating edges from connections...")

    # 노드 ID 매핑 생성
    edge_to_node = {}
    for u, v, key in G.edges(keys=True):
        edge_to_node[(u, v, key)] = f"{u}_{v}_{key}"

    connection_count = 0

    for node in G.nodes():
        # 이 노드로 들어오는 Edge들
        in_edges = list(G.in_edges(node, keys=True))
        # 이 노드에서 나가는 Edge들
        out_edges = list(G.out_edges(node, keys=True))

        # 모든 (in_edge, out_edge) 쌍에 대해 Line Graph 간선 추가
        for in_edge in in_edges:
            for out_edge in out_edges:
                # 같은 Edge는 건너뛰기 (반대 방향도)
                in_u, in_v, in_k = in_edge
                out_u, out_v, out_k = out_edge

                # U-turn 방지 (같은 도로의 반대 방향)
                if in_u == out_v and in_v == out_u:
                    continue

                in_node_id = edge_to_node.get(in_edge)
                out_node_id = edge_to_node.get(out_edge)

                if in_node_id is None or out_node_id is None:
                    continue

                # 회전 각도 계산
                in_bearing = L.nodes[in_node_id].get('bearing')
                out_bearing = L.nodes[out_node_id].get('bearing')
                turn_angle = calculate_turn_angle(in_bearing, out_bearing)
                turn_type = classify_turn(turn_angle)

                # Line Graph 간선 추가
                L.add_edge(in_node_id, out_node_id,
                          turn_angle=turn_angle,
                          turn_type=turn_type,
                          via_node=node)

                connection_count += 1

    print(f"    Created {connection_count:,} edges")

    return L


def print_statistics(L):
    """Line Graph 통계 출력"""
    print("\n[3] Line Graph Statistics...")

    print(f"\n    Nodes (roads): {L.number_of_nodes():,}")
    print(f"    Edges (connections): {L.number_of_edges():,}")

    # Highway type 분포
    highway_counts = defaultdict(int)
    for node, data in L.nodes(data=True):
        hw = data.get('highway', 'unknown')
        highway_counts[hw] += 1

    print("\n    Highway type distribution:")
    for hw, count in sorted(highway_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"    - {hw}: {count:,}")

    # 테마 점수 분포
    print("\n    Theme score distribution:")
    for theme in ['green_score', 'food_score', 'cafe_score', 'nightlife_score', 'shopping_score']:
        scores = [data.get(theme, 0) for node, data in L.nodes(data=True)]
        non_zero = sum(1 for s in scores if s > 0)
        avg = sum(scores) / len(scores) if scores else 0
        max_score = max(scores) if scores else 0
        print(f"    - {theme}: avg={avg:.2f}, max={max_score}, non-zero={non_zero:,}")

    # 회전 유형 분포
    turn_counts = defaultdict(int)
    for u, v, data in L.edges(data=True):
        turn_type = data.get('turn_type', 'unknown')
        turn_counts[turn_type] += 1

    print("\n    Turn type distribution:")
    for turn, count in sorted(turn_counts.items(), key=lambda x: -x[1]):
        print(f"    - {turn}: {count:,}")


def save_line_graph(L):
    """Line Graph 저장"""
    print("\n[4] Saving Line Graph...")

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_PKL, 'wb') as f:
        pickle.dump(L, f)

    print(f"    [OK] Saved: {OUTPUT_PKL}")


def main():
    print("=" * 60)
    print(" Step 4: Line Graph 변환")
    print("=" * 60)

    # 1. Enriched 그래프 로드
    G = load_enriched_graph()

    # 2. Line Graph 생성
    L = build_line_graph(G)

    # 3. 통계 출력
    print_statistics(L)

    # 4. 저장
    save_line_graph(L)

    print("\n" + "=" * 60)
    print(" [OK] Step 4 Complete!")
    print("=" * 60)

    # 원본 그래프도 함께 반환 (경로 시각화용)
    return L, G


if __name__ == "__main__":
    main()
