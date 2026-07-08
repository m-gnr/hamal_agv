from hamals_interfaces.msg import ForkState


STATE_TO_TEXT = {
    ForkState.IDLE: "IDLE",
    ForkState.MOVING_UP: "MOVING_UP",
    ForkState.MOVING_DOWN: "MOVING_DOWN",
    ForkState.UP_DONE: "UP_DONE",
    ForkState.DOWN_DONE: "DOWN_DONE",
    ForkState.ERROR: "ERROR",
}


ERROR_TO_TEXT = {
    ForkState.ERROR_NONE: "ERROR_NONE",
    ForkState.ERROR_TIMEOUT: "ERROR_TIMEOUT",
    ForkState.ERROR_INVALID_COMMAND: "ERROR_INVALID_COMMAND",
}


def state_to_text(state: int) -> str:
    return STATE_TO_TEXT.get(state, "UNKNOWN")


def error_to_text(error_code: int) -> str:
    return ERROR_TO_TEXT.get(error_code, "UNKNOWN")