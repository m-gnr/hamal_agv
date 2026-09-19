"""PLC hold must preserve a docking action's relative progress, with no ROS."""
from types import SimpleNamespace as NS

import pytest

from test_dropoff_escape import docking, assert_stopped
from test_line_follow_active import initialized


def test_escape_wait_longer_than_timeout_preserves_remaining_distance():
    n, goal, clock = docking()
    paused = False
    released = False
    hold_started = None

    def tick():
        nonlocal paused, released, hold_started
        n.odom_last_seen = clock.now
        if n.commands and n.commands[-1].linear.x < 0:
            assert not n._mission_hold
            n.odom_x -= .005
        if not paused and n.odom_x <= 2.9:
            paused = True
            hold_started = clock.now
            n._mission_state_received(NS(state=8))
        elif paused and not released:
            assert n.commands[-1].linear.x == 0
            if clock.now - hold_started > 10.:  # Longer than the 8s motion timeout.
                released = True
                n._mission_state_received(NS(state=2))

    clock.tick = tick
    assert n.drive_reverse_odom(goal, .5, .08)[0]
    assert paused and released
    assert .5 <= 3. - n.odom_x < .511
    assert_stopped(n)


@pytest.mark.parametrize('method', ['drive_forward_odom', 'rotate_dropoff_180'])
def test_integrated_motion_does_not_count_paused_interval(method):
    n, goal, clock, _ = initialized()
    n.action_running = True
    n.odom_linear_x = .1
    n.odom_angular_z = 1.
    n.stop_robot = lambda: n.cmd_pub.publish(NS(linear=NS(x=0.), angular=NS(z=0.)))
    paused = released = False
    moving_ticks = 0
    hold_started = None

    def tick():
        nonlocal paused, released, moving_ticks, hold_started
        n.odom_last_seen = clock.now
        cmd = n.commands[-1] if n.commands else None
        moving = cmd and (cmd.linear.x or cmd.angular.z)
        if moving:
            assert not n._mission_hold
            moving_ticks += 1
        if moving_ticks >= 3 and not paused:
            paused = True
            hold_started = clock.now
            n._mission_state_received(NS(state=8))
        elif paused and not released and clock.now - hold_started > 10.:
            released = True
            n._mission_state_received(NS(state=2))

    clock.tick = tick
    if method == 'drive_forward_odom':
        assert n.drive_forward_odom(goal, .10, .1)
        assert moving_ticks >= 19
    else:
        assert n.rotate_dropoff_180(goal)[0]
        assert moving_ticks >= 62
    assert paused and released


def test_cancel_during_plc_hold_still_terminates_action():
    n, goal, clock = docking()
    n._mission_state_received(NS(state=8))
    clock.tick = lambda: setattr(goal, 'is_cancel_requested', True)
    assert not n.drive_reverse_odom(goal, .5, .08)[0]
    assert all(cmd.linear.x == 0 for cmd in n.commands)
    assert_stopped(n)


def test_manual_hold_after_plc_resume_cannot_restart_docking():
    n, goal, clock = docking()
    n._mission_state_received(NS(state=8))
    n._mission_state_received(NS(state=5))
    n._publish_motion(NS(linear=NS(x=.1), angular=NS(z=0)))
    assert n.commands[-1].linear.x == 0
    n._mission_state_received(NS(state=2))
    n._publish_motion(NS(linear=NS(x=.1), angular=NS(z=0)))
    assert n.commands[-1].linear.x == .1
