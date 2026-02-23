import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt
import contextily as cx
import geopandas as gpd
from shapely.geometry import MultiPoint

def download_osm_network(place: str, dist: int) -> nx.MultiDiGraph:
    """OSM 보행자 네트워크 데이터를 다운로드합니다. (고속/간선 차도만 제외, 골목길 포함)"""
    print("1. OSM 도보 네트워크 데이터를 다운로드합니다...")
    
    ox.settings.useful_tags_node += ['highway', 'crossing']
    ox.settings.useful_tags_way += ['highway', 'footway', 'crossing', 'bridge', 'tunnel']
    
    G = ox.graph_from_address(
        place, 
        dist=dist, 
        network_type='walk',
        simplify=False
    )
    
    print(f"다운로드 완료: 원래 노드 수 {len(G.nodes)}")
    
    return G

def remove_crosswalk_edges(G: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """네트워크에서 횡단보도 및 입체 교차(육교, 지하도, 계단 등) 노드와 엣지를 꼼꼼하게 식별하고 제거합니다."""
    print("2. 횡단보도 및 입체 교차 구조물 링크(Edge)를 탐색하고 제거합니다...")
    
    crossing_nodes = set()
    structure_nodes = set()

    # [강화됨] 노드(Node) 레벨에서의 필터링
    for n, data in G.nodes(data=True):
        hw = str(data.get('highway', ''))
        cr = str(data.get('crossing', ''))
        
        # 1. 노드 자체가 횡단보도인 경우
        # highway=crossing이 없더라도 crossing=* 태그가 존재할 수 있음
        if hw == 'crossing' or (cr != '' and cr not in ['None', 'no']):
            crossing_nodes.add(n)
            
        # 2. 노드 자체가 입체 교차/단절 지점(엘리베이터 등)인 경우
        if hw == 'elevator':
            structure_nodes.add(n)

    print(f"탐지된 횡단보도 노드 수: {len(crossing_nodes)}")
    print(f"탐지된 수직 구조물(엘리베이터 등) 노드 수: {len(structure_nodes)}")

    edges_to_remove = []
    count_crossing_edges = 0
    count_structural_edges = 0
    
    # [강화됨] 엣지(Edge) 레벨에서의 필터링
    for u, v, key, data in G.edges(keys=True, data=True):
        hw = str(data.get('highway', ''))
        fw = str(data.get('footway', ''))
        cr = str(data.get('crossing', '')) 
        br = str(data.get('bridge', ''))
        tn = str(data.get('tunnel', ''))
        cv = str(data.get('conveying', '')) # 에스컬레이터/무빙워크 태그 추가

        # 1. 횡단보도 조건 검사 (엣지 자체 속성)
        is_crossing = any([
            'crossing' in hw,
            'crossing' in fw,
            cr != '' and cr not in ['None', 'no']
        ])
        
        # 엣지의 양끝 노드 중 하나라도 횡단보도 노드라면 해당 엣지도 횡단보도로 간주
        if u in crossing_nodes or v in crossing_nodes:
            is_crossing = True
            
        if is_crossing:
            count_crossing_edges += 1

        # 2. 입체 교차 및 단절 구간 조건 검사 (엣지 자체 속성)
        is_structure = any([
            br != '' and br not in ['None', 'no'],
            tn != '' and tn not in ['None', 'no'],
            'steps' in hw,
            'elevator' in hw,
            cv != '' and cv not in ['None', 'no'] # 에스컬레이터 추가
        ])
        
        # 엣지의 양끝 노드 중 하나라도 수직 구조물 노드라면 단절 엣지로 간주
        if u in structure_nodes or v in structure_nodes:
            is_structure = True
            
        if is_structure:
            count_structural_edges += 1
        
        # 횡단보도이거나 입체 교차 구조물이면 제거 대상 리스트에 추가
        if is_crossing or is_structure:
            edges_to_remove.append((u, v, key))

    # 리스트 중복 제거 (하나의 엣지가 횡단보도이면서 구조물 조건을 모두 만족할 경우 대비)
    edges_to_remove = list(set(edges_to_remove))

    G_separated = G.copy()
    G_separated.remove_edges_from(edges_to_remove)
    
    print(f"제거된 최종 엣지(링크) 수: {len(edges_to_remove)}")
    print(f" - 횡단보도 관련 감지(중복 포함): {count_crossing_edges}")
    print(f" - 육교/지하도/계단 관련 감지(중복 포함): {count_structural_edges}")
    
    return G_separated

def get_connected_zones(G_separated: nx.MultiDiGraph, min_nodes=5) -> gpd.GeoDataFrame | None:
    """분리된 그래프에서 유효한 크기의 연결 요소(도보 구역)를 추출합니다."""
    print("3. 연결된 도보 구역(Connected Components)을 추출합니다...")
    
    G_undirected = G_separated.to_undirected()
    connected_components = list(nx.connected_components(G_undirected))
    
    valid_components = [c for c in connected_components if len(c) >= min_nodes]
    
    print(f"분리된 전체 도보 구역 수: {len(connected_components)}")
    print(f"유효한 도보 구역(노드 {min_nodes}개 이상) 수: {len(valid_components)}")
    
    return G_undirected, valid_components

def create_and_export_polygons(G, components, output_filename="pedestrian_zones.geojson"):
    """각 도보 구역의 노드 좌표를 기반으로 폴리곤을 생성하고 GeoDataFrame을 반환합니다."""
    print(f"4. 구역 데이터를 폴리곤으로 변환하여 {output_filename}에 저장합니다...")
    
    polygons = []
    
    for i, component in enumerate(components):
        points = [(G.nodes[node]['x'], G.nodes[node]['y']) for node in component]
        
        if len(points) >= 3:
            poly = MultiPoint(points).convex_hull
            if poly.geom_type == 'Polygon':
                polygons.append({
                    'zone_id': i,
                    'node_count': len(component),
                    'geometry': poly
                })
                
    if polygons:
        gdf = gpd.GeoDataFrame(polygons, crs="EPSG:4326")
        gdf.to_file(output_filename, driver="GeoJSON")
        print(f"저장 완료: 총 {len(gdf)}개의 폴리곤이 생성되었습니다.")
        return gdf  # 시각화를 위해 반환
    else:
        print("폴리곤으로 변환할 수 있는 유효한 구역이 없습니다.")
        return None

def visualize_network_with_polygons(G: nx.MultiDiGraph, components, gdf=None):
    """도보 구역과 폴리곤 결과를 배경 지도와 함께 시각화합니다."""
    print("5. 결과를 시각화합니다...")
    
    # 캔버스(Figure)와 축(Axes)을 먼저 생성해서 모든 그림을 이 위에 겹치도록 설정
    fig, ax = plt.subplots(figsize=(12, 12))
    
    # 1. 폴리곤 시각화 (GeoDataFrame이 있는 경우)
    if gdf is not None and not gdf.empty:
        # column을 'zone_id'로 주어 구역마다 색을 다르게 지정하고, alpha로 투명도 설정
        gdf.plot(ax=ax, column='zone_id', cmap='tab20', alpha=0.35, edgecolor='black', linewidth=0.8)

    # 2. 노드 및 엣지(네트워크 선) 색상 설정
    node_colors = {}
    colors = plt.colormaps.get_cmap('tab20')
    
    for i, component in enumerate(components):
        for node in component:
            node_colors[node] = colors(i % 20)

    nc = [node_colors.get(node, (0.8, 0.8, 0.8, 0.5)) for node in G.nodes()]

    # ax=ax 파라미터를 통해 미리 만들어둔 캔버스 위에 네트워크를 겹쳐서 그림
    ox.plot_graph(
        G,
        ax=ax,
        node_color=nc,
        node_size=8,
        edge_color="#555555",
        edge_linewidth=1.2,
        show=False,
        close=False,
        bgcolor="none"
    )
    
    # 3. 배경 지도 깔기
    cx.add_basemap(ax, crs="EPSG:4326", source=cx.providers.CartoDB.Positron)
    
    plt.title("Pedestrian Zones & Polygons Separated by Crosswalks", fontsize=16, fontweight='bold', color="black")
    
    # 여백 조절 후 출력
    plt.tight_layout()
    plt.show()

def main():
    place = "KAIST, Daejeon, South Korea"
    dist = 1000
    
    G = download_osm_network(place, dist)
    G_separated = remove_crosswalk_edges(G)
    G_undirected, valid_components = get_connected_zones(G_separated, min_nodes=5)
    
    # 함수에서 GeoDataFrame(gdf)을 리턴 받음
    gdf = create_and_export_polygons(G_undirected, valid_components, output_filename="src/divide_section/pedestrian_zones.geojson")
    
    # 리턴 받은 gdf를 시각화 함수에 넘겨줌
    visualize_network_with_polygons(G_undirected, valid_components, gdf)

if __name__ == "__main__":
    main()