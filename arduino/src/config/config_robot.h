#pragma once

#include <cstdint>

// ======================================================
//                WHEEL & ENCODER
// ======================================================

// Wheel radius (meters)
constexpr float WHEEL_RADIUS_M = 0.10f;      // 10 cm

//-------------------------------------------------------
// Encoder resolution (Counts Per Wheel Revolution)
//
// Motor:
//   Encoder      : 100 PPR (according to motor label)
//   Gear Ratio   : 30:1
//
// Firmware:
//   Quadrature decoding (A + B, CHANGE)
//   => X4 decoding
//
// Theoretical CPR:
//
//     100 × 30 × 4 = 12000 Counts
//
// IMPORTANT:
// This value should still be verified experimentally
// by rotating the wheel exactly one revolution.
//-------------------------------------------------------

constexpr int ENCODER_CPR_LEFT  = 12000;
constexpr int ENCODER_CPR_RIGHT = 12000;

//-------------------------------------------------------
// Encoder direction
//
// Determined experimentally.
//-------------------------------------------------------

constexpr int ENC_L_DIRECTION = -1;
constexpr int ENC_R_DIRECTION = -1;

// ======================================================
//                ROBOT GEOMETRY
// ======================================================

// Distance between wheel centers
constexpr float TRACK_WIDTH_M = 0.47f;

// ======================================================
//                MOTION LIMITS
// ======================================================

// These values should be updated after real driving tests.

constexpr float MAX_WHEEL_RAD_S   = 5.0f;
constexpr float MAX_LINEAR_M_S    = 0.25f;
constexpr float MAX_ANGULAR_RAD_S = 0.80f;

// ======================================================
//                CONTROL TIMING
// ======================================================

// 100 Hz control loop

constexpr float CONTROL_DT_S = 0.01f;

// ======================================================
//                WATCHDOG
// ======================================================

constexpr uint32_t CMD_WATCHDOG_TIMEOUT_MS = 500;

constexpr float CMD_VEL_GRACE_S   = 0.30f;
constexpr float CMD_VEL_TIMEOUT_S = 0.50f;

// ======================================================
//                PWM
// ======================================================

constexpr int PWM_MAX = 255;

// ======================================================
//                MOTOR DEADZONE
// ======================================================

// These values were measured experimentally.
//
// START:
// Minimum PWM required to start wheel rotation.
//
// RUN:
// Minimum PWM required to keep wheel rotating.

/*
constexpr float PWM_MIN_START_L = 85.0f;
constexpr float PWM_MIN_RUN_L   = 70.0f;
constexpr float PWM_MIN_START_R = 90.0f;
constexpr float PWM_MIN_RUN_R   = 75.0f;

*/  


constexpr float DEADZONE_CMD_EPS  = 0.05f;
constexpr float DEADZONE_MEAS_EPS = 0.20f;



constexpr float PWM_MIN_START_L =65.0f;
constexpr float PWM_MIN_RUN_L   =50.0f;

constexpr float PWM_MIN_START_R = 70.0f;
constexpr float PWM_MIN_RUN_R   = 55.0f;

// ======================================================
//                ACCELERATION LIMIT
// ======================================================

constexpr float MAX_WHEEL_ACCEL_RAD_S2 = 50.0f;

// ======================================================
//                IMU
// ======================================================

// Reject unrealistic yaw jumps.

constexpr float IMU_SPIKE_THRESHOLD_RAD = 0.40f;

// ======================================================
//                YAW CORRECTION
// ======================================================

// Disable during Navigation2.

constexpr bool ENABLE_YAW_CORRECTION = false;

constexpr float YAW_CORRECTION_W_THRESHOLD = 0.05f;
constexpr float YAW_CORRECTION_KP = 2.0f;

// ======================================================
//                WHEEL PID
// ======================================================

// PID values have NOT been tuned yet.
//
// Start with:
//
// KP = 30
// KI = 15
// KD = 0
//
// only after verifying encoder CPR and wheel speed.
//
// Current values remain disabled.

constexpr float WHEEL_PID_KP = 0.08f;
constexpr float WHEEL_PID_KI = 0.0f;
constexpr float WHEEL_PID_KD = 0.0f;
//-------------------------------------------------------
// PWM ramp
//
// Prevents sudden acceleration.
//
// Value still requires tuning.
//-------------------------------------------------------

constexpr float WHEEL_PID_RAMP_STEP = 15.0f;

// ======================================================
//                SERIAL TELEMETRY
// ======================================================

// Encoder telemetry
constexpr float ENC_TX_DT_S = 0.02f;      // 50 Hz

// IMU telemetry
constexpr float IMU_TX_DT_S = 0.02f;      // 50 Hz

// Backward compatibility
constexpr float ODOM_TX_DT_S = ENC_TX_DT_S; 