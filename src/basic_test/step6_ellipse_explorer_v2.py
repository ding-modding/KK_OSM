"""
Step 6 v2: 타원 기반 POI 산점도 탐색기 생성기

이 스크립트는 홍대 지역의 POI 데이터를 로드하고,
타원 기반 경로 탐색 기능이 포함된 HTML 파일을 생성합니다.

v1과의 차이점:
- 줌레벨별 클러스터링 제거 → 모든 줌레벨에서 개별 POI 산점도 표시
- 줌 아웃 시 점 크기가 지도 스케일에 맞춰 축소

사용법:
    python step6_ellipse_explorer_v2.py

출력:
    ellipse_explorer_v2.html
"""
import os
import json
import pickle
import pandas as pd
import math
from collections import defaultdict

# ============================================================
# 설정 (Configuration)
# ============================================================
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SRC_DIR, 'data')
LINEGRAPH_PKL = os.path.join(DATA_DIR, 'hongdae-linegraph.pkl')
ENRICHED_PKL = os.path.join(DATA_DIR, 'hongdae-enriched.pkl')
POI_CSV = os.path.join(DATA_DIR, 'hongdae-poi-classified.csv')
OUTPUT_HTML = os.path.join(SRC_DIR, 'ellipse_explorer_v2.html')

# ============================================================
# 테마 설정
# ============================================================
THEMES = ['cafe', 'food', 'nightlife', 'shopping', 'green']
THEME_INFO = {
    'cafe': {'name': '카페', 'color': '#8B4513', 'icon': 'coffee'},
    'food': {'name': '맛집', 'color': '#FF6347', 'icon': 'utensils'},
    'nightlife': {'name': '유흥', 'color': '#9400D3', 'icon': 'moon'},
    'shopping': {'name': '쇼핑', 'color': '#FF69B4', 'icon': 'shopping-bag'},
    'green': {'name': '녹지', 'color': '#228B22', 'icon': 'tree'},
}


def haversine_distance(lat1, lng1, lat2, lng2):
    """두 좌표 간의 Haversine 거리 (미터)"""
    R = 6371000
    dLat = math.radians(lat2 - lat1)
    dLng = math.radians(lng2 - lng1)
    a = math.sin(dLat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dLng/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def load_data():
    """데이터 로드"""
    print("[1] Loading data...")

    with open(LINEGRAPH_PKL, 'rb') as f:
        L = pickle.load(f)
    print(f"    Line Graph: {L.number_of_nodes():,} nodes, {L.number_of_edges():,} edges")

    with open(ENRICHED_PKL, 'rb') as f:
        G = pickle.load(f)
    print(f"    Original Graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges")

    poi_df = pd.read_csv(POI_CSV)
    print(f"    POIs: {len(poi_df):,}")

    return L, G, poi_df


def prepare_data(L, G, poi_df):
    """시각화용 데이터 준비"""
    print("[2] Preparing data...")

    # 노드 -> 도로 매핑
    node_to_roads = defaultdict(list)
    for node_id in L.nodes():
        data = L.nodes[node_id]
        source = data.get('source')
        target = data.get('target')
        node_to_roads[str(source)].append(node_id)
        node_to_roads[str(target)].append(node_id)

    # 도로 가중치
    road_weights = {}
    for node_id in L.nodes():
        data = L.nodes[node_id]
        road_weights[node_id] = {
            'length': data.get('length', 50) or 50,
        }

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

    # 노드 목록
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

    # POI 데이터 준비
    pois_data = []
    for _, row in poi_df.iterrows():
        try:
            lat = float(row['위도'])
            lng = float(row['경도'])
            if pd.isna(lat) or pd.isna(lng):
                continue

            theme = row.get('primary_theme', 'other')
            name = str(row.get('상호명', ''))[:30]

            if theme in THEMES:
                pois_data.append({
                    'lat': lat,
                    'lng': lng,
                    'theme': theme,
                    'name': name,
                })
        except:
            continue

    # 테마별 개별 POI 데이터 (산점도용)
    pois_by_theme = {}
    for theme in THEMES:
        pois_by_theme[theme] = [
            {'lat': p['lat'], 'lng': p['lng'], 'name': p['name']}
            for p in pois_data if p['theme'] == theme
        ]

    # 중심점
    center_lat = sum(n['lat'] for n in nodes_data) / len(nodes_data) if nodes_data else 37.556
    center_lng = sum(n['lng'] for n in nodes_data) / len(nodes_data) if nodes_data else 126.923

    print(f"    Nodes: {len(nodes_data):,}, Roads: {len(road_coords):,}, POIs: {len(pois_data):,}")
    for theme in THEMES:
        print(f"      {theme}: {len(pois_by_theme[theme]):,}")

    return {
        'road_weights': road_weights,
        'node_to_roads': dict(node_to_roads),
        'road_coords': road_coords,
        'nodes': nodes_data,
        'edges': edges_data,
        'adjacency': dict(adjacency),
        'pois_by_theme': pois_by_theme,
        'center': {'lat': center_lat, 'lng': center_lng},
    }


def generate_html(data):
    """HTML 생성"""
    print("[3] Generating HTML...")

    html = f'''<!DOCTYPE html>
<html>
<head>
    <title>홍대 타원 산점도 탐색기 v2</title>
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

        .sidebar-header h1 {{ font-size: 18px; margin-bottom: 5px; }}
        .sidebar-header p {{ font-size: 12px; opacity: 0.9; }}

        .section {{
            background: #fafafa;
            border-radius: 12px;
            padding: 15px;
            margin: 15px;
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

        .theme-btn:hover {{ border-color: #667eea; transform: translateY(-2px); }}
        .theme-btn.active {{ border-color: var(--theme-color); background: var(--theme-color); color: white; }}
        .theme-btn i {{ font-size: 18px; margin-bottom: 4px; display: block; }}
        .theme-btn span {{ font-size: 11px; font-weight: 500; }}

        .time-slider-container {{ margin-top: 15px; }}
        .time-slider {{ width: 100%; margin: 10px 0; }}
        .time-display {{ text-align: center; font-size: 18px; font-weight: bold; color: #667eea; }}
        .time-hint {{ text-align: center; font-size: 11px; color: #888; }}

        .btn {{
            padding: 12px 20px;
            border: none;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            width: 100%;
            margin-top: 10px;
        }}

        .btn-primary {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }}
        .btn-primary:hover {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgba(102,126,234,0.4); }}
        .btn-secondary {{ background: #f0f0f0; color: #666; }}
        .btn-secondary:hover {{ background: #e0e0e0; }}

        .waypoint-list {{ max-height: 200px; overflow-y: auto; }}
        .waypoint-item {{
            background: white;
            border-radius: 8px;
            padding: 10px 12px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-left: 4px solid #FF9800;
        }}
        .waypoint-info {{ flex: 1; }}
        .waypoint-name {{ font-size: 13px; font-weight: 500; color: #333; }}
        .waypoint-theme {{ font-size: 11px; color: #888; }}
        .waypoint-remove {{ background: none; border: none; color: #999; cursor: pointer; padding: 5px; font-size: 16px; }}
        .waypoint-remove:hover {{ color: #f44336; }}

        .route-info {{ background: white; border-radius: 8px; padding: 12px; margin-top: 10px; }}
        .route-stat {{ display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid #eee; font-size: 13px; }}
        .route-stat:last-child {{ border-bottom: none; }}
        .route-stat .label {{ color: #666; }}
        .route-stat .value {{ font-weight: bold; color: #333; }}

        .instructions {{
            background: linear-gradient(135deg, #e3f2fd 0%, #f3e5f5 100%);
            border-radius: 10px;
            padding: 15px;
            margin: 15px;
            font-size: 12px;
            line-height: 1.8;
            color: #555;
        }}

        .no-waypoints {{ text-align: center; color: #888; font-size: 12px; padding: 20px; }}
    </style>
</head>
<body>
    <div id="map"></div>

    <div class="sidebar">
        <div class="sidebar-header">
            <h1><i class="fas fa-route"></i> 타원 산점도 탐색기 v2</h1>
            <p>테마별 POI를 탐색하고 경유지를 선택하세요</p>
        </div>

        <div class="section">
            <div class="section-title"><i class="fas fa-map-pin"></i> 출발/도착</div>
            <div class="point-box start">
                <div class="point-label">출발점 (클릭)</div>
                <div class="point-value" id="startPoint">지도를 클릭하세요</div>
            </div>
            <div class="point-box end">
                <div class="point-label">도착점 (클릭)</div>
                <div class="point-value" id="endPoint">-</div>
            </div>
        </div>

        <div class="section">
            <div class="section-title"><i class="fas fa-palette"></i> 테마 선택</div>
            <div class="theme-grid">
                <div class="theme-btn active" data-theme="cafe" style="--theme-color: #8B4513">
                    <i class="fas fa-coffee"></i><span>카페</span>
                </div>
                <div class="theme-btn" data-theme="food" style="--theme-color: #FF6347">
                    <i class="fas fa-utensils"></i><span>맛집</span>
                </div>
                <div class="theme-btn" data-theme="nightlife" style="--theme-color: #9400D3">
                    <i class="fas fa-moon"></i><span>유흥</span>
                </div>
                <div class="theme-btn" data-theme="shopping" style="--theme-color: #FF69B4">
                    <i class="fas fa-shopping-bag"></i><span>쇼핑</span>
                </div>
                <div class="theme-btn" data-theme="green" style="--theme-color: #228B22">
                    <i class="fas fa-tree"></i><span>녹지</span>
                </div>
            </div>

            <div class="time-slider-container" id="timeSliderSection" style="display: none;">
                <div class="section-title"><i class="fas fa-clock"></i> 이동 시간 (타원 크기)</div>
                <div id="minDistanceInfo" style="background: #e8f5e9; padding: 8px; border-radius: 6px; margin-bottom: 8px; font-size: 12px; color: #2e7d32;"></div>
                <input type="range" class="time-slider" id="timeSlider" min="10" max="120" value="30" step="5">
                <div class="time-display"><span id="timeValue">30</span>분</div>
                <div class="time-hint">* 약 <span id="distanceValue">2.2</span>km 거리 (도보 기준)</div>
            </div>

            <button class="btn btn-primary" id="btnShowPOIs" style="display: none;">
                <i class="fas fa-search"></i> POI 표시
            </button>
        </div>

        <div class="section">
            <div class="section-title"><i class="fas fa-map-marker-alt"></i> 경유지 목록</div>
            <div class="waypoint-list" id="waypointList">
                <div class="no-waypoints">POI를 클릭하여 경유지를 추가하세요</div>
            </div>
            <button class="btn btn-primary" id="btnFindRoute" style="display: none;">
                <i class="fas fa-route"></i> 경로 생성
            </button>
            <button class="btn btn-secondary" id="btnClearWaypoints" style="display: none;">
                <i class="fas fa-trash"></i> 경유지 초기화
            </button>
        </div>

        <div class="section" id="routeInfoSection" style="display: none;">
            <div class="section-title"><i class="fas fa-info-circle"></i> 경로 정보</div>
            <div class="route-info">
                <div class="route-stat"><span class="label">총 거리</span><span class="value" id="totalDistance">-</span></div>
                <div class="route-stat"><span class="label">예상 시간</span><span class="value" id="estimatedTime">-</span></div>
                <div class="route-stat"><span class="label">경유지 수</span><span class="value" id="waypointCount">-</span></div>
            </div>
        </div>

        <div class="instructions">
            <strong><i class="fas fa-info-circle"></i> 사용법</strong><br>
            1. 지도에서 <b>출발점</b>과 <b>도착점</b>을 클릭<br>
            2. <b>테마</b>와 <b>이동 시간</b>을 선택<br>
            3. <b>POI 표시</b> 버튼 클릭<br>
            4. 원하는 <b>POI를 클릭</b>하여 경유지 추가<br>
            5. <b>경로 생성</b> 버튼으로 최단경로 확인
        </div>

        <div style="padding: 0 15px 15px;">
            <button class="btn btn-secondary" onclick="clearAll()">
                <i class="fas fa-redo"></i> 전체 초기화
            </button>
        </div>
    </div>

    <script>
        // =====================================================
        // DATA
        // =====================================================
        const roadWeights = {json.dumps(data['road_weights'])};
        const nodeToRoads = {json.dumps(data['node_to_roads'])};
        const roadCoords = {json.dumps(data['road_coords'])};
        const nodesData = {json.dumps(data['nodes'])};
        const edgesData = {json.dumps(data['edges'])};
        const adjacency = {json.dumps(data['adjacency'])};
        const poisByTheme = {json.dumps(data['pois_by_theme'])};
        const center = {json.dumps(data['center'])};

        const themeColors = {{ cafe: '#8B4513', food: '#FF6347', nightlife: '#9400D3', shopping: '#FF69B4', green: '#228B22' }};
        const themeNames = {{ cafe: '카페', food: '맛집', nightlife: '유흥', shopping: '쇼핑', green: '녹지' }};

        // =====================================================
        // MAP INITIALIZATION
        // =====================================================
        const map = L.map('map').setView([center.lat, center.lng], 15);
        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '&copy; OpenStreetMap, &copy; CartoDB'
        }}).addTo(map);

        const bgLayer = L.layerGroup().addTo(map);
        edgesData.forEach(e => {{
            L.polyline([[e.lat1, e.lng1], [e.lat2, e.lng2]], {{ color: '#ddd', weight: 1, opacity: 0.6 }}).addTo(bgLayer);
        }});

        const ellipseLayer = L.layerGroup().addTo(map);
        const scatterLayer = L.layerGroup().addTo(map);
        const routeLayer = L.layerGroup().addTo(map);
        const markerLayer = L.layerGroup().addTo(map);

        // =====================================================
        // STATE
        // =====================================================
        let startNode = null, endNode = null, startMarker = null, endMarker = null;
        let currentTheme = 'cafe', walkTime = 30, minWalkTime = 10, shortestDistance = 0;
        let waypoints = [], waypointMarkers = [], currentEllipse = null;

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

        function haversineDistance(lat1, lng1, lat2, lng2) {{
            const R = 6371000;
            const dLat = (lat2 - lat1) * Math.PI / 180;
            const dLng = (lng2 - lng1) * Math.PI / 180;
            const a = Math.sin(dLat/2)**2 + Math.cos(lat1*Math.PI/180)*Math.cos(lat2*Math.PI/180)*Math.sin(dLng/2)**2;
            return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        }}

        // =====================================================
        // SCATTER DOT SIZE (줌 레벨에 따른 점 크기)
        // =====================================================
        function getScatterRadius() {{
            const zoom = map.getZoom();
            return Math.max(1, Math.min(8, (zoom - 10) * 0.75));
        }}

        function getScatterHoverRadius() {{
            return getScatterRadius() + 2;
        }}

        // =====================================================
        // ELLIPSE FUNCTIONS
        // =====================================================
        function calculateEllipseParams(start, end, totalDistance) {{
            const straightDistance = haversineDistance(start.lat, start.lng, end.lat, end.lng);
            let detourRatio = 1.3;
            if (shortestDistance > 0 && straightDistance > 0) {{
                detourRatio = Math.max(1.0, Math.min(shortestDistance / straightDistance, 2.0));
            }}
            const adjustedTotalDistance = totalDistance / detourRatio;
            const a = adjustedTotalDistance / 2;
            const c = straightDistance / 2;
            const aAdjusted = Math.max(a, c * 1.1);
            const b = Math.sqrt(Math.max(aAdjusted**2 - c**2, 0));
            return {{ a: aAdjusted, b, c, centerLat: (start.lat+end.lat)/2, centerLng: (start.lng+end.lng)/2, focalDistance: straightDistance }};
        }}

        function isPOIInEllipse(poi, ellipse, start, end) {{
            const d1 = haversineDistance(poi.lat, poi.lng, start.lat, start.lng);
            const d2 = haversineDistance(poi.lat, poi.lng, end.lat, end.lng);
            const sumDist = d1 + d2;
            const ellipseBoundary = ellipse.a * 2;
            const INNER_MARGIN = 0.6;
            const OUTER_BUFFER = 80;
            const innerLimit = ellipseBoundary * INNER_MARGIN;
            const outerLimit = ellipseBoundary + OUTER_BUFFER;
            return sumDist >= innerLimit && sumDist <= outerLimit;
        }}

        function drawEllipse(start, end, totalDistance) {{
            ellipseLayer.clearLayers();
            const ellipse = calculateEllipseParams(start, end, totalDistance);
            const points = [];
            const dx = end.lng - start.lng, dy = end.lat - start.lat;
            const rotationAngle = Math.atan2(dy, dx);

            for (let i = 0; i <= 100; i++) {{
                const theta = (2 * Math.PI * i) / 100;
                const localX = ellipse.a * Math.cos(theta);
                const localY = ellipse.b * Math.sin(theta);
                const rotatedX = localX * Math.cos(rotationAngle) - localY * Math.sin(rotationAngle);
                const rotatedY = localX * Math.sin(rotationAngle) + localY * Math.cos(rotationAngle);
                const lngOffset = rotatedX / (111320 * Math.cos(ellipse.centerLat * Math.PI / 180));
                const latOffset = rotatedY / 111320;
                points.push([ellipse.centerLat + latOffset, ellipse.centerLng + lngOffset]);
            }}

            L.polyline(points, {{ color: themeColors[currentTheme], weight: 3, opacity: 0.8, dashArray: '10, 5' }}).addTo(ellipseLayer);
            return ellipse;
        }}

        // =====================================================
        // SCATTER PLOT DISPLAY
        // =====================================================
        function showPOIs() {{
            if (!startNode || !endNode) {{ alert('출발점과 도착점을 먼저 선택하세요.'); return; }}
            scatterLayer.clearLayers();
            const totalDistance = walkTime * 75;
            const start = {{ lat: startNode.lat, lng: startNode.lng }};
            const end = {{ lat: endNode.lat, lng: endNode.lng }};
            currentEllipse = drawEllipse(start, end, totalDistance);
            updateScatterDisplay();
        }}

        function updateScatterDisplay() {{
            if (!currentEllipse) return;
            scatterLayer.clearLayers();

            const start = {{ lat: startNode.lat, lng: startNode.lng }};
            const end = {{ lat: endNode.lat, lng: endNode.lng }};
            const themePOIs = poisByTheme[currentTheme] || [];
            const filteredPOIs = themePOIs.filter(poi => isPOIInEllipse(poi, currentEllipse, start, end));
            const radius = getScatterRadius();
            const hoverRadius = getScatterHoverRadius();

            filteredPOIs.forEach(poi => {{
                const marker = L.circleMarker([poi.lat, poi.lng], {{
                    radius: radius,
                    color: themeColors[currentTheme],
                    weight: 2,
                    opacity: 0.9,
                    fillColor: themeColors[currentTheme],
                    fillOpacity: 0.6
                }}).addTo(scatterLayer);

                marker.bindPopup(`<b>${{poi.name}}</b><br>${{themeNames[currentTheme]}}`);
                marker.on('click', e => {{
                    L.DomEvent.stopPropagation(e);
                    addWaypoint({{ lat: poi.lat, lng: poi.lng, name: poi.name }});
                }});
                marker.on('mouseover', function() {{ this.setStyle({{ fillOpacity: 1, radius: hoverRadius }}); }});
                marker.on('mouseout', function() {{ this.setStyle({{ fillOpacity: 0.6, radius: radius }}); }});
            }});

            console.log(`Zoom: ${{map.getZoom()}}, Radius: ${{radius.toFixed(1)}}px, POIs: ${{filteredPOIs.length}}`);

            if (filteredPOIs.length === 0) {{
                alert(`선택한 영역 내에 ${{themeNames[currentTheme]}} POI가 없습니다.\\n이동 시간을 늘리거나 다른 테마를 선택해보세요.`);
            }}
        }}

        // =====================================================
        // WAYPOINT MANAGEMENT
        // =====================================================
        function addWaypoint(poi) {{
            const waypointId = `${{poi.lat.toFixed(5)}}_${{poi.lng.toFixed(5)}}`;
            if (waypoints.some(w => w.id === waypointId)) {{ alert('이미 추가된 경유지입니다.'); return; }}

            waypoints.push({{
                id: waypointId, lat: poi.lat, lng: poi.lng,
                name: poi.name || `${{themeNames[currentTheme]}}`,
                theme: currentTheme
            }});

            const marker = L.marker([poi.lat, poi.lng], {{
                icon: L.divIcon({{
                    className: 'waypoint-marker',
                    html: `<div style="background:#FF9800;color:white;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:14px;box-shadow:0 2px 6px rgba(0,0,0,0.3);border:2px solid white;">${{waypoints.length}}</div>`,
                    iconSize: [28, 28], iconAnchor: [14, 14]
                }})
            }}).addTo(markerLayer);
            waypointMarkers.push(marker);
            updateWaypointUI();
        }}

        function removeWaypoint(index) {{
            waypoints.splice(index, 1);
            if (waypointMarkers[index]) {{ markerLayer.removeLayer(waypointMarkers[index]); waypointMarkers.splice(index, 1); }}
            updateWaypointMarkers();
            updateWaypointUI();
        }}

        function updateWaypointMarkers() {{
            waypointMarkers.forEach(m => markerLayer.removeLayer(m));
            waypointMarkers = [];
            waypoints.forEach((wp, idx) => {{
                const marker = L.marker([wp.lat, wp.lng], {{
                    icon: L.divIcon({{
                        className: 'waypoint-marker',
                        html: `<div style="background:#FF9800;color:white;width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:bold;font-size:14px;box-shadow:0 2px 6px rgba(0,0,0,0.3);border:2px solid white;">${{idx+1}}</div>`,
                        iconSize: [28, 28], iconAnchor: [14, 14]
                    }})
                }}).addTo(markerLayer);
                waypointMarkers.push(marker);
            }});
        }}

        function updateWaypointUI() {{
            const list = document.getElementById('waypointList');
            const btnRoute = document.getElementById('btnFindRoute');
            const btnClear = document.getElementById('btnClearWaypoints');

            if (waypoints.length === 0) {{
                list.innerHTML = '<div class="no-waypoints">POI를 클릭하여 경유지를 추가하세요</div>';
                btnRoute.style.display = 'none';
                btnClear.style.display = 'none';
            }} else {{
                list.innerHTML = waypoints.map((wp, idx) => `
                    <div class="waypoint-item">
                        <div class="waypoint-info">
                            <div class="waypoint-name">${{idx+1}}. ${{wp.name}}</div>
                            <div class="waypoint-theme" style="color:${{themeColors[wp.theme]}}">${{themeNames[wp.theme]}}</div>
                        </div>
                        <button class="waypoint-remove" onclick="removeWaypoint(${{idx}})"><i class="fas fa-times"></i></button>
                    </div>
                `).join('');
                btnRoute.style.display = 'block';
                btnClear.style.display = 'block';
            }}
        }}

        function clearWaypoints() {{
            waypoints = [];
            waypointMarkers.forEach(m => markerLayer.removeLayer(m));
            waypointMarkers = [];
            updateWaypointUI();
            routeLayer.clearLayers();
            document.getElementById('routeInfoSection').style.display = 'none';
        }}

        // =====================================================
        // SHORTEST PATH
        // =====================================================
        function dijkstra(startNodeId, endNodeId) {{
            const startRoads = nodeToRoads[String(startNodeId)] || [];
            const endRoads = nodeToRoads[String(endNodeId)] || [];
            if (!startRoads.length || !endRoads.length) return null;

            const endSet = new Set(endRoads);
            const dist = {{}}, prev = {{}}, visited = new Set(), pq = [];
            startRoads.forEach(road => {{ dist[road] = 0; pq.push([0, road]); }});

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

                (adjacency[u] || []).forEach(v => {{
                    if (visited.has(v)) return;
                    const w = roadWeights[v];
                    if (!w) return;
                    const newDist = d + w.length;
                    if (dist[v] === undefined || newDist < dist[v]) {{
                        dist[v] = newDist;
                        prev[v] = u;
                        pq.push([newDist, v]);
                    }}
                }});
            }}
            return null;
        }}

        function calculateShortestDistance(startNodeId, endNodeId) {{
            const path = dijkstra(startNodeId, endNodeId);
            if (!path) return null;
            return path.reduce((sum, roadId) => sum + (roadWeights[roadId]?.length || 0), 0);
        }}

        function updateTimeSliderMin() {{
            if (!startNode || !endNode) return;
            shortestDistance = calculateShortestDistance(startNode.id, endNode.id);
            if (shortestDistance === null) return;

            minWalkTime = Math.max(Math.ceil(shortestDistance / 75 / 5) * 5, 5);
            const timeSlider = document.getElementById('timeSlider');
            timeSlider.min = minWalkTime;

            if (walkTime < minWalkTime) {{
                walkTime = minWalkTime;
                timeSlider.value = walkTime;
                document.getElementById('timeValue').textContent = walkTime;
                document.getElementById('distanceValue').textContent = (walkTime * 75 / 1000).toFixed(1);
            }}
            document.getElementById('minDistanceInfo').textContent = `최단거리: ${{formatDistance(shortestDistance)}} (${{minWalkTime}}분)`;
        }}

        function findRoute() {{
            if (!startNode || !endNode) {{ alert('출발점과 도착점을 선택하세요.'); return; }}
            routeLayer.clearLayers();

            const waypointNodes = waypoints.map(wp => {{
                const nearestNode = findNearestNode(wp.lat, wp.lng);
                return {{ node: nearestNode, distFromStart: haversineDistance(startNode.lat, startNode.lng, wp.lat, wp.lng) }};
            }}).filter(item => item.node !== null);
            waypointNodes.sort((a, b) => a.distFromStart - b.distFromStart);

            const stops = [startNode, ...waypointNodes.map(item => item.node), endNode];
            let totalDistance = 0;
            const allPaths = [];

            for (let i = 0; i < stops.length - 1; i++) {{
                const path = dijkstra(stops[i].id, stops[i + 1].id);
                if (!path) {{ alert(`${{i + 1}}번째 구간의 경로를 찾을 수 없습니다.`); return; }}
                allPaths.push(path);
                path.forEach(roadId => {{ totalDistance += roadWeights[roadId]?.length || 0; }});
            }}

            allPaths.forEach(path => {{
                path.forEach(roadId => {{
                    const coords = roadCoords[roadId];
                    if (coords) {{
                        L.polyline([[coords.lat1, coords.lng1], [coords.lat2, coords.lng2]], {{ color: '#667eea', weight: 5, opacity: 0.9 }}).addTo(routeLayer);
                    }}
                }});
            }});

            document.getElementById('routeInfoSection').style.display = 'block';
            document.getElementById('totalDistance').textContent = formatDistance(totalDistance);
            document.getElementById('estimatedTime').textContent = Math.round(totalDistance / 75) + '분';
            document.getElementById('waypointCount').textContent = waypoints.length + '개';
        }}

        // =====================================================
        // MAP CLICK HANDLER
        // =====================================================
        map.on('click', function(e) {{
            const nearest = findNearestNode(e.latlng.lat, e.latlng.lng);
            if (!nearest) return;

            if (!startNode) {{
                startNode = nearest;
                if (startMarker) markerLayer.removeLayer(startMarker);
                startMarker = L.marker([nearest.lat, nearest.lng], {{
                    icon: L.divIcon({{ className: 'start-marker', html: '<div style="background:#4CAF50;color:white;width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 6px rgba(0,0,0,0.3);border:2px solid white;"><i class="fas fa-play"></i></div>', iconSize: [32, 32], iconAnchor: [16, 16] }})
                }}).addTo(markerLayer);
                document.getElementById('startPoint').textContent = `${{nearest.lat.toFixed(5)}}, ${{nearest.lng.toFixed(5)}}`;
            }} else if (!endNode) {{
                endNode = nearest;
                if (endMarker) markerLayer.removeLayer(endMarker);
                endMarker = L.marker([nearest.lat, nearest.lng], {{
                    icon: L.divIcon({{ className: 'end-marker', html: '<div style="background:#f44336;color:white;width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;box-shadow:0 2px 6px rgba(0,0,0,0.3);border:2px solid white;"><i class="fas fa-flag-checkered"></i></div>', iconSize: [32, 32], iconAnchor: [16, 16] }})
                }}).addTo(markerLayer);
                document.getElementById('endPoint').textContent = `${{nearest.lat.toFixed(5)}}, ${{nearest.lng.toFixed(5)}}`;
                updateTimeSliderMin();
                document.getElementById('timeSliderSection').style.display = 'block';
                document.getElementById('btnShowPOIs').style.display = 'block';
            }}
        }});

        // =====================================================
        // EVENT LISTENERS
        // =====================================================
        document.querySelectorAll('.theme-btn').forEach(btn => {{
            btn.addEventListener('click', function() {{
                document.querySelectorAll('.theme-btn').forEach(b => b.classList.remove('active'));
                this.classList.add('active');
                currentTheme = this.dataset.theme;
                if (currentEllipse) updateScatterDisplay();
            }});
        }});

        document.getElementById('timeSlider').addEventListener('input', function() {{
            walkTime = parseInt(this.value);
            document.getElementById('timeValue').textContent = walkTime;
            document.getElementById('distanceValue').textContent = (walkTime * 75 / 1000).toFixed(1);
        }});

        document.getElementById('btnShowPOIs').addEventListener('click', showPOIs);
        document.getElementById('btnFindRoute').addEventListener('click', findRoute);
        document.getElementById('btnClearWaypoints').addEventListener('click', clearWaypoints);

        // 줌 변경 시 점 크기 재계산
        map.on('zoomend', function() {{ if (currentEllipse) updateScatterDisplay(); }});

        function clearAll() {{
            startNode = endNode = null;
            if (startMarker) markerLayer.removeLayer(startMarker);
            if (endMarker) markerLayer.removeLayer(endMarker);
            startMarker = endMarker = null;
            clearWaypoints();
            ellipseLayer.clearLayers();
            scatterLayer.clearLayers();
            routeLayer.clearLayers();
            currentEllipse = null;
            minWalkTime = 10;
            shortestDistance = 0;
            walkTime = 30;
            document.getElementById('timeSlider').min = 10;
            document.getElementById('timeSlider').value = 30;
            document.getElementById('timeValue').textContent = '30';
            document.getElementById('distanceValue').textContent = '2.2';
            document.getElementById('timeSliderSection').style.display = 'none';
            document.getElementById('btnShowPOIs').style.display = 'none';
            document.getElementById('startPoint').textContent = '지도를 클릭하세요';
            document.getElementById('endPoint').textContent = '-';
            document.getElementById('routeInfoSection').style.display = 'none';
        }}

        console.log('Ellipse Scatter Explorer v2 initialized');
    </script>
</body>
</html>'''

    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"    [OK] Saved to: {OUTPUT_HTML}")


def main():
    """메인 실행"""
    print("=" * 60)
    print("Step 6 v2: Ellipse Scatter Explorer Generator")
    print("=" * 60)

    L, G, poi_df = load_data()
    data = prepare_data(L, G, poi_df)
    generate_html(data)

    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)


if __name__ == '__main__':
    main()
