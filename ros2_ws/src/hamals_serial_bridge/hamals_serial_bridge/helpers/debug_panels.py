# hamals_serial_bridge/helpers/debug_panels.py

from .config_loader import SerialBridgeConfig


def format_startup_config(cfg: SerialBridgeConfig) -> str:
    return f"""
[HAMALS SERIAL BRIDGE] Startup Config

Serial:
  port              : {cfg.port}
  baudrate          : {cfg.baudrate}
  timeout_ms        : {cfg.timeout_ms}

Topics:
  cmd_vel           : {cfg.cmd_vel_topic}
  odom              : {cfg.odom_topic}
  imu               : {cfg.imu_topic}

Frames:
  frame_id          : {cfg.frame_id}
  child_frame_id    : {cfg.child_frame_id}
  imu_frame_id      : {cfg.imu_frame_id}

Encoder:
  wheel_radius_m    : {cfg.wheel_radius_m}
  track_width_m     : {cfg.track_width_m}
  cpr_left          : {cfg.cpr_left}
  cpr_right         : {cfg.cpr_right}
  enc_dt_min_s      : {cfg.enc_dt_min_s}
  enc_dt_max_s      : {cfg.enc_dt_max_s}

IMU:
  publish_accel     : {cfg.publish_linear_accel}
  gyro_cov_diag     : {cfg.imu_ang_vel_cov_diag}
  accel_cov_diag    : {cfg.imu_lin_acc_cov_diag}

Command:
  timeout_ms        : {cfg.cmd_vel_timeout_ms}
  rate_limit_hz     : {cfg.cmd_vel_rate_limit_hz}
  dedup_enabled     : {cfg.cmd_dedup_enabled}
  dedup_eps_v       : {cfg.cmd_dedup_eps_v}
  dedup_eps_w       : {cfg.cmd_dedup_eps_w}
  force_resend_ms   : {cfg.cmd_force_resend_ms}

Startup:
  reset_on_startup  : {cfg.reset_on_startup}
  reset_pulse_ms    : {cfg.reset_pulse_ms}
  boot_wait_ms      : {cfg.reset_boot_wait_ms}
  debug             : {cfg.debug}
"""


def format_debug_panel(
    tx_packets: int,
    tx_dedup_skipped: int,
    tx_ratelimit_skipped: int,
    odom_published: int,
    rx_bytes: int,
    rx_valid_frames: int,
    rx_invalid_frames: int,
    deadman_active: bool,
    last_cmd_v: float,
    last_cmd_w: float,
    last_odom_v: float,
    last_odom_w: float,
) -> str:
    return f"""
[HAMALS SERIAL BRIDGE] Debug

TX:
  packets           : {tx_packets}
  dedup_skipped     : {tx_dedup_skipped}
  ratelimit_skipped : {tx_ratelimit_skipped}

RX:
  bytes             : {rx_bytes}
  valid_frames      : {rx_valid_frames}
  invalid_frames    : {rx_invalid_frames}

ROS:
  odom_published    : {odom_published}
  deadman_active    : {deadman_active}

Last values:
  cmd_vel           : v={last_cmd_v:.3f}, w={last_cmd_w:.3f}
  odom_raw_twist    : v={last_odom_v:.3f}, w={last_odom_w:.3f}
"""