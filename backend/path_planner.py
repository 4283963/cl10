import heapq
from collections import defaultdict
from datetime import datetime, timedelta

from config import Config
from models import PipeNode, PipeConnection, GasReading, db


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
