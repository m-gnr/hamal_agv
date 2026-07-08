# hamals_serial_bridge/helpers/config_loader.py

from dataclasses import dataclass
from typing import List

from rclpy.node import Node


@dataclass
class SerialBridgeConfig:
    # Serial
    port: str
    baudrate: int
    timeout_ms: int

    # Topics
    cmd_vel_topic: str
    wheel_ticks_topic: str
    imu_topic: str

    # Frames
    imu_frame_id: str

    # MCU reset
    reset_on_startup: bool
    reset_pulse_ms: int
    reset_boot_wait_ms: int

    # Command safety
    cmd_vel_timeout_ms: int
    cmd_vel_rate_limit_hz: int
    debug: bool

    # Command deduplication
    cmd_dedup_enabled: bool
    cmd_dedup_eps_v: float
    cmd_dedup_eps_w: float
    cmd_force_resend_ms: int

    # IMU
    imu_ang_vel_cov_diag: List[float]
    imu_lin_acc_cov_diag: List[float]
    publish_linear_accel: bool


def declare_parameters(node: Node) -> None:
    node.declare_parameter('port', '/dev/ttyACM0')
    node.declare_parameter('baudrate', 115200)
    node.declare_parameter('timeout_ms', 50)

    node.declare_parameter('cmd_vel_topic', '/cmd_vel')
    node.declare_parameter('wheel_ticks_topic', '/wheel_ticks')
    node.declare_parameter('imu_topic', '/imu/data')

    node.declare_parameter('imu_frame_id', 'imu_link')

    node.declare_parameter('reset_on_startup', True)
    node.declare_parameter('reset_pulse_ms', 100)
    node.declare_parameter('reset_boot_wait_ms', 1500)

    node.declare_parameter('cmd_vel_timeout_ms', 500)
    node.declare_parameter('cmd_vel_rate_limit_hz', 50)
    node.declare_parameter('debug', False)

    node.declare_parameter('cmd_dedup_enabled', True)
    node.declare_parameter('cmd_dedup_eps_v', 0.01)
    node.declare_parameter('cmd_dedup_eps_w', 0.02)
    node.declare_parameter('cmd_force_resend_ms', 300)

    node.declare_parameter('imu_ang_vel_cov_diag', [9999.0, 9999.0, 0.005])
    node.declare_parameter('imu_lin_acc_cov_diag', [0.01, 9999.0, 9999.0])
    node.declare_parameter('publish_linear_accel', True)


def load_config(node: Node) -> SerialBridgeConfig:
    declare_parameters(node)

    cfg = SerialBridgeConfig(
        port=str(node.get_parameter('port').value),
        baudrate=int(node.get_parameter('baudrate').value),
        timeout_ms=int(node.get_parameter('timeout_ms').value),

        cmd_vel_topic=str(node.get_parameter('cmd_vel_topic').value),
        wheel_ticks_topic=str(node.get_parameter('wheel_ticks_topic').value),
        imu_topic=str(node.get_parameter('imu_topic').value),

        imu_frame_id=str(node.get_parameter('imu_frame_id').value),

        reset_on_startup=bool(node.get_parameter('reset_on_startup').value),
        reset_pulse_ms=int(node.get_parameter('reset_pulse_ms').value),
        reset_boot_wait_ms=int(node.get_parameter('reset_boot_wait_ms').value),

        cmd_vel_timeout_ms=int(node.get_parameter('cmd_vel_timeout_ms').value),
        cmd_vel_rate_limit_hz=int(node.get_parameter('cmd_vel_rate_limit_hz').value),
        debug=bool(node.get_parameter('debug').value),

        cmd_dedup_enabled=bool(node.get_parameter('cmd_dedup_enabled').value),
        cmd_dedup_eps_v=float(node.get_parameter('cmd_dedup_eps_v').value),
        cmd_dedup_eps_w=float(node.get_parameter('cmd_dedup_eps_w').value),
        cmd_force_resend_ms=int(node.get_parameter('cmd_force_resend_ms').value),

        imu_ang_vel_cov_diag=list(node.get_parameter('imu_ang_vel_cov_diag').value),
        imu_lin_acc_cov_diag=list(node.get_parameter('imu_lin_acc_cov_diag').value),
        publish_linear_accel=bool(node.get_parameter('publish_linear_accel').value),
    )

    validate_config(cfg)
    return cfg


def validate_config(cfg: SerialBridgeConfig) -> None:
    if len(cfg.imu_ang_vel_cov_diag) != 3:
        raise ValueError("imu_ang_vel_cov_diag must contain 3 elements")

    if len(cfg.imu_lin_acc_cov_diag) != 3:
        raise ValueError("imu_lin_acc_cov_diag must contain 3 elements")

    if cfg.baudrate <= 0:
        raise ValueError("baudrate must be positive")

    if cfg.timeout_ms < 0:
        raise ValueError("timeout_ms cannot be negative")
