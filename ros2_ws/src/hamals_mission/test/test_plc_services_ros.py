"""Real ROS service contract smoke test; skipped on hosts without ROS."""
from types import SimpleNamespace

import pytest

rclpy = pytest.importorskip('rclpy')
from rclpy.executors import MultiThreadedExecutor
from std_srvs.srv import Trigger
from hamals_interfaces.msg import MissionState
from hamals_mission.mission_context import MissionContext
from hamals_mission.mission_node import MissionNode


def test_plc_trigger_services_pause_and_resume_independently():
    rclpy.init()
    node = MissionNode()
    client_node = rclpy.create_node('plc_service_smoke_test')
    executor = MultiThreadedExecutor(num_threads=2)
    executor.add_node(node)
    executor.add_node(client_node)
    try:
        node._mctx = MissionContext('test', 'A1', 'B2', MissionState.EXECUTING)
        node._safety = SimpleNamespace(estop_active=False, manual_mode=False,
                                       motion_allowed=True, state=0, reason='')
        for name, expected in (('pause', MissionState.PAUSED_PLC),
                               ('resume', MissionState.EXECUTING)):
            client = client_node.create_client(Trigger, f'/mission/plc_{name}')
            assert client.wait_for_service(timeout_sec=3.)
            future = client.call_async(Trigger.Request())
            executor.spin_until_future_complete(future, timeout_sec=3.)
            assert future.done() and future.result().success
            assert node._mctx.top_state == expected
    finally:
        executor.shutdown()
        node.destroy_node()
        client_node.destroy_node()
        rclpy.shutdown()
