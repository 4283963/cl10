import heapq
from collections import defaultdict
from datetime import datetime, timedelta

from config import Config
from models import PipeNode, PipeConnection, GasReading, db


COMPROMISE_CONFIG = {
    'MAX_WALKING_TIME_MINUTES': 10,
    'WALKING_SPEED_M_PER_MIN': 60,
    'DANGER_NODE_PENALTY': 1000.0,
    'WARNING_NODE_PENALTY': 50.0,
    'H2S_WEIGHT': 1.0,
    'CH4_WEIGHT': 2.0,
    'DISTANCE_WEIGHT': 0.1,
}


def get_latest_gas_readings():
    subquery = db.session.query(
        GasReading.node_id,
        db.func.max(GasReading.recorded_at).label('max_time')
    ).group_by(GasReading.node_id).subquery()

    readings = db.session.query(GasReading).join(
        subquery,
        db.and_(
            GasReading.node_id == subquery.c.node_id,
            GasReading.recorded_at == subquery.c.max_time
        )
    ).all()

    result = {}
    for r in readings:
        result[r.node_id] = {
            'h2s': r.h2s_concentration,
            'ch4': r.ch4_concentration,
            'recorded_at': r.recorded_at
        }
    return result


def is_node_safe(gas_data):
    if not gas_data:
        return True
    h2s = gas_data.get('h2s', 0.0) or 0.0
    ch4 = gas_data.get('ch4', 0.0) or 0.0
    if h2s >= Config.H2S_THRESHOLD:
        return False
    if ch4 >= Config.CH4_THRESHOLD:
        return False
    return True


def calculate_node_risk(gas_data):
    if not gas_data:
        return 0.0
    h2s = gas_data.get('h2s', 0.0) or 0.0
    ch4 = gas_data.get('ch4', 0.0) or 0.0
    h2s_risk = h2s / Config.H2S_THRESHOLD if Config.H2S_THRESHOLD > 0 else 0
    ch4_risk = ch4 / Config.CH4_THRESHOLD if Config.CH4_THRESHOLD > 0 else 0
    return h2s_risk + ch4_risk


def build_graph():
    nodes = PipeNode.query.all()
    connections = PipeConnection.query.all()

    graph = defaultdict(list)
    node_map = {node.id: node for node in nodes}

    for conn in connections:
        graph[conn.from_node_id].append((conn.to_node_id, conn.distance))
        graph[conn.to_node_id].append((conn.from_node_id, conn.distance))

    return graph, node_map


def dijkstra_safe_route(start_id, end_id):
    try:
        graph, node_map = build_graph()
    except Exception as e:
        return {
            'success': False,
            'error': f'加载管网拓扑数据失败: {str(e)}'
        }

    if start_id not in node_map:
        return {'success': False, 'error': f'起点 {start_id} 不存在'}
    if end_id not in node_map:
        return {'success': False, 'error': f'终点 {end_id} 不存在'}

    try:
        gas_readings = get_latest_gas_readings()
    except Exception as e:
        return {
            'success': False,
            'error': f'读取气体浓度数据失败: {str(e)}'
        }

    start_gas = gas_readings.get(start_id)
    end_gas = gas_readings.get(end_id)
    start_risk = calculate_node_risk(start_gas)

    if not is_node_safe(start_gas):
        h2s_val = start_gas.get('h2s', '?') if start_gas else '?'
        ch4_val = start_gas.get('ch4', '?') if start_gas else '?'
        return {
            'success': False,
            'error': (
                f'起点 {start_id}({node_map[start_id].name}) 气体浓度超标 '
                f'(H₂S={h2s_val}/≥{Config.H2S_THRESHOLD} ppm, '
                f'CH₄={ch4_val}/≥{Config.CH4_THRESHOLD} %LEL)，暂时无法出发。'
                f'请等待通风或改选其他井口。'
            ),
            'blocked_nodes': [start_id]
        }
    if not is_node_safe(end_gas):
        h2s_val = end_gas.get('h2s', '?') if end_gas else '?'
        ch4_val = end_gas.get('ch4', '?') if end_gas else '?'
        return {
            'success': False,
            'error': (
                f'终点 {end_id}({node_map[end_id].name}) 气体浓度超标 '
                f'(H₂S={h2s_val}/≥{Config.H2S_THRESHOLD} ppm, '
                f'CH₄={ch4_val}/≥{Config.CH4_THRESHOLD} %LEL)，暂时无法到达。'
                f'请等待通风或改选其他井口。'
            ),
            'blocked_nodes': [end_id]
        }

    all_safe_nodes = set()
    all_blocked_nodes = []
    for nid, node in node_map.items():
        g = gas_readings.get(nid)
        if is_node_safe(g):
            all_safe_nodes.add(nid)
        else:
            all_blocked_nodes.append({
                'id': nid,
                'name': node.name,
                'h2s': g.get('h2s', 0) if g else 0,
                'ch4': g.get('ch4', 0) if g else 0
            })

    pq = [(start_risk, 0, start_id, [start_id])]
    visited = {}

    while pq:
        total_risk, total_dist, current, path = heapq.heappop(pq)

        if current in visited:
            if visited[current] <= total_risk:
                continue
        visited[current] = total_risk

        if current == end_id:
            node_details = []
            unsafe_nodes = []
            total_h2s = 0.0
            total_ch4 = 0.0

            for nid in path:
                gas = gas_readings.get(nid)
                node = node_map[nid]
                detail = {
                    'id': nid,
                    'name': node.name,
                    'node_type': node.node_type,
                    'x': node.x,
                    'y': node.y
                }
                if gas:
                    detail['h2s'] = gas.get('h2s', 0.0)
                    detail['ch4'] = gas.get('ch4', 0.0)
                    recorded = gas.get('recorded_at')
                    detail['recorded_at'] = recorded.isoformat() if recorded and hasattr(recorded, 'isoformat') else (recorded if recorded else None)
                    total_h2s += gas.get('h2s', 0.0)
                    total_ch4 += gas.get('ch4', 0.0)
                    if not is_node_safe(gas):
                        unsafe_nodes.append(nid)
                else:
                    detail['h2s'] = 0.0
                    detail['ch4'] = 0.0
                node_details.append(detail)

            edges = []
            for i in range(len(path) - 1):
                edges.append({
                    'from': path[i],
                    'to': path[i + 1]
                })

            avg_h2s = total_h2s / len(path) if path else 0
            avg_ch4 = total_ch4 / len(path) if path else 0

            return {
                'success': True,
                'path': path,
                'nodes': node_details,
                'edges': edges,
                'total_distance': round(total_dist, 2),
                'total_risk_score': round(total_risk, 4),
                'avg_h2s': round(avg_h2s, 4),
                'avg_ch4': round(avg_ch4, 4),
                'unsafe_nodes': unsafe_nodes
            }

        for neighbor, distance in graph[current]:
            if neighbor not in node_map:
                continue
            if neighbor not in all_safe_nodes:
                continue
            if neighbor in visited:
                continue
            neighbor_gas = gas_readings.get(neighbor)
            neighbor_risk = calculate_node_risk(neighbor_gas)
            new_risk = total_risk + neighbor_risk + (distance / 1000.0)
            new_dist = total_dist + distance
            new_path = path + [neighbor]
            heapq.heappush(pq, (new_risk, new_dist, neighbor, new_path))

    blocked_names = '、'.join(
        f'{b["name"]}({b["id"]})[H₂S={b["h2s"]},CH₄={b["ch4"]}]'
        for b in all_blocked_nodes
    ) or '无'

    return {
        'success': False,
        'error': (
            f'雨季管网大面积超标，从 {node_map[start_id].name} 到 {node_map[end_id].name} '
            f'暂时没有可通行的安全路线。所有中间路径均被超标节点阻断。'
            f'建议：(1) 启动强制通风系统；(2) 绕行地面路段；(3) 等待 30 分钟后重试。'
        ),
        'blocked_nodes': all_blocked_nodes,
        'blocked_summary': blocked_names,
        'safe_node_count': len(all_safe_nodes),
        'total_node_count': len(node_map)
    }


def calculate_compromise_cost(gas_data, distance, node_type='junction'):
    cfg = COMPROMISE_CONFIG
    h2s = gas_data.get('h2s', 0.0) or 0.0
    ch4 = gas_data.get('ch4', 0.0) or 0.0

    gas_cost = (h2s * cfg['H2S_WEIGHT']) + (ch4 * cfg['CH4_WEIGHT'])
    dist_cost = distance * cfg['DISTANCE_WEIGHT']

    if not is_node_safe(gas_data):
        penalty = cfg['DANGER_NODE_PENALTY']
    elif calculate_node_risk(gas_data) > 0.5:
        penalty = cfg['WARNING_NODE_PENALTY']
    else:
        penalty = 0.0

    if node_type == 'wellhead':
        penalty *= 0.5

    return gas_cost + dist_cost + penalty


def dijkstra_compromise_route(start_id, end_id):
    try:
        graph, node_map = build_graph()
    except Exception as e:
        return {
            'success': False,
            'error': f'加载管网拓扑数据失败: {str(e)}'
        }

    if start_id not in node_map:
        return {'success': False, 'error': f'起点 {start_id} 不存在'}
    if end_id not in node_map:
        return {'success': False, 'error': f'终点 {end_id} 不存在'}

    try:
        gas_readings = get_latest_gas_readings()
    except Exception as e:
        return {
            'success': False,
            'error': f'读取气体浓度数据失败: {str(e)}'
        }

    cfg = COMPROMISE_CONFIG
    max_distance = cfg['MAX_WALKING_TIME_MINUTES'] * cfg['WALKING_SPEED_M_PER_MIN']

    start_gas = gas_readings.get(start_id, {})
    start_node = node_map[start_id]
    initial_cost = calculate_compromise_cost(start_gas, 0, start_node.node_type)

    pq = [(initial_cost, 0, 0.0, 0.0, start_id, [start_id])]
    visited = {}
    best_result = None

    while pq:
        total_cost, total_dist, total_h2s, total_ch4, current, path = heapq.heappop(pq)

        if total_dist > max_distance:
            continue

        state_key = current
        if state_key in visited:
            if visited[state_key] <= total_cost:
                continue
        visited[state_key] = total_cost

        if current == end_id:
            if best_result is None or total_cost < best_result['total_cost']:
                node_details = []
                danger_nodes = []
                warning_nodes = []

                for nid in path:
                    gas = gas_readings.get(nid, {})
                    node = node_map[nid]
                    h2s_val = gas.get('h2s', 0.0) or 0.0
                    ch4_val = gas.get('ch4', 0.0) or 0.0

                    detail = {
                        'id': nid,
                        'name': node.name,
                        'node_type': node.node_type,
                        'x': node.x,
                        'y': node.y,
                        'h2s': h2s_val,
                        'ch4': ch4_val,
                    }
                    recorded = gas.get('recorded_at')
                    detail['recorded_at'] = recorded.isoformat() if recorded and hasattr(recorded, 'isoformat') else (recorded if recorded else None)

                    node_safe = is_node_safe(gas)
                    node_risk = calculate_node_risk(gas)

                    if not node_safe:
                        detail['status'] = 'danger'
                        danger_nodes.append({
                            'id': nid,
                            'name': node.name,
                            'h2s': h2s_val,
                            'ch4': ch4_val
                        })
                    elif node_risk > 0.5:
                        detail['status'] = 'warning'
                        warning_nodes.append({
                            'id': nid,
                            'name': node.name,
                            'h2s': h2s_val,
                            'ch4': ch4_val
                        })
                    else:
                        detail['status'] = 'safe'

                    node_details.append(detail)

                edges = []
                for i in range(len(path) - 1):
                    edges.append({'from': path[i], 'to': path[i + 1]})

                walking_time = round(total_dist / cfg['WALKING_SPEED_M_PER_MIN'], 1)
                time_acceptable = walking_time <= cfg['MAX_WALKING_TIME_MINUTES']

                best_result = {
                    'success': True,
                    'route_type': 'compromise',
                    'path': path,
                    'nodes': node_details,
                    'edges': edges,
                    'total_cost': round(total_cost, 4),
                    'total_distance': round(total_dist, 2),
                    'total_h2s': round(total_h2s, 4),
                    'total_ch4': round(total_ch4, 4),
                    'avg_h2s': round(total_h2s / len(path), 4) if path else 0,
                    'avg_ch4': round(total_ch4 / len(path), 4) if path else 0,
                    'walking_time_minutes': walking_time,
                    'max_allowed_time_minutes': cfg['MAX_WALKING_TIME_MINUTES'],
                    'time_acceptable': time_acceptable,
                    'danger_nodes': danger_nodes,
                    'warning_nodes': warning_nodes,
                    'danger_count': len(danger_nodes),
                    'warning_count': len(warning_nodes),
                    'safe_count': len(path) - len(danger_nodes) - len(warning_nodes),
                    'recommendation': (
                        '⚠️ 此为妥协路线，包含超标节点。'
                        f'预计通行时间 {walking_time} 分钟（≤ {cfg["MAX_WALKING_TIME_MINUTES"]}分钟）。'
                        f'必须佩戴正压式防毒面具，建议 2 人以上同行，携带便携式气体检测仪实时监测。'
                        f'途经 {len(danger_nodes)} 个超标节点、{len(warning_nodes)} 个预警节点，请快速通过不要停留。'
                    ) if time_acceptable else (
                        '⚠️ 此路线距离过远，超过 10 分钟快速通过极限。'
                        '强烈建议等待通风降低浓度后再作业，或改选地面绕行方案。'
                    )
                }
            continue

        for neighbor, distance in graph[current]:
            if neighbor not in node_map:
                continue
            if neighbor in path:
                continue

            neighbor_gas = gas_readings.get(neighbor, {})
            neighbor_node = node_map[neighbor]
            step_cost = calculate_compromise_cost(neighbor_gas, distance, neighbor_node.node_type)

            new_cost = total_cost + step_cost
            new_dist = total_dist + distance
            new_h2s = total_h2s + (neighbor_gas.get('h2s', 0.0) or 0.0)
            new_ch4 = total_ch4 + (neighbor_gas.get('ch4', 0.0) or 0.0)
            new_path = path + [neighbor]

            heapq.heappush(pq, (new_cost, new_dist, new_h2s, new_ch4, neighbor, new_path))

    if best_result:
        return best_result

    return {
        'success': False,
        'error': (
            f'从 {node_map[start_id].name} 到 {node_map[end_id].name} 无法找到可行路线，'
            f'即使允许经过超标节点，所有路径距离均超过 10 分钟快速通过极限（> {max_distance}m）。'
        ),
        'max_allowed_distance': max_distance
    }


def calculate_both_routes(start_id, end_id):
    safe_result = dijkstra_safe_route(start_id, end_id)
    compromise_result = dijkstra_compromise_route(start_id, end_id)

    response = {
        'success': safe_result.get('success') or compromise_result.get('success'),
        'safe_route': safe_result if safe_result.get('success') else None,
        'compromise_route': compromise_result if compromise_result.get('success') else None,
    }

    if not response['success']:
        safe_err = safe_result.get('error', '') if not safe_result.get('success') else ''
        comp_err = compromise_result.get('error', '') if not compromise_result.get('success') else ''
        errors = [e for e in [safe_err, comp_err] if e]
        response['error'] = '；'.join(errors) if errors else '无法计算任何路线'

    return response


def get_all_nodes_status():
    nodes = PipeNode.query.all()
    gas_readings = get_latest_gas_readings()
    threshold = {
        'h2s': Config.H2S_THRESHOLD,
        'ch4': Config.CH4_THRESHOLD
    }

    result = []
    for node in nodes:
        gas = gas_readings.get(node.id)
        status = 'safe'
        if gas:
            if not is_node_safe(gas):
                status = 'danger'
            elif calculate_node_risk(gas) > 0.5:
                status = 'warning'
        entry = node.to_dict()
        if gas:
            entry['h2s'] = gas.get('h2s', 0.0) or 0.0
            entry['ch4'] = gas.get('ch4', 0.0) or 0.0
            entry['risk_score'] = round(calculate_node_risk(gas), 4)
            recorded = gas.get('recorded_at')
            entry['recorded_at'] = recorded.isoformat() if recorded and hasattr(recorded, 'isoformat') else (recorded if recorded else None)
        else:
            entry['h2s'] = 0.0
            entry['ch4'] = 0.0
            entry['risk_score'] = 0.0
        entry['status'] = status
        entry['thresholds'] = threshold
        result.append(entry)

    return result


def get_all_connections():
    connections = PipeConnection.query.all()
    return [c.to_dict() for c in connections]
