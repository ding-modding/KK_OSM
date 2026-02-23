import pickle
import osmnx as ox
import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as cx

def load_graph_from_pkl(filepath):
    """pkl 파일에서 OSM 네트워크 그래프(G)를 불러옵니다."""
    print(f"1. 로컬 파일({filepath})에서 데이터를 불러옵니다...")
    with open(filepath, 'rb') as f:
        G = pickle.load(f)
    print(f"불러오기 완료: 전체 노드 수 {len(G.nodes)}")
    return G

def get_base_area_and_roads(G):
    """불러온 그래프에서 전체 도화지와 두께가 다른 차도 데이터를 추출합니다."""
    print("2. 그래프에서 전체 도화지와 차도 데이터를 추출합니다...")
    
    nodes, edges = ox.graph_to_gdfs(G)
    
    utm_crs = nodes.estimate_utm_crs()
    nodes_proj = nodes.to_crs(utm_crs)
    edges_proj = edges.to_crs(utm_crs)
    
    base_area_geom = nodes_proj.union_all().convex_hull.buffer(50)
    base_area_proj = gpd.GeoSeries([base_area_geom], crs=utm_crs)
    
    buffer_widths = {
        'motorway': 8.0,
        'trunk': 8.0,
        'busway': 2.0,
        'primary': 6.0,
        'secondary': 4.5,
        'tertiary': 3.0,
        'unclassified': 2.0,
        'residential': 1.5
    }
    
    macro_basic = ['motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'busway']
    macro_roads = macro_basic + [f"{road}_link" for road in macro_basic]
    micro_roads = macro_roads + ['unclassified', 'residential', 'living_street', 'service']
    
    def get_barrier_union(target_road_types):
        def is_target(hw):
            if isinstance(hw, list):
                return any(h in target_road_types for h in hw)
            return hw in target_road_types
            
        barrier_edges = edges_proj[edges_proj['highway'].apply(is_target)].copy()
        
        if 'tunnel' in barrier_edges.columns:
            barrier_edges = barrier_edges[~barrier_edges['tunnel'].isin(['yes', 'true'])]
            
        def get_width(hw):
            if isinstance(hw, list):
                return max([buffer_widths.get(h, 2.0) for h in hw])
            return buffer_widths.get(hw, 2.0)
            
        barrier_edges['buffer_width'] = barrier_edges['highway'].apply(get_width)
        buffered_geoms = barrier_edges.geometry.buffer(barrier_edges['buffer_width'])
        
        return buffered_geoms.union_all()

    print("- 매크로(큰 구역) 분리용 도로 추출 및 차등 두께 적용 중...")
    macro_barrier_union = get_barrier_union(macro_roads)
    
    print("- 마이크로(작은 구역) 분리용 도로 추출 및 차등 두께 적용 중...")
    micro_barrier_union = get_barrier_union(micro_roads)
    
    return base_area_proj, macro_barrier_union, micro_barrier_union, utm_crs

def create_hierarchical_zones(base_area_proj, macro_barrier_union, micro_barrier_union, utm_crs, min_area=500):
    """큰 구역과 작은 구역을 각각 만들고, 작은 구역에 큰 구역의 ID를 매핑합니다."""
    print("3. 계층적 보행 구역(큰 구역 & 작은 구역)을 생성하고 매칭합니다...")
    
    def extract_polygons(barrier_union, prefix):
        zones_geom = base_area_proj.iloc[0].difference(barrier_union)
        if zones_geom.geom_type == 'MultiPolygon':
            polygons = list(zones_geom.geoms)
        else:
            polygons = [zones_geom]
            
        valid_polygons = [p for p in polygons if p.area >= min_area]
        gdf = gpd.GeoDataFrame(geometry=valid_polygons, crs=utm_crs)
        gdf[f'{prefix}_id'] = range(len(gdf))
        return gdf

    macro_gdf = extract_polygons(macro_barrier_union, 'macro')
    print(f" - 큰 간선도로로 나뉜 메인 구역 수: {len(macro_gdf)}")

    micro_gdf = extract_polygons(micro_barrier_union, 'micro')
    print(f" - 골목길까지 포함해 잘게 쪼개진 구역 수: {len(micro_gdf)}")

    micro_gdf['rep_point'] = micro_gdf.geometry.representative_point()
    micro_pts = micro_gdf.set_geometry('rep_point')
    
    joined = gpd.sjoin(micro_pts, macro_gdf[['macro_id', 'geometry']], how='left', predicate='within')
    
    micro_gdf['macro_id'] = joined['macro_id']
    micro_gdf = micro_gdf.set_geometry('geometry').drop(columns=['rep_point'])
    
    # 💡 수정된 부분: 마이크로 구역뿐만 아니라 매크로(큰 구역) 폴리곤도 함께 반환
    micro_wgs84 = micro_gdf.to_crs("EPSG:4326")
    macro_wgs84 = macro_gdf.to_crs("EPSG:4326")
    
    return micro_wgs84, macro_wgs84

def visualize_and_export(micro_gdf, macro_gdf, output_filename="hongdae_zones.geojson"):
    print(f"4. 결과를 {output_filename}로 저장하고 시각화합니다...")
    
    # 내보내기는 작은 구역(골목길까지 쪼개진 최종 구역) 기준으로 저장
    micro_gdf.to_file(output_filename, driver="GeoJSON")
    macro_gdf.to_file(output_filename.replace(".geojson", "_macro.geojson"), driver="GeoJSON")
    
    # 지도가 복잡하므로 캔버스를 살짝 더 키움
    fig, ax = plt.subplots(figsize=(15, 15))
    
    # 1. 자식 구역(Micro) 그리기: 내부 색상 채우기 + 얇은 검은색 테두리
    micro_gdf.plot(
        ax=ax, 
        column='micro_id', 
        cmap='tab20',          # 💡 Set3(12색) 대신 tab20(20색)을 써서 색 겹침 확률을 줄임
        alpha=0.55, 
        edgecolor='black', 
        linewidth=0.8
    )
    
    # 2. 💡 부모 구역(Macro) 그리기: 속은 비우고 굵고 눈에 띄는 빨간색 점선 테두리만 덧그림!
    macro_gdf.plot(
        ax=ax,
        facecolor='none',      # 내부 색상 투명하게 (자식 구역 색상이 보이도록)
        edgecolor='#FF3333',   # 눈에 확 띄는 빨간색
        linewidth=2,         # 선 굵기를 아주 두껍게
        linestyle='-'         # 특수선(점선) 처리
    )
    
    cx.add_basemap(ax, crs="EPSG:4326", source=cx.providers.CartoDB.Positron)
    
    plt.title("Pedestrian Zones (Red Dashed Line = Major Roads Boundary)", fontsize=18, fontweight='bold')
    plt.axis('off')
    plt.tight_layout()
    plt.show()

def main():
    filepath = "src/data/hongdae-osm-network.pkl"
    
    G = load_graph_from_pkl(filepath)
    base_area_proj, macro_barrier_union, micro_barrier_union, utm_crs = get_base_area_and_roads(G)
    
    # 💡 두 개의 gdf를 반환받음
    micro_zones_gdf, macro_zones_gdf = create_hierarchical_zones(
        base_area_proj, macro_barrier_union, micro_barrier_union, utm_crs, min_area=500
    )
    
    # 시각화 함수에 두 gdf를 모두 넘겨줌
    visualize_and_export(
        micro_zones_gdf, 
        macro_zones_gdf, 
        output_filename="src/divide_section/data/hongdae_pedestrian_zones.geojson"
    )

if __name__ == "__main__":
    main()