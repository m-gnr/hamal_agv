# hamals_fork/fork_controller.py

import time

from hamals_interfaces.msg import ForkCommand, ForkState


class ForkController:
    """
    Timer-based open-loop fork controller.

    Bu controller doğrudan ROS publisher/subscriber bilmez.
    Sadece fork state, command ve süre mantığını yönetir.

    İlk sürümde çatal konumu ölçülmez.
    UP/DOWN komutları belirlenen süre boyunca motor sürülerek tamamlanır.
    """

    def __init__(self, up_duration_ms: int, down_duration_ms: int):
        self.up_duration_ms = int(up_duration_ms)
        self.down_duration_ms = int(down_duration_ms)

        self.state = ForkState.IDLE
        self.last_command = ForkState.CMD_NONE
        self.error_code = ForkState.ERROR_NONE

        self._motion_start_time_s = None
        self._motion_duration_ms = 0
        self._active_motion_command = None

    # ------------------------------------------------------------
    # COMMAND HANDLING
    # ------------------------------------------------------------

    def handle_command(self, command: int):
        """
        Gelen ForkCommand değerini işler.

        Return:
            mcu_cmd: str | None

        mcu_cmd:
            "UP", "DOWN", "STOP" veya None döner.
            None dönerse MCU'ya komut gönderilmez.
        """

        if command == ForkCommand.STOP:
            return self.stop()

        if command == ForkCommand.UP:
            return self.start_up()

        if command == ForkCommand.DOWN:
            return self.start_down()

        self.state = ForkState.ERROR
        self.error_code = ForkState.ERROR_INVALID_COMMAND
        return None

    def start_up(self):
        """
        Yukarı hareketi başlatır.
        """
        self.state = ForkState.MOVING_UP
        self.last_command = ForkState.CMD_UP
        self.error_code = ForkState.ERROR_NONE

        self._motion_start_time_s = time.time()
        self._motion_duration_ms = self.up_duration_ms
        self._active_motion_command = ForkCommand.UP

        return "UP"

    def start_down(self):
        """
        Aşağı hareketi başlatır.
        """
        self.state = ForkState.MOVING_DOWN
        self.last_command = ForkState.CMD_DOWN
        self.error_code = ForkState.ERROR_NONE

        self._motion_start_time_s = time.time()
        self._motion_duration_ms = self.down_duration_ms
        self._active_motion_command = ForkCommand.DOWN

        return "DOWN"

    def stop(self):
        """
        Hareketi manuel olarak durdurur.
        """
        self.state = ForkState.IDLE
        self.last_command = ForkState.CMD_STOP
        self.error_code = ForkState.ERROR_NONE

        self._clear_motion()

        return "STOP"

    # ------------------------------------------------------------
    # PERIODIC UPDATE
    # ------------------------------------------------------------

    def update(self):
        """
        Periyodik olarak çağrılır.

        Timer süresi dolduysa state'i UP_DONE/DOWN_DONE yapar
        ve MCU'ya STOP gönderilmesi gerektiğini bildirir.

        Return:
            mcu_cmd: str | None
        """

        if not self.is_moving():
            return None

        remaining_ms = self.get_remaining_time_ms()

        if remaining_ms > 0:
            return None

        # Süre bitti, motor durmalı.
        if self._active_motion_command == ForkCommand.UP:
            self.state = ForkState.UP_DONE
            self.last_command = ForkState.CMD_UP
        elif self._active_motion_command == ForkCommand.DOWN:
            self.state = ForkState.DOWN_DONE
            self.last_command = ForkState.CMD_DOWN
        else:
            self.state = ForkState.ERROR
            self.error_code = ForkState.ERROR_TIMEOUT

        self._clear_motion()

        return "STOP"

    # ------------------------------------------------------------
    # STATE HELPERS
    # ------------------------------------------------------------

    def is_moving(self) -> bool:
        return self.state in (
            ForkState.MOVING_UP,
            ForkState.MOVING_DOWN,
        )

    def get_remaining_time_ms(self) -> int:
        if self._motion_start_time_s is None:
            return 0

        elapsed_ms = int((time.time() - self._motion_start_time_s) * 1000.0)
        remaining_ms = self._motion_duration_ms - elapsed_ms

        if remaining_ms < 0:
            return 0

        return remaining_ms

    def make_state_msg(self, stamp):
        """
        ForkState ROS mesajı üretir.
        """
        msg = ForkState()
        msg.stamp = stamp
        msg.state = self.state
        msg.last_command = self.last_command
        msg.error_code = self.error_code
        msg.is_moving = self.is_moving()
        msg.remaining_time_ms = self.get_remaining_time_ms()
        return msg

    def _clear_motion(self):
        self._motion_start_time_s = None
        self._motion_duration_ms = 0
        self._active_motion_command = None