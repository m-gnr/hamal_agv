"""Post-release escape orchestration tests using the existing ROS-free fixture."""
from types import SimpleNamespace as NS

import pytest

from test_plc_pause import mission, Fork, State


def test_dropoff_escape_only_after_release():
    n = mission()
    steps = []
    # Keep the existing pre-release docking rotation inside the dropoff action.
    n._switch_camera = lambda **kw: None
    n._confirm_door_qr = lambda *args: None
    n._dock = lambda station, op: steps.append(op)
    Fork.DOWN, Fork.AT_BOTTOM = 6, 7
    n._move_fork = lambda command, state, phase: steps.append(phase)
    n._dropoff_custom(NS(expected_qr='D4'), 'D4', True)
    assert steps == ['dropoff', 'LOWER_LOAD', 'dropoff_escape']
    assert n._mctx.carrying_load is False


def test_failed_release_never_starts_escape():
    import pytest
    n = mission()
    steps = []
    n._switch_camera = lambda **kw: None
    n._confirm_door_qr = lambda *args: None
    n._dock = lambda station, op: steps.append(op)
    Fork.DOWN, Fork.AT_BOTTOM = 6, 7

    def failed(*args):
        raise RuntimeError('fork did not lower')

    n._move_fork = failed
    with pytest.raises(RuntimeError, match='fork did not lower'):
        n._dropoff_custom(NS(expected_qr='D4'), 'D4', True)
    assert steps == ['dropoff']


def test_escape_can_arm_during_obstacle_but_cannot_override_cancel():
    n = mission()
    State.OBSTACLE = 1
    n._safety.state = State.OBSTACLE
    n._safety.motion_allowed = False
    n._wait_ready(arm_dropoff_escape=True)
    assert n._mctx.top_state == State.EXECUTING
    # Cancel remains effective even on the special arming path.
    import pytest
    n._cancel = True
    with pytest.raises(RuntimeError, match='canceled'):
        n._wait_ready(arm_dropoff_escape=True)


@pytest.mark.parametrize('hold', ['estop', 'stale', 'manual', 'resume'])
def test_escape_arming_preserves_other_holds(hold, monkeypatch):
    n = mission()
    State.OBSTACLE = 1
    n._safety.state = State.OBSTACLE
    n._safety.motion_allowed = False
    if hold == 'estop':
        n._safety.estop_active = True
    elif hold == 'stale':
        n._safety.state = State.SENSOR_STALE
    elif hold == 'manual':
        n._safety.manual_mode = True
    else:
        n._manual_resume_required = True
    # A held path must wait, not return permission. End that wait with cancel.
    monkeypatch.setattr(n._wait_ready.__globals__['time'], 'sleep',
                        lambda _: setattr(n, '_cancel', True))
    with pytest.raises(RuntimeError):
        n._wait_ready(arm_dropoff_escape=True)


def test_escape_action_is_canceled_when_mission_wait_fails():
    n = mission()
    canceled = []
    handle = NS(accepted=True, get_result_async=lambda: 'result',
                cancel_goal_async=lambda: canceled.append(True))
    n._wait_ready = lambda **kw: None
    n.dock_client = NS(wait_for_server=lambda **kw: True,
                       send_goal_async=lambda goal: 'sent')

    def wait(future, *args):
        if future == 'sent':
            return handle
        raise RuntimeError('mission canceled')

    n._wait_future = wait
    n._wait_dock_result = lambda future, *a, **kw: wait(future)
    with pytest.raises(RuntimeError, match='mission canceled'):
        n._dock(NS(id='D4', expected_qr='D4', docking_profile='standard'), 'dropoff_escape')
    assert canceled == [True]
