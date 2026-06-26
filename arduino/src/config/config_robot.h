#pragma once

// -------------------- Wheel & Encoder ------------------

// Wheel radius in meters
constexpr float WHEEL_RADIUS_M = 0.03729f;   

// Encoder resolution counts per WHEEL revolution (measured by 10-turn hand test)
// (quadrature decoding included)
constexpr int ENCODER_CPR_LEFT  = 3959;
constexpr int ENCODER_CPR_RIGHT = 3963;

// ---------------- Encoder Direction ----------------
constexpr int ENC_L_DIRECTION = -1;   // -1 normal, 1 reverse
constexpr int ENC_R_DIRECTION = -1;

// DEBUG NOTE (Encoder Validation):
// - Rotate ONE wheel exactly 1 full revolution by hand
// - Count encoder pulses reported by firmware
// - Expected value ≈ ENCODER_CPR (±5%)
// - If value differs, update ENCODER_CPR and/or GEAR_RATIO here

// -------------------- Robot Geometry -------------------

// Distance between left and right wheels (meters)
constexpr float TRACK_WIDTH_M = 0.18f;     // 18.0 cm 

// -------------------- Motion Limits -------------------

// Maximum wheel angular speed (rad/s)
constexpr float MAX_WHEEL_RAD_S = 12.0f;

// Maximum linear speed of robot (m/s)
constexpr float MAX_LINEAR_M_S = 0.5f;

// Maximum angular speed of robot (rad/s)
constexpr float MAX_ANGULAR_RAD_S = 1.5f;

// -------------------- Control Timing ------------------

// Control loop period (seconds)
// Must match timing scheduler
constexpr float CONTROL_DT_S = 0.01f;      // 10 ms

// -------------------- Command Timeout -----------------

// Maximum allowed time without new cmd_vel (seconds)
constexpr float CMD_VEL_GRACE_S   = 0.3f;  // soft zone
constexpr float CMD_VEL_TIMEOUT_S = 0.5f;  // hard stop

// -------------------- PWM Limits ----------------------

// PWM range (platform dependent)
constexpr int PWM_MAX = 255;

// -------------------- Motor Deadzone -------------------
// Motors + driver have static friction (stiction): below a certain PWM the wheel will not start moving.
// These per-wheel thresholds let the controller "kick" the motors to start and then keep them running.
//
// START: minimum PWM needed to start moving from standstill
// RUN:   minimum PWM needed to keep moving once already rotating

// Left wheel thresholds
constexpr float PWM_MIN_START_L = 85.0f;   // start threshold (measured + safety margin)
constexpr float PWM_MIN_RUN_L   = 70.0f;   // run/keep-moving threshold

// Right wheel thresholds (often slightly higher than left)
constexpr float PWM_MIN_START_R = 90.0f;
constexpr float PWM_MIN_RUN_R   = 75.0f;

// Deadzone activation thresholds:
// - If |omega_target| is below CMD_EPS, treat it as zero (do not apply deadzone).
// - If |omega_measured| is below MEAS_EPS, treat the wheel as "not moving" (apply START threshold).
constexpr float DEADZONE_CMD_EPS  = 0.05f;  // rad/s
constexpr float DEADZONE_MEAS_EPS = 0.20f;  // rad/s

// -------------------- Motion Limits -------------------

// Maximum wheel angular acceleration (rad/s^2)
constexpr float MAX_WHEEL_ACCEL_RAD_S2 = 50.0f;

// -------------------- IMU Spike Guard ------------------

// Maximum allowed yaw jump per control step (rad)
// If |dyaw| exceeds this, IMU sample is rejected
constexpr float IMU_SPIKE_THRESHOLD_RAD = 0.4f;

// -------------------- Yaw Correction ------------------

// Enable heading hold (yaw correction) when w ≈ 0
// TURN OFF THIS VALUE WHEN NAV2 IS TRUE !!!!!
constexpr bool ENABLE_YAW_CORRECTION = false;

// Only active if |w_target| < threshold
constexpr float YAW_CORRECTION_W_THRESHOLD = 0.05f; // rad/s

// Proportional gain
constexpr float YAW_CORRECTION_KP = 2.0f; // 1.0–3.0

// -------------------- Wheel PID ------------------------

// Wheel speed PID gains
constexpr float WHEEL_PID_KP = 30.0f;
constexpr float WHEEL_PID_KI = 15.0f;
constexpr float WHEEL_PID_KD = 0.0f;

// PWM ramp limit (per control step)
constexpr float WHEEL_PID_RAMP_STEP = 15.0f;

// -------------------- Serial TX -----------------------
// Telemetry periods (seconds)
// Contract:
//   $ENC,t_us,dl,dr*CS @ ENC_TX_DT_S
//   $IMU,t_us,gz,ax,ay,az*CS @ IMU_TX_DT_S

// Encoder telemetry transmit period (seconds)
constexpr float ENC_TX_DT_S = 0.02f;   // 50 Hz

// IMU telemetry transmit period (seconds)
constexpr float IMU_TX_DT_S = 0.02f;   // 50 Hz

// Backward-compatible alias (older code used this name)
// Prefer ENC_TX_DT_S / IMU_TX_DT_S going forward.
constexpr float ODOM_TX_DT_S = ENC_TX_DT_S;