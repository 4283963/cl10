import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import heapq
from collections import defaultdict
from path_planner import (
    is_node_safe,
    calculate_node_risk,
    dijkstra_safe_route,
    dijkstra_compromise_route,
    calculate_both_routes,
    calculate_compromise_cost,
    COMPROMISE_CONFIG,
)


class MockNode:
    def __init__(self, id, name, node_type, x, y):
        self.id = id
        self.name = name
        self.node_type = node_type
        self.x = x
        self.y = y


class MockConnection:
    def __init__(self, from_node_id, to_node_id, distance):
        self.from_node_id = from_node_id
        self.to_node_id = to_node_id
        self.distance = distance


def make_nodes():
    return [
        MockNode('A', '井口A', 'wellhead', 0, 0),
        MockNode('B', '井口B', 'wellhead', 300, 0),
        MockNode('M1', '中间节点1', 'junction', 100, 0),
        MockNode('M2', '中间节点2', 'junction', 200, 0),
        MockNode('M3', '绕行节点', 'junction', 150, 100),
    ]


def make_connections():
    return [
        MockConnection('A', 'M1', 80),
        MockConnection('M1', 'M2', 80),
        MockConnection('M2', 'B', 80),
        MockConnection('A', 'M3', 120),
        MockConnection('M3', 'B', 120),
        MockConnection('M1', 'M3', 60),
        MockConnection('M2', 'M3', 60),
    ]


class TestIsNodeSafe(unittest.TestCase):
    def test_safe_node(self):
        self.assertTrue(is_node_safe({'h2s': 5.0, 'ch4': 0.5}))

    def test_h2s_over_threshold(self):
        self.assertFalse(is_node_safe({'h2s': 15.0, 'ch4': 0.1}))

    def test_ch4_over_threshold(self):
        self.assertFalse(is_node_safe({'h2s': 1.0, 'ch4': 1.5}))

    def test_both_over(self):
        self.assertFalse(is_node_safe({'h2s': 20.0, 'ch4': 2.0}))

    def test_no_data(self):
        self.assertTrue(is_node_safe(None))

    def test_boundary_equal(self):
        self.assertFalse(is_node_safe({'h2s': 10.0, 'ch4': 0.5}))
        self.assertFalse(is_node_safe({'h2s': 5.0, 'ch4': 1.0}))


class TestCalculateNodeRisk(unittest.TestCase):
    def test_zero_risk(self):
        self.assertEqual(calculate_node_risk({'h2s': 0, 'ch4': 0}), 0.0)

    def test_partial(self):
        risk = calculate_node_risk({'h2s': 5.0, 'ch4': 0.5})
        self.assertAlmostEqual(risk, 5.0 / 10.0 + 0.5 / 1.0)

    def test_no_data(self):
        self.assertEqual(calculate_node_risk(None), 0.0)


class TestDijkstraDeadEnd(unittest.TestCase):

    def _run_with_gas(self, gas_readings):
        with patch('path_planner.build_graph') as mock_build, \
             patch('path_planner.get_latest_gas_readings') as mock_gas:
            nodes = make_nodes()
            conns = make_connections()
            graph = defaultdict(list)
            node_map = {n.id: n for n in nodes}
            for c in conns:
                graph[c.from_node_id].append((c.to_node_id, c.distance))
                graph[c.to_node_id].append((c.from_node_id, c.distance))
            mock_build.return_value = (graph, node_map)
            mock_gas.return_value = gas_readings
            return dijkstra_safe_route('A', 'B')

    def test_normal_route_exists(self):
        gas = {
            'A': {'h2s': 1.0, 'ch4': 0.1},
            'B': {'h2s': 1.0, 'ch4': 0.1},
            'M1': {'h2s': 2.0, 'ch4': 0.2},
            'M2': {'h2s': 3.0, 'ch4': 0.3},
            'M3': {'h2s': 2.5, 'ch4': 0.25},
        }
        result = self._run_with_gas(gas)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get('success'), f"应该成功但返回: {result.get('error')}")
        self.assertIsInstance(result.get('path'), list)
        self.assertGreater(len(result['path']), 0)
        self.assertEqual(result['path'][0], 'A')
        self.assertEqual(result['path'][-1], 'B')
        self.assertIn('edges', result)
        self.assertIn('total_distance', result)

    def test_all_intermediate_blocked_dead_end(self):
        gas = {
            'A': {'h2s': 1.0, 'ch4': 0.1},
            'B': {'h2s': 1.0, 'ch4': 0.1},
            'M1': {'h2s': 25.0, 'ch4': 2.0},
            'M2': {'h2s': 30.0, 'ch4': 3.0},
            'M3': {'h2s': 15.0, 'ch4': 1.5},
        }
        result = self._run_with_gas(gas)
        self.assertIsNotNone(result, '不能返回 None！这是触发前端崩溃的根因')
        self.assertIsInstance(result, dict, '必须返回字典')
        self.assertIn('success', result)
        self.assertFalse(result['success'])
        self.assertIn('error', result)
        self.assertIsInstance(result['error'], str)
        self.assertGreater(len(result['error']), 0)
        self.assertIn('blocked_nodes', result)
        self.assertIsInstance(result['blocked_nodes'], list)
        self.assertGreater(len(result['blocked_nodes']), 0)
        self.assertIn('safe_node_count', result)
        self.assertEqual(result['safe_node_count'], 2)
        self.assertIn('total_node_count', result)
        self.assertEqual(result['total_node_count'], 5)
        self.assertNotIn('path', result, '失败时不应带 path 字段避免前端误用')

    def test_start_node_blocked(self):
        gas = {
            'A': {'h2s': 20.0, 'ch4': 2.0},
            'B': {'h2s': 1.0, 'ch4': 0.1},
            'M1': {'h2s': 1.0, 'ch4': 0.1},
            'M2': {'h2s': 1.0, 'ch4': 0.1},
            'M3': {'h2s': 1.0, 'ch4': 0.1},
        }
        result = self._run_with_gas(gas)
        self.assertIsNotNone(result)
        self.assertFalse(result['success'])
        self.assertIn('超标', result['error'])
        self.assertIn('blocked_nodes', result)

    def test_end_node_blocked(self):
        gas = {
            'A': {'h2s': 1.0, 'ch4': 0.1},
            'B': {'h2s': 20.0, 'ch4': 2.0},
            'M1': {'h2s': 1.0, 'ch4': 0.1},
            'M2': {'h2s': 1.0, 'ch4': 0.1},
            'M3': {'h2s': 1.0, 'ch4': 0.1},
        }
        result = self._run_with_gas(gas)
        self.assertIsNotNone(result)
        self.assertFalse(result['success'])
        self.assertIn('超标', result['error'])

    def test_unknown_start_node(self):
        result = self._run_with_gas({})
        with patch('path_planner.build_graph') as mock_build:
            mock_build.return_value = (defaultdict(list), {})
            res = dijkstra_safe_route('X', 'Y')
            self.assertIsNotNone(res)
            self.assertFalse(res['success'])

    def test_partial_blocked_still_has_route(self):
        gas = {
            'A': {'h2s': 1.0, 'ch4': 0.1},
            'B': {'h2s': 1.0, 'ch4': 0.1},
            'M1': {'h2s': 20.0, 'ch4': 2.0},
            'M2': {'h2s': 20.0, 'ch4': 2.0},
            'M3': {'h2s': 2.0, 'ch4': 0.2},
        }
        result = self._run_with_gas(gas)
        self.assertIsNotNone(result)
        self.assertTrue(result['success'])
        self.assertEqual(result['path'], ['A', 'M3', 'B'])

    def test_no_gas_data_at_all(self):
        result = self._run_with_gas({})
        self.assertIsNotNone(result)
        self.assertTrue(result['success'])


class TestCalculateCompromiseCost(unittest.TestCase):
    def test_safe_node_low_cost(self):
        cost = calculate_compromise_cost({'h2s': 1.0, 'ch4': 0.1}, 10)
        self.assertAlmostEqual(cost, 1.0 * 1.0 + 0.1 * 2.0 + 10 * 0.1)

    def test_warning_node_medium_cost(self):
        cost = calculate_compromise_cost({'h2s': 7.0, 'ch4': 0.7}, 10)
        self.assertGreater(cost, 50.0)

    def test_danger_node_high_cost(self):
        cost = calculate_compromise_cost({'h2s': 15.0, 'ch4': 1.5}, 10)
        self.assertGreater(cost, 1000.0)

    def test_wellhead_penalty_reduced(self):
        cost_normal = calculate_compromise_cost({'h2s': 15.0, 'ch4': 1.5}, 10, 'junction')
        cost_well = calculate_compromise_cost({'h2s': 15.0, 'ch4': 1.5}, 10, 'wellhead')
        self.assertLess(cost_well, cost_normal)


class TestDijkstraCompromiseRoute(unittest.TestCase):

    def _run_with_gas(self, gas_readings):
        with patch('path_planner.build_graph') as mock_build, \
             patch('path_planner.get_latest_gas_readings') as mock_gas:
            nodes = make_nodes()
            conns = make_connections()
            graph = defaultdict(list)
            node_map = {n.id: n for n in nodes}
            for c in conns:
                graph[c.from_node_id].append((c.to_node_id, c.distance))
                graph[c.to_node_id].append((c.from_node_id, c.distance))
            mock_build.return_value = (graph, node_map)
            mock_gas.return_value = gas_readings
            return dijkstra_compromise_route('A', 'B')

    def test_normal_route_selects_safest_path(self):
        gas = {
            'A': {'h2s': 1.0, 'ch4': 0.1},
            'B': {'h2s': 1.0, 'ch4': 0.1},
            'M1': {'h2s': 2.0, 'ch4': 0.2},
            'M2': {'h2s': 3.0, 'ch4': 0.3},
            'M3': {'h2s': 2.5, 'ch4': 0.25},
        }
        result = self._run_with_gas(gas)
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success'))
        self.assertEqual(result.get('route_type'), 'compromise')
        self.assertIsInstance(result.get('path'), list)
        self.assertGreater(len(result['path']), 0)
        self.assertEqual(result['path'][0], 'A')
        self.assertEqual(result['path'][-1], 'B')
        self.assertIn('walking_time_minutes', result)
        self.assertIn('danger_count', result)
        self.assertIn('recommendation', result)

    def test_all_intermediate_blocked_selects_least_toxic(self):
        gas = {
            'A': {'h2s': 1.0, 'ch4': 0.1},
            'B': {'h2s': 1.0, 'ch4': 0.1},
            'M1': {'h2s': 25.0, 'ch4': 2.0},
            'M2': {'h2s': 30.0, 'ch4': 3.0},
            'M3': {'h2s': 15.0, 'ch4': 1.5},
        }
        result = self._run_with_gas(gas)
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success'), f"应该找到妥协路线: {result.get('error')}")
        self.assertEqual(result['path'], ['A', 'M3', 'B'])
        self.assertGreater(result['danger_count'], 0)
        self.assertIn('⚠️ 此为妥协路线', result['recommendation'])

    def test_compromise_route_within_time_limit(self):
        gas = {
            'A': {'h2s': 1.0, 'ch4': 0.1},
            'B': {'h2s': 1.0, 'ch4': 0.1},
            'M1': {'h2s': 2.0, 'ch4': 0.2},
            'M2': {'h2s': 3.0, 'ch4': 0.3},
            'M3': {'h2s': 2.5, 'ch4': 0.25},
        }
        result = self._run_with_gas(gas)
        self.assertTrue(result.get('success'))
        self.assertLessEqual(
            result['walking_time_minutes'],
            COMPROMISE_CONFIG['MAX_WALKING_TIME_MINUTES']
        )
        self.assertTrue(result['time_acceptable'])

    def test_start_node_blocked_still_finds_compromise(self):
        gas = {
            'A': {'h2s': 20.0, 'ch4': 2.0},
            'B': {'h2s': 1.0, 'ch4': 0.1},
            'M1': {'h2s': 2.0, 'ch4': 0.2},
            'M2': {'h2s': 3.0, 'ch4': 0.3},
            'M3': {'h2s': 2.5, 'ch4': 0.25},
        }
        result = self._run_with_gas(gas)
        self.assertIsNotNone(result)
        self.assertTrue(result.get('success'))
        self.assertEqual(result['path'][0], 'A')
        self.assertEqual(result['path'][-1], 'B')
        self.assertGreater(result['danger_count'], 0)

    def test_returns_detailed_node_status(self):
        gas = {
            'A': {'h2s': 1.0, 'ch4': 0.1},
            'B': {'h2s': 1.0, 'ch4': 0.1},
            'M1': {'h2s': 7.0, 'ch4': 0.7},
            'M2': {'h2s': 25.0, 'ch4': 2.0},
            'M3': {'h2s': 2.0, 'ch4': 0.2},
        }
        result = self._run_with_gas(gas)
        self.assertTrue(result.get('success'))
        self.assertIsInstance(result.get('nodes'), list)
        for node in result['nodes']:
            self.assertIn('status', node)
            self.assertIn(node['status'], ['safe', 'warning', 'danger'])

    def test_too_far_route_exceeds_time_limit(self):
        with patch('path_planner.build_graph') as mock_build, \
             patch('path_planner.get_latest_gas_readings') as mock_gas:
            nodes = [
                MockNode('A', '起点', 'wellhead', 0, 0),
                MockNode('B', '终点', 'wellhead', 1000, 0),
                MockNode('M1', '中间', 'junction', 500, 0),
            ]
            conns = [
                MockConnection('A', 'M1', 400),
                MockConnection('M1', 'B', 400),
            ]
            graph = defaultdict(list)
            node_map = {n.id: n for n in nodes}
            for c in conns:
                graph[c.from_node_id].append((c.to_node_id, c.distance))
                graph[c.to_node_id].append((c.from_node_id, c.distance))
            mock_build.return_value = (graph, node_map)
            mock_gas.return_value = {
                'A': {'h2s': 1.0, 'ch4': 0.1},
                'B': {'h2s': 1.0, 'ch4': 0.1},
                'M1': {'h2s': 1.0, 'ch4': 0.1},
            }
            result = dijkstra_compromise_route('A', 'B')
            self.assertIsNotNone(result)
            if result.get('success'):
                self.assertFalse(result.get('time_acceptable', True))
                self.assertIn('超过 10 分钟', result.get('recommendation', ''))


class TestCalculateBothRoutes(unittest.TestCase):

    def _run_with_gas(self, gas_readings):
        with patch('path_planner.build_graph') as mock_build, \
             patch('path_planner.get_latest_gas_readings') as mock_gas:
            nodes = make_nodes()
            conns = make_connections()
            graph = defaultdict(list)
            node_map = {n.id: n for n in nodes}
            for c in conns:
                graph[c.from_node_id].append((c.to_node_id, c.distance))
                graph[c.to_node_id].append((c.from_node_id, c.distance))
            mock_build.return_value = (graph, node_map)
            mock_gas.return_value = gas_readings
            return calculate_both_routes('A', 'B')

    def test_both_routes_available_when_safe(self):
        gas = {
            'A': {'h2s': 1.0, 'ch4': 0.1},
            'B': {'h2s': 1.0, 'ch4': 0.1},
            'M1': {'h2s': 2.0, 'ch4': 0.2},
            'M2': {'h2s': 3.0, 'ch4': 0.3},
            'M3': {'h2s': 2.5, 'ch4': 0.25},
        }
        result = self._run_with_gas(gas)
        self.assertTrue(result.get('success'))
        self.assertIsNotNone(result.get('safe_route'))
        self.assertIsNotNone(result.get('compromise_route'))
        self.assertTrue(result['safe_route']['success'])
        self.assertTrue(result['compromise_route']['success'])

    def test_only_compromise_available_when_safe_blocked(self):
        gas = {
            'A': {'h2s': 1.0, 'ch4': 0.1},
            'B': {'h2s': 1.0, 'ch4': 0.1},
            'M1': {'h2s': 20.0, 'ch4': 2.0},
            'M2': {'h2s': 20.0, 'ch4': 2.0},
            'M3': {'h2s': 20.0, 'ch4': 2.0},
        }
        result = self._run_with_gas(gas)
        self.assertTrue(result.get('success'))
        self.assertIsNone(result.get('safe_route'))
        self.assertIsNotNone(result.get('compromise_route'))
        self.assertTrue(result['compromise_route']['success'])

    def test_success_false_when_both_blocked(self):
        gas = {}
        with patch('path_planner.build_graph') as mock_build, \
             patch('path_planner.get_latest_gas_readings') as mock_gas:
            mock_build.return_value = (defaultdict(list), {})
            mock_gas.return_value = {}
            result = calculate_both_routes('X', 'Y')
        self.assertFalse(result.get('success'))
        self.assertIsNotNone(result.get('error'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
