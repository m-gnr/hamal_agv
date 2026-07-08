from __future__ import annotations

import time

from hamals_interfaces.msg import ForkCommand, ForkState

from hamals_fork.fork_commands import COMMAND_TO_STATE_COMMAND, is_valid_command


class ForkController:
    def __init__(self, mcu_state_timeout_ms: int):
        if mcu_state_timeout_ms <= 0:
            raise ValueError("mcu_state_timeout_ms must be greater than 0")

        self.mcu_state_timeout_s = mcu_state_timeout_ms / 1000.0
        self.state = ForkState.IDLE
        self.last_command = ForkState.CMD_NONE
        self.error_code = ForkState.ERROR_NONE
        self.is_moving = False
        self.upper_limit = False
        self.lower_limit = False
        self.t_us = 0
        self._last_mcu_state_time_s = None

    def handle_command(self, command: int) -> str | None:
        if self.state == ForkState.ERROR:
            return self._handle_command_while_error(command)

        if not is_valid_command(command):
            self.state = ForkState.ERROR
            self.error_code = ForkState.ERROR_INVALID_COMMAND
            self.is_moving = False
            return None

        self.last_command = COMMAND_TO_STATE_COMMAND[command]

        if command == ForkCommand.STOP:
            self.state = ForkState.IDLE
            self.error_code = ForkState.ERROR_NONE
            self.is_moving = False
            return "STOP"

        if command == ForkCommand.UP:
            return "UP"

        if command == ForkCommand.DOWN:
            return "DOWN"

        return None

    def update_from_mcu_state(self, msg: ForkState) -> None:
        self.t_us = msg.t_us
        self.state = msg.state
        self.error_code = msg.error_code
        self.is_moving = msg.is_moving
        self.upper_limit = msg.upper_limit
        self.lower_limit = msg.lower_limit
        self._last_mcu_state_time_s = time.monotonic()

        if self.upper_limit and self.lower_limit:
            self.state = ForkState.ERROR
            self.error_code = ForkState.ERROR_LIMIT_CONFLICT
            self.is_moving = False

    def update(self) -> None:
        if self._last_mcu_state_time_s is None:
            return

        elapsed_s = time.monotonic() - self._last_mcu_state_time_s
        if elapsed_s > self.mcu_state_timeout_s:
            self.state = ForkState.ERROR
            self.error_code = ForkState.ERROR_MCU_TIMEOUT
            self.is_moving = False

    def make_state_msg(self, stamp) -> ForkState:
        msg = ForkState()
        msg.stamp = stamp
        msg.t_us = self.t_us
        msg.state = self.state
        msg.last_command = self.last_command
        msg.error_code = self.error_code
        msg.is_moving = self.is_moving
        msg.upper_limit = self.upper_limit
        msg.lower_limit = self.lower_limit
        return msg

    def _handle_command_while_error(self, command: int) -> str | None:
        if command == ForkCommand.STOP:
            self.last_command = ForkState.CMD_STOP
            self.state = ForkState.IDLE
            self.error_code = ForkState.ERROR_NONE
            self.is_moving = False
            return "STOP"

        if command in (ForkCommand.UP, ForkCommand.DOWN):
            self.is_moving = False
            return None

        self.error_code = ForkState.ERROR_INVALID_COMMAND
        self.is_moving = False
        return None
