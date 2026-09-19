"""State lifecycle tests using production methods and the deterministic ROS stub."""
from types import SimpleNamespace as NS

import pytest

from test_dropoff_escape import docking


def initialized():
    node, goal, clock = docking()
    publishers = {"/cmd_vel/docking": node.cmd_pub,
                  "/docking/dropoff_escape_active": node.dropoff_escape_pub}
    node.create_publisher = lambda typ, topic, depth: publishers.setdefault(
        topic, NS(publish=lambda msg: None, depth=depth))
    node.create_subscription = lambda *a, **kw: None
    node.declare_parameter = lambda name, default: NS(value=default)
    node.create_timer = lambda period, callback, **kw: NS(
        period=period, callback=callback, **kw)
    node.__init__()
    node.line_flags = []
    node.logs = []
    node.line_follow_active_pub.publish = lambda msg: node.line_flags.append(msg.data)
    node.get_logger = lambda: NS(info=node.logs.append, error=node.logs.append)
    node.line_detected = True
    node.line_last_seen = clock.now
    node.odom_last_seen = clock.now
    return node, goal, clock, publishers


def test_initial_state_and_change_only_publication():
    n, _, _, pubs = initialized()
    assert n.line_follow_active is False
    assert pubs['/docking/line_follow_active'].depth == 1
    with n.lock:  # Reentrant use matches existing state locking.
        for value in (False, True, True, False, False):
            n.set_line_follow_active(value)
    assert n.line_flags == [True, False]
    assert n.logs == ['LINE FOLLOW ACTIVE ON', 'LINE FOLLOW ACTIVE OFF']


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('exit_kind', ['success', 'cancel', 'timeout', 'exception', 'shutdown'])
def test_line_follow_lifecycle(reverse, exit_kind):
    n, g, clock, _ = initialized()
    n.timeout_sec = n.dropoff_timeout_sec = 0.1

    def tick():
        assert n.line_follow_active is True
        n.odom_last_seen = clock.now
        if exit_kind == 'success':
            n.odom_x += 2.0
            n.mz80_detected = True
        elif exit_kind == 'cancel':
            g.is_cancel_requested = True
        elif exit_kind == 'exception':
            clock.tick = lambda: None
            raise RuntimeError('injected failure')
        elif exit_kind == 'shutdown':
            clock.running = False

    # Stop sleeps are unrelated to controller progress.
    n.stop_robot = lambda: None
    clock.tick = tick
    follow = lambda: n.follow_reverse_line(g) if reverse else n.follow_line(g, 'pickup')
    if exit_kind == 'exception':
        with pytest.raises(RuntimeError, match='injected failure'):
            follow()
    else:
        assert follow()[0] is (exit_kind == 'success')
    assert n.line_flags == [True, False]
    assert n.line_follow_active is False


def test_pickup_nudge_is_not_line_follow():
    n, g, clock, _ = initialized()
    n.pickup_arm_time_s = 0.0
    n.line_detected = False
    n.odom_linear_x = 1.0
    seen = []

    def tick():
        n.odom_last_seen = clock.now
        if n.commands and n.commands[-1].linear.x == n.pickup_nudge_speed:
            seen.append(n.line_follow_active)

    clock.tick = tick
    assert n.follow_line(g, 'pickup')[0]
    assert seen and not any(seen)
    assert n.line_flags == [True, False]


def test_line_lost_normal_exit():
    n, g, _, _ = initialized()
    n.line_detected = False
    n.dropoff_lost_grace_s = 0.0
    assert n.follow_line(g, 'dropoff')[0]
    assert n.line_flags == [True, False]


def test_reverse_then_rotation_and_escape_stay_false():
    n, g, clock, _ = initialized()
    g.request.operation = 'dropoff'
    rotation_states = []
    escape_states = []

    def tick():
        n.odom_last_seen = clock.now
        n.odom_angular_z = 10.0
        if n.commands:
            cmd = n.commands[-1]
            if cmd.linear.x < 0:
                n.odom_x -= 0.2
                if n.dropoff_escape_active:
                    escape_states.append(n.line_follow_active)
            if cmd.angular.z > 0:
                rotation_states.append(n.line_follow_active)

    clock.tick = tick
    assert n.execute_callback(g).success
    assert rotation_states and not any(rotation_states)
    assert n.line_flags == [True, False]
    g.request.operation = 'dropoff_escape'
    assert n.execute_callback(g).success
    assert escape_states and not any(escape_states)
    assert n.line_flags == [True, False]


@pytest.mark.parametrize('closed', [False, True])
def test_destroy_clears_state_even_with_closed_publisher(closed):
    n, _, _, _ = initialized()
    n.set_line_follow_active(True)
    if closed:
        def publish(msg):
            raise RuntimeError('publisher closed')
        n.line_follow_active_pub.publish = publish
    n.destroy_node()
    assert n.line_follow_active is False
    assert n.destroyed
    if not closed:
        assert n.line_flags == [True, False]
    n.set_line_follow_active(True)
    assert n.line_follow_active is False


def test_heartbeat_active_only_and_no_log_spam():
    n, _, _, _ = initialized()
    timer = n.line_follow_heartbeat_timer
    assert timer.period == pytest.approx(0.1)
    assert timer.clock.clock_type == "steady"
    timer.callback()
    assert n.line_flags == []
    n.set_line_follow_active(True)
    for _ in range(5):
        timer.callback()
    assert n.line_flags == [True] * 6
    assert n.logs == ['LINE FOLLOW ACTIVE ON']
    n.set_line_follow_active(False)
    timer.callback()
    assert n.line_flags == [True] * 6 + [False]
    assert n.logs == ['LINE FOLLOW ACTIVE ON', 'LINE FOLLOW ACTIVE OFF']


def test_shutdown_suppresses_heartbeat_even_if_state_was_true():
    n, _, _, _ = initialized()
    n.set_line_follow_active(True)
    n.shutting_down = True
    n.line_follow_heartbeat_timer.callback()
    assert n.line_flags == [True]
    n.destroy_node()
    n.line_follow_heartbeat_timer.callback()
    assert n.line_flags == [True, False]
