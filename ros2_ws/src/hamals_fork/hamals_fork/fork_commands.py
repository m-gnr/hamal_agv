from hamals_interfaces.msg import ForkCommand

COMMAND_TO_TEXT = {
    ForkCommand.STOP: "STOP",
    ForkCommand.UP: "UP",
    ForkCommand.DOWN: "DOWN",
}


def command_to_text(command: int) -> str:
    return COMMAND_TO_TEXT.get(command, "UNKNOWN")


def is_valid_command(command: int) -> bool:
    return command in COMMAND_TO_TEXT