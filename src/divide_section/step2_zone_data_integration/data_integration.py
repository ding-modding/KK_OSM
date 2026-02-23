import pandas as pd
import geopandas as gpd

ZONE_PATH = "C:\\WEBD\\KK_OSM\\src\\divide_section\\data\\hongdae_pedestrian_zones.geojson"
POI_PATH = "C:\\WEBD\\KK_OSM\\src\\divide_section\\data\\POI_data.csv"
OUTPUT_PATH = "C:\\WEBD\\KK_OSM\\src\\divide_section\\data\\mapped_poi_results.csv"

def main():
    # 1. GeoJSON 폴리곤 데이터 로드
    polygons_gdf = gpd.read_file(ZONE_PATH)

    # 2. POI CSV 데이터 로드
    # 첫 행이 헤더이므로 header=None과 names 옵션을 제거하여 자동 인식하도록 합니다.
    poi_df = pd.read_csv(POI_PATH)

    # 결측치 제거 (실제 컬럼명인 '경도', '위도' 사용)
    poi_df = poi_df.dropna(subset=["경도", "위도"])
    
    # 지오메트리 객체 생성
    geometry = gpd.points_from_xy(poi_df['경도'], poi_df['위도'])
    poi_gdf = gpd.GeoDataFrame(poi_df, geometry=geometry)
    
    # 좌표계 설정 (WGS84, EPSG:4326)
    poi_gdf.set_crs(epsg=4326, inplace=True) 
    polygons_gdf.set_crs(epsg=4326, inplace=True, allow_override=True)

    # 3. 공간 조인 (Spatial Join) 수행
    # sjoin 내부적으로 R-Tree(STRtree) 기반의 인덱싱을 사용하여 초고속으로 매핑합니다.
    mapped_gdf = gpd.sjoin(poi_gdf, polygons_gdf, how="inner", predicate="within")

    # GeoJSON으로 저장하기 위해 GeoDataFrame 유지
    result_gdf = mapped_gdf[['상호명',"상권업종대분류코드","상권업종대분류명","상권업종중분류코드","상권업종중분류명","상권업종소분류코드","상권업종소분류명", 'micro_id', 'geometry']]
    result_gdf.columns = ['store_name', 'large_category_code', 'large_category_name', 'medium_category_code', 'medium_category_name', 'small_category_code', 'small_category_name', 'matched_micro_id', 'geometry']
    
    result_gdf = result_gdf.sort_values(by='small_category_code', ascending=True).reset_index(drop=True)
    
    # GeoJSON으로 내보내기
    output_geojson_path = "C:\\WEBD\\KK_OSM\\src\\divide_section\\data\\mapped_poi_results.geojson"
    result_gdf.to_file(output_geojson_path, driver="GeoJSON", encoding='utf-8')
    print(f"\nGeoJSON으로 성공적으로 저장되었습니다: {output_geojson_path}")
    
if __name__ == "__main__":
    main()