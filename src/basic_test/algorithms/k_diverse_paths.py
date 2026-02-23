"""
K-Diverse Paths Algorithm
- 동일 출발/도착점에 대해 K개의 다양한 경로 생성
- Penalty-based diversity: 이전 경로에서 사용된 엣지에 페널티
- Jaccard distance로 다양성 보장
"""
import heapq
from collections import defaultdict


def dijkstra_with_penalty(L, start_roads, end_roads, theme, max_scores, edge_penalties, road_weights):
    """
    페널티가 적용된 Dijkstra 알고리즘

    Args:
        L: Line Graph (networkx)
        start_roads: 시작 노드에 연결된 도로들
        end_roads: 도착 노드에 연결된 도로들
        theme: 테마 (cafe, food, green, etc.)
        max_scores: 테마별 최대 점수
        edge_penalties: 엣지별 페널티 값
        road_weights: 도로별 가중치 데이터

    Returns:
        path: 경로 (도로 ID 리스트) 또는 None
    """
    if not start_roads or not end_roads:
        return None

    end_road_set = set(end_roads)
    dist = {}
    prev = {}
    visited = set()
    pq = []  # (distance, road_id)

    # 시작 도로들 초기화
    for road in start_roads:
        dist[road] = 0
        heapq.heappush(pq, (0, road))

    while pq:
        d, u = heapq.heappop(pq)

        if u in visited:
            continue
        visited.add(u)

        # 도착점 도달
        if u in end_road_set:
            path = [u]
            curr = u
            while curr in prev:
                curr = prev[curr]
                path.insert(0, curr)
            return path

        # 인접 도로 탐색
        for v in L.successors(u):
            if v in visited:
                continue

            w = road_weights.get(v)
            if not w:
                continue

            # 기본 비용: 거리
            length = w.get('length', 50)

            # 테마 가중치 적용
            if theme and theme != 'shortest':
                score_key = theme
                score = w.get(score_key, 0) or 0
                max_score = max_scores.get(score_key, 1)
                normalized = min(score / max_score, 1) if max_score > 0 else 0
                weight = length * (1 - 0.6 * normalized)
            else:
                weight = length

            # 페널티 적용
            penalty = edge_penalties.get(v, 0)
            weight = weight * (1 + penalty)

            new_dist = d + weight
            if v not in dist or new_dist < dist[v]:
                dist[v] = new_dist
                prev[v] = u
                heapq.heappush(pq, (new_dist, v))

    return None


def calculate_jaccard_distance(path1, path2):
    """두 경로 간의 Jaccard distance 계산"""
    if not path1 or not path2:
        return 1.0

    set1 = set(path1)
    set2 = set(path2)

    intersection = len(set1 & set2)
    union = len(set1 | set2)

    if union == 0:
        return 1.0

    return 1 - (intersection / union)


def calculate_path_stats(path, road_weights):
    """경로 통계 계산"""
    stats = {
        'distance': 0,
        'cafe': 0,
        'food': 0,
        'nightlife': 0,
        'shopping': 0,
        'green': 0,
        'edges': len(path) if path else 0,
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

    return stats


def find_k_diverse_paths(L, start_node, end_node, theme, k=5,
                         max_scores=None, road_weights=None, node_to_roads=None,
                         min_diversity=0.25, penalty_factor=0.5):
    """
    K개의 다양한 경로 찾기

    Args:
        L: Line Graph
        start_node: 시작 노드 ID
        end_node: 도착 노드 ID
        theme: 테마
        k: 찾을 경로 수
        max_scores: 테마별 최대 점수
        road_weights: 도로별 가중치
        node_to_roads: 노드 -> 도로 매핑
        min_diversity: 최소 다양성 (Jaccard distance)
        penalty_factor: 페널티 강도

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
    end_roads = node_to_roads.get(str(end_node), [])

    if not start_roads or not end_roads:
        return []

    paths = []
    edge_penalties = defaultdict(float)

    # 최대 시도 횟수
    max_attempts = k * 3
    attempts = 0

    while len(paths) < k and attempts < max_attempts:
        attempts += 1

        # 경로 탐색
        path = dijkstra_with_penalty(
            L, start_roads, end_roads, theme,
            max_scores, edge_penalties, road_weights
        )

        if not path:
            break

        # 다양성 체크
        is_diverse = True
        for existing_path, _ in paths:
            diversity = calculate_jaccard_distance(path, existing_path)
            if diversity < min_diversity:
                is_diverse = False
                break

        if is_diverse:
            stats = calculate_path_stats(path, road_weights)
            paths.append((path, stats))

        # 페널티 업데이트 (사용된 엣지 비용 증가)
        decay = (k - len(paths) + 1) / k  # 점점 감소하는 페널티
        for edge in path:
            edge_penalties[edge] += penalty_factor * decay

    # 테마 점수 기준으로 정렬
    theme_key = theme if theme and theme != 'shortest' else 'distance'
    if theme_key == 'distance':
        paths.sort(key=lambda x: x[1]['distance'])
    else:
        paths.sort(key=lambda x: -x[1].get(theme_key, 0))

    return paths


def find_all_themes_paths(L, start_node, end_node, themes, k=5,
                          max_scores=None, road_weights=None, node_to_roads=None):
    """
    모든 테마에 대해 K개씩 경로 찾기

    Returns:
        Dict[theme -> List[(path, stats)]]
    """
    results = {}

    for theme in themes:
        paths = find_k_diverse_paths(
            L, start_node, end_node, theme, k,
            max_scores, road_weights, node_to_roads
        )
        results[theme] = paths

    return results
