#!/usr/bin/env python3
"""POI 밀도 시각화 (matplotlib 인터랙티브) - 줌 레벨별 자동 전환

줌 레벨에 따라 표시 방식이 자동으로 달라진다:
  ① 축소 (넓은 뷰)  : macro 구역 밀도  - macro_id 라벨 표시
  ② 중간 줌         : micro 구역 밀도  - macro 경계 오버레이 (기존 동작)
  ③ 확대 (좁은 뷰)  : 개별 POI 포인트 표시

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
DATA_DIR         = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
ZONES_FILE       = os.path.join(DATA_DIR, 'hongdae_pedestrian_zones.geojson')
MACRO_ZONES_FILE = os.path.join(DATA_DIR, 'hongdae_pedestrian_zones_macro.geojson')
POI_FILE         = os.path.join(DATA_DIR, 'mapped_poi_results.geojson')

# ── 시각화 상수 ───────────────────────────────────────────────────────────────
BASE_COLOR_RGB = np.array([0.2, 0.53, 1.0])   # #3388FF (파란색)
ALPHA_MIN      = 0.05
ALPHA_MAX      = 1.0
N_SLOTS        = 10                             # 한 페이지 버튼 수

# ── 줌 레벨 임계값 (초기 뷰 너비 대비 비율) ──────────────────────────────────
# 조정 방법: ZOOM_MACRO_RATIO ↑ → 더 많이 축소해야 macro 뷰 진입
#            ZOOM_POINTS_RATIO ↑ → 더 적게 확대해도 포인트 뷰 진입
ZOOM_MACRO_RATIO  = 0.5   # 초기 뷰의 50% 이상 넓이 → macro 밀도
ZOOM_POINTS_RATIO = 0.15   # 초기 뷰의 15% 이하 넓이 → 개별 포인트


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
    utm_crs   = zones_gdf.estimate_utm_crs()
    zones_utm = zones_gdf.to_crs(utm_crs)
    zones_gdf = zones_gdf.copy()
    zones_gdf['area_m2'] = zones_utm.geometry.area.clip(lower=1.0)

    # 카테고리 계층 구축
    print("카테고리 계층 구축 중...")

    large_df = (
        poi_gdf[['large_category_code', 'large_category_name']]
        .drop_duplicates().dropna()
    )
    large_list = sorted(zip(large_df['large_category_code'], large_df['large_category_name']))

    medium_df = (
        poi_gdf[['large_category_code', 'medium_category_code', 'medium_category_name']]
        .drop_duplicates().dropna()
    )
    medium_dict = {}
    for lc, grp in medium_df.groupby('large_category_code'):
        medium_dict[lc] = sorted(zip(grp['medium_category_code'], grp['medium_category_name']))

    small_df = (
        poi_gdf[['medium_category_code', 'small_category_code', 'small_category_name']]
        .drop_duplicates().dropna()
    )
    small_dict = {}
    for mc, grp in small_df.groupby('medium_category_code'):
        small_dict[mc] = sorted(zip(grp['small_category_code'], grp['small_category_name']))

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

def _filter_poi(poi_gdf, selected_large, selected_medium, selected_small):
    """카테고리 필터링."""
    if selected_small is not None:
        return poi_gdf[poi_gdf['small_category_code']  == selected_small]
    elif selected_medium is not None:
        return poi_gdf[poi_gdf['medium_category_code'] == selected_medium]
    elif selected_large is not None:
        return poi_gdf[poi_gdf['large_category_code']  == selected_large]
    else:
        return poi_gdf


def _apply_alpha(result, density_col='density'):
    max_d = result[density_col].max()
    if max_d > 0:
        result['alpha'] = ALPHA_MIN + (result[density_col] / max_d) * (ALPHA_MAX - ALPHA_MIN)
    else:
        result['alpha'] = ALPHA_MIN
    return result


def compute_micro_density(filtered_poi, zones_gdf):
    """micro_id 기준 밀도 계산 → 'alpha' 컬럼 포함 GeoDataFrame."""
    count_series = filtered_poi.groupby('matched_micro_id').size()
    result = zones_gdf.copy()
    result['count']   = result['micro_id'].map(count_series).fillna(0)
    result['density'] = result['count'] / result['area_m2']
    return _apply_alpha(result)


def compute_macro_density(filtered_poi, zones_gdf, macro_gdf):
    """macro_id 기준 밀도 계산 → 'alpha' 컬럼 포함 GeoDataFrame."""
    if 'macro_id' not in macro_gdf.columns:
        result = macro_gdf.copy()
        result['alpha'] = ALPHA_MIN
        return result

    # micro별 count → macro 매핑 → macro별 집계
    count_per_micro = (
        filtered_poi.groupby('matched_micro_id').size()
        .reset_index(name='count')
    )
    count_per_micro.columns = ['micro_id', 'count']

    micro_macro = zones_gdf[['micro_id', 'macro_id']].drop_duplicates()
    merged = count_per_micro.merge(micro_macro, on='micro_id', how='left')
    count_per_macro = merged.groupby('macro_id')['count'].sum()

    result = macro_gdf.copy()
    result['count']   = result['macro_id'].map(count_per_macro).fillna(0)
    result['density'] = result['count'] / result['area_m2']
    return _apply_alpha(result)


# ─────────────────────────────────────────────────────────────────────────────
# 3~5단계: matplotlib 인터랙티브 시각화
# ─────────────────────────────────────────────────────────────────────────────

class POIDensityVisualizer:
    """줌 레벨별 자동 전환 POI 밀도 시각화."""

    _ZOOM_MODE_LABEL = {
        'macro':  '[Macro 구역 밀도]',
        'micro':  '[Micro 구역 밀도]',
        'points': '[POI 포인트]',
    }

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

        # 매크로 경계 로딩 + 면적 계산
        print("매크로 경계 로딩 중...")
        macro_raw = gpd.read_file(MACRO_ZONES_FILE)
        utm_crs   = macro_raw.estimate_utm_crs()
        macro_utm = macro_raw.to_crs(utm_crs)
        self.macro_gdf = macro_raw.copy()
        self.macro_gdf['area_m2'] = macro_utm.geometry.area.clip(lower=1.0)

        # 탐색 상태
        self.state = {
            'level':           'large',
            'selected_large':  None,
            'selected_medium': None,
            'selected_small':  None,
            'page':            0,
        }

        self._slot_cids = [None] * N_SLOTS

        # 렌더링 제어 플래그
        self._first_draw = True
        self._updating   = False   # xlim 콜백 재진입 방지

        # 줌 레벨 임계값 (첫 렌더링 후 초기화)
        self._initial_width    = None
        self._zoom_macro_thr   = None
        self._zoom_points_thr  = None
        self._current_zoom_mode = None

        # 밀도 데이터 캐시
        self._micro_density_gdf = None
        self._macro_density_gdf = None
        self._filtered_poi      = None

        self._setup_figure()
        self._setup_buttons()
        self.refresh_buttons()
        self.update_map()

        # 줌/팬 콜백 연결 (첫 렌더링 완료 후)
        # x축 변경 시
        self.ax_map.callbacks.connect('xlim_changed', self._on_view_changed)

    # ── 레이아웃 ──────────────────────────────────────────────────────────────

    def _setup_figure(self):
        self.fig = plt.figure(figsize=(18, 12))
        self.fig.patch.set_facecolor('#F2F2F2')

        self.ax_map = self.fig.add_axes([0.02, 0.08, 0.70, 0.88])

        self.status_text = self.fig.text(
            0.02, 0.03, '선택: 전체',
            fontsize=12, va='center', color='#222222',
        )
        # 줌 모드 표시 (하단 중앙)
        self.zoom_text = self.fig.text(
            0.40, 0.03, '',
            fontsize=11, va='center', color='#555555',
        )

        self.fig.text(
            0.86, 0.967, '카테고리 선택',
            fontsize=13, fontweight='bold', ha='center', color='#222222',
        )

    def _setup_buttons(self):
        ax_back = self.fig.add_axes([0.74, 0.915, 0.24, 0.048])
        self.btn_back = Button(ax_back, '<- Back', color='#FFCCCC', hovercolor='#FF9999')
        self.btn_back.on_clicked(self._on_back)

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

        ax_prev = self.fig.add_axes([0.74,  0.075, 0.115, 0.048])
        ax_next = self.fig.add_axes([0.865, 0.075, 0.115, 0.048])
        self.btn_prev = Button(ax_prev, '< 이전', color='#E0E0E0', hovercolor='#B0B0B0')
        self.btn_next = Button(ax_next, '다음 >', color='#E0E0E0', hovercolor='#B0B0B0')
        self.btn_prev.on_clicked(self._on_prev)
        self.btn_next.on_clicked(self._on_next)

    # ── 버튼 상태 관리 ────────────────────────────────────────────────────────

    def _get_current_items(self):
        level = self.state['level']
        if level == 'large':
            return self.large_list
        elif level == 'medium':
            return self.medium_dict.get(self.state['selected_large'], [])
        else:
            return self.small_dict.get(self.state['selected_medium'], [])

    def refresh_buttons(self):
        all_items  = self._get_current_items()
        page       = self.state['page']
        start      = page * N_SLOTS
        page_items = all_items[start:start + N_SLOTS]

        for i, (ax, btn) in enumerate(zip(self.slot_axes, self.slot_buttons)):
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
                self._slot_cids[i] = btn.on_clicked(
                    lambda event, idx=i: self._on_category_click(idx)
                )
            else:
                btn.label.set_text('')
                ax.set_visible(False)

        self.btn_prev.ax.set_visible(page > 0)
        self.btn_next.ax.set_visible((page + 1) * N_SLOTS < len(all_items))
        self.btn_back.ax.set_visible(self.state['level'] != 'large')
        self.fig.canvas.draw_idle()

    # ── 이벤트 핸들러 ─────────────────────────────────────────────────────────

    def _on_category_click(self, idx):
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

        else:
            state['selected_small'] = code

        self.refresh_buttons()
        self.update_map()

    def _on_back(self, event):
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

    # ── 줌 레벨 감지 ──────────────────────────────────────────────────────────

    def _get_zoom_mode(self):
        """현재 xlim 너비로 'macro' | 'micro' | 'points' 반환."""
        if self._zoom_macro_thr is None:
            return 'macro'
        width = abs(self.ax_map.get_xlim()[1] - self.ax_map.get_xlim()[0])
        if width >= self._zoom_macro_thr:
            return 'macro'
        elif width <= self._zoom_points_thr:
            return 'points'
        else:
            return 'micro'

    def _on_view_changed(self, ax):
        """xlim 변경 콜백 - zoom mode가 바뀔 때만 재렌더링."""
        print("뷰 변경 감지: ", self._first_draw, self._updating,  end='')
        if self._first_draw or self._updating:
            return
        new_mode = self._get_zoom_mode()
        if new_mode != self._current_zoom_mode:
            self._current_zoom_mode = new_mode
            print(f"줌 모드 전환: {self._ZOOM_MODE_LABEL.get(new_mode, new_mode)}")
            self._redraw_map()

    # ── 지도 갱신 ─────────────────────────────────────────────────────────────

    def _build_status_text(self):
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
        """밀도 재계산 후 지도 다시 그리기 (카테고리 변경 시 호출)."""
        state  = self.state
        status = self._build_status_text()
        print(f"지도 업데이트: {status}")

        # 줌/팬 상태 보존 (첫 렌더링 제외)
        if not self._first_draw:
            saved_xlim = self.ax_map.get_xlim()
            saved_ylim = self.ax_map.get_ylim()

        # 밀도 재계산
        filtered = _filter_poi(
            self.poi_gdf,
            state['selected_large'],
            state['selected_medium'],
            state['selected_small'],
        )
        self._filtered_poi      = filtered
        self._micro_density_gdf = compute_micro_density(filtered, self.zones_gdf)
        self._macro_density_gdf = compute_macro_density(filtered, self.zones_gdf, self.macro_gdf)

        self._current_zoom_mode = self._get_zoom_mode()

        # 렌더링 (xlim 콜백 억제)
        self._updating = True
        self._draw_layers()
        if not self._first_draw:
            self.ax_map.set_xlim(saved_xlim)
            self.ax_map.set_ylim(saved_ylim)
        self._updating = False

        # 첫 렌더링: 초기 뷰 너비로 임계값 설정
        if self._first_draw:
            w = abs(self.ax_map.get_xlim()[1] - self.ax_map.get_xlim()[0])
            self._initial_width   = w
            self._zoom_macro_thr  = w * ZOOM_MACRO_RATIO
            self._zoom_points_thr = w * ZOOM_POINTS_RATIO
            self._current_zoom_mode = self._get_zoom_mode()
            print(
                f"  초기 뷰 너비: {w:.6f}  "
                f"| macro 전환: > {self._zoom_macro_thr:.6f}  "
                f"| points 전환: < {self._zoom_points_thr:.6f}"
            )

        self._first_draw = False
        self.status_text.set_text(status)
        self.zoom_text.set_text(self._ZOOM_MODE_LABEL.get(self._current_zoom_mode, ''))
        self.fig.canvas.draw_idle()

    def _redraw_map(self):
        """줌 모드 전환 시 밀도 재계산 없이 지도만 다시 그리기."""
        if self._micro_density_gdf is None:
            return

        saved_xlim = self.ax_map.get_xlim()
        saved_ylim = self.ax_map.get_ylim()

        self._updating = True
        self._draw_layers()
        self.ax_map.set_xlim(saved_xlim)
        self.ax_map.set_ylim(saved_ylim)
        self._updating = False

        self.zoom_text.set_text(self._ZOOM_MODE_LABEL.get(self._current_zoom_mode, ''))
        self.fig.canvas.draw_idle()

    def _draw_layers(self):
        """현재 zoom mode에 따라 지도 레이어 렌더링."""
        self.ax_map.cla()

        mode = self._current_zoom_mode
        if mode == 'macro':
            self._draw_macro_density()
        elif mode == 'points':
            self._draw_points()
        else:
            self._draw_micro_density()

        # 베이스맵
        try:
            cx.add_basemap(
                self.ax_map,
                crs=self._micro_density_gdf.crs.to_string(),
                source=cx.providers.CartoDB.Positron,
            )
        except Exception as e:
            print(f"  베이스맵 로드 실패: {e}")

        self.ax_map.set_axis_off()
        # 콜백 재연결 (필수!)
        self.ax_map.callbacks.connect('xlim_changed', self._on_view_changed)

    def _draw_macro_density(self):
        """macro_id 기준 밀도 - 구역 색상 + ID 라벨."""
        gdf    = self._macro_density_gdf
        colors = [(*BASE_COLOR_RGB, float(a)) for a in gdf['alpha']]
        gdf.plot(ax=self.ax_map, color=colors, edgecolor='#333333', linewidth=1.5)

        # macro_id 라벨
        '''
        if 'macro_id' in gdf.columns:
            for _, row in gdf.iterrows():
                centroid = row.geometry.centroid
                self.ax_map.annotate(
                    str(int(row['macro_id'])),
                    xy=(centroid.x, centroid.y),
                    ha='center', va='center',
                    fontsize=12, fontweight='bold', color='white',
                    bbox=dict(boxstyle='round,pad=0.3', fc='#222222', alpha=0.55, lw=0),
                )
        '''

    def _draw_micro_density(self):
        """micro_id 기준 밀도 - micro 구역 + macro 경계 오버레이."""
        gdf    = self._micro_density_gdf
        colors = [(*BASE_COLOR_RGB, float(a)) for a in gdf['alpha']]
        gdf.plot(ax=self.ax_map, color=colors, edgecolor='black', linewidth=0.5)

        self.macro_gdf.plot(
            ax=self.ax_map, facecolor='none', edgecolor='red', linewidth=1.0,
        )

    def _draw_points(self):
        """확대 뷰 - 구역 배경(반투명) + macro 경계 + POI 포인트."""
        # 구역 배경 (밀도 비례 반투명)
        micro_gdf = self._micro_density_gdf
        bg_colors = [(*BASE_COLOR_RGB, max(float(a) * 0.35, 0.04)) for a in micro_gdf['alpha']]
        micro_gdf.plot(ax=self.ax_map, color=bg_colors, edgecolor='#888888', linewidth=0.3)

        # macro 경계
        self.macro_gdf.plot(
            ax=self.ax_map, facecolor='none', edgecolor='red', linewidth=1.5,
        )

        # POI 포인트
        if self._filtered_poi is not None and len(self._filtered_poi) > 0:
            try:
                self._filtered_poi.plot(
                    ax=self.ax_map,
                    color='#FF6600',
                    markersize=6,
                    alpha=0.85,
                    zorder=5,
                )
            except Exception as e:
                print(f"  POI 포인트 렌더링 실패: {e}")

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
