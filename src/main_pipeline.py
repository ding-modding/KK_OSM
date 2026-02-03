"""
OSM + POI 테마 기반 보행 네트워크 파이프라인
- Step 1: OSM 데이터 로드 (도로, 건물, 지리)
- Step 2: POI 테마 분류
- Step 3: Edge 속성 부착 (POI 매핑, 녹지 점수, 보행 점수)
- Step 4: Line Graph 변환
"""
import os
import sys
import time

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_step(step_name, module_name):
    """단일 Step 실행"""
    print(f"\n{'#' * 70}")
    print(f"# {step_name}")
    print(f"{'#' * 70}")

    start_time = time.time()

    try:
        module = __import__(module_name)
        result = module.main()
        elapsed = time.time() - start_time
        print(f"\n[OK] {step_name} completed in {elapsed:.1f}s")
        return result
    except Exception as e:
        print(f"\n[FAIL] {step_name} failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    print("=" * 70)
    print("  OSM + POI 테마 기반 보행 네트워크 파이프라인")
    print("=" * 70)

    total_start = time.time()

    # Step 1: OSM 데이터 로드
    result1 = run_step("Step 1: OSM 데이터 로드", "step1_osm_loader")
    if result1 is None:
        print("\nPipeline failed at Step 1")
        return

    # Step 2: POI 테마 분류
    result2 = run_step("Step 2: POI 테마 분류", "step2_poi_classifier")
    if result2 is None:
        print("\nPipeline failed at Step 2")
        return

    # Step 3: Feature Enrichment
    result3 = run_step("Step 3: Feature Enrichment", "step3_feature_enricher")
    if result3 is None:
        print("\nPipeline failed at Step 3")
        return

    # Step 4: Line Graph 변환
    result4 = run_step("Step 4: Line Graph 변환", "step4_linegraph_builder")
    if result4 is None:
        print("\nPipeline failed at Step 4")
        return

    total_elapsed = time.time() - total_start

    print("\n" + "=" * 70)
    print("  Pipeline Complete!")
    print("=" * 70)
    print(f"\n  Total time: {total_elapsed:.1f}s")
    print("\n  Output files:")
    print("  - data/hongdae-osm-network.pkl    (원본 보행 네트워크)")
    print("  - data/hongdae-geo-features.pkl   (지리 데이터)")
    print("  - data/hongdae-poi-classified.csv (분류된 POI)")
    print("  - data/hongdae-enriched.pkl       (속성 추가된 그래프)")
    print("  - data/hongdae-linegraph.pkl      (Line Graph)")


if __name__ == "__main__":
    main()
