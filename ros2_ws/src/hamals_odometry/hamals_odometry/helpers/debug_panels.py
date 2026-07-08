# hamals_odometry/helpers/debug_panels.py

from .config_loader import OdometryConfig


def format_startup_config(cfg: OdometryConfig) -> str:
    return f"""
[HAMALS ODOMETRY] Startup Config

Topics:
  wheel_ticks       : {cfg.wheel_ticks_topic}
  odom              : {cfg.odom_topic}

Frames:
  frame_id          : {cfg.frame_id}
  child_frame_id    : {cfg.child_frame_id}

Encoder:
  wheel_radius_m    : {cfg.wheel_radius_m}
  track_width_m     : {cfg.track_width_m}
  cpr_left          : {cfg.cpr_left}
  cpr_right         : {cfg.cpr_right}
  enc_dt_min_s      : {cfg.enc_dt_min_s}
  enc_dt_max_s      : {cfg.enc_dt_max_s}

Startup:
  debug             : {cfg.debug}
"""


def format_debug_panel(
    wheel_ticks_rx: int,
    odom_published: int,
    odom_skipped_dt: int,
    last_ticks_t_us: int,
    last_ticks_dl: int,
    last_ticks_dr: int,
    last_dt_s: float,
    last_odom_v: float,
    last_odom_w: float,
) -> str:
    return f"""
[HAMALS ODOMETRY] Debug

RX:
  wheel_ticks       : {wheel_ticks_rx}

ROS:
  odom_published    : {odom_published}
  odom_skipped_dt   : {odom_skipped_dt}

Last values:
  wheel_ticks       : t_us={last_ticks_t_us}, dl={last_ticks_dl}, dr={last_ticks_dr}
  dt_s              : {last_dt_s:.6f}
  odom_raw_twist    : v={last_odom_v:.3f}, w={last_odom_w:.3f}
"""
