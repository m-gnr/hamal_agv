# hamals_odometry/helpers/config_loader.py

from dataclasses import dataclass
from typing import List

from rclpy.node import Node


@dataclass
class OdometryConfig:
    # Topics
    wheel_ticks_topic: str
    odom_topic: str

    # Frames
    frame_id: str
    child_frame_id: str

    # Encoder / wheel model
    wheel_radius_m: float
    track_width_m: float
    cpr_left: int
    cpr_right: int
    enc_dt_max_s: float
    enc_dt_min_s: float

    # Covariances
    pose_covariance: List[float]
    twist_covariance: List[float]

    # Debug
    debug: bool


def declare_parameters(node: Node) -> None:
    node.declare_parameter('wheel_ticks_topic', '/wheel_ticks')
    node.declare_parameter('odom_topic', '/odom_raw')

    node.declare_parameter('frame_id', 'odom')
    node.declare_parameter('child_frame_id', 'base_footprint')

    node.declare_parameter('wheel_radius_m', 0.035)
    node.declare_parameter('track_width_m', 0.18)
    node.declare_parameter('cpr_left', 3959)
    node.declare_parameter('cpr_right', 3963)

    node.declare_parameter('enc_dt_max_s', 0.5)
    node.declare_parameter('enc_dt_min_s', 0.0)

    node.declare_parameter('pose_covariance', [0.0] * 36)
    node.declare_parameter('twist_covariance', [0.0] * 36)

    node.declare_parameter('debug', False)


def load_config(node: Node) -> OdometryConfig:
    declare_parameters(node)

    cfg = OdometryConfig(
        wheel_ticks_topic=str(node.get_parameter('wheel_ticks_topic').value),
        odom_topic=str(node.get_parameter('odom_topic').value),

        frame_id=str(node.get_parameter('frame_id').value),
        child_frame_id=str(node.get_parameter('child_frame_id').value),

        wheel_radius_m=float(node.get_parameter('wheel_radius_m').value),
        track_width_m=float(node.get_parameter('track_width_m').value),
        cpr_left=int(node.get_parameter('cpr_left').value),
        cpr_right=int(node.get_parameter('cpr_right').value),
        enc_dt_max_s=float(node.get_parameter('enc_dt_max_s').value),
        enc_dt_min_s=float(node.get_parameter('enc_dt_min_s').value),

        pose_covariance=list(node.get_parameter('pose_covariance').value),
        twist_covariance=list(node.get_parameter('twist_covariance').value),

        debug=bool(node.get_parameter('debug').value),
    )

    validate_config(cfg)
    return cfg


def validate_config(cfg: OdometryConfig) -> None:
    if len(cfg.pose_covariance) != 36:
        raise ValueError("pose_covariance must contain 36 elements")

    if len(cfg.twist_covariance) != 36:
        raise ValueError("twist_covariance must contain 36 elements")

    if cfg.wheel_radius_m <= 0.0:
        raise ValueError("wheel_radius_m must be positive")

    if cfg.track_width_m <= 0.0:
        raise ValueError("track_width_m must be positive")

    if cfg.cpr_left <= 0 or cfg.cpr_right <= 0:
        raise ValueError("cpr_left and cpr_right must be positive")
