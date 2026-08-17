"""Runtime-only mission state; static field data stays in world model."""

from dataclasses import dataclass, field
import time


@dataclass
class MissionContext:
    task_id: str
    pickup_id: str
    dropoff_id: str
    top_state: int
    phase: str = 'VALIDATE_TASK'
    carrying_load: bool = False
    active_target: str = ''
    expected_qr: str = ''
    verified_qr: str = ''
    pause_reason: str = ''
    error_code: str = ''
    message: str = ''
    retry_count: int = 0
    config_checksum: str = ''
    route: list[str] = field(default_factory=list)
    route_index: int = 0
    started_at: float = field(default_factory=time.monotonic)
