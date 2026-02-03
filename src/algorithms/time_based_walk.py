"""
Time-based Walk Algorithm
- 목적지 없이 시간 기반 탐색
- 출발점에서 시작해 테마 방향으로 탐색 후 복귀
- 순환 경로 (루프) 생성
"""
import heapq
import random
from collections import defaultdict


# 평균 보행 속도: 4.5 km/h = 75 m/min
WALK_SPEED_M_PER_MIN = 75


def theme_guided_walk(L, start_roads, theme, target_distance,
                      max_scores, road_weights, avoid_edges=None, randomness=0.3):
    """
    테마 가이드 워크 - 확률적으로 테마 점수 높은 방향 선택

    Args:
        L: Line Graph
        start_roads: 시작 가능한 도로들
        theme: 테마
        target_distance: 목표 거리 (meters)
        max_scores: 테마별 최대 점수
        road_weights: 도로별 가중치
        avoid_edges: 피해야 할 엣지들
        randomness: 랜덤 선택 확률 (0~1)

    Returns:
        path: 탐색 경로
        end_road: 마지막 도로
    """
    if avoid_edges is None:
        avoid_edges = set()

    if not start_roads:
        return [], None

    # 시작 도로 선택 (테마 점수 기반)
    start_scores = []
    for road in start_roads:
        if road in avoid_edges:
            continue
        w = road_weights.get(road, {})
        score = w.get(theme, 0) if theme else 0
        start_scores.append((road, score + 1))

    if not start_scores:
        start_scores = [(r, 1) for r in start_roads[:3]]

    # 가중치 기반 선택
    total = sum(s for _, s in start_scores)
    r = random.random() * total
    cumsum = 0
    current = start_scores[0][0]
    for road, score in start_scores:
        cumsum += score
        if r <= cumsum:
            current = road
            break

    path = [current]
    total_dist = road_weights.get(current, {}).get('length', 0)
    visited = {current}

    while total_dist < target_distance:
        # 인접 도로 가져오기
        neighbors = list(L.successors(current))
        candidates = []

        for road in neighbors:
            if road in visited or road in avoid_edges:
                continue

            w = road_weights.get(road, {})
            length = w.get('length', 50)

            # 남은 거리보다 너무 길면 스킵
            if total_dist + length > target_distance * 1.3:
                continue

            score = w.get(theme, 0) if theme else 0
            candidates.append((road, score + 0.1, length))

        if not candidates:
            # 막다른 길 - 방문했던 곳도 허용
            for road in neighbors:
                if road in avoid_edges:
                    continue
                w = road_weights.get(road, {})
                length = w.get('length', 50)
                score = w.get(theme, 0) if theme else 0
                candidates.append((road, score + 0.1, length))

        if not candidates:
            break

        # 확률적 선택
        if random.random() < randomness:
            # 완전 랜덤
            selected, _, length = random.choice(candidates)
        else:
            # 점수 가중치 기반
            total_score = sum(s for _, s, _ in candidates)
            r = random.random() * total_score
            cumsum = 0
            selected = candidates[0][0]
            length = candidates[0][2]
            for road, score, l in candidates:
                cumsum += score
                if r <= cumsum:
                    selected = road
                    length = l
                    break

        path.append(selected)
        visited.add(selected)
        current = selected
        total_dist += length

    return path, current


def find_return_path(L, start_road, end_roads, max_scores, road_weights,
                     avoid_edges=None, theme=None):
    """
    복귀 경로 찾기 - 피해야 할 엣지 최대한 회피

    Args:
        L: Line Graph
        start_road: 현재 위치 도로
        end_roads: 도착 가능한 도로들
        avoid_edges: 피해야 할 엣지들

    Returns:
        path: 복귀 경로
    """
    if avoid_edges is None:
        avoid_edges = set()

    end_road_set = set(end_roads)
    dist = {start_road: 0}
    prev = {}
    visited = set()
    pq = [(0, start_road)]

    while pq:
        d, u = heapq.heappop(pq)

        if u in visited:
            continue
        visited.add(u)

        if u in end_road_set:
            path = [u]
            curr = u
            while curr in prev:
                curr = prev[curr]
                path.insert(0, curr)
            return path

        for v in L.successors(u):
            if v in visited:
                continue

            w = road_weights.get(v, {})
            length = w.get('length', 50)

            # 피해야 할 엣지에 페널티
            if v in avoid_edges:
                length *= 2.0

            # 테마 보너스 (선택적)
            if theme:
                score = w.get(theme, 0) or 0
                max_score = max_scores.get(theme, 1)
                if max_score > 0 and score > 0:
                    length *= (1 - 0.3 * min(score / max_score, 1))

            new_dist = d + length
            if v not in dist or new_dist < dist[v]:
                dist[v] = new_dist
                prev[v] = u
                heapq.heappush(pq, (new_dist, v))

    return []


def calculate_loop_stats(path, road_weights):
    """루프 경로 통계 계산"""
    stats = {
        'distance': 0,
        'cafe': 0,
        'food': 0,
        'nightlife': 0,
        'shopping': 0,
        'green': 0,
        'edges': len(path) if path else 0,
        'estimated_time': 0,
    }

    if not path:
        return stats

    for road_id in path:
        w = road_weights.get(road_id, {})
        stats['distance'] += w.get('length', 0)
        stats['cafe'] += w.get('cafe', 0)
        stats['food'] += w.get('food', 0)
        stats['nightlife'] += w.get('nightlife', 0)
        stats['shopping'] += w.get('shopping', 0)
        stats['green'] += w.get('green', 0)

    # 예상 시간 (분)
    stats['estimated_time'] = round(stats['distance'] / WALK_SPEED_M_PER_MIN, 1)

    return stats


def find_time_based_loops(L, start_node, theme, time_minutes, k=5,
                          max_scores=None, road_weights=None, node_to_roads=None):
    """
    시간 기반 순환 경로 K개 찾기

    Args:
        L: Line Graph
        start_node: 시작 노드 ID
        theme: 테마
        time_minutes: 산책 시간 (분)
        k: 찾을 경로 수
        max_scores: 테마별 최대 점수
        road_weights: 도로별 가중치
        node_to_roads: 노드 -> 도로 매핑

    Returns:
        List of (path, stats) tuples
    """
    if max_scores is None:
        max_scores = {}
    if road_weights is None:
        road_weights = {}
    if node_to_roads is None:
        node_to_roads = {}

    start_roads = node_to_roads.get(str(start_node), [])
    if not start_roads:
        return []

    # 목표 거리 계산
    target_distance = time_minutes * WALK_SPEED_M_PER_MIN
    half_distance = target_distance / 2

    loops = []
    used_initial_edges = set()

    for i in range(k):
        # Phase 1: 테마 방향 탐색
        # 다양성을 위해 이전 루프 초반부 회피
        avoid = used_initial_edges.copy()

        outbound, end_road = theme_guided_walk(
            L, start_roads, theme, half_distance,
            max_scores, road_weights, avoid,
            randomness=0.2 + i * 0.1  # 점점 더 랜덤하게
        )

        if not outbound or not end_road:
            continue

        # Phase 2: 복귀 경로
        inbound = find_return_path(
            L, end_road, start_roads,
            max_scores, road_weights,
            avoid_edges=set(outbound),
            theme=theme
        )

        if not inbound:
            # 복귀 실패 시 outbound 역순으로 대체
            inbound = list(reversed(outbound))

        # 루프 완성
        loop = outbound + inbound[1:]  # 중복 제거

        stats = calculate_loop_stats(loop, road_weights)
        loops.append((loop, stats))

        # 다양성을 위해 초반 엣지 기록
        for edge in outbound[:max(3, len(outbound) // 4)]:
            used_initial_edges.add(edge)

    # 테마 점수 기준 정렬
    theme_key = theme if theme else 'distance'
    if theme_key == 'distance':
        loops.sort(key=lambda x: x[1]['distance'])
    else:
        loops.sort(key=lambda x: -x[1].get(theme_key, 0))

    return loops
