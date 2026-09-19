"""Regression checks execute production callbacks, command publishing and fork wait."""
from types import SimpleNamespace as NS

import pytest

from test_plc_pause import mission


class Fork:
    STOP, UP, DOWN = 0, 1, 2
    AT_TOP, AT_BOTTOM, MOVING, ERROR = 3, 4, 5, 6
    ERROR_TOP_TIMEOUT, ERROR_BOTTOM_TIMEOUT = 7, 8

    def __init__(self):
        self.command = self.STOP


def setup_fork(command=Fork.DOWN):
    node = mission()
    clock = NS(now=10.0, sent=False, polls=0, on_sleep=lambda _: None)
    node._fork_state_seq = 10
    node._fork_state_last_seen = clock.now
    target = Fork.AT_BOTTOM if command == Fork.DOWN else Fork.AT_TOP
    node._fork_state = NS(state=target, lower_limit=True, error_code=0)
    node._wait_ready = lambda: None
    node._set_phase = lambda *args: None
    node.get_parameter = lambda key: NS(value={
        'fork_timeout_sec': 2.0, 'fork_state_timeout_sec': .5}[key])
    node.logs = []
    node.get_logger = lambda: NS(info=node.logs.append, warning=node.logs.append)
    node.sent = []

    def publish(msg):
        node.sent.append(msg.command)
        if msg.command == command:
            clock.sent = True

    def sleep(dt):
        clock.now += dt
        if clock.sent:
            clock.polls += 1
        clock.on_sleep(dt)

    node.fork_pub = NS(publish=publish)
    ns = node._move_fork.__globals__
    ns['time'] = NS(monotonic=lambda: clock.now, sleep=sleep)
    ns['ForkCommand'] = ns['ForkState'] = Fork
    return node, clock, target


def receive(node, state=Fork.AT_BOTTOM, lower=True):
    node._fork_received(NS(state=state, lower_limit=lower, error_code=0))


def test_cached_bottom_without_any_new_message_times_out():
    n, c, target = setup_fork()
    with pytest.raises(RuntimeError, match='LOWER_LOAD timeout'):
        n._move_fork(Fork.DOWN, target, 'LOWER_LOAD')
    assert n._fork_state_seq == 10
    assert c.now >= 12.5
    assert not any('CONFIRMED' in log for log in n.logs)


def test_new_valid_bottom_accepted():
    n, c, target = setup_fork()
    c.on_sleep = lambda _: receive(n) if c.sent and c.polls == 1 else None
    n._move_fork(Fork.DOWN, target, 'LOWER_LOAD')
    assert n._fork_state_seq == 11
    assert n._fork_state_last_seen == c.now
    assert n.sent == [Fork.STOP, Fork.DOWN, Fork.STOP]


@pytest.mark.parametrize('kind', ['lower_false', 'stale', 'moving'])
def test_new_invalid_bottom_does_not_complete(kind):
    n, c, target = setup_fork()

    def event(_):
        if c.sent and c.polls == 1:
            receive(n, Fork.MOVING if kind == 'moving' else Fork.AT_BOTTOM,
                    lower=kind != 'lower_false')
            if kind == 'stale':
                # The production callback received a message, but it aged before polling.
                c.now += .6

    c.on_sleep = event
    with pytest.raises(RuntimeError, match='LOWER_LOAD timeout'):
        n._move_fork(Fork.DOWN, target, 'LOWER_LOAD')
    assert n._fork_state_seq == 11
    if kind == 'lower_false':
        assert any('REJECTED' in log for log in n.logs)


def test_moving_then_valid_bottom_completes_only_on_second_message():
    n, c, target = setup_fork()

    def event(_):
        if c.sent and c.polls in (1, 2):
            receive(n, Fork.MOVING if c.polls == 1 else Fork.AT_BOTTOM)

    c.on_sleep = event
    n._move_fork(Fork.DOWN, target, 'LOWER_LOAD')
    assert c.polls == 2 and n._fork_state_seq == 12


@pytest.mark.parametrize('new_message', [False, True])
def test_up_requires_new_fresh_state_without_changing_target_semantics(new_message):
    n, c, target = setup_fork(Fork.UP)
    if new_message:
        c.on_sleep = lambda _: receive(n, Fork.AT_TOP, False) if c.sent and c.polls == 1 else None
        n._move_fork(Fork.UP, target, 'LIFT_LOAD')
        assert n.sent[-1] == Fork.STOP
    else:
        with pytest.raises(RuntimeError, match='LIFT_LOAD timeout'):
            n._move_fork(Fork.UP, target, 'LIFT_LOAD')


def test_state_received_during_stop_delay_cannot_confirm_down():
    n, c, target = setup_fork()
    c.on_sleep = lambda _: receive(n) if not c.sent else None
    with pytest.raises(RuntimeError, match='LOWER_LOAD timeout'):
        n._move_fork(Fork.DOWN, target, 'LOWER_LOAD')
    assert n._fork_state_seq == 11
    assert any('start_seq=11' in log for log in n.logs)


def test_retry_takes_a_new_sequence_boundary():
    n, c, target = setup_fork()
    retried = False

    def event(_):
        nonlocal retried
        if c.polls == 1 and not retried:
            n._fork_received(NS(state=Fork.ERROR, lower_limit=False,
                                error_code=Fork.ERROR_BOTTOM_TIMEOUT))
            retried = True
        elif c.polls == 2:
            # Arrives during the retry's STOP delay, before its DOWN publish.
            receive(n)

    c.on_sleep = event
    with pytest.raises(RuntimeError, match='LOWER_LOAD timeout'):
        n._move_fork(Fork.DOWN, target, 'LOWER_LOAD')
    assert n.sent.count(Fork.DOWN) == 2
