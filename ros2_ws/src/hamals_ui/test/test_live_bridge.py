"""Behavioral bridge tests with ROS transports stubbed (no ROS installation needed)."""
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace as NS
from unittest.mock import Mock

import pytest
import yaml

ROOT = Path(__file__).parents[1]


@pytest.fixture
def bridge(monkeypatch):
    def module(name, **attrs):
        mod = ModuleType(name)
        mod.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, mod)
    class Message:
        def __init__(self, **kw):
            self.__dict__.update(kw)
    class Twist:
        def __init__(self):
            self.linear = NS(x=0.0)
            self.angular = NS(z=0.0)
    class ForkCommand(Message):
        STOP, UP, DOWN = 0, 1, 2
    class Goal:
        def __init__(self):
            self.task = NS()
    module('rclpy')
    class Node:
        def __init__(self, name):
            self.name = name
    module('rclpy.node', Node=Node)
    module('rclpy.qos', QoSProfile=Mock(), ReliabilityPolicy=Mock(), DurabilityPolicy=Mock())
    module('rclpy.action', ActionClient=Mock())
    module('ament_index_python.packages', get_package_share_directory=Mock())
    module('std_msgs.msg', Bool=Message, String=Message)
    module('geometry_msgs.msg', Twist=Twist)
    module('hamals_interfaces.msg', ForkCommand=ForkCommand)
    module('hamals_interfaces.action', ExecuteMission=NS(Goal=Goal))
    module('hamals_interfaces.srv', PauseMission=NS(Request=Message), ResumeMission=NS(Request=Message))
    module('rcl_interfaces.srv', GetParameters=NS(Request=Message))
    spec = importlib.util.spec_from_file_location('bridge_under_test', ROOT / 'hamals_ui/ui_bridge_node.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    clock = NS(now=100.0)
    monkeypatch.setattr(mod, 'time', NS(time=lambda: clock.now, monotonic=lambda: clock.now))
    node = mod.UIBridgeNode.__new__(mod.UIBridgeNode)
    node._mode = 'live'
    node._state = mod._default_state()
    node._session_started_at = clock.now
    node._topic_last_seen = {}
    node._topic_offline_key = {}
    node._goal_handle = None
    node._goal_pending = False
    node._mission_action = Mock()
    node._pause_client = Mock()
    node._resume_client = Mock()
    node._mission_action.server_is_ready.return_value = True
    node._pause_client.service_is_ready.return_value = True
    node._resume_client.service_is_ready.return_value = True
    node._fork_pub = Mock()
    node._camera_select_pub = Mock()
    node._state_pub = Mock()
    node.get_logger = Mock(return_value=Mock())
    node.get_clock = Mock(return_value=Mock())
    node.create_publisher = Mock(return_value=Mock())
    node._bridge_cfg = yaml.safe_load((ROOT / 'config/bridge.yaml').read_text())
    node._test_clock = clock
    node._test_module = mod
    return node


def receive(node, topic, **fields):
    source = next(s for s in node._bridge_cfg['sources'] if s['topic'] == topic)
    node._on_topic(topic, NS(**fields), source['fields'], source.get('offline_key', ''))


def command(node, kind, **payload):
    node._cmd_callback(NS(data=json.dumps({'type': kind, 'payload': payload})))


def test_camera_selection_publishes_bool_without_manual_mode(bridge):
    command(bridge, 'switch_camera', is_up=True)
    assert bridge._camera_select_pub.publish.call_args.args[0].data is True
    command(bridge, 'switch_camera', is_up=False)
    assert bridge._camera_select_pub.publish.call_args.args[0].data is False
    assert bridge._camera_select_pub.publish.call_count == 2
    command(bridge, 'switch_camera', is_up='false')
    assert bridge._camera_select_pub.publish.call_count == 2


@pytest.mark.parametrize('mode', ['manual', 'auto', 'unknown', 'MANUAL', ' manual', ''])
def test_manual_topic_and_mode_gate(bridge, mode):
    receive(bridge, '/switch/mode', data=mode)
    command(bridge, 'teleop', linear=0.2, angular=0, state_ts=100)
    if mode == 'manual':
        assert bridge.create_publisher.call_args.args[1] == '/cmd_vel/manual_teleop'
        assert bridge.create_publisher.return_value.publish.call_args.args[0].linear.x == 0.2
    else:
        bridge.create_publisher.assert_not_called()


@pytest.mark.parametrize('case', ['missing_mode', 'stale_mode', 'old_lease', 'missing_lease', 'future_lease', 'nan', 'overspeed'])
def test_invalid_manual_commands_never_publish(bridge, case):
    if case != 'missing_mode':
        receive(bridge, '/switch/mode', data='manual')
    if case == 'stale_mode':
        bridge._test_clock.now += 2
    payload = dict(linear=0.1, angular=0, state_ts=bridge._test_clock.now)
    if case == 'old_lease': payload['state_ts'] = 90
    if case == 'future_lease': payload['state_ts'] = 110
    if case == 'missing_lease': payload.pop('state_ts')
    if case == 'nan': payload['linear'] = float('nan')
    if case == 'overspeed': payload['linear'] = 20
    command(bridge, 'teleop', **payload)
    bridge.create_publisher.assert_not_called()


def test_auto_rejects_zero_too(bridge):
    receive(bridge, '/switch/mode', data='auto')
    command(bridge, 'teleop', linear=0, angular=0, state_ts=100)
    bridge.create_publisher.assert_not_called()


def test_live_estop_and_mode_are_read_only(bridge):
    receive(bridge, '/switch/mode', data='auto')
    receive(bridge, '/estop', data=False)
    for kind in ('estop', 'estop_ack', 'switch_mode'):
        command(bridge, kind, mode='manual')
    assert bridge._state['switch']['mode'] == 'auto'
    assert bridge._state['estop']['active'] is False
    assert bridge._state['mission']['fsm'] == 'unknown'


def test_live_has_no_fake_defaults(bridge):
    s = bridge._state
    assert s['battery']['percent'] is None
    assert s['battery']['voltage'] is None
    assert not s['pose'] and not s['safety'] and not s['fork']
    assert s['plc']['connected'] is None
    assert s['estop']['active'] is None


def test_fork_command_uses_real_enum_without_mutating_feedback(bridge):
    receive(bridge, '/switch/mode', data='manual')
    receive(bridge, '/fork/state', state=0, upper_limit=False, lower_limit=True,
            is_moving=False, error_code=0, last_command=0, t_us=12)
    before = dict(bridge._state['fork'])
    for action, enum in [('up', 1), ('down', 2), ('stop', 0)]:
        command(bridge, 'lift', action=action, state_ts=100)
        assert bridge._fork_pub.publish.call_args.args[0].command == enum
    assert bridge._state['fork'] == before
    assert 'lift' not in bridge._state


def test_obstacle_boolean_and_region_distances(bridge):
    receive(bridge, '/safety/state', obstacle_active=True)
    receive(bridge, '/scan/obstacle_state', regions=[NS(region='front', has_obstacle=True, min_distance=0.4)])
    assert bridge._state['safety']['obstacle_active'] is True
    assert bridge._state['obstacle']['active'] is True
    assert bridge._state['obstacle']['regions'][0]['min_distance'] == 0.4


def test_qr_loss_clears_old_payload(bridge):
    receive(bridge, '/qr/detection', payload='A1', detected=True)
    receive(bridge, '/qr/detection', payload='A1', detected=False)
    assert bridge._state['qr'] == {'detected': False, 'id': None}


@pytest.mark.parametrize('enum,expected', [(0, False), (1, False), (2, True), (3, False), (42, None)])
def test_plc_connection_semantics(bridge, enum, expected):
    receive(bridge, '/plc/state', connection_state=enum)
    assert bridge._state['plc']['connected'] is expected
    assert bridge._state['connection']['plc'] is expected


def test_mission_normalization_preserves_phase_timer(bridge):
    receive(bridge, '/mission/state', state=2, phase='MOVE_LOADED', active_target='D2', elapsed_s=45.5)
    assert bridge._state['mission']['fsm'] == 'executing'
    assert bridge._state['mission']['phase'] == 'MOVE_LOADED'
    assert bridge._state['mission']['phase_normalized'] == 'move_loaded'
    assert bridge._state['mission']['timer']['elapsed_s'] == 45.5
    assert bridge._state['nav']['current_goal'] == 'D2'


def test_live_heartbeat_does_not_refresh_raw_source_age(bridge):
    receive(bridge, '/switch/mode', data='manual')
    bridge._test_clock.now += 8
    bridge._publish_state()
    msg = json.loads(bridge._state_pub.publish.call_args.args[0].data)
    assert msg['meta']['sources']['/switch/mode']['age_s'] == 8
    assert msg['meta']['sources']['/safety/state']['age_s'] is None
    assert msg['battery']['percent'] is None


def test_session_clock_survives_mission_change(bridge):
    bridge._publish_state()
    assert json.loads(bridge._state_pub.publish.call_args.args[0].data)['host']['session_elapsed_s'] == 0
    bridge._test_clock.now += 3
    bridge._state['mission']['elapsed_s'] = 0
    bridge._publish_state()
    assert json.loads(bridge._state_pub.publish.call_args.args[0].data)['host']['session_elapsed_s'] == 3
    bridge._test_clock.now += 3
    bridge._publish_state()
    assert json.loads(bridge._state_pub.publish.call_args.args[0].data)['host']['session_elapsed_s'] == 6


def test_action_goal_uses_real_task_fields(bridge):
    receive(bridge, '/switch/mode', data='auto')
    command(bridge, 'start_mission', task_id='test', pickup_id='A1', dropoff_id='B2')
    goal = bridge._mission_action.send_goal_async.call_args.args[0]
    assert (goal.task.task_id, goal.task.pickup_id, goal.task.dropoff_id) == ('test', 'A1', 'B2')
    assert bridge._state['mission']['fsm'] == 'unknown'
    assert bridge._goal_pending


def test_action_start_missing_inputs_is_rejected(bridge):
    receive(bridge, '/switch/mode', data='auto')
    command(bridge, 'start_mission', task_id='test')
    bridge._mission_action.send_goal_async.assert_not_called()
    assert bridge._state['command_result']['status'] == 'rejected'


def test_pause_resume_and_owned_goal_cancel(bridge):
    command(bridge, 'pause_mission', reason='operator test')
    assert bridge._pause_client.call_async.call_args.args[0].reason == 'operator test'
    command(bridge, 'resume_mission', operator_id='operator1')
    assert bridge._resume_client.call_async.call_args.args[0].operator_id == 'operator1'
    command(bridge, 'cancel_mission')
    assert bridge._state['command_result']['status'] == 'rejected'
    bridge._goal_handle = Mock()
    command(bridge, 'cancel_mission')
    bridge._goal_handle.cancel_goal_async.assert_called_once()


def test_mapping_fields_exist_in_repository_interfaces(bridge):
    interfaces = ROOT.parent / 'hamals_interfaces/msg'
    for source in bridge._bridge_cfg['sources']:
        if not source['type'].startswith('hamals_interfaces/'):
            continue
        message = (interfaces / (source['type'].split('/')[1] + '.msg')).read_text()
        declared = {line.split()[1] for line in message.splitlines()
                    if line.strip() and not line.startswith('#') and len(line.split()) == 2}
        for field in source['fields']:
            assert field['msg_field'] in declared


def test_nonfinite_feedback_becomes_null_and_clears_previous(bridge):
    receive(bridge, '/safety/state', obstacle_distance_m=0.5)
    receive(bridge, '/safety/state', obstacle_distance_m=float('nan'))
    assert bridge._state['safety']['obstacle_distance_m'] is None
    bridge._publish_state()
    json.loads(bridge._state_pub.publish.call_args.args[0].data)


def test_mock_lift_and_estop_still_simulate(bridge):
    bridge._mode = 'mock'
    bridge._state = bridge._test_module._mock_default_state()
    bridge._mock_paused = False
    command(bridge, 'lift', action='up')
    assert bridge._state['lift']['height_pct'] == 10
    command(bridge, 'estop')
    assert bridge._state['estop']['active'] is True
    bridge._fork_pub.publish.assert_not_called()



def test_fork_auto_stale_and_missing_feedback_are_rejected(bridge):
    receive(bridge, '/switch/mode', data='manual')
    command(bridge, 'lift', action='up', state_ts=100)
    bridge._fork_pub.publish.assert_not_called()
    receive(bridge, '/fork/state', state=0)
    command(bridge, 'lift', action='up', state_ts=90)
    bridge._fork_pub.publish.assert_not_called()
    receive(bridge, '/switch/mode', data='auto')
    command(bridge, 'lift', action='stop', state_ts=100)
    bridge._fork_pub.publish.assert_not_called()


def test_action_acceptance_and_result_do_not_simulate_mission(bridge):
    handle = Mock(accepted=True)
    bridge._goal_pending = True
    bridge._mission_goal_response(Mock(result=lambda: handle))
    assert bridge._goal_handle is handle
    assert bridge._goal_pending is False
    assert bridge._state['command_result']['status'] == 'accepted'
    result = NS(result=NS(success=False, message='real action error'))
    bridge._mission_finished(Mock(result=lambda: result))
    assert bridge._goal_handle is None
    assert bridge._state['command_result']['message'] == 'real action error'
    assert bridge._state['mission']['fsm'] == 'unknown'


def test_plc_runtime_config_comes_from_parameter_response(bridge):
    bridge._plc_params = Mock()
    bridge._plc_params_pending = False
    bridge._read_plc_config()
    request = bridge._plc_params.call_async.call_args.args[0]
    assert request.names == ['transport', 'plc_ip', 'plc_port']
    callback = bridge._plc_params.call_async.return_value.add_done_callback.call_args.args[0]
    values = [NS(type=4, string_value='udp'), NS(type=4, string_value='10.100.68.144'),
              NS(type=2, integer_value=1515)]
    callback(Mock(result=lambda: NS(values=values)))
    assert bridge._state['plc']['config']['transport'] == 'udp'
    assert bridge._state['plc']['config']['port'] == 1515
    assert bridge._state['plc']['connected'] is None


def test_live_constructor_creates_real_fork_and_mission_transports(bridge):
    mod = bridge._test_module
    mod.get_package_share_directory = lambda _: str(ROOT)
    bridge.declare_parameter = Mock()
    bridge.get_parameter = lambda name: NS(
        value=8081, get_parameter_value=lambda: NS(string_value='live'))
    bridge.create_subscription = Mock()
    bridge.create_timer = Mock()
    bridge.create_client = Mock()
    mod.UIBridgeNode.__init__(bridge)
    topics = [call.args[1] for call in bridge.create_publisher.call_args_list]
    assert topics == ['/ui/state', '/fork/cmd', '/fork/is_up']
    services = [call.args[1] for call in bridge.create_client.call_args_list]
    assert '/mission/pause' in services and '/mission/resume' in services
    assert mod.ActionClient.call_args.args[2] == '/mission/execute'
    assert bridge._state['switch']['mode'] == 'unknown'
    assert bridge._state['fork'] == {}
