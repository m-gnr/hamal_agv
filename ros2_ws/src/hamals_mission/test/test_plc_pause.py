"""ROS-free checks against the mission coordinator's production methods."""

import ast
from pathlib import Path
import threading
import time
from types import SimpleNamespace as NS


class State:
    EXECUTING, WAITING_PLC, PAUSED_MANUAL = 2, 3, 5
    EMERGENCY_STOP, PAUSED_OBSTACLE, PAUSED_PLC = 7, 4, 8
    SENSOR_STALE = 9


class Fork:
    STOP, UP, AT_TOP, ERROR = 0, 1, 2, 3
    ERROR_TOP_TIMEOUT, ERROR_BOTTOM_TIMEOUT = 4, 5

    def __init__(self):
        self.command = None


class Twist:
    def __init__(self):
        self.linear = NS(x=0.0)
        self.angular = NS(z=0.0)


def mission():
    path = Path(__file__).resolve().parents[1] / 'hamals_mission/mission_node.py'
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MissionNode')
    cls.bases = []
    ns = dict(time=time, threading=threading, MissionState=State,
              rclpy=NS(ok=lambda: True),
              SafetyState=State, ForkCommand=Fork, ForkState=Fork, Twist=Twist,
              MissionFailure=RuntimeError, NavigateToPose=NS(Goal=lambda: NS(pose=None)),
              Dock=NS(Goal=lambda: NS(station_id='', operation='', expected_qr='', profile='')),
              PoseStamped=lambda: NS(header=NS(frame_id='', stamp=None),
                                     pose=NS(position=NS(x=0, y=0),
                                             orientation=NS(z=0, w=1))))
    import math
    ns['math'] = math
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                 str(path), 'exec'), ns)
    n = object.__new__(ns['MissionNode'])
    n._lock = threading.RLock()
    n._mctx = NS(top_state=State.EXECUTING, pause_reason='', phase='', message='',
                 active_target='', carrying_load=False, retry_count=0, verified_qr='')
    n._safety = NS(estop_active=False, state=0, manual_mode=False,
                   motion_allowed=True, reason='')
    n._manual_resume_required = n._plc_pause_required = n._cancel = False
    n._plc_pause_generation = 0
    n.cmd_pub = NS(messages=[], publish=lambda msg: n.cmd_pub.messages.append(msg))
    n.fork_pub = NS(messages=[], publish=lambda msg: n.fork_pub.messages.append(msg))
    n.get_parameter = lambda key: NS(value={
        'reverse_when_loaded': True, 'max_nav_retries': 1, 'nav_timeout_sec': 5.,
        'fork_timeout_sec': 2., 'dock_timeout_sec': 5.,
        'line_follow_speed': .1, 'line_follow_gain': .05,
        'line_follow_deadband_px': 18., 'line_follow_smoothing': .35,
        'line_follow_max_turn': .45, 'line_follow_invert': True,
        'line_follow_lost_sec': 1., 'qr_search_angular_speed': .3}[key])
    n.get_clock = lambda: NS(now=lambda: NS(to_msg=lambda: None))
    n.get_logger = lambda: NS(info=lambda *_: None)
    n._publish_state = lambda: None
    return n


def test_plc_resume_preserves_manual_and_safety_holds():
    n = mission()
    n._plc_pause_required = True
    n._manual_resume_required = True
    response = NS(success=False, message='')
    n._plc_resume(None, response)
    assert response.success and n._mctx.top_state == State.PAUSED_MANUAL
    n._manual_resume_required = False
    n._safety.motion_allowed = False
    n._plc_pause_required = True
    n._plc_resume(None, response)
    assert n._mctx.top_state == State.PAUSED_OBSTACLE
    n._safety.estop_active = True
    n._plc_pause_required = True
    response = NS(success=False, message='')
    n._plc_resume(None, response)
    assert not response.success and n._plc_pause_required


def test_nav_cancels_and_resends_same_target():
    n = mission()
    sent_poses = []
    canceled = []

    class ResultFuture:
        def __init__(self, first):
            self.first = first
            self.checked = False

        def done(self):
            if self.first and not self.checked:
                self.checked = True
                n._plc_pause_generation += 1
                n._plc_pause_required = True
                return False
            return True

        def result(self):
            return NS(status=4)

    class Handle:
        accepted = True

        def __init__(self, first):
            self.future = ResultFuture(first)

        def get_result_async(self):
            return self.future

    def send(goal):
        sent_poses.append((goal.pose.pose.position.x, goal.pose.pose.position.y))
        return Handle(len(sent_poses) == 1)

    n.nav_client = NS(wait_for_server=lambda **_: True, send_goal_async=send)
    n._wait_future = lambda future, *_: future
    n._wait_ready = lambda: setattr(n, '_plc_pause_required', False)
    n._cancel_for_plc = lambda handle, future, label: canceled.append(label)
    n._set_phase = lambda *_: None
    assert n._navigate('A1', NS(x=1.2, y=3.4, theta=0)) is False
    assert sent_poses == [(1.2, 3.4), (1.2, 3.4)]
    assert canceled == ['Nav2'] and n._mctx.retry_count == 0


def test_dock_cancel_acknowledged_before_restart():
    n = mission()
    order = []

    class Future:
        def __init__(self, first):
            self.first = first
            self.checked = False

        def done(self):
            if self.first and not self.checked:
                self.checked = True
                n._plc_pause_generation += 1
                return False
            return True

        def result(self):
            return NS(status=4, result=NS(success=True))

    class Handle:
        accepted = True

        def __init__(self, first):
            self.future = Future(first)

        def get_result_async(self):
            return self.future

        def cancel_goal_async(self):
            order.append('cancel')
            return NS(goals_canceling=[self])

    def send(_goal):
        order.append('send')
        return Handle(order.count('send') == 1)

    n.dock_client = NS(wait_for_server=lambda **_: True, send_goal_async=send)
    n._wait_future = lambda future, *_: future
    n._wait_ready = lambda: 0
    n._set_phase = lambda *_: None
    n._dock(NS(id='A1', expected_qr='A1', docking_profile='standard'), 'pickup')
    assert order == ['send', 'cancel', 'send']
    assert n._mctx.verified_qr == 'A1'


def test_fork_stop_then_resume_command():
    n = mission()
    n._fork_state = NS(state=0)
    sent = []
    n._set_phase = lambda *_: None
    n._wait_ready = lambda: 0
    n._send_fork = lambda cmd: (sent.append(cmd), setattr(n._fork_state, 'state', Fork.AT_TOP)
                                 if len(sent) == 2 else None)
    checks = iter((False, True))
    n._wait_ready_state = lambda: next(checks, True)
    n._move_fork(Fork.UP, Fork.AT_TOP, 'LIFT_LOAD')
    assert sent == [Fork.UP, Fork.UP]
    assert [m.command for m in n.fork_pub.messages] == [Fork.STOP, Fork.STOP]


def test_line_follow_stops_and_continues():
    n = mission()
    n._cancel = False
    n._qr_text = 'BASLA'
    n._line_detected = True
    n._line_last_seen = time.monotonic()
    n._line_error = 0
    n._stop_cmd = lambda: n.cmd_pub.publish(Twist())
    n._plc_pause_required = True
    n._wait_ready = lambda: setattr(n, '_plc_pause_required', False) or .01
    n._qr_seen = lambda _: len(n.cmd_pub.messages) > 1
    assert n._line_follow_until_qr('BASLA', time.monotonic() + 1.)
    assert n.cmd_pub.messages[0].linear.x == 0
    assert any(m.linear.x > 0 for m in n.cmd_pub.messages)
    assert n.cmd_pub.messages[-1].linear.x == 0


def test_odom_drive_and_rotation_observe_plc_hold():
    n = mission()
    n._stop_cmd = lambda: n.cmd_pub.publish(Twist())
    n._plc_pause_required = True
    n._wait_ready = lambda: setattr(n, '_plc_pause_required', False) or .01
    n._odom_last_seen = time.monotonic()
    n._odom_linear_x = .1
    n._drive_distance_by_odom(.005, .1, timeout_sec=.3)
    assert n.cmd_pub.messages[0].linear.x == 0
    assert any(m.linear.x > 0 for m in n.cmd_pub.messages)
    n.cmd_pub.messages.clear()
    n._plc_pause_required = True
    n._qr_seen = lambda _: any(m.angular.z > 0 for m in n.cmd_pub.messages)
    assert n._rotate_rel(.1, 'QR')
    assert n.cmd_pub.messages[0].angular.z == 0
    assert any(m.angular.z > 0 for m in n.cmd_pub.messages)
