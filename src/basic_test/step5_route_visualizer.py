"""
Step 5: 테마별 경로 탐색 + HTML 시각화
- Line Graph 기반 경로 탐색
- 지도에서 클릭으로 시작점/도착점 선택
- 테마별 경로 비교 (카페, 식당, 유흥, 쇼핑, 보행)
"""
import os
import json
import pickle
import networkx as nx
from collections import defaultdict

# Configuration
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SRC_DIR, 'data')
LINEGRAPH_PKL = os.path.join(DATA_DIR, 'hongdae-linegraph.pkl')
ENRICHED_PKL = os.path.join(DATA_DIR, 'hongdae-enriched.pkl')
OUTPUT_HTML = os.path.join(SRC_DIR, 'hongdae_route_explorer.html')

# 테마 설정
THEMES = {
    'cafe': {'name': '카페길', 'color': '#8B4513', 'icon': '☕', 'weight': 'cafe_score'},
    'food': {'name': '맛집길', 'color': '#FF6347', 'icon': '🍽️', 'weight': 'food_score'},
    'nightlife': {'name': '유흥길', 'color': '#9400D3', 'icon': '🌙', 'weight': 'nightlife_score'},
    'shopping': {'name': '쇼핑길', 'color': '#FF69B4', 'icon': '🛒', 'weight': 'shopping_score'},
    'green': {'name': '녹지길', 'color': '#228B22', 'icon': '🌳', 'weight': 'green_score'},
    'shortest': {'name': '최단경로', 'color': '#333333', 'icon': '📍', 'weight': None},
}


def load_data():
    """데이터 로드"""
    print("[1] Loading data...")

    with open(LINEGRAPH_PKL, 'rb') as f:
        L = pickle.load(f)
    print(f"    Line Graph: {L.number_of_nodes():,} nodes, {L.number_of_edges():,} edges")

    with open(ENRICHED_PKL, 'rb') as f:
        G = pickle.load(f)
    print(f"    Original Graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

    return L, G


def prepare_graph_data(G, L):
    """시각화용 데이터 준비"""
    print("[2] Preparing visualization data...")

    # 1. 모든 Edge 데이터 (배경 도로)
    edges_data = []
    for u, v, data in G.edges(data=True):
        u_data = G.nodes[u]
        v_data = G.nodes[v]

        if 'x' not in u_data or 'x' not in v_data:
            continue

        hw = data.get('highway', 'other')
        if isinstance(hw, list):
            hw = hw[0]

        edges_data.append({
            'lat1': u_data['y'], 'lng1': u_data['x'],
            'lat2': v_data['y'], 'lng2': v_data['x'],
            'highway': hw,
        })

    print(f"    Background edges: {len(edges_data):,}")

    # 2. 노드 좌표 맵 (클릭 위치 → 가장 가까운 노드)
    nodes_data = []
    for node_id, data in G.nodes(data=True):
        if 'x' in data and 'y' in data:
            nodes_data.append({
                'id': node_id,
                'lat': data['y'],
                'lng': data['x'],
            })

    print(f"    Nodes for click: {len(nodes_data):,}")

    # 3. Line Graph 노드 → 좌표 맵 (경로 시각화용)
    road_coords = {}
    for node_id in L.nodes():
        data = L.nodes[node_id]
        source = data.get('source')
        target = data.get('target')

        if source in G.nodes and target in G.nodes:
            s_data = G.nodes[source]
            t_data = G.nodes[target]
            if 'x' in s_data and 'x' in t_data:
                road_coords[node_id] = {
                    'lat1': s_data['y'], 'lng1': s_data['x'],
                    'lat2': t_data['y'], 'lng2': t_data['x'],
                    'cafe': data.get('cafe_score', 0) or 0,
                    'food': data.get('food_score', 0) or 0,
                    'nightlife': data.get('nightlife_score', 0) or 0,
                    'shopping': data.get('shopping_score', 0) or 0,
                    'green': data.get('green_score', 0) or 0,
                    'highway': data.get('highway', ''),
                    'name': data.get('name', '') or '',
                    'length': round(data.get('length', 0) or 0, 1),
                }

    print(f"    Road coordinates: {len(road_coords):,}")

    # 4. 노드 → Line Graph 노드 매핑 (시작/종료 노드로 경로 찾기)
    node_to_roads = defaultdict(list)
    for node_id in L.nodes():
        data = L.nodes[node_id]
        source = data.get('source')
        target = data.get('target')
        node_to_roads[source].append(node_id)
        node_to_roads[target].append(node_id)

    # 5. Line Graph 인접 리스트 (JavaScript에서 경로 탐색용)
    adjacency = defaultdict(list)
    for u, v, data in L.edges(data=True):
        adjacency[u].append({
            'to': v,
            'turn': data.get('turn_type', 'straight'),
        })

    print(f"    Adjacency entries: {len(adjacency):,}")

    # 중심점 계산
    if nodes_data:
        center_lat = sum(n['lat'] for n in nodes_data) / len(nodes_data)
        center_lng = sum(n['lng'] for n in nodes_data) / len(nodes_data)
    else:
        center_lat, center_lng = 37.556, 126.923

    return {
        'edges': edges_data,
        'nodes': nodes_data,
        'road_coords': road_coords,
        'node_to_roads': dict(node_to_roads),
        'adjacency': dict(adjacency),
        'center': {'lat': center_lat, 'lng': center_lng},
    }


def generate_html(graph_data, L, G):
    """HTML 생성"""
    print("[3] Generating HTML...")

    # Line Graph 노드별 가중치 데이터
    road_weights = {}

    # 정규화를 위한 최대값 계산
    max_scores = {
        'cafe': max((L.nodes[n].get('cafe_score', 0) or 0) for n in L.nodes()) or 1,
        'food': max((L.nodes[n].get('food_score', 0) or 0) for n in L.nodes()) or 1,
        'nightlife': max((L.nodes[n].get('nightlife_score', 0) or 0) for n in L.nodes()) or 1,
        'shopping': max((L.nodes[n].get('shopping_score', 0) or 0) for n in L.nodes()) or 1,
        'green': max((L.nodes[n].get('green_score', 0) or 0) for n in L.nodes()) or 1,
        'walk': max((L.nodes[n].get('walkability_score', 0) or 0) for n in L.nodes()) or 1,
    }

    for node_id in L.nodes():
        data = L.nodes[node_id]
        road_weights[node_id] = {
            'length': data.get('length', 50) or 50,
            'cafe': data.get('cafe_score', 0) or 0,
            'food': data.get('food_score', 0) or 0,
            'nightlife': data.get('nightlife_score', 0) or 0,
            'shopping': data.get('shopping_score', 0) or 0,
            'green': data.get('green_score', 0) or 0,
            'walk': data.get('walkability_score', 5) or 5,
        }

    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>홍대 테마별 경로 탐색기</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Malgun Gothic', sans-serif; }}
        #map {{ position: fixed; top: 0; left: 0; right: 320px; bottom: 0; }}

        .sidebar {{
            position: fixed; top: 0; right: 0; width: 320px; height: 100%;
            background: #f8f9fa; overflow-y: auto; padding: 20px;
            box-shadow: -2px 0 10px rgba(0,0,0,0.1);
        }}

        .sidebar h2 {{
            color: #333; margin-bottom: 15px; padding-bottom: 10px;
            border-bottom: 3px solid #667eea;
        }}

        .section {{ margin-bottom: 20px; }}
        .section h3 {{ color: #555; font-size: 14px; margin-bottom: 10px; }}

        .point-display {{
            background: white; padding: 12px; border-radius: 8px;
            margin-bottom: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .point-display .label {{ font-size: 12px; color: #888; }}
        .point-display .value {{ font-size: 14px; color: #333; font-weight: bold; }}
        .point-display.start {{ border-left: 4px solid #4CAF50; }}
        .point-display.end {{ border-left: 4px solid #f44336; }}

        .theme-buttons {{
            display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
        }}
        .theme-btn {{
            padding: 12px 8px; border: none; border-radius: 8px;
            cursor: pointer; font-size: 13px; transition: all 0.2s;
            display: flex; flex-direction: column; align-items: center;
            background: white; box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }}
        .theme-btn:hover {{ transform: translateY(-2px); box-shadow: 0 4px 10px rgba(0,0,0,0.15); }}
        .theme-btn.active {{ color: white; }}
        .theme-btn .icon {{ font-size: 20px; margin-bottom: 4px; }}

        .route-info {{
            background: white; padding: 15px; border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1); display: none;
        }}
        .route-info.visible {{ display: block; }}
        .route-info h4 {{ color: #333; margin-bottom: 10px; }}
        .route-stat {{ display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #eee; }}
        .route-stat:last-child {{ border-bottom: none; }}
        .route-stat .label {{ color: #666; }}
        .route-stat .value {{ font-weight: bold; }}

        .instructions {{
            background: #e3f2fd; padding: 12px; border-radius: 8px;
            font-size: 12px; color: #1565c0; line-height: 1.6;
        }}

        .clear-btn {{
            width: 100%; padding: 12px; background: #757575; color: white;
            border: none; border-radius: 8px; cursor: pointer; margin-top: 10px;
        }}
        .clear-btn:hover {{ background: #616161; }}
    </style>
</head>
<body>
    <div id="map"></div>

    <div class="sidebar">
        <h2>🗺️ 홍대 경로 탐색기</h2>

        <div class="section">
            <h3>📍 출발/도착</h3>
            <div class="point-display start">
                <div class="label">출발점</div>
                <div class="value" id="startPoint">지도를 클릭하세요</div>
            </div>
            <div class="point-display end">
                <div class="label">도착점</div>
                <div class="value" id="endPoint">-</div>
            </div>
        </div>

        <div class="section">
            <h3>🎨 테마 선택</h3>
            <div class="theme-buttons">
                <button class="theme-btn" data-theme="cafe" style="--color: #8B4513">
                    <span class="icon">☕</span>카페길
                </button>
                <button class="theme-btn" data-theme="food" style="--color: #FF6347">
                    <span class="icon">🍽️</span>맛집길
                </button>
                <button class="theme-btn" data-theme="nightlife" style="--color: #9400D3">
                    <span class="icon">🌙</span>유흥길
                </button>
                <button class="theme-btn" data-theme="shopping" style="--color: #FF69B4">
                    <span class="icon">🛒</span>쇼핑길
                </button>
                <button class="theme-btn" data-theme="green" style="--color: #228B22">
                    <span class="icon">🌳</span>녹지길
                </button>
                <button class="theme-btn" data-theme="shortest" style="--color: #333333">
                    <span class="icon">📍</span>최단경로
                </button>
            </div>
        </div>

        <div class="section">
            <div class="route-info" id="routeInfo">
                <h4 id="routeTitle">경로 정보</h4>
                <div class="route-stat"><span class="label">총 거리</span><span class="value" id="routeDistance">-</span></div>
                <div class="route-stat"><span class="label">도로 수</span><span class="value" id="routeRoads">-</span></div>
                <div class="route-stat"><span class="label">카페</span><span class="value" id="routeCafe">-</span></div>
                <div class="route-stat"><span class="label">식당</span><span class="value" id="routeFood">-</span></div>
                <div class="route-stat"><span class="label">유흥</span><span class="value" id="routeNightlife">-</span></div>
                <div class="route-stat"><span class="label">쇼핑</span><span class="value" id="routeShopping">-</span></div>
                <div class="route-stat"><span class="label">녹지</span><span class="value" id="routeGreen">-</span></div>
            </div>
        </div>

        <div class="section">
            <div class="instructions">
                <strong>사용법:</strong><br>
                1. 지도를 클릭하여 출발점 선택<br>
                2. 다시 클릭하여 도착점 선택<br>
                3. 테마 버튼을 눌러 경로 탐색
            </div>
            <button class="clear-btn" onclick="clearAll()">초기화</button>
        </div>
    </div>

    <script>
        // 데이터 로드
        const graphData = {json.dumps(graph_data, ensure_ascii=False)};
        const roadWeights = {json.dumps(road_weights)};
        const themes = {json.dumps(THEMES, ensure_ascii=False)};
        const maxScores = {json.dumps(max_scores)};

        // 지도 초기화
        const map = L.map('map').setView([graphData.center.lat, graphData.center.lng], 15);
        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '&copy; OpenStreetMap, &copy; CartoDB'
        }}).addTo(map);

        // 배경 도로 그리기
        const bgLayer = L.layerGroup().addTo(map);
        graphData.edges.forEach(e => {{
            L.polyline([[e.lat1, e.lng1], [e.lat2, e.lng2]], {{
                color: '#ccc', weight: 1, opacity: 0.5
            }}).addTo(bgLayer);
        }});

        // 상태 변수
        let startNode = null, endNode = null;
        let startMarker = null, endMarker = null;
        let routeLayer = L.layerGroup().addTo(map);
        let currentTheme = 'cafe';

        // 가장 가까운 노드 찾기
        function findNearestNode(lat, lng) {{
            let minDist = Infinity, nearest = null;
            graphData.nodes.forEach(n => {{
                const dist = Math.sqrt(Math.pow(n.lat - lat, 2) + Math.pow(n.lng - lng, 2));
                if (dist < minDist) {{ minDist = dist; nearest = n; }}
            }});
            return nearest;
        }}

        // Dijkstra 경로 탐색
        function findPath(startNodeId, endNodeId, theme) {{
            // JSON 키는 문자열이므로 변환 필요!
            const startRoads = graphData.node_to_roads[String(startNodeId)] || [];
            const endRoads = graphData.node_to_roads[String(endNodeId)] || [];

            if (startRoads.length === 0 || endRoads.length === 0) return null;

            const endRoadSet = new Set(endRoads);
            const dist = {{}}, prev = {{}}, visited = new Set();
            const pq = [];

            // 시작 도로들 초기화
            startRoads.forEach(road => {{
                dist[road] = 0;
                pq.push([0, road]);
            }});

            while (pq.length > 0) {{
                pq.sort((a, b) => a[0] - b[0]);
                const [d, u] = pq.shift();

                if (visited.has(u)) continue;
                visited.add(u);

                if (endRoadSet.has(u)) {{
                    // 경로 역추적
                    const path = [u];
                    let curr = u;
                    while (prev[curr]) {{ curr = prev[curr]; path.unshift(curr); }}
                    return path;
                }}

                const neighbors = graphData.adjacency[u] || [];
                neighbors.forEach(edge => {{
                    const v = edge.to;
                    if (visited.has(v)) return;

                    const w = roadWeights[v];
                    if (!w) return;

                    let weight = w.length;
                    if (theme !== 'shortest' && themes[theme]) {{
                        const scoreKey = themes[theme].weight.replace('_score', '');
                        const score = w[scoreKey] || 0;
                        const maxScore = maxScores[scoreKey] || 1;
                        const normalizedScore = Math.min(score / maxScore, 1);  // 0~1 정규화
                        // 새 공식: 최대 60% 할인, 거리가 기본 비용
                        weight = w.length * (1 - 0.6 * normalizedScore);
                    }}

                    const newDist = d + weight;
                    if (dist[v] === undefined || newDist < dist[v]) {{
                        dist[v] = newDist;
                        prev[v] = u;
                        pq.push([newDist, v]);
                    }}
                }});
            }}
            return null;
        }}

        // 경로 그리기
        function drawRoute(path, theme) {{
            routeLayer.clearLayers();
            if (!path || path.length === 0) return;

            const color = themes[theme]?.color || '#333';
            let totalDist = 0, totalCafe = 0, totalFood = 0, totalNight = 0, totalShop = 0, totalGreen = 0;

            path.forEach(roadId => {{
                const coord = graphData.road_coords[roadId];
                if (!coord) return;

                L.polyline([[coord.lat1, coord.lng1], [coord.lat2, coord.lng2]], {{
                    color: color, weight: 5, opacity: 0.8
                }}).bindPopup(`<b>${{coord.name || '도로'}}</b><br>
                    거리: ${{coord.length}}m<br>
                    카페: ${{coord.cafe}}, 식당: ${{coord.food}}<br>
                    유흥: ${{coord.nightlife}}, 쇼핑: ${{coord.shopping}}, 녹지: ${{coord.green}}`
                ).addTo(routeLayer);

                totalDist += coord.length;
                totalCafe += coord.cafe;
                totalFood += coord.food;
                totalNight += coord.nightlife;
                totalShop += coord.shopping;
                totalGreen += coord.green;
            }});

            // 경로 정보 업데이트
            document.getElementById('routeInfo').classList.add('visible');
            document.getElementById('routeTitle').textContent = themes[theme]?.icon + ' ' + themes[theme]?.name;
            document.getElementById('routeDistance').textContent = Math.round(totalDist) + 'm';
            document.getElementById('routeRoads').textContent = path.length + '개';
            document.getElementById('routeCafe').textContent = totalCafe + '개';
            document.getElementById('routeFood').textContent = totalFood + '개';
            document.getElementById('routeNightlife').textContent = totalNight + '개';
            document.getElementById('routeShopping').textContent = totalShop + '개';
            document.getElementById('routeGreen').textContent = totalGreen + '점';
        }}

        // 지도 클릭 이벤트
        map.on('click', function(e) {{
            const nearest = findNearestNode(e.latlng.lat, e.latlng.lng);
            if (!nearest) return;

            if (!startNode) {{
                startNode = nearest;
                if (startMarker) map.removeLayer(startMarker);
                startMarker = L.marker([nearest.lat, nearest.lng], {{
                    icon: L.divIcon({{ html: '<div style="font-size:24px">🟢</div>', className: '', iconSize: [30,30], iconAnchor: [15,15] }})
                }}).addTo(map);
                document.getElementById('startPoint').textContent = `${{nearest.lat.toFixed(5)}}, ${{nearest.lng.toFixed(5)}}`;
            }} else if (!endNode) {{
                endNode = nearest;
                if (endMarker) map.removeLayer(endMarker);
                endMarker = L.marker([nearest.lat, nearest.lng], {{
                    icon: L.divIcon({{ html: '<div style="font-size:24px">🔴</div>', className: '', iconSize: [30,30], iconAnchor: [15,15] }})
                }}).addTo(map);
                document.getElementById('endPoint').textContent = `${{nearest.lat.toFixed(5)}}, ${{nearest.lng.toFixed(5)}}`;

                // 자동으로 경로 탐색
                const path = findPath(startNode.id, endNode.id, currentTheme);
                if (path) drawRoute(path, currentTheme);
                else alert('경로를 찾을 수 없습니다.');
            }}
        }});

        // 테마 버튼 이벤트
        document.querySelectorAll('.theme-btn').forEach(btn => {{
            btn.addEventListener('click', function() {{
                document.querySelectorAll('.theme-btn').forEach(b => {{
                    b.classList.remove('active');
                    b.style.background = 'white';
                    b.style.color = '#333';
                }});
                this.classList.add('active');
                this.style.background = themes[this.dataset.theme]?.color || '#333';
                this.style.color = 'white';

                currentTheme = this.dataset.theme;

                if (startNode && endNode) {{
                    const path = findPath(startNode.id, endNode.id, currentTheme);
                    if (path) drawRoute(path, currentTheme);
                }}
            }});
        }});

        // 초기화
        function clearAll() {{
            startNode = endNode = null;
            if (startMarker) map.removeLayer(startMarker);
            if (endMarker) map.removeLayer(endMarker);
            startMarker = endMarker = null;
            routeLayer.clearLayers();
            document.getElementById('startPoint').textContent = '지도를 클릭하세요';
            document.getElementById('endPoint').textContent = '-';
            document.getElementById('routeInfo').classList.remove('visible');
        }}

        // 첫 번째 테마 버튼 활성화
        document.querySelector('.theme-btn[data-theme="cafe"]').click();
    </script>
</body>
</html>'''

    return html


def main():
    print("=" * 60)
    print(" Step 5: 테마별 경로 탐색 + HTML 시각화")
    print("=" * 60)

    # 1. 데이터 로드
    L, G = load_data()

    # 2. 시각화 데이터 준비
    graph_data = prepare_graph_data(G, L)

    # 3. HTML 생성
    html = generate_html(graph_data, L, G)

    # 4. 저장
    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n[OK] Saved: {OUTPUT_HTML}")
    print("    브라우저에서 열어서 확인하세요!")

    print("\n" + "=" * 60)
    print(" [OK] Step 5 Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
