from hamals_interfaces.msg import ForkState
from hamals_fork.fork_keepalive import ForkKeepalive


def test_up_keepalive_starts_after_moving_up_state():
    keepalive = ForkKeepalive()

    keepalive.record_published_command("UP")
    assert keepalive.command_to_publish() is None

    keepalive.update_from_mcu_state(ForkState.MOVING_UP)

    assert keepalive.command_to_publish() == "UP"


def test_at_top_stops_up_keepalive():
    keepalive = ForkKeepalive()
    keepalive.record_published_command("UP")
    keepalive.update_from_mcu_state(ForkState.MOVING_UP)

    keepalive.update_from_mcu_state(ForkState.AT_TOP)

    assert keepalive.command_to_publish() is None


def test_down_keepalive_starts_after_moving_down_state():
    keepalive = ForkKeepalive()

    keepalive.record_published_command("DOWN")
    assert keepalive.command_to_publish() is None

    keepalive.update_from_mcu_state(ForkState.MOVING_DOWN)

    assert keepalive.command_to_publish() == "DOWN"


def test_at_bottom_stops_down_keepalive():
    keepalive = ForkKeepalive()
    keepalive.record_published_command("DOWN")
    keepalive.update_from_mcu_state(ForkState.MOVING_DOWN)

    keepalive.update_from_mcu_state(ForkState.AT_BOTTOM)

    assert keepalive.command_to_publish() is None


def test_stop_immediately_stops_keepalive():
    keepalive = ForkKeepalive()
    keepalive.record_published_command("UP")
    keepalive.update_from_mcu_state(ForkState.MOVING_UP)

    keepalive.record_published_command("STOP")

    assert keepalive.command_to_publish() is None


def test_error_state_stops_keepalive():
    keepalive = ForkKeepalive()
    keepalive.record_published_command("UP")
    keepalive.update_from_mcu_state(ForkState.ERROR)

    assert keepalive.command_to_publish() is None


def test_opposite_moving_state_does_not_start_keepalive():
    keepalive = ForkKeepalive()
    keepalive.record_published_command("UP")

    keepalive.update_from_mcu_state(ForkState.MOVING_DOWN)

    assert keepalive.command_to_publish() is None
