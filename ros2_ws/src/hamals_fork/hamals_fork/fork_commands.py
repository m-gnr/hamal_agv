from hamals_interfaces.msg import ForkCommand, ForkState


COMMAND_TO_MCU = {
    ForkCommand.STOP: "STOP",
    ForkCommand.UP: "UP",
    ForkCommand.DOWN: "DOWN",
}

COMMAND_TO_STATE_COMMAND = {
    ForkCommand.STOP: ForkState.CMD_STOP,
    ForkCommand.UP: ForkState.CMD_UP,
    ForkCommand.DOWN: ForkState.CMD_DOWN,
}


def is_valid_command(command: int) -> bool:
    return command in COMMAND_TO_MCU
