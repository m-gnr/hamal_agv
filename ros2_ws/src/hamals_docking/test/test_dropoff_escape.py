"""Exercise production docking methods with deterministic odometry and clock, no ROS."""
import ast
import math
from pathlib import Path
import threading
from types import SimpleNamespace as NS

import pytest


class Twist:
    def __init__(self):
        self.linear = NS(x=0.0)
        self.angular = NS(z=0.0)


def docking():
    path = Path(__file__).resolve().parents[1] / 'hamals_docking/docking_node.py'
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    class Node:
        def __init__(self, name):
            pass

        def destroy_node(self):
            self.destroyed = True

    cls.bases = [ast.Name(id='Node', ctx=ast.Load())]
    clock = NS(now=10.0, tick=lambda: None, running=True)

    def sleep(dt):
        clock.now += dt
        clock.tick()

    ns = dict(Node=Node, ReentrantCallbackGroup=lambda: None,
              Clock=lambda **kw: NS(**kw), ClockType=NS(STEADY_TIME="steady"),
              ActionServer=lambda *a, **kw: None, Odometry=object, Int32=object,
              math=math, threading=threading, Twist=Twist, Bool=lambda **kw: NS(**kw),
              time=NS(monotonic=lambda: clock.now, sleep=sleep),
              rclpy=NS(ok=lambda: clock.running), Dock=NS(Result=lambda **kw: NS(**kw)))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                 str(path), 'exec'), ns)
    node = object.__new__(ns['DockingNode'])
    node.lock = threading.RLock()
    node.odom_x = 3.0
    node.odom_y = 4.0
    node.odom_last_seen = clock.now
    node.odom_timeout_sec = 0.5
    node.dropoff_escape_enabled = True
    node.dropoff_escape_distance_m = 0.5
    node.dropoff_escape_speed_mps = 0.08
    node.dropoff_escape_timeout_sec = 8.0
    node.dropoff_escape_active = False
    node.line_follow_active = False
    node.line_flags = []
    node.line_follow_active_pub = NS(publish=lambda msg: node.line_flags.append(msg.data))
    node.shutting_down = False
    node.action_running = True
    node.active = False
    node.get_logger = lambda: NS(info=lambda *_: None, error=lambda *_: None)
    node.commands, node.flags, node.events = [], [], []
    node.cmd_pub = NS(publish=lambda msg: (node.commands.append(msg),
                                          node.events.append(('cmd', msg.linear.x))))
    node.dropoff_escape_pub = NS(publish=lambda msg: (node.flags.append(msg.data),
                                                     node.events.append(('mask', msg.data))))
    goal = NS(is_cancel_requested=False, request=NS(operation='dropoff_escape', station_id='D4'),
              outcome=None)
    for status in ('succeed', 'abort', 'canceled'):
        setattr(goal, status, lambda status=status: setattr(goal, 'outcome', status))
    return node, goal, clock


def assert_stopped(node):
    assert node.commands[-1].linear.x == 0.0
    assert node.commands[-1].angular.z == 0.0
    assert node.flags[-1] is False
    assert node.dropoff_escape_active is False


def test_displacement_and_straight_reverse_heartbeat():
    n, g, clock = docking()

    def move():
        if n.commands and n.commands[-1].linear.x < 0:
            # A 3-4-5 displacement checks both axes, not velocity integration.
            n.odom_x -= 0.003
            n.odom_y -= 0.004
            n.odom_last_seen = clock.now

    clock.tick = move
    assert n.drive_reverse_odom(g, .50, .08)[0]
    moving = [c for c in n.commands if c.linear.x]
    assert moving and all(c.linear.x == -.08 and c.angular.z == 0 for c in moving)
    assert math.hypot(n.odom_x - 3, n.odom_y - 4) >= .5
    assert len([v for v in n.flags if v]) == len(moving)
    assert n.events[0] == ('mask', True)
    assert n.events[-2:] == [('cmd', 0.0), ('mask', False)]
    assert_stopped(n)


@pytest.mark.parametrize('failure', ['missing', 'stale', 'cancel', 'timeout', 'exception', 'shutdown', 'nan'])
def test_failures_abort_action_and_clear_mask(failure):
    n, g, clock = docking()
    if failure == 'missing':
        n.odom_last_seen = None

    def tick():
        if failure != 'stale':
            n.odom_last_seen = clock.now
        if failure == 'cancel':
            g.is_cancel_requested = True
        elif failure == 'exception' and any(n.flags):
            clock.tick = lambda: None
            raise RuntimeError('injected failure')
        elif failure == 'shutdown':
            clock.running = False
        elif failure == 'nan':
            n.odom_x = float('nan')

    clock.tick = tick
    result = n.execute_callback(g)
    assert not result.success
    assert g.outcome == ('canceled' if failure == 'cancel' else 'abort')
    assert_stopped(n)
    if failure == 'missing':
        assert not any(n.flags) and not any(c.linear.x for c in n.commands)


def test_disabled_does_not_move_or_arm():
    n, g, _ = docking()
    n.dropoff_escape_enabled = False
    assert n.execute_callback(g).success
    assert not any(n.flags)
    assert not any(c.linear.x or c.angular.z for c in n.commands)


@pytest.mark.parametrize('operation, expected', [('pickup', ['pickup']), ('dropoff', ['line', 'rotate'])])
def test_existing_actions_keep_their_sequence(operation, expected):
    n, g, _ = docking()
    calls = []
    g.request.operation = operation
    n.follow_line = lambda goal, op: (calls.append(op) is None, 'ok')
    n.follow_reverse_line = lambda goal: (calls.append('line') is None, 'ok')
    n.rotate_dropoff_180 = lambda goal: (calls.append('rotate') is None, 'ok')
    n.drive_reverse_odom = lambda *args: pytest.fail('escape before release')
    assert n.execute_callback(g).success
    assert calls == expected
