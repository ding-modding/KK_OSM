#!/usr/bin/env python3
"""POI 밀도 시각화 (matplotlib 인터랙티브)

카테고리를 large → medium → small 순서로 선택하면
해당 카테고리의 POI 밀도에 따라 구역 불투명도(alpha)가 달라지는 지도를 보여준다.

실행: uv run python src/divide_section/step3_visualization/visualization.py
"""

import os
import sys

import numpy as np
import geopandas as gpd
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
import contextily as cx

# Windows 한국어 폰트 설정
matplotlib.rcParams['font.family'] = 'Malgun Gothic'
matplotlib.rcParams['axes.unicode_minus'] = False

# ── 데이터 경로 ──────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
ZONES_FILE       = os.path.join(DATA_DIR, 'hongdae_pedestrian_zones.geojson')
MACRO_ZONES_FILE = os.path.join(DATA_DIR, 'hongdae_pedestrian_zones_macro.geojson')
POI_FILE         = os.path.join(DATA_DIR, 'mapped_poi_results.geojson')

# ── 시각화 상수 ───────────────────────────────────────────────────────────────
BASE_COLOR_RGB = np.array([0.2, 0.53, 1.0])   # #3388FF (파란색)
ALPHA_MIN      = 0.05                           # POI 없는 구역
ALPHA_MAX      = 1                           # 최고 밀도 구역
N_SLOTS        = 10                             # 한 페이지 버튼 수


# ─────────────────────────────────────────────────────────────────────────────
# 1단계: 데이터 로딩 및 전처리
# ─────────────────────────────────────────────────────────────────────────────

def load_data():
    """구역·POI 데이터 로딩, 면적 계산, 카테고리 계층 구축."""
    print("구역 데이터 로딩 중...")
    zones_gdf = gpd.read_file(ZONES_FILE)
    zones_gdf['micro_id'] = zones_gdf['micro_id'].astype(int)
    zones_gdf['macro_id'] = zones_gdf['macro_id'].astype(int)
    print(f"  구역 수: {len(zones_gdf)}")

    print("POI 데이터 로딩 중...")
    poi_gdf = gpd.read_file(POI_FILE)
    poi_gdf = poi_gdf.dropna(subset=['matched_micro_id'])
    poi_gdf['matched_micro_id'] = poi_gdf['matched_micro_id'].astype(int)
    print(f"  POI 수: {len(poi_gdf)}")

    # UTM 투영으로 면적(m²) 계산
    print("면적 계산 중...")
    utm_crs = zones_gdf.estimate_utm_crs()
    zones_utm = zones_gdf.to_crs(utm_crs)
    zones_gdf = zones_gdf.copy()
    zones_gdf['area_m2'] = zones_utm.geometry.area.clip(lower=1.0)

    # 카테고리 계층 구축 (pandas drop_duplicates 활용)
    print("카테고리 계층 구축 중...")

    large_df = (
        poi_gdf[['large_category_code', 'large_category_name']]
        .drop_duplicates()
        .dropna()
    )
    large_list = sorted(
        zip(large_df['large_category_code'], large_df['large_category_name'])
    )

    medium_df = (
        poi_gdf[['large_category_code', 'medium_category_code', 'medium_category_name']]
        .drop_duplicates()
        .dropna()
    )
    medium_dict = {}
    for lc, grp in medium_df.groupby('large_category_code'):
        medium_dict[lc] = sorted(
            zip(grp['medium_category_code'], grp['medium_category_name'])
        )

    small_df = (
        poi_gdf[['medium_category_code', 'small_category_code', 'small_category_name']]
        .drop_duplicates()
        .dropna()
    )
    small_dict = {}
    for mc, grp in small_df.groupby('medium_category_code'):
        small_dict[mc] = sorted(
            zip(grp['small_category_code'], grp['small_category_name'])
        )

    # 평면 이름 조회 맵
    large_name_map  = dict(large_list)
    medium_name_map = dict(zip(medium_df['medium_category_code'], medium_df['medium_category_name']))
    small_name_map  = dict(zip(small_df['small_category_code'],  small_df['small_category_name']))

    print(
        f"  Large: {len(large_list)}개  "
        f"Medium 그룹: {len(medium_dict)}개  "
        f"Small 그룹: {len(small_dict)}개"
    )
    return (
        zones_gdf, poi_gdf,
        large_list, medium_dict, small_dict,
        large_name_map, medium_name_map, small_name_map,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 2단계: 밀도 계산
# ─────────────────────────────────────────────────────────────────────────────

def compute_density(poi_gdf, zones_gdf, selected_large, selected_medium, selected_small):
    """POI 필터링 → 구역별 밀도 계산 → 'alpha' 컬럼 추가한 GeoDataFrame 반환."""
    if selected_small is not None:
        filtered = poi_gdf[poi_gdf['small_category_code']  == selected_small]
    elif selected_medium is not None:
        filtered = poi_gdf[poi_gdf['medium_category_code'] == selected_medium]
    elif selected_large is not None:
        filtered = poi_gdf[poi_gdf['large_category_code']  == selected_large]
    else:
        filtered = poi_gdf

    count_series = filtered.groupby('matched_micro_id').size()

    result = zones_gdf.copy()
    result['count']   = result['micro_id'].map(count_series).fillna(0)
    result['density'] = result['count'] / result['area_m2']

    max_density = result['density'].max()
    if max_density > 0:
        result['alpha'] = ALPHA_MIN + (result['density'] / max_density) * (ALPHA_MAX - ALPHA_MIN)
    else:
        result['alpha'] = ALPHA_MIN

    return result


# ─────────────────────────────────────────────────────────────────────────────
# 3~5단계: matplotlib 인터랙티브 시각화
# ─────────────────────────────────────────────────────────────────────────────

class POIDensityVisualizer:
    """카테고리 선택 → POI 밀도 → 구역 alpha 인터랙티브 지도."""

    def __init__(
        self,
        zones_gdf, poi_gdf,
        large_list, medium_dict, small_dict,
        large_name_map, medium_name_map, small_name_map,
    ):
        self.zones_gdf       = zones_gdf
        self.poi_gdf         = poi_gdf
        self.large_list      = large_list
        self.medium_dict     = medium_dict
        self.small_dict      = small_dict
        self.large_name_map  = large_name_map
        self.medium_name_map = medium_name_map
        self.small_name_map  = small_name_map

        # 매크로 경계 로딩
        print("매크로 경계 로딩 중...")
        self.macro_gdf = gpd.read_file(MACRO_ZONES_FILE)

        # 탐색 상태
        self.state = {
            'level':           'large',
            'selected_large':  None,
            'selected_medium': None,
            'selected_small':  None,
            'page':            0,
        }

        self._slot_cids  = [None] * N_SLOTS   # 버튼 콜백 연결 ID
        self._first_draw = True               # 첫 렌더링 여부 (줌 복원 제어용)

        self._setup_figure()
        self._setup_buttons()
        self.refresh_buttons()
        self.update_map()

    # ── 레이아웃 ──────────────────────────────────────────────────────────────

    def _setup_figure(self):
        self.fig = plt.figure(figsize=(18, 12))
        self.fig.patch.set_facecolor('#F2F2F2')

        # 지도 영역 (왼쪽 70%)
        self.ax_map = self.fig.add_axes([0.02, 0.08, 0.70, 0.88])

        # 하단 상태 표시
        self.status_text = self.fig.text(
            0.02, 0.03, '선택: 전체',
            fontsize=12, va='center', color='#222222',
        )

        # 사이드바 타이틀
        self.fig.text(
            0.86, 0.967, '카테고리 선택',
            fontsize=13, fontweight='bold', ha='center', color='#222222',
        )

    def _setup_buttons(self):
        # Back 버튼 (사이드바 상단)
        ax_back = self.fig.add_axes([0.74, 0.915, 0.24, 0.048])
        self.btn_back = Button(ax_back, '← Back', color='#FFCCCC', hovercolor='#FF9999')
        self.btn_back.on_clicked(self._on_back)

        # 카테고리 슬롯 버튼 (N_SLOTS개)
        self.slot_axes    = []
        self.slot_buttons = []
        for i in range(N_SLOTS):
            y   = 0.852 - i * 0.073
            ax  = self.fig.add_axes([0.74, y, 0.24, 0.062])
            btn = Button(ax, '', color='#DDEEFF', hovercolor='#AACCFF')
            btn.label.set_fontsize(10)
            btn.label.set_wrap(True)
            self.slot_axes.append(ax)
            self.slot_buttons.append(btn)

        # Prev / Next 버튼 (사이드바 하단)
        ax_prev = self.fig.add_axes([0.74,  0.075, 0.115, 0.048])
        ax_next = self.fig.add_axes([0.865, 0.075, 0.115, 0.048])
        self.btn_prev = Button(ax_prev, '◀ 이전', color='#E0E0E0', hovercolor='#B0B0B0')
        self.btn_next = Button(ax_next, '다음 ▶', color='#E0E0E0', hovercolor='#B0B0B0')
        self.btn_prev.on_clicked(self._on_prev)
        self.btn_next.on_clicked(self._on_next)

    # ── 버튼 상태 관리 ────────────────────────────────────────────────────────

    def _get_current_items(self):
        """현재 레벨의 전체 (code, name) 목록 반환."""
        level = self.state['level']
        if level == 'large':
            return self.large_list
        elif level == 'medium':
            return self.medium_dict.get(self.state['selected_large'], [])
        else:  # small
            return self.small_dict.get(self.state['selected_medium'], [])

    def refresh_buttons(self):
        """현재 상태에 맞게 버튼 목록 갱신."""
        all_items  = self._get_current_items()
        page       = self.state['page']
        start      = page * N_SLOTS
        page_items = all_items[start:start + N_SLOTS]

        for i, (ax, btn) in enumerate(zip(self.slot_axes, self.slot_buttons)):
            # 기존 콜백 해제
            if self._slot_cids[i] is not None:
                try:
                    btn.disconnect(self._slot_cids[i])
                except Exception:
                    pass
                self._slot_cids[i] = None

            if i < len(page_items):
                code, name = page_items[i]
                btn.label.set_text(name)
                ax.set_visible(True)
                # 새 콜백 등록 (lambda로 인덱스 고정)
                self._slot_cids[i] = btn.on_clicked(
                    lambda event, idx=i: self._on_category_click(idx)
                )
            else:
                btn.label.set_text('')
                ax.set_visible(False)

        # Prev / Next 가시성
        self.btn_prev.ax.set_visible(page > 0)
        self.btn_next.ax.set_visible((page + 1) * N_SLOTS < len(all_items))

        # Back 가시성 (large 레벨에서는 숨김)
        self.btn_back.ax.set_visible(self.state['level'] != 'large')

        self.fig.canvas.draw_idle()

    # ── 이벤트 핸들러 ─────────────────────────────────────────────────────────

    def _on_category_click(self, idx):
        """슬롯 idx 카테고리 버튼 클릭."""
        all_items  = self._get_current_items()
        page       = self.state['page']
        page_items = all_items[page * N_SLOTS:(page + 1) * N_SLOTS]

        if idx >= len(page_items):
            return

        code, _ = page_items[idx]
        state   = self.state

        if state['level'] == 'large':
            state['selected_large']  = code
            state['selected_medium'] = None
            state['selected_small']  = None
            state['page']            = 0
            if self.medium_dict.get(code):
                state['level'] = 'medium'

        elif state['level'] == 'medium':
            state['selected_medium'] = code
            state['selected_small']  = None
            state['page']            = 0
            if self.small_dict.get(code):
                state['level'] = 'small'

        else:  # small
            state['selected_small'] = code

        self.refresh_buttons()
        self.update_map()

    def _on_back(self, event):
        """상위 레벨로 복귀 (해당 레벨 density 복원)."""
        state = self.state
        if state['level'] == 'small':
            state['selected_small'] = None
            state['level']          = 'medium'
        elif state['level'] == 'medium':
            state['selected_medium'] = None
            state['level']           = 'large'
        state['page'] = 0
        self.refresh_buttons()
        self.update_map()

    def _on_prev(self, event):
        if self.state['page'] > 0:
            self.state['page'] -= 1
            self.refresh_buttons()

    def _on_next(self, event):
        all_items = self._get_current_items()
        if (self.state['page'] + 1) * N_SLOTS < len(all_items):
            self.state['page'] += 1
            self.refresh_buttons()

    # ── 지도 갱신 ─────────────────────────────────────────────────────────────

    def _build_status_text(self):
        """현재 선택 상태를 한 줄 텍스트로 반환."""
        state = self.state
        parts = ['선택:']
        if state['selected_large']:
            parts.append(self.large_name_map.get(state['selected_large'], state['selected_large']))
        if state['selected_medium']:
            parts.append('>')
            parts.append(self.medium_name_map.get(state['selected_medium'], state['selected_medium']))
        if state['selected_small']:
            parts.append('>')
            parts.append(self.small_name_map.get(state['selected_small'], state['selected_small']))
        if len(parts) == 1:
            parts.append('전체')
        return ' '.join(parts)

    def update_map(self):
        """밀도 재계산 후 지도 다시 그리기."""
        state = self.state
        status = self._build_status_text()
        print(f"지도 업데이트: {status}")

        # 첫 렌더링이 아니면 현재 줌/팬 상태 저장
        if not self._first_draw:
            saved_xlim = self.ax_map.get_xlim()
            saved_ylim = self.ax_map.get_ylim()

        density_gdf = compute_density(
            self.poi_gdf, self.zones_gdf,
            state['selected_large'],
            state['selected_medium'],
            state['selected_small'],
        )

        self.ax_map.cla()

        # 구역 플롯: 각 구역에 개별 alpha 적용 (RGBA 리스트)
        colors = [(*BASE_COLOR_RGB, float(a)) for a in density_gdf['alpha']]
        density_gdf.plot(
            ax=self.ax_map,
            color=colors,
            edgecolor='black',
            linewidth=0.5,
        )

        # 매크로 경계 오버레이 (빨간 테두리)
        self.macro_gdf.plot(
            ax=self.ax_map,
            facecolor='none',
            edgecolor='red',
            linewidth=1.0,
        )

        # 베이스맵 (CartoDB Positron)
        try:
            cx.add_basemap(
                self.ax_map,
                crs=density_gdf.crs.to_string(),
                source=cx.providers.CartoDB.Positron,
            )
        except Exception as e:
            print(f"  베이스맵 로드 실패: {e}")

        self.ax_map.set_axis_off()

        # 저장해뒀던 줌/팬 상태 복원 (첫 렌더링은 데이터에 맞게 auto-fit)
        if not self._first_draw:
            self.ax_map.set_xlim(saved_xlim)
            self.ax_map.set_ylim(saved_ylim)
        self._first_draw = False

        self.status_text.set_text(status)
        self.fig.canvas.draw_idle()

    def show(self):
        plt.show()


# ─────────────────────────────────────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────────────────────────────────────

def main():
    (
        zones_gdf, poi_gdf,
        large_list, medium_dict, small_dict,
        large_name_map, medium_name_map, small_name_map,
    ) = load_data()

    viz = POIDensityVisualizer(
        zones_gdf, poi_gdf,
        large_list, medium_dict, small_dict,
        large_name_map, medium_name_map, small_name_map,
    )
    viz.show()


if __name__ == '__main__':
    main()
