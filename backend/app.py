from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

from config import Config
from models import db, PipeNode, PipeConnection, GasReading
from path_planner import (
    dijkstra_safe_route,
    get_all_nodes_status,
    get_all_connections,
    get_latest_gas_readings
)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        seed_sample_data()

    register_routes(app)
    return app


def seed_sample_data():
    if PipeNode.query.count() > 0:
        return

    nodes_data = [
        {'id': 'WELL-A', 'name': 'A井口', 'node_type': 'wellhead', 'x': 50, 'y': 80, 'depth': 2.5},
        {'id': 'J-01', 'name': '节点J-01', 'node_type': 'junction', 'x': 150, 'y': 80, 'depth': 3.0},
        {'id': 'J-02', 'name': '节点J-02', 'node_type': 'junction', 'x': 250, 'y': 120, 'depth': 3.2},
        {'id': 'J-03', 'name': '节点J-03', 'node_type': 'junction', 'x': 150, 'y': 180, 'depth': 3.5},
        {'id': 'J-04', 'name': '节点J-04', 'node_type': 'junction', 'x': 350, 'y': 80, 'depth': 2.8},
        {'id': 'J-05', 'name': '节点J-05', 'node_type': 'junction', 'x': 350, 'y': 200, 'depth': 4.0},
        {'id': 'J-06', 'name': '节点J-06', 'node_type': 'junction', 'x': 450, 'y': 140, 'depth': 3.8},
        {'id': 'J-07', 'name': '节点J-07', 'node_type': 'junction', 'x': 250, 'y': 250, 'depth': 4.2},
        {'id': 'J-08', 'name': '节点J-08', 'node_type': 'junction', 'x': 500, 'y': 260, 'depth': 3.6},
        {'id': 'WELL-B', 'name': 'B井口', 'node_type': 'wellhead', 'x': 600, 'y': 180, 'depth': 2.5},
        {'id': 'MON-01', 'name': '监测点1', 'node_type': 'monitor', 'x': 50, 'y': 200, 'depth': 3.0},
        {'id': 'MON-02', 'name': '监测点2', 'node_type': 'monitor', 'x': 600, 'y': 80, 'depth': 3.0},
    ]

    for nd in nodes_data:
        node = PipeNode(**nd)
        db.session.add(node)

    connections_data = [
        ('WELL-A', 'J-01', 80, 0.8),
        ('J-01', 'J-02', 60, 0.8),
        ('J-01', 'J-03', 70, 0.6),
        ('J-02', 'J-04', 65, 0.8),
        ('J-02', 'J-05', 90, 0.6),
        ('J-03', 'J-05', 80, 0.6),
        ('J-03', 'J-07', 75, 0.6),
        ('J-04', 'J-06', 85, 0.8),
        ('J-05', 'J-06', 70, 0.6),
        ('J-05', 'J-08', 95, 0.6),
        ('J-06', 'WELL-B', 100, 0.8),
        ('J-07', 'J-08', 85, 0.6),
        ('J-08', 'WELL-B', 80, 0.8),
        ('WELL-A', 'MON-01', 100, 0.5),
        ('MON-01', 'J-03', 90, 0.5),
        ('J-04', 'MON-02', 110, 0.5),
        ('MON-02', 'WELL-B', 90, 0.5),
    ]

    for conn in connections_data:
        connection = PipeConnection(
            from_node_id=conn[0],
            to_node_id=conn[1],
            distance=conn[2],
            pipe_diameter=conn[3]
        )
        db.session.add(connection)

    readings_data = [
        ('WELL-A', 2.5, 0.15, 'ROBOT-001'),
        ('J-01', 3.2, 0.22, 'ROBOT-001'),
        ('J-02', 4.8, 0.35, 'ROBOT-001'),
        ('J-03', 8.5, 0.55, 'ROBOT-002'),
        ('J-04', 2.1, 0.10, 'ROBOT-002'),
        ('J-05', 12.3, 0.85, 'ROBOT-002'),
        ('J-06', 5.6, 0.40, 'ROBOT-003'),
        ('J-07', 15.2, 1.25, 'ROBOT-003'),
        ('J-08', 6.8, 0.48, 'ROBOT-003'),
        ('WELL-B', 2.8, 0.18, 'ROBOT-001'),
        ('MON-01', 7.2, 0.50, 'ROBOT-002'),
        ('MON-02', 3.5, 0.25, 'ROBOT-003'),
    ]

    now = datetime.utcnow()
    for i, rd in enumerate(readings_data):
        reading = GasReading(
            node_id=rd[0],
            h2s_concentration=rd[1],
            ch4_concentration=rd[2],
            temperature=20.0 + i * 0.5,
            humidity=55.0 + i,
            robot_id=rd[3],
            recorded_at=now
        )
        db.session.add(reading)

    db.session.commit()


def register_routes(app):

    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({
            'status': 'ok',
            'service': '地下管网巡检系统 - 路径规划服务',
            'timestamp': datetime.utcnow().isoformat()
        })

    @app.route('/api/nodes', methods=['GET'])
    def get_nodes():
        nodes = get_all_nodes_status()
        return jsonify({
            'success': True,
            'data': nodes,
            'count': len(nodes)
        })

    @app.route('/api/connections', methods=['GET'])
    def get_connections():
        connections = get_all_connections()
        return jsonify({
            'success': True,
            'data': connections,
            'count': len(connections)
        })

    @app.route('/api/topology', methods=['GET'])
    def get_topology():
        nodes = get_all_nodes_status()
        connections = get_all_connections()
        return jsonify({
            'success': True,
            'data': {
                'nodes': nodes,
                'connections': connections
            }
        })

    @app.route('/api/gas-readings', methods=['POST'])
    def submit_gas_reading():
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': '请求数据为空'}), 400

        required_fields = ['node_id', 'h2s_concentration', 'ch4_concentration']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'缺少必填字段: {field}'}), 400

        node = PipeNode.query.get(data['node_id'])
        if not node:
            return jsonify({'success': False, 'error': f'节点 {data["node_id"]} 不存在'}), 404

        try:
            h2s = float(data['h2s_concentration'])
            ch4 = float(data['ch4_concentration'])
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': '气体浓度必须是数值'}), 400

        recorded_at = data.get('recorded_at')
        if recorded_at:
            try:
                recorded_at = datetime.fromisoformat(recorded_at.replace('Z', '+00:00'))
            except ValueError:
                recorded_at = datetime.utcnow()
        else:
            recorded_at = datetime.utcnow()

        reading = GasReading(
            node_id=data['node_id'],
            h2s_concentration=h2s,
            ch4_concentration=ch4,
            temperature=float(data.get('temperature', 25.0)),
            humidity=float(data.get('humidity', 60.0)),
            robot_id=data.get('robot_id'),
            recorded_at=recorded_at
        )
        db.session.add(reading)
        db.session.commit()

        is_safe = True
        if h2s >= app.config['H2S_THRESHOLD']:
            is_safe = False
        if ch4 >= app.config['CH4_THRESHOLD']:
            is_safe = False

        return jsonify({
            'success': True,
            'message': '气体浓度数据已保存',
            'data': reading.to_dict(),
            'node_safe': is_safe,
            'thresholds': {
                'h2s': app.config['H2S_THRESHOLD'],
                'ch4': app.config['CH4_THRESHOLD']
            }
        }), 201

    @app.route('/api/gas-readings/batch', methods=['POST'])
    def submit_batch_readings():
        data = request.get_json()
        if not data or 'readings' not in data:
            return jsonify({'success': False, 'error': '缺少 readings 数组'}), 400

        readings = data['readings']
        saved_count = 0
        errors = []

        for idx, item in enumerate(readings):
            required_fields = ['node_id', 'h2s_concentration', 'ch4_concentration']
            missing = [f for f in required_fields if f not in item]
            if missing:
                errors.append(f'第 {idx+1} 条记录缺少字段: {", ".join(missing)}')
                continue

            node = PipeNode.query.get(item['node_id'])
            if not node:
                errors.append(f'第 {idx+1} 条记录: 节点 {item["node_id"]} 不存在')
                continue

            try:
                h2s = float(item['h2s_concentration'])
                ch4 = float(item['ch4_concentration'])
            except (TypeError, ValueError):
                errors.append(f'第 {idx+1} 条记录: 浓度值无效')
                continue

            recorded_at = item.get('recorded_at')
            if recorded_at:
                try:
                    recorded_at = datetime.fromisoformat(recorded_at.replace('Z', '+00:00'))
                except ValueError:
                    recorded_at = datetime.utcnow()
            else:
                recorded_at = datetime.utcnow()

            reading = GasReading(
                node_id=item['node_id'],
                h2s_concentration=h2s,
                ch4_concentration=ch4,
                temperature=float(item.get('temperature', 25.0)),
                humidity=float(item.get('humidity', 60.0)),
                robot_id=item.get('robot_id'),
                recorded_at=recorded_at
            )
            db.session.add(reading)
            saved_count += 1

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'成功保存 {saved_count} 条记录',
            'saved_count': saved_count,
            'errors': errors if errors else None
        }), 201

    @app.route('/api/gas-readings/<node_id>', methods=['GET'])
    def get_node_readings(node_id):
        limit = request.args.get('limit', 10, type=int)
        readings = GasReading.query.filter_by(node_id=node_id)\
            .order_by(GasReading.recorded_at.desc())\
            .limit(limit).all()
        return jsonify({
            'success': True,
            'data': [r.to_dict() for r in readings]
        })

    @app.route('/api/gas-readings/latest', methods=['GET'])
    def get_latest_readings():
        readings = get_latest_gas_readings()
        result = []
        for node_id, gas in readings.items():
            result.append({
                'node_id': node_id,
                'h2s': gas['h2s'],
                'ch4': gas['ch4'],
                'recorded_at': gas['recorded_at'].isoformat() if gas['recorded_at'] else None
            })
        return jsonify({
            'success': True,
            'data': result
        })

    @app.route('/api/route', methods=['GET', 'POST'])
    def calculate_route():
        if request.method == 'POST':
            data = request.get_json() or {}
            start_id = data.get('start_id')
            end_id = data.get('end_id')
        else:
            start_id = request.args.get('start_id', 'WELL-A')
            end_id = request.args.get('end_id', 'WELL-B')

        if not start_id or not end_id:
            return jsonify({'success': False, 'error': '请提供 start_id 和 end_id'}), 400

        try:
            result = dijkstra_safe_route(start_id, end_id)
            if result is None:
                result = {
                    'success': False,
                    'error': '路径规划算法返回空值，请检查管网数据是否完整'
                }
            if not isinstance(result, dict):
                result = {
                    'success': False,
                    'error': f'路径规划返回异常数据格式: {type(result).__name__}'
                }
            if 'success' not in result:
                result['success'] = False
                if 'error' not in result:
                    result['error'] = '路径规划返回结果格式不完整'
            return jsonify(result)
        except Exception as e:
            db.session.rollback()
            app.logger.exception(f'路径规划异常: {e}')
            return jsonify({
                'success': False,
                'error': f'路径规划服务异常: {str(e)}。请稍后重试或联系运维。'
            }), 500

    @app.route('/api/thresholds', methods=['GET'])
    def get_thresholds():
        return jsonify({
            'success': True,
            'data': {
                'h2s_threshold': app.config['H2S_THRESHOLD'],
                'h2s_unit': 'ppm',
                'ch4_threshold': app.config['CH4_THRESHOLD'],
                'ch4_unit': '%LEL'
            }
        })

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'success': False, 'error': '接口不存在'}), 404

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return jsonify({'success': False, 'error': '服务器内部错误'}), 500


app = create_app()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
