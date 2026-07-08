import time

from hamals_interfaces.msg import ForkCommand, ForkState
from hamals_fork.fork_controller import ForkController


def make_mcu_state(**overrides):
    msg = ForkState()
    msg.t_us = overrides.get("t_us", 123)
    msg.state = overrides.get("state", ForkState.IDLE)
    msg.last_command = overrides.get("last_command", ForkState.CMD_NONE)
    msg.error_code = overrides.get("error_code", ForkState.ERROR_NONE)
    msg.is_moving = overrides.get("is_moving", False)
    msg.upper_limit = overrides.get("upper_limit", False)
    msg.lower_limit = overrides.get("lower_limit", False)
    return msg


def test_stop_command_returns_stop_and_sets_last_command():
    controller = ForkController(mcu_state_timeout_ms=1000)

    assert controller.handle_command(ForkCommand.STOP) == "STOP"
    assert controller.last_command == ForkState.CMD_STOP
    assert controller.state == ForkState.IDLE
    assert controller.error_code == ForkState.ERROR_NONE


def test_up_command_returns_up_and_sets_last_command():
    controller = ForkController(mcu_state_timeout_ms=1000)

    assert controller.handle_command(ForkCommand.UP) == "UP"
    assert controller.last_command == ForkState.CMD_UP


def test_down_command_returns_down_and_sets_last_command():
    controller = ForkController(mcu_state_timeout_ms=1000)

    assert controller.handle_command(ForkCommand.DOWN) == "DOWN"
    assert controller.last_command == ForkState.CMD_DOWN


def test_invalid_command_sets_error_and_returns_none():
    controller = ForkController(mcu_state_timeout_ms=1000)

    assert controller.handle_command(99) is None
    assert controller.state == ForkState.ERROR
    assert controller.error_code == ForkState.ERROR_INVALID_COMMAND
    assert controller.is_moving is False


def test_update_before_first_mcu_state_does_not_timeout():
    controller = ForkController(mcu_state_timeout_ms=1)

    time.sleep(0.002)
    controller.update()

    assert controller.state == ForkState.IDLE
    assert controller.error_code == ForkState.ERROR_NONE


def test_update_after_mcu_state_times_out():
    controller = ForkController(mcu_state_timeout_ms=1)
    controller.update_from_mcu_state(make_mcu_state(state=ForkState.MOVING_UP))

    time.sleep(0.002)
    controller.update()

    assert controller.state == ForkState.ERROR
    assert controller.error_code == ForkState.ERROR_MCU_TIMEOUT
    assert controller.is_moving is False


def test_error_rejects_up_and_down():
    controller = ForkController(mcu_state_timeout_ms=1000)
    controller.handle_command(99)

    assert controller.handle_command(ForkCommand.UP) is None
    assert controller.state == ForkState.ERROR
    assert controller.error_code == ForkState.ERROR_INVALID_COMMAND

    assert controller.handle_command(ForkCommand.DOWN) is None
    assert controller.state == ForkState.ERROR
    assert controller.error_code == ForkState.ERROR_INVALID_COMMAND


def test_error_accepts_stop_and_clears_error():
    controller = ForkController(mcu_state_timeout_ms=1000)
    controller.handle_command(99)

    assert controller.handle_command(ForkCommand.STOP) == "STOP"
    assert controller.last_command == ForkState.CMD_STOP
    assert controller.state == ForkState.IDLE
    assert controller.error_code == ForkState.ERROR_NONE


def test_update_from_mcu_state_ignores_mcu_last_command():
    controller = ForkController(mcu_state_timeout_ms=1000)
    controller.handle_command(ForkCommand.UP)

    controller.update_from_mcu_state(
        make_mcu_state(
            state=ForkState.MOVING_UP,
            last_command=ForkState.CMD_DOWN,
            is_moving=True,
        )
    )

    assert controller.last_command == ForkState.CMD_UP
    assert controller.state == ForkState.MOVING_UP
    assert controller.is_moving is True


def test_limit_conflict_sets_error():
    controller = ForkController(mcu_state_timeout_ms=1000)

    controller.update_from_mcu_state(
        make_mcu_state(
            state=ForkState.MOVING_UP,
            is_moving=True,
            upper_limit=True,
            lower_limit=True,
        )
    )

    assert controller.state == ForkState.ERROR
    assert controller.error_code == ForkState.ERROR_LIMIT_CONFLICT
    assert controller.is_moving is False
