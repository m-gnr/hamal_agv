"""Exercise the real bridge methods and serial frames without ROS/hardware.

Load the class AST to avoid installing or globally mocking ROS message modules.
Node construction is replaced by a small state fixture; routing, deadman,
deduplication, rate limiting and serial encoding run unchanged.
"""
import ast
from pathlib import Path
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hamals_serial_bridge.protocol import encode_cmd


@pytest.fixture
def bridge():
    source = Path(__file__).parents[1] / 'hamals_serial_bridge' / 'main.py'
    tree = ast.parse(source.read_text())
    cls = next(item for item in tree.body if isinstance(item, ast.ClassDef))
    clock = SimpleNamespace(time=lambda: 100.0)
    namespace = dict(Node=object, Twist=SimpleNamespace, String=SimpleNamespace,
                     time=clock, encode_cmd=encode_cmd)
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(source), 'exec'), namespace)
    node = namespace['SerialBridgeNode'].__new__(namespace['SerialBridgeNode'])
    node.cfg = SimpleNamespace(cmd_vel_timeout_ms=500, cmd_dedup_enabled=True,
                               cmd_dedup_eps_v=0.02, cmd_dedup_eps_w=0.05,
                               cmd_force_resend_ms=300)
    node._mode = None
    node._last_cmd_time = 100.0
    node._last_cmd_send_time = 0.0
    node._deadman_active = False
    node._cmd_send_min_interval = 0.04
    node._last_sent_cmd_v = node._last_sent_cmd_w = None
    node._last_sent_cmd_time = 0.0
    node._dbg_tx = node._dbg_tx_skipped_dedup = node._dbg_tx_skipped_ratelimit = 0
    node._dbg_last_cmd = (0.0, 0.0)
    node._tx_lock = threading.Lock()
    node.ser = SimpleNamespace(is_open=True, write=Mock())
    node.clock = clock
    return node


def velocity(v=0.1):
    return SimpleNamespace(linear=SimpleNamespace(x=v), angular=SimpleNamespace(z=0.0))


def mode(node, value):
    node.mode_callback(SimpleNamespace(data=value))


def frames(node):
    return [call.args[0] for call in node.ser.write.call_args_list]


def packet(v):
    return encode_cmd(v, 0.0).encode('utf-8')


@pytest.mark.parametrize('value', [None, '', 'MANUAL', 'manual ', 'AUTO', 'invalid'])
def test_unknown_or_invalid_mode_drops_all(bridge, value):
    if value is not None:
        mode(bridge, value)
    bridge.manual_cmd_vel_callback(velocity())
    bridge.auto_cmd_vel_callback(velocity())
    assert frames(bridge) == []
    assert bridge._last_cmd_time == 100.0


@pytest.mark.parametrize('value,accepted,rejected', [
    ('manual', 'manual_cmd_vel_callback', 'auto_cmd_vel_callback'),
    ('auto', 'auto_cmd_vel_callback', 'manual_cmd_vel_callback'),
])
def test_only_selected_source_and_rejected_traffic_cannot_feed_deadman(
        bridge, value, accepted, rejected):
    mode(bridge, value)
    getattr(bridge, accepted)(velocity())
    bridge.clock.time = lambda: 100.6
    getattr(bridge, rejected)(velocity(0.9))
    assert bridge._last_cmd_time == 100.0
    bridge._check_cmd_timeout()
    bridge._check_cmd_timeout()
    assert frames(bridge) == [packet(0.1), packet(0.0)]


@pytest.mark.parametrize('initial,following', [('manual', 'auto'), ('auto', 'manual'),
                                             ('manual', 'bad'), ('auto', 'bad')])
def test_mode_change_forces_exactly_one_stop_and_does_not_replay(bridge, initial, following):
    mode(bridge, initial)
    getattr(bridge, initial + '_cmd_vel_callback')(velocity())
    mode(bridge, following)
    mode(bridge, following)
    bridge._check_cmd_timeout()
    assert frames(bridge) == [packet(0.1), packet(0.0)]
    getattr(bridge, initial + '_cmd_vel_callback')(velocity(0.9))
    assert frames(bridge) == [packet(0.1), packet(0.0)]
    if following in ('manual', 'auto'):
        getattr(bridge, following + '_cmd_vel_callback')(velocity(0.2))
        assert frames(bridge)[-1] == packet(0.2)


def test_repeated_mode_dedup_rate_limit_and_force_resend(bridge):
    mode(bridge, 'manual')
    bridge.manual_cmd_vel_callback(velocity())
    mode(bridge, 'manual')
    bridge.manual_cmd_vel_callback(velocity())
    bridge.manual_cmd_vel_callback(velocity(0.2))
    assert frames(bridge) == [packet(0.1)]
    assert bridge._dbg_tx_skipped_dedup == 1
    assert bridge._dbg_tx_skipped_ratelimit == 1
    bridge.clock.time = lambda: 100.31
    bridge.manual_cmd_vel_callback(velocity())
    assert frames(bridge) == [packet(0.1), packet(0.1)]


def test_mode_stop_bypasses_dedup_even_if_already_stopped(bridge):
    mode(bridge, 'manual')
    bridge.manual_cmd_vel_callback(velocity(0.0))
    mode(bridge, 'auto')
    assert frames(bridge) == [packet(0.0), packet(0.0)]


@pytest.mark.parametrize('initial,following', [('manual', 'auto'), ('auto', 'manual')])
def test_first_command_after_switch_rearms_deadman_without_intermediate_timer(
        bridge, initial, following):
    mode(bridge, initial)
    mode(bridge, following)
    getattr(bridge, following + '_cmd_vel_callback')(velocity())
    # The executor may be delayed beyond the timeout before its next timer.
    bridge.clock.time = lambda: 100.6
    bridge._check_cmd_timeout()
    bridge._check_cmd_timeout()
    assert frames(bridge) == [packet(0.0), packet(0.1), packet(0.0)]


@pytest.mark.parametrize('selected,rejected', [('manual', 'auto'), ('auto', 'manual')])
@pytest.mark.parametrize('after_timeout', [False, True])
def test_rejected_command_preserves_all_accepted_command_state(
        bridge, selected, rejected, after_timeout):
    mode(bridge, selected)
    getattr(bridge, selected + '_cmd_vel_callback')(velocity())
    bridge.clock.time = lambda: 100.6
    if after_timeout:
        bridge._check_cmd_timeout()
    fields = ('_last_cmd_time', '_deadman_active', '_last_cmd_send_time',
              '_last_sent_cmd_v', '_last_sent_cmd_w', '_last_sent_cmd_time',
              '_dbg_last_cmd', '_dbg_tx', '_dbg_tx_skipped_dedup',
              '_dbg_tx_skipped_ratelimit')
    before = {name: getattr(bridge, name) for name in fields}
    sent = frames(bridge)
    getattr(bridge, rejected + '_cmd_vel_callback')(velocity(0.9))
    assert {name: getattr(bridge, name) for name in fields} == before
    assert frames(bridge) == sent
