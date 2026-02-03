import pickle
import networkx as nx

# 로드
with open('src/data/hongdae-linegraph.pkl', 'rb') as f:
    L = pickle.load(f)

# 테마별 경로 탐색 (카페 위주)
def cafe_weight(u, v, data):
    node_data = L.nodes[v]
    length = node_data.get('length', 50) or 50
    cafe = node_data.get('cafe_score', 0) or 0
    walkability = node_data.get('walkability_score', 5) or 5

    # 카페 많을수록 가중치 낮게 (선호)
    return length / (1 + cafe * 0.5 + walkability * 0.1)

# 시작/종료 노드 (도로 ID)
start_road = list(L.nodes())[0]
end_road = list(L.nodes())[1000]

# 최단 경로 (카페 선호)
path = nx.dijkstra_path(L, start_road, end_road, weight=cafe_weight)

# 경로 정보 출력
for road_id in path[:]:
    data = L.nodes[road_id]
    print(f"도로: {data.get('name', '무명')}, {road_id}"
        f"카페: {data.get('cafe_score', 0)}, "
        f"보행: {data.get('walkability_score', 0):.1f}")