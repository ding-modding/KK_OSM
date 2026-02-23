import osmnx as ox
import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as cx
from shapely.geometry import Point

# ==========================================
# 💡 [필수 추가] API 불안정성 해결을 위한 설정
# ==========================================
ox.settings.use_cache = False       # 한 번 다운로드한 데이터는 로컬에 저장하여 재사용 (속도 향상 및 일관성 확보)
ox.settings.requests_timeout = 180 # 서버 응답 대기 시간을 180초로 늘림 (데이터 누락 방지)

def get_base_area(place, dist=500):
    """중심점으로부터 지정된 반경(m)만큼의 원형 도화지(Base Polygon)를 만듭니다."""
    print("1. 분석할 전체 구역(Base Area)을 생성합니다...")
    
    # 지명으로 중심점 위도/경도 획득
    center_pt = ox.geocode(place)
    
    # 점을 GeoDataFrame으로 변환 (위도, 경도 -> EPSG:4326)
    pt_gdf = gpd.GeoDataFrame(geometry=[Point(center_pt[1], center_pt[0])], crs="EPSG:4326")
    
    # 💡 수정된 부분: GeoPandas 자체 기능을 사용해 해당 지역의 UTM(미터 단위) 좌표계로 투영
    utm_crs = pt_gdf.estimate_utm_crs()
    base_area_proj = pt_gdf.to_crs(utm_crs).buffer(dist)
    
    return center_pt, base_area_proj, utm_crs

def get_barrier_roads(center_pt, utm_crs, dist=600):
    """보행을 가로막는 '차량 전용 도로' 데이터를 가져와 두께(Buffer)를 줍니다."""
    print("2. 보행을 가로막는 차도 데이터를 다운로드합니다...")
    
    # 차가 다니는 길(drive)만 가져오기
    G_roads = ox.graph_from_point(center_pt, dist=dist, network_type='drive')
    
    # 그래프를 GeoDataFrame(점, 선 데이터)으로 변환
    nodes, edges = ox.graph_to_gdfs(G_roads)
    
    # 터널(지하차도) 제외: 보행자는 터널 위 땅으로 걸어 다닐 수 있으므로 장애물이 아님!
    if 'tunnel' in edges.columns:
        edges = edges[~edges['tunnel'].isin(['yes', 'true'])]
        
    print(f"가져온 차도 링크 수: {len(edges)}")
    
    # 💡 수정된 부분: GeoPandas를 이용해 아까 구한 UTM 좌표계로 투영 (미터 단위 계산을 위해)
    edges_proj = edges.to_crs(utm_crs)
    
    # 도로(선) 양옆으로 4m씩(총 폭 8m) 살을 붙여서 면(Polygon)으로 만듦
    # 도로 폭을 더 넓게 잡고 싶다면 이 숫자를 키우면 됨! (예: 6이면 12m 폭)
    road_buffers = edges_proj.buffer(3)
    
    # 여러 개의 도로 면들을 겹치는 부분 없이 하나의 거대한 덩어리로 합침(Union)
    road_barrier_union = road_buffers.union_all()
    
    return road_barrier_union

def create_pedestrian_zones(base_area_proj, road_barrier_union, utm_crs, min_area=500):
    """전체 도화지에서 도로 면적을 파내어(Difference) 보행 섬을 만듭니다."""
    print("3. 전체 구역에서 차도를 도려내어 보행 구역(섬)을 분리합니다...")
    
    # 도화지 면적 - 도로 면적
    zones_geom = base_area_proj.iloc[0].difference(road_barrier_union)
    
    # 결과가 여러 개의 섬(MultiPolygon)으로 쪼개짐, 이를 개별 다각형 리스트로 분리
    if zones_geom.geom_type == 'MultiPolygon':
        polygons = list(zones_geom.geoms)
    else:
        polygons = [zones_geom]
        
    # 너무 작은 자투리 땅(파편) 제거 (예: 500제곱미터 이하 제거)
    valid_polygons = [p for p in polygons if p.area >= min_area]
    
    print(f"쪼개진 전체 보행 구역 수: {len(polygons)}")
    print(f"유효한 크기의 보행 구역 수: {len(valid_polygons)}")
    
    # 다시 위도/경도(EPSG:4326)로 되돌려서 GeoDataFrame 생성
    gdf_proj = gpd.GeoDataFrame(geometry=valid_polygons, crs=utm_crs)
    gdf_wgs84 = gdf_proj.to_crs("EPSG:4326")
    
    # 구역마다 ID 부여
    gdf_wgs84['zone_id'] = range(len(gdf_wgs84))
    
    return gdf_wgs84

def visualize_and_export(gdf, output_filename="pedestrian_zones_polygon.geojson"):
    """결과를 파일로 저장하고 지도에 시각화합니다."""
    print(f"4. 결과를 {output_filename}로 저장하고 시각화합니다...")
    
    # GeoJSON 저장
    gdf.to_file(output_filename, driver="GeoJSON")
    
    # 시각화 (도화지 세팅)
    fig, ax = plt.subplots(figsize=(12, 12))
    
    # 구역별로 다른 색상 칠하기
    gdf.plot(ax=ax, column='zone_id', cmap='Set3', alpha=0.6, edgecolor='black', linewidth=1.5)
    
    # 배경 지도 추가
    cx.add_basemap(ax, crs="EPSG:4326", source=cx.providers.CartoDB.Positron)
    
    plt.title("Pedestrian Zones Separated by Road Barriers", fontsize=16, fontweight='bold')
    plt.axis('off')
    plt.tight_layout()
    plt.show()

def main():
    place = "Hondae, Seoul, South Korea"
    dist = 1500
    
    # 1. 반경 500m 원형 도화지 생성 (utm_crs 좌표계를 반환받아 통일되게 사용)
    center_pt, base_area_proj, utm_crs = get_base_area(place, dist)
    
    # 2. 보행을 막는 차도를 가져와서 면(버퍼)으로 뻥튀기
    road_barrier_union = get_barrier_roads(center_pt, utm_crs, dist=600)
    
    # 3. 도화지에서 차도를 파내어(Difference) 보행 구역 생성
    pedestrian_zones_gdf = create_pedestrian_zones(base_area_proj, road_barrier_union, utm_crs, min_area=500)
    
    # 4. 저장 및 시각화
    visualize_and_export(pedestrian_zones_gdf)

if __name__ == "__main__":
    main()