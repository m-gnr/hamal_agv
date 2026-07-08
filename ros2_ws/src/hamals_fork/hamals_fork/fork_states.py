from hamals_interfaces.msg import ForkState


STATE_NAMES = {
    ForkState.IDLE: "IDLE",
    ForkState.MOVING_UP: "MOVING_UP",
    ForkState.MOVING_DOWN: "MOVING_DOWN",
    ForkState.AT_TOP: "AT_TOP",
    ForkState.AT_BOTTOM: "AT_BOTTOM",
    ForkState.ERROR: "ERROR",
}

ERROR_NAMES = {
    ForkState.ERROR_NONE: "ERROR_NONE",
    ForkState.ERROR_INVALID_COMMAND: "ERROR_INVALID_COMMAND",
    ForkState.ERROR_TOP_TIMEOUT: "ERROR_TOP_TIMEOUT",
    ForkState.ERROR_BOTTOM_TIMEOUT: "ERROR_BOTTOM_TIMEOUT",
    ForkState.ERROR_LIMIT_CONFLICT: "ERROR_LIMIT_CONFLICT",
    ForkState.ERROR_MCU_TIMEOUT: "ERROR_MCU_TIMEOUT",
}


def state_name(state: int) -> str:
    return STATE_NAMES.get(state, f"UNKNOWN_STATE_{state}")


def error_name(error_code: int) -> str:
    return ERROR_NAMES.get(error_code, f"UNKNOWN_ERROR_{error_code}")
