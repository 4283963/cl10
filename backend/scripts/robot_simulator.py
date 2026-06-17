import requests
import random
import time
import json
from datetime import datetime

API_BASE = "http://localhost:5000/api"

NODES = [
    'WELL-A', 'J-01', 'J-02', 'J-03', 'J-04', 'J-05',
    'J-06', 'J-07', 'J-08', 'WELL-B', 'MON-01', 'MON-02'
]

ROBOTS = ['ROBOT-001', 'ROBOT-002', 'ROBOT-003']


def generate_reading(node_id):
    danger_nodes = ['J-05', 'J-07']

    if node_id in danger_nodes:
        h2s = random.uniform(8.0, 18.0)
        ch4 = random.uniform(0.6, 1.5)
    elif node_id in ['J-03', 'MON-01']:
        h2s = random.uniform(4.0, 9.5)
        ch4 = random.uniform(0.3, 0.9)
    else:
        h2s = random.uniform(0.5, 5.0)
        ch4 = random.uniform(0.05, 0.5)

    return {
        'node_id': node_id,
        'h2s_concentration': round(h2s, 2),
        'ch4_concentration': round(ch4, 3),
        'temperature': round(random.uniform(18.0, 28.0), 1),
        'humidity': round(random.uniform(50.0, 80.0), 1),
        'robot_id': random.choice(ROBOTS),
        'recorded_at': datetime.utcnow().isoformat()
    }


def submit_single(reading):
    try:
        resp = requests.post(f"{API_BASE}/gas-readings", json=reading, timeout=5)
        data = resp.json()
        status = '⚠️' if not data.get('node_safe', True) else '✓'
        print(f"{status} [{reading['node_id']:8s}] H2S={reading['h2s_concentration']:5.2f}  CH4={reading['ch4_concentration']:5.3f}  robot={reading['robot_id']}")
        return data
    except Exception as e:
        print(f"❌ 提交失败: {reading['node_id']} - {e}")
        return None


def submit_batch(readings):
    try:
        resp = requests.post(f"{API_BASE}/gas-readings/batch",
                            json={'readings': readings},
                            timeout=10)
        data = resp.json()
        print(f"\n📦 批量提交: 成功 {data.get('saved_count', 0)} 条")
        if data.get('errors'):
            for err in data['errors']:
                print(f"   ❌ {err}")
        return data
    except Exception as e:
        print(f"❌ 批量提交失败: {e}")
        return None


def check_health():
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def run_once(mode='batch'):
    print("\n" + "=" * 70)
    print(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  巡检机器人上报气体数据")
    print("=" * 70)

    readings = [generate_reading(nid) for nid in NODES]

    if mode == 'batch':
        submit_batch(readings)
    else:
        for r in readings:
            submit_single(r)
            time.sleep(0.2)

    print("\n🔍 请求规划路线 (WELL-A -> WELL-B)")
    try:
        resp = requests.get(f"{API_BASE}/route",
                           params={'start_id': 'WELL-A', 'end_id': 'WELL-B'},
                           timeout=5)
        data = resp.json()
        if data.get('success'):
            path = data.get('path', [])
            print(f"✅ 安全路线: {' → '.join(path)}")
            print(f"   总距离: {data.get('total_distance')}m  风险分: {data.get('total_risk_score')}")
            print(f"   平均H2S: {data.get('avg_h2s')} ppm  平均CH4: {data.get('avg_ch4')} %LEL")
            unsafe = data.get('unsafe_nodes', [])
            if unsafe:
                print(f"   ⚠️  路线中标注节点: {unsafe}")
        else:
            print(f"❌ 规划失败: {data.get('error')}")
    except Exception as e:
        print(f"❌ 获取路线失败: {e}")


def run_continuous(interval=15, mode='batch'):
    print(f"🚀 巡检机器人模拟器启动 (每{interval}秒上报一次, Ctrl+C 退出)")
    print(f"   API 地址: {API_BASE}")
    while True:
        if not check_health():
            print("⚠️  后端服务未就绪，等待连接...")
            time.sleep(3)
            continue
        run_once(mode)
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\n🛑 模拟器已停止")
            break


if __name__ == '__main__':
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else 'once'
    if mode == 'continuous':
        run_continuous(interval=15, mode='batch')
    elif mode == 'single':
        run_once(mode='single')
    else:
        run_once(mode='batch')
