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
    odom_topic: str
    imu_topic: str

    # Covariances
    pose_covariance: List[float]
    twist_covariance: List[float]

    # Frames
    frame_id: str
    child_frame_id: str
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

    # Encoder / wheel model
    wheel_radius_m: float
    track_width_m: float
    cpr_left: int
    cpr_right: int
    enc_dt_max_s: float
    enc_dt_min_s: float

    # IMU
    imu_ang_vel_cov_diag: List[float]
    imu_lin_acc_cov_diag: List[float]
    publish_linear_accel: bool


def declare_parameters(node: Node) -> None:
    node.declare_parameter('port', '/dev/ttyACM0')
    node.declare_parameter('baudrate', 115200)
    node.declare_parameter('timeout_ms', 50)

    node.declare_parameter('cmd_vel_topic', '/cmd_vel')
    node.declare_parameter('odom_topic', '/odom_raw')
    node.declare_parameter('imu_topic', '/imu/data')

    node.declare_parameter('pose_covariance', [0.0] * 36)
    node.declare_parameter('twist_covariance', [0.0] * 36)

    node.declare_parameter('frame_id', 'odom')
    node.declare_parameter('child_frame_id', 'base_footprint')
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

    node.declare_parameter('wheel_radius_m', 0.035)
    node.declare_parameter('track_width_m', 0.18)
    node.declare_parameter('cpr_left', 3959)
    node.declare_parameter('cpr_right', 3963)

    node.declare_parameter('enc_dt_max_s', 0.5)
    node.declare_parameter('enc_dt_min_s', 0.0)

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
        odom_topic=str(node.get_parameter('odom_topic').value),
        imu_topic=str(node.get_parameter('imu_topic').value),

        pose_covariance=list(node.get_parameter('pose_covariance').value),
        twist_covariance=list(node.get_parameter('twist_covariance').value),

        frame_id=str(node.get_parameter('frame_id').value),
        child_frame_id=str(node.get_parameter('child_frame_id').value),
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

        wheel_radius_m=float(node.get_parameter('wheel_radius_m').value),
        track_width_m=float(node.get_parameter('track_width_m').value),
        cpr_left=int(node.get_parameter('cpr_left').value),
        cpr_right=int(node.get_parameter('cpr_right').value),
        enc_dt_max_s=float(node.get_parameter('enc_dt_max_s').value),
        enc_dt_min_s=float(node.get_parameter('enc_dt_min_s').value),

        imu_ang_vel_cov_diag=list(node.get_parameter('imu_ang_vel_cov_diag').value),
        imu_lin_acc_cov_diag=list(node.get_parameter('imu_lin_acc_cov_diag').value),
        publish_linear_accel=bool(node.get_parameter('publish_linear_accel').value),
    )

    validate_config(cfg)
    return cfg


def validate_config(cfg: SerialBridgeConfig) -> None:
    if len(cfg.pose_covariance) != 36:
        raise ValueError("pose_covariance must contain 36 elements")

    if len(cfg.twist_covariance) != 36:
        raise ValueError("twist_covariance must contain 36 elements")

    if len(cfg.imu_ang_vel_cov_diag) != 3:
        raise ValueError("imu_ang_vel_cov_diag must contain 3 elements")

    if len(cfg.imu_lin_acc_cov_diag) != 3:
        raise ValueError("imu_lin_acc_cov_diag must contain 3 elements")

    if cfg.baudrate <= 0:
        raise ValueError("baudrate must be positive")

    if cfg.timeout_ms < 0:
        raise ValueError("timeout_ms cannot be negative")

    if cfg.wheel_radius_m <= 0.0:
        raise ValueError("wheel_radius_m must be positive")

    if cfg.track_width_m <= 0.0:
        raise ValueError("track_width_m must be positive")

    if cfg.cpr_left <= 0 or cfg.cpr_right <= 0:
        raise ValueError("cpr_left and cpr_right must be positive")