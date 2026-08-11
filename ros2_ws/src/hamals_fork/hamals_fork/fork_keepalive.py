from __future__ import annotations

from hamals_interfaces.msg import ForkState


class ForkKeepalive:
    def __init__(self) -> None:
        self._requested_command: str | None = None
        self._active_command: str | None = None

    def record_published_command(self, command: str) -> None:
        if command in ("UP", "DOWN"):
            self._requested_command = command
            self._active_command = None
            return

        if command == "STOP":
            self.stop()

    def update_from_mcu_state(self, state: int) -> None:
        if state == ForkState.MOVING_UP:
            self._activate_if_requested("UP")
            return

        if state == ForkState.MOVING_DOWN:
            self._activate_if_requested("DOWN")
            return

        # Hareketsiz state: sadece zaten aktif bir hareket varsa durdur.
        # İstek beklemedeyken silme, yoksa MCU MOVING demeden keepalive ölür. Abdullah Değiştirdi
        if self._active_command is not None:
            self.stop()

    def command_to_publish(self) -> str | None:
        return self._active_command

    def stop(self) -> None:
        self._requested_command = None
        self._active_command = None

    def _activate_if_requested(self, command: str) -> None:
        if self._requested_command == command or self._active_command == command:
            self._requested_command = command
            self._active_command = command
        else:
            self.stop()
