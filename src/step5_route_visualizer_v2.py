"""
Step 5 V2: 고급 경로 탐색 시스템
- K-Diverse Paths: 테마당 5개 다양한 경로
- 시간 기반 탐색: 목적지 없이 순환 경로
- 경로 비교 UI
"""
import os
import json
import pickle
from collections import defaultdict

# Configuration
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SRC_DIR, 'data')
LINEGRAPH_PKL = os.path.join(DATA_DIR, 'hongdae-linegraph.pkl')
ENRICHED_PKL = os.path.join(DATA_DIR, 'hongdae-enriched.pkl')
OUTPUT_HTML = os.path.join(SRC_DIR, 'hongdae_route_explorer_v2.html')

# 테마 설정
THEMES = ['cafe', 'food', 'nightlife', 'shopping', 'green', 'shortest']
THEME_INFO = {
    'cafe': {'name': '카페길', 'color': '#8B4513', 'icon': 'coffee'},
    'food': {'name': '맛집길', 'color': '#FF6347', 'icon': 'utensils'},
    'nightlife': {'name': '유흥길', 'color': '#9400D3', 'icon': 'moon'},
    'shopping': {'name': '쇼핑길', 'color': '#FF69B4', 'icon': 'shopping-bag'},
    'green': {'name': '녹지길', 'color': '#228B22', 'icon': 'tree'},
    'shortest': {'name': '최단경로', 'color': '#333333', 'icon': 'location-arrow'},
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


def prepare_data(L, G):
    """시각화용 데이터 준비"""
    print("[2] Preparing data...")

    # 최대 점수 계산
    max_scores = {
        'cafe': max((L.nodes[n].get('cafe_score', 0) or 0) for n in L.nodes()) or 1,
        'food': max((L.nodes[n].get('food_score', 0) or 0) for n in L.nodes()) or 1,
        'nightlife': max((L.nodes[n].get('nightlife_score', 0) or 0) for n in L.nodes()) or 1,
        'shopping': max((L.nodes[n].get('shopping_score', 0) or 0) for n in L.nodes()) or 1,
        'green': max((L.nodes[n].get('green_score', 0) or 0) for n in L.nodes()) or 1,
    }
    print(f"    Max scores: {max_scores}")

    # 도로 가중치
    road_weights = {}
    for node_id in L.nodes():
        data = L.nodes[node_id]
        road_weights[node_id] = {
            'length': data.get('length', 50) or 50,
            'cafe': data.get('cafe_score', 0) or 0,
            'food': data.get('food_score', 0) or 0,
            'nightlife': data.get('nightlife_score', 0) or 0,
            'shopping': data.get('shopping_score', 0) or 0,
            'green': data.get('green_score', 0) or 0,
        }

    # 노드 -> 도로 매핑
    node_to_roads = defaultdict(list)
    for node_id in L.nodes():
        data = L.nodes[node_id]
        source = data.get('source')
        target = data.get('target')
        node_to_roads[str(source)].append(node_id)
        node_to_roads[str(target)].append(node_id)

    # 도로 좌표
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
                }

    # 노드 목록 (클릭용)
    nodes_data = []
    for node_id, data in G.nodes(data=True):
        if 'x' in data and 'y' in data:
            nodes_data.append({
                'id': node_id,
                'lat': data['y'],
                'lng': data['x'],
            })

    # 배경 도로
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

    # 인접 리스트
    adjacency = defaultdict(list)
    for u, v, data in L.edges(data=True):
        adjacency[u].append(v)

    # 중심점
    center_lat = sum(n['lat'] for n in nodes_data) / len(nodes_data) if nodes_data else 37.556
    center_lng = sum(n['lng'] for n in nodes_data) / len(nodes_data) if nodes_data else 126.923

    print(f"    Nodes: {len(nodes_data):,}, Roads: {len(road_coords):,}")

    return {
        'max_scores': max_scores,
        'road_weights': road_weights,
        'node_to_roads': dict(node_to_roads),
        'road_coords': road_coords,
        'nodes': nodes_data,
        'edges': edges_data,
        'adjacency': dict(adjacency),
        'center': {'lat': center_lat, 'lng': center_lng},
    }


def generate_html(data):
    """HTML 생성"""
    print("[3] Generating HTML...")

    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>홍대 테마 경로 탐색기 V2</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Malgun Gothic', -apple-system, sans-serif; background: #f0f2f5; }}

        #map {{
            position: fixed;
            top: 0;
            left: 0;
            right: 380px;
            bottom: 0;
            z-index: 1;
        }}

        .sidebar {{
            position: fixed;
            top: 0;
            right: 0;
            width: 380px;
            height: 100%;
            background: white;
            overflow-y: auto;
            box-shadow: -4px 0 20px rgba(0,0,0,0.1);
            z-index: 100;
        }}

        .sidebar-header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            position: sticky;
            top: 0;
            z-index: 10;
        }}

        .sidebar-header h1 {{
            font-size: 20px;
            margin-bottom: 5px;
        }}

        .sidebar-header p {{
            font-size: 12px;
            opacity: 0.9;
        }}

        .tab-container {{
            display: flex;
            border-bottom: 2px solid #e0e0e0;
            background: #fafafa;
        }}

        .tab {{
            flex: 1;
            padding: 15px 10px;
            text-align: center;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            color: #666;
            border-bottom: 3px solid transparent;
            transition: all 0.2s;
        }}

        .tab:hover {{ background: #f0f0f0; }}
        .tab.active {{
            color: #667eea;
            border-bottom-color: #667eea;
            background: white;
        }}

        .tab-content {{
            display: none;
            padding: 15px;
        }}

        .tab-content.active {{ display: block; }}

        .section {{
            background: #fafafa;
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 15px;
        }}

        .section-title {{
            font-size: 14px;
            font-weight: 600;
            color: #333;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .point-box {{
            background: white;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 8px;
            border-left: 4px solid #ccc;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}

        .point-box.start {{ border-left-color: #4CAF50; }}
        .point-box.end {{ border-left-color: #f44336; }}

        .point-label {{ font-size: 11px; color: #888; margin-bottom: 4px; }}
        .point-value {{ font-size: 13px; color: #333; font-weight: 500; }}

        .theme-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
        }}

        .theme-btn {{
            padding: 12px 8px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            background: white;
            cursor: pointer;
            text-align: center;
            transition: all 0.2s;
        }}

        .theme-btn:hover {{
            border-color: #667eea;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102,126,234,0.2);
        }}

        .theme-btn.active {{
            border-color: var(--theme-color);
            background: var(--theme-color);
            color: white;
        }}

        .theme-btn i {{ font-size: 18px; margin-bottom: 4px; display: block; }}
        .theme-btn span {{ font-size: 11px; font-weight: 500; }}

        .time-input-group {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 10px;
        }}

        .time-input {{
            flex: 1;
            padding: 10px 15px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            text-align: center;
        }}

        .time-input:focus {{
            outline: none;
            border-color: #667eea;
        }}

        .btn {{
            padding: 12px 20px;
            border: none;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }}

        .btn-primary {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}

        .btn-primary:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(102,126,234,0.4);
        }}

        .btn-secondary {{
            background: #f0f0f0;
            color: #666;
        }}

        .btn-secondary:hover {{ background: #e0e0e0; }}

        .btn-block {{ width: 100%; margin-top: 10px; }}

        .path-list {{
            max-height: 400px;
            overflow-y: auto;
        }}

        .path-item {{
            background: white;
            border-radius: 10px;
            padding: 12px;
            margin-bottom: 10px;
            cursor: pointer;
            border: 2px solid transparent;
            transition: all 0.2s;
            box-shadow: 0 2px 6px rgba(0,0,0,0.06);
        }}

        .path-item:hover {{
            border-color: #667eea;
            transform: translateX(3px);
        }}

        .path-item.active {{
            border-color: var(--theme-color, #667eea);
            background: linear-gradient(135deg, rgba(102,126,234,0.05) 0%, rgba(118,75,162,0.05) 100%);
        }}

        .path-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }}

        .path-rank {{
            width: 28px;
            height: 28px;
            background: var(--theme-color, #667eea);
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: bold;
        }}

        .path-distance {{
            font-size: 16px;
            font-weight: 600;
            color: #333;
        }}

        .path-stats {{
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }}

        .path-stat {{
            font-size: 11px;
            color: #666;
            display: flex;
            align-items: center;
            gap: 4px;
        }}

        .path-stat i {{ color: var(--stat-color, #888); }}

        .no-results {{
            text-align: center;
            padding: 40px 20px;
            color: #888;
        }}

        .no-results i {{
            font-size: 48px;
            margin-bottom: 15px;
            opacity: 0.3;
        }}

        .loading {{
            text-align: center;
            padding: 30px;
        }}

        .loading i {{
            font-size: 32px;
            color: #667eea;
            animation: spin 1s linear infinite;
        }}

        @keyframes spin {{
            from {{ transform: rotate(0deg); }}
            to {{ transform: rotate(360deg); }}
        }}

        .instructions {{
            background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%);
            border-radius: 10px;
            padding: 15px;
            font-size: 12px;
            line-height: 1.8;
            color: #555;
        }}

        .instructions strong {{ color: #333; }}

        .loop-legend {{
            display: flex;
            gap: 15px;
            font-size: 11px;
            color: #666;
            margin-top: 8px;
            padding: 8px 12px;
            background: #f5f5f5;
            border-radius: 6px;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .legend-line {{
            width: 24px;
            height: 4px;
            border-radius: 2px;
        }}

        .legend-line.solid {{ background: var(--theme-color, #667eea); }}
        .legend-line.dashed {{
            background: repeating-linear-gradient(
                90deg,
                var(--theme-color, #667eea) 0px,
                var(--theme-color, #667eea) 6px,
                transparent 6px,
                transparent 10px
            );
            opacity: 0.6;
        }}
    </style>
</head>
<body>
    <div id="map"></div>

    <div class="sidebar">
        <div class="sidebar-header">
            <h1><i class="fas fa-map-marked-alt"></i> 홍대 경로 탐색기</h1>
            <p>테마별 다양한 경로를 탐색해보세요</p>
        </div>

        <div class="tab-container">
            <div class="tab active" data-tab="destination">
                <i class="fas fa-route"></i> 목적지 경로
            </div>
            <div class="tab" data-tab="explore">
                <i class="fas fa-walking"></i> 시간 탐색
            </div>
        </div>

        <!-- 목적지 경로 탭 -->
        <div id="tab-destination" class="tab-content active">
            <div class="section">
                <div class="section-title"><i class="fas fa-map-pin"></i> 출발/도착</div>
                <div class="point-box start">
                    <div class="point-label">출발점</div>
                    <div class="point-value" id="startPoint">지도를 클릭하세요</div>
                </div>
                <div class="point-box end">
                    <div class="point-label">도착점</div>
                    <div class="point-value" id="endPoint">-</div>
                </div>
            </div>

            <div class="section">
                <div class="section-title"><i class="fas fa-palette"></i> 테마 선택</div>
                <div class="theme-grid">
                    <div class="theme-btn" data-theme="cafe" style="--theme-color: #8B4513">
                        <i class="fas fa-coffee"></i>
                        <span>카페길</span>
                    </div>
                    <div class="theme-btn" data-theme="food" style="--theme-color: #FF6347">
                        <i class="fas fa-utensils"></i>
                        <span>맛집길</span>
                    </div>
                    <div class="theme-btn" data-theme="nightlife" style="--theme-color: #9400D3">
                        <i class="fas fa-moon"></i>
                        <span>유흥길</span>
                    </div>
                    <div class="theme-btn" data-theme="shopping" style="--theme-color: #FF69B4">
                        <i class="fas fa-shopping-bag"></i>
                        <span>쇼핑길</span>
                    </div>
                    <div class="theme-btn" data-theme="green" style="--theme-color: #228B22">
                        <i class="fas fa-tree"></i>
                        <span>녹지길</span>
                    </div>
                    <div class="theme-btn" data-theme="shortest" style="--theme-color: #333333">
                        <i class="fas fa-location-arrow"></i>
                        <span>최단경로</span>
                    </div>
                </div>
                <button class="btn btn-primary btn-block" id="btnFindPaths">
                    <i class="fas fa-search"></i> 경로 탐색 (5개)
                </button>
            </div>

            <div class="section" id="pathResults" style="display: none;">
                <div class="section-title">
                    <i class="fas fa-list"></i>
                    <span id="resultsTitle">경로 목록</span>
                </div>
                <div class="path-list" id="pathList"></div>
            </div>
        </div>

        <!-- 시간 탐색 탭 -->
        <div id="tab-explore" class="tab-content">
            <div class="section">
                <div class="section-title"><i class="fas fa-map-pin"></i> 출발점</div>
                <div class="point-box start">
                    <div class="point-label">출발점</div>
                    <div class="point-value" id="exploreStartPoint">지도를 클릭하세요</div>
                </div>
            </div>

            <div class="section">
                <div class="section-title"><i class="fas fa-clock"></i> 산책 시간</div>
                <div class="time-input-group">
                    <input type="number" class="time-input" id="walkTime" value="30" min="10" max="120" step="5">
                    <span>분</span>
                </div>
                <p style="font-size: 11px; color: #888; margin-top: 8px;">
                    * 약 <span id="estimatedDistance">2.2</span>km 예상 (순환 경로)
                </p>
            </div>

            <div class="section">
                <div class="section-title"><i class="fas fa-palette"></i> 테마 선택</div>
                <div class="theme-grid">
                    <div class="theme-btn explore-theme" data-theme="cafe" style="--theme-color: #8B4513">
                        <i class="fas fa-coffee"></i>
                        <span>카페</span>
                    </div>
                    <div class="theme-btn explore-theme" data-theme="food" style="--theme-color: #FF6347">
                        <i class="fas fa-utensils"></i>
                        <span>맛집</span>
                    </div>
                    <div class="theme-btn explore-theme" data-theme="nightlife" style="--theme-color: #9400D3">
                        <i class="fas fa-moon"></i>
                        <span>유흥</span>
                    </div>
                    <div class="theme-btn explore-theme" data-theme="shopping" style="--theme-color: #FF69B4">
                        <i class="fas fa-shopping-bag"></i>
                        <span>쇼핑</span>
                    </div>
                    <div class="theme-btn explore-theme" data-theme="green" style="--theme-color: #228B22">
                        <i class="fas fa-tree"></i>
                        <span>녹지</span>
                    </div>
                </div>
                <button class="btn btn-primary btn-block" id="btnExplore">
                    <i class="fas fa-walking"></i> 산책 코스 찾기
                </button>
            </div>

            <div class="section" id="exploreResults" style="display: none;">
                <div class="section-title">
                    <i class="fas fa-list"></i>
                    <span id="exploreResultsTitle">순환 코스</span>
                </div>
                <div class="loop-legend" id="loopLegend">
                    <div class="legend-item">
                        <div class="legend-line solid"></div>
                        <span>가는 길</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-line dashed"></div>
                        <span>오는 길</span>
                    </div>
                </div>
                <div class="path-list" id="explorePathList"></div>
            </div>
        </div>

        <div style="padding: 15px;">
            <div class="instructions">
                <strong><i class="fas fa-info-circle"></i> 사용법</strong><br>
                <b>목적지 경로:</b> 출발점/도착점 클릭 후 테마 선택<br>
                <b>시간 탐색:</b> 출발점 클릭, 시간 설정 후 탐색<br>
                <br>
                <i class="fas fa-lightbulb"></i> 각 테마별로 5개의 다양한 경로를 제공합니다
            </div>
            <button class="btn btn-secondary btn-block" onclick="clearAll()">
                <i class="fas fa-redo"></i> 초기화
            </button>
        </div>
    </div>

    <script>
        // =====================================================
        // DATA
        // =====================================================
        const maxScores = {json.dumps(data['max_scores'])};
        const roadWeights = {json.dumps(data['road_weights'])};
        const nodeToRoads = {json.dumps(data['node_to_roads'])};
        const roadCoords = {json.dumps(data['road_coords'])};
        const nodesData = {json.dumps(data['nodes'])};
        const edgesData = {json.dumps(data['edges'])};
        const adjacency = {json.dumps(data['adjacency'])};
        const center = {json.dumps(data['center'])};

        const themeColors = {{
            cafe: '#8B4513',
            food: '#FF6347',
            nightlife: '#9400D3',
            shopping: '#FF69B4',
            green: '#228B22',
            shortest: '#333333'
        }};

        const themeNames = {{
            cafe: '카페길',
            food: '맛집길',
            nightlife: '유흥길',
            shopping: '쇼핑길',
            green: '녹지길',
            shortest: '최단경로'
        }};

        // =====================================================
        // MAP INITIALIZATION
        // =====================================================
        const map = L.map('map').setView([center.lat, center.lng], 15);
        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '&copy; OpenStreetMap, &copy; CartoDB'
        }}).addTo(map);

        // Background roads
        const bgLayer = L.layerGroup().addTo(map);
        edgesData.forEach(e => {{
            L.polyline([[e.lat1, e.lng1], [e.lat2, e.lng2]], {{
                color: '#ddd', weight: 1, opacity: 0.6
            }}).addTo(bgLayer);
        }});

        // Route layer
        const routeLayer = L.layerGroup().addTo(map);

        // =====================================================
        // STATE
        // =====================================================
        let startNode = null;
        let endNode = null;
        let startMarker = null;
        let endMarker = null;
        let currentTheme = 'cafe';
        let exploreTheme = 'cafe';
        let currentPaths = [];
        let activeTab = 'destination';

        // =====================================================
        // UTILITY FUNCTIONS
        // =====================================================
        function findNearestNode(lat, lng) {{
            let minDist = Infinity, nearest = null;
            nodesData.forEach(n => {{
                const dist = Math.sqrt(Math.pow(n.lat - lat, 2) + Math.pow(n.lng - lng, 2));
                if (dist < minDist) {{ minDist = dist; nearest = n; }}
            }});
            return nearest;
        }}

        function formatDistance(meters) {{
            if (meters >= 1000) return (meters / 1000).toFixed(1) + 'km';
            return Math.round(meters) + 'm';
        }}

        // =====================================================
        // K-DIVERSE PATHS ALGORITHM (JavaScript Implementation)
        // =====================================================
        function dijkstraWithPenalty(startRoads, endRoads, theme, penalties) {{
            if (!startRoads.length || !endRoads.length) return null;

            const endSet = new Set(endRoads);
            const dist = {{}};
            const prev = {{}};
            const visited = new Set();
            const pq = [];

            startRoads.forEach(road => {{
                dist[road] = 0;
                pq.push([0, road]);
            }});

            while (pq.length > 0) {{
                pq.sort((a, b) => a[0] - b[0]);
                const [d, u] = pq.shift();

                if (visited.has(u)) continue;
                visited.add(u);

                if (endSet.has(u)) {{
                    const path = [u];
                    let curr = u;
                    while (prev[curr]) {{ curr = prev[curr]; path.unshift(curr); }}
                    return path;
                }}

                const neighbors = adjacency[u] || [];
                neighbors.forEach(v => {{
                    if (visited.has(v)) return;

                    const w = roadWeights[v];
                    if (!w) return;

                    let weight = w.length;

                    // Theme weight
                    if (theme && theme !== 'shortest') {{
                        const score = w[theme] || 0;
                        const maxScore = maxScores[theme] || 1;
                        const normalized = Math.min(score / maxScore, 1);
                        weight = weight * (1 - 0.6 * normalized);
                    }}

                    // Penalty
                    const penalty = penalties[v] || 0;
                    weight = weight * (1 + penalty);

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

        function calculatePathStats(path) {{
            const stats = {{ distance: 0, cafe: 0, food: 0, nightlife: 0, shopping: 0, green: 0, edges: path.length }};
            path.forEach(roadId => {{
                const w = roadWeights[roadId] || {{}};
                stats.distance += w.length || 0;
                stats.cafe += w.cafe || 0;
                stats.food += w.food || 0;
                stats.nightlife += w.nightlife || 0;
                stats.shopping += w.shopping || 0;
                stats.green += w.green || 0;
            }});
            return stats;
        }}

        function jaccardDistance(path1, path2) {{
            const set1 = new Set(path1);
            const set2 = new Set(path2);
            const intersection = [...set1].filter(x => set2.has(x)).length;
            const union = new Set([...set1, ...set2]).size;
            return union === 0 ? 1 : 1 - intersection / union;
        }}

        function findKDiversePaths(startNodeId, endNodeId, theme, k = 5) {{
            const startRoads = nodeToRoads[String(startNodeId)] || [];
            const endRoads = nodeToRoads[String(endNodeId)] || [];

            if (!startRoads.length || !endRoads.length) return [];

            // 최단경로는 1개만
            const targetCount = (theme === 'shortest') ? 1 : k;

            const paths = [];
            const penalties = {{}};
            const minDiversity = 0.25;
            const penaltyFactor = 0.5;
            let attempts = 0;

            while (paths.length < targetCount && attempts < targetCount * 3) {{
                attempts++;

                const path = dijkstraWithPenalty(startRoads, endRoads, theme, penalties);
                if (!path) break;

                // Check diversity
                let isDiverse = true;
                for (const [existingPath, _] of paths) {{
                    if (jaccardDistance(path, existingPath) < minDiversity) {{
                        isDiverse = false;
                        break;
                    }}
                }}

                if (isDiverse) {{
                    paths.push([path, calculatePathStats(path)]);
                }}

                // Update penalties
                const decay = (k - paths.length + 1) / k;
                path.forEach(edge => {{
                    penalties[edge] = (penalties[edge] || 0) + penaltyFactor * decay;
                }});
            }}

            // Sort by theme score
            if (theme && theme !== 'shortest') {{
                paths.sort((a, b) => (b[1][theme] || 0) - (a[1][theme] || 0));
            }} else {{
                paths.sort((a, b) => a[1].distance - b[1].distance);
            }}

            return paths;
        }}

        // =====================================================
        // TIME-BASED EXPLORATION ALGORITHM
        // =====================================================
        function themeGuidedWalk(startRoads, theme, targetDistance, avoidEdges, randomness = 0.3) {{
            if (!startRoads.length) return [[], null];

            const avoid = new Set(avoidEdges || []);
            const visited = new Set();
            let current = null;
            let totalDist = 0;
            const path = [];

            // Select start road
            const validStarts = startRoads.filter(r => !avoid.has(r));
            if (!validStarts.length) return [[], null];

            // Weighted random selection
            const startScores = validStarts.map(r => {{
                const w = roadWeights[r] || {{}};
                return [r, (w[theme] || 0) + 1];
            }});
            const totalScore = startScores.reduce((s, [_, sc]) => s + sc, 0);
            let rand = Math.random() * totalScore;
            for (const [road, score] of startScores) {{
                rand -= score;
                if (rand <= 0) {{ current = road; break; }}
            }}
            if (!current) current = validStarts[0];

            path.push(current);
            visited.add(current);
            totalDist += (roadWeights[current]?.length || 0);

            while (totalDist < targetDistance) {{
                const neighbors = adjacency[current] || [];
                let candidates = [];

                for (const road of neighbors) {{
                    if (visited.has(road) || avoid.has(road)) continue;
                    const w = roadWeights[road] || {{}};
                    const length = w.length || 50;
                    if (totalDist + length > targetDistance * 1.3) continue;
                    candidates.push([road, (w[theme] || 0) + 0.1, length]);
                }}

                if (!candidates.length) {{
                    // Allow visited
                    for (const road of neighbors) {{
                        if (avoid.has(road)) continue;
                        const w = roadWeights[road] || {{}};
                        candidates.push([road, (w[theme] || 0) + 0.1, w.length || 50]);
                    }}
                }}

                if (!candidates.length) break;

                // Select next
                let selected, length;
                if (Math.random() < randomness) {{
                    const idx = Math.floor(Math.random() * candidates.length);
                    [selected, , length] = candidates[idx];
                }} else {{
                    const total = candidates.reduce((s, [_, sc]) => s + sc, 0);
                    let r = Math.random() * total;
                    for (const [road, score, len] of candidates) {{
                        r -= score;
                        if (r <= 0) {{ selected = road; length = len; break; }}
                    }}
                    if (!selected) {{ [selected, , length] = candidates[0]; }}
                }}

                path.push(selected);
                visited.add(selected);
                current = selected;
                totalDist += length;
            }}

            return [path, current];
        }}

        function findReturnPath(startRoad, endRoads, avoidEdges, theme) {{
            const avoid = new Set(avoidEdges || []);
            const endSet = new Set(endRoads);
            const dist = {{ [startRoad]: 0 }};
            const prev = {{}};
            const visited = new Set();
            const pq = [[0, startRoad]];

            while (pq.length > 0) {{
                pq.sort((a, b) => a[0] - b[0]);
                const [d, u] = pq.shift();

                if (visited.has(u)) continue;
                visited.add(u);

                if (endSet.has(u)) {{
                    const path = [u];
                    let curr = u;
                    while (prev[curr]) {{ curr = prev[curr]; path.unshift(curr); }}
                    return path;
                }}

                const neighbors = adjacency[u] || [];
                for (const v of neighbors) {{
                    if (visited.has(v)) continue;

                    const w = roadWeights[v] || {{}};
                    let length = w.length || 50;

                    if (avoid.has(v)) length *= 2.0;

                    if (theme) {{
                        const score = w[theme] || 0;
                        const maxScore = maxScores[theme] || 1;
                        if (maxScore > 0 && score > 0) {{
                            length *= (1 - 0.3 * Math.min(score / maxScore, 1));
                        }}
                    }}

                    const newDist = d + length;
                    if (dist[v] === undefined || newDist < dist[v]) {{
                        dist[v] = newDist;
                        prev[v] = u;
                        pq.push([newDist, v]);
                    }}
                }}
            }}

            return [];
        }}

        function findTimeBasedLoops(startNodeId, theme, timeMinutes, k = 5) {{
            const startRoads = nodeToRoads[String(startNodeId)] || [];
            if (!startRoads.length) return [];

            const targetDistance = timeMinutes * 75; // 75 m/min
            const halfDistance = targetDistance / 2;

            // 시간 바운더리: 목표 시간의 90% ~ 107% (30분 -> 27~32분)
            const minTime = timeMinutes * 0.9;
            const maxTime = timeMinutes * 1.07;

            const loops = [];
            const usedInitialEdges = new Set();
            let attempts = 0;
            const maxAttempts = k * 5;  // 더 많이 시도해서 바운더리 맞는 것 찾기

            while (loops.length < k && attempts < maxAttempts) {{
                attempts++;

                const [outbound, endRoad] = themeGuidedWalk(
                    startRoads, theme, halfDistance,
                    usedInitialEdges, 0.15 + attempts * 0.05
                );

                if (!outbound.length || !endRoad) continue;

                let inbound = findReturnPath(endRoad, startRoads, new Set(outbound), theme);

                if (!inbound.length) {{
                    inbound = [...outbound].reverse();
                }}

                const loop = [...outbound, ...inbound.slice(1)];
                const stats = calculatePathStats(loop);
                stats.estimatedTime = Math.round(stats.distance / 75);

                // 시간 바운더리 체크
                if (stats.estimatedTime < minTime || stats.estimatedTime > maxTime) {{
                    // 바운더리 밖이면 초기 엣지만 기록하고 다시 시도
                    outbound.slice(0, 2).forEach(e => usedInitialEdges.add(e));
                    continue;
                }}

                // outbound/inbound 분리 저장 (색상 구분용)
                stats.outboundLength = outbound.length;

                loops.push([loop, stats]);

                // Record initial edges for diversity
                outbound.slice(0, Math.max(3, Math.floor(outbound.length / 4))).forEach(e => {{
                    usedInitialEdges.add(e);
                }});
            }}

            // Sort by theme score
            loops.sort((a, b) => (b[1][theme] || 0) - (a[1][theme] || 0));

            return loops;
        }}

        // =====================================================
        // UI FUNCTIONS
        // =====================================================
        function drawPath(path, color, weight = 5, opacity = 0.8) {{
            path.forEach(roadId => {{
                const coord = roadCoords[roadId];
                if (!coord) return;
                L.polyline([[coord.lat1, coord.lng1], [coord.lat2, coord.lng2]], {{
                    color, weight, opacity
                }}).addTo(routeLayer);
            }});
        }}

        // 루프 경로 그리기 (가는길/오는길 색상 구분)
        function drawLoopPath(path, outboundLength, baseColor) {{
            // 가는 길 (진한 색)
            const outbound = path.slice(0, outboundLength);
            outbound.forEach(roadId => {{
                const coord = roadCoords[roadId];
                if (!coord) return;
                L.polyline([[coord.lat1, coord.lng1], [coord.lat2, coord.lng2]], {{
                    color: baseColor,
                    weight: 6,
                    opacity: 0.9
                }}).addTo(routeLayer);
            }});

            // 오는 길 (연한 색 + 대시)
            const inbound = path.slice(outboundLength);
            inbound.forEach(roadId => {{
                const coord = roadCoords[roadId];
                if (!coord) return;
                L.polyline([[coord.lat1, coord.lng1], [coord.lat2, coord.lng2]], {{
                    color: baseColor,
                    weight: 5,
                    opacity: 0.5,
                    dashArray: '10, 8'
                }}).addTo(routeLayer);
            }});
        }}

        function renderPathList(paths, theme, listId, titleId, isLoop = false) {{
            const list = document.getElementById(listId);
            const title = document.getElementById(titleId);
            const container = document.getElementById(listId === 'pathList' ? 'pathResults' : 'exploreResults');

            if (!paths.length) {{
                container.style.display = 'block';
                list.innerHTML = `
                    <div class="no-results">
                        <i class="fas fa-route"></i>
                        <p>경로를 찾을 수 없습니다</p>
                    </div>
                `;
                return;
            }}

            container.style.display = 'block';
            const pathCountText = theme === 'shortest' ? '' : ` - ${{paths.length}}개 경로`;
            title.innerHTML = `<i class="fas fa-${{theme === 'shortest' ? 'location-arrow' : 'list'}}"></i> ${{themeNames[theme] || theme}}${{pathCountText}}`;

            list.innerHTML = paths.map(([path, stats], idx) => `
                <div class="path-item" data-index="${{idx}}" style="--theme-color: ${{themeColors[theme]}}">
                    <div class="path-header">
                        <div class="path-rank">${{idx + 1}}</div>
                        <div class="path-distance">${{formatDistance(stats.distance)}}</div>
                    </div>
                    <div class="path-stats">
                        <div class="path-stat" style="--stat-color: #8B4513">
                            <i class="fas fa-coffee"></i> ${{stats.cafe}}
                        </div>
                        <div class="path-stat" style="--stat-color: #FF6347">
                            <i class="fas fa-utensils"></i> ${{stats.food}}
                        </div>
                        <div class="path-stat" style="--stat-color: #9400D3">
                            <i class="fas fa-moon"></i> ${{stats.nightlife}}
                        </div>
                        <div class="path-stat" style="--stat-color: #FF69B4">
                            <i class="fas fa-shopping-bag"></i> ${{stats.shopping}}
                        </div>
                        <div class="path-stat" style="--stat-color: #228B22">
                            <i class="fas fa-tree"></i> ${{stats.green}}
                        </div>
                        ${{stats.estimatedTime ? `<div class="path-stat"><i class="fas fa-clock"></i> ${{stats.estimatedTime}}분</div>` : ''}}
                    </div>
                </div>
            `).join('');

            // Click handlers
            list.querySelectorAll('.path-item').forEach(item => {{
                item.addEventListener('click', () => {{
                    const idx = parseInt(item.dataset.index);
                    selectPath(paths, idx, theme, isLoop);

                    list.querySelectorAll('.path-item').forEach(i => i.classList.remove('active'));
                    item.classList.add('active');
                }});
            }});

            // Auto-select first
            if (paths.length > 0) {{
                selectPath(paths, 0, theme, isLoop);
                list.querySelector('.path-item').classList.add('active');
            }}
        }}

        function selectPath(paths, index, theme, isLoop = false) {{
            routeLayer.clearLayers();
            const [path, stats] = paths[index];

            // 루프인 경우 가는길/오는길 색상 구분
            if (isLoop && stats.outboundLength) {{
                drawLoopPath(path, stats.outboundLength, themeColors[theme] || '#667eea');
            }} else {{
                drawPath(path, themeColors[theme] || '#667eea', 6, 0.9);
            }}

            // Fit bounds
            const bounds = [];
            path.forEach(roadId => {{
                const coord = roadCoords[roadId];
                if (coord) {{
                    bounds.push([coord.lat1, coord.lng1]);
                    bounds.push([coord.lat2, coord.lng2]);
                }}
            }});
            if (bounds.length > 0) {{
                map.fitBounds(bounds, {{ padding: [50, 50] }});
            }}
        }}

        function clearAll() {{
            startNode = null;
            endNode = null;
            if (startMarker) map.removeLayer(startMarker);
            if (endMarker) map.removeLayer(endMarker);
            startMarker = null;
            endMarker = null;
            routeLayer.clearLayers();
            currentPaths = [];

            document.getElementById('startPoint').textContent = '지도를 클릭하세요';
            document.getElementById('endPoint').textContent = '-';
            document.getElementById('exploreStartPoint').textContent = '지도를 클릭하세요';
            document.getElementById('pathResults').style.display = 'none';
            document.getElementById('exploreResults').style.display = 'none';

            document.querySelectorAll('.theme-btn').forEach(b => b.classList.remove('active'));
        }}

        // =====================================================
        // EVENT HANDLERS
        // =====================================================

        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {{
            tab.addEventListener('click', () => {{
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

                tab.classList.add('active');
                activeTab = tab.dataset.tab;
                document.getElementById(`tab-${{activeTab}}`).classList.add('active');

                clearAll();
            }});
        }});

        // Theme selection (destination)
        document.querySelectorAll('.theme-btn:not(.explore-theme)').forEach(btn => {{
            btn.addEventListener('click', () => {{
                document.querySelectorAll('.theme-btn:not(.explore-theme)').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                currentTheme = btn.dataset.theme;
            }});
        }});

        // Theme selection (explore)
        document.querySelectorAll('.explore-theme').forEach(btn => {{
            btn.addEventListener('click', () => {{
                document.querySelectorAll('.explore-theme').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                exploreTheme = btn.dataset.theme;
            }});
        }});

        // Time input
        document.getElementById('walkTime').addEventListener('input', (e) => {{
            const time = parseInt(e.target.value) || 30;
            document.getElementById('estimatedDistance').textContent = (time * 75 / 1000).toFixed(1);
        }});

        // Map click
        map.on('click', (e) => {{
            const nearest = findNearestNode(e.latlng.lat, e.latlng.lng);
            if (!nearest) return;

            if (activeTab === 'destination') {{
                if (!startNode) {{
                    startNode = nearest;
                    if (startMarker) map.removeLayer(startMarker);
                    startMarker = L.circleMarker([nearest.lat, nearest.lng], {{
                        radius: 10, fillColor: '#4CAF50', color: 'white', weight: 3, fillOpacity: 1
                    }}).addTo(map);
                    document.getElementById('startPoint').textContent = `${{nearest.lat.toFixed(5)}}, ${{nearest.lng.toFixed(5)}}`;
                }} else if (!endNode) {{
                    endNode = nearest;
                    if (endMarker) map.removeLayer(endMarker);
                    endMarker = L.circleMarker([nearest.lat, nearest.lng], {{
                        radius: 10, fillColor: '#f44336', color: 'white', weight: 3, fillOpacity: 1
                    }}).addTo(map);
                    document.getElementById('endPoint').textContent = `${{nearest.lat.toFixed(5)}}, ${{nearest.lng.toFixed(5)}}`;
                }}
            }} else {{
                // Explore mode
                startNode = nearest;
                if (startMarker) map.removeLayer(startMarker);
                startMarker = L.circleMarker([nearest.lat, nearest.lng], {{
                    radius: 10, fillColor: '#4CAF50', color: 'white', weight: 3, fillOpacity: 1
                }}).addTo(map);
                document.getElementById('exploreStartPoint').textContent = `${{nearest.lat.toFixed(5)}}, ${{nearest.lng.toFixed(5)}}`;
            }}
        }});

        // Find paths button
        document.getElementById('btnFindPaths').addEventListener('click', () => {{
            if (!startNode || !endNode) {{
                alert('출발점과 도착점을 모두 선택해주세요');
                return;
            }}

            const paths = findKDiversePaths(startNode.id, endNode.id, currentTheme, 5);
            currentPaths = paths;
            renderPathList(paths, currentTheme, 'pathList', 'resultsTitle');
        }});

        // Explore button
        document.getElementById('btnExplore').addEventListener('click', () => {{
            if (!startNode) {{
                alert('출발점을 선택해주세요');
                return;
            }}

            const time = parseInt(document.getElementById('walkTime').value) || 30;
            const loops = findTimeBasedLoops(startNode.id, exploreTheme, time, 5);
            currentPaths = loops;
            renderPathList(loops, exploreTheme, 'explorePathList', 'exploreResultsTitle', true);  // isLoop=true
        }});

        // Initial theme selection
        document.querySelector('.theme-btn[data-theme="cafe"]').classList.add('active');
        document.querySelector('.explore-theme[data-theme="cafe"]').classList.add('active');

    </script>
</body>
</html>
'''

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n[OK] Saved: {OUTPUT_HTML}")


def main():
    print("=" * 60)
    print(" Step 5 V2: Advanced Route Explorer")
    print("=" * 60)

    # 1. Load data
    L, G = load_data()

    # 2. Prepare data
    data = prepare_data(L, G)

    # 3. Generate HTML
    generate_html(data)

    print("\n" + "=" * 60)
    print(" [OK] Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
