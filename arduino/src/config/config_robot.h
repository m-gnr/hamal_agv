#pragma once

#include <cstdint>

// ======================================================
//                WHEEL & ENCODER
// ======================================================

constexpr float WHEEL_RADIUS_M = 0.10f;      // 10 cm

constexpr int ENCODER_CPR_LEFT  = 12000;
constexpr int ENCODER_CPR_RIGHT = 12000;

constexpr int ENC_L_DIRECTION = -1;
constexpr int ENC_R_DIRECTION = 1;

// ======================================================
//                ROBOT GEOMETRY
// ======================================================

constexpr float TRACK_WIDTH_M = 0.47f;

// ======================================================
//                MOTION LIMITS
// ======================================================

constexpr float MAX_WHEEL_RAD_S   = 5.0f;
constexpr float MAX_LINEAR_M_S    = 0.25f;
constexpr float MAX_ANGULAR_RAD_S = 0.50f;

// ======================================================
//                CONTROL TIMING
// ======================================================

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

/*
constexpr float PWM_MIN_START_L = 85.0f;
constexpr float PWM_MIN_RUN_L   = 70.0f;
constexpr float PWM_MIN_START_R = 90.0f;
constexpr float PWM_MIN_RUN_R   = 75.0f;

*/  


constexpr float DEADZONE_CMD_EPS  = 0.05f;
constexpr float DEADZONE_MEAS_EPS = 0.20f;

// Deadzone "kick" suresi: teker durduktan sonra minimum PWM sadece
// bu sure kadar zorlanir, sonrasinda taban tamamen kalkar ve PID
// (Ki dahil) serbest calisir. Dusuk hizlarda surekli taban
// zorlamasini onlemek icin eklendi.
constexpr float DEADZONE_KICK_DURATION_S = 0.08f;   // 80 ms



constexpr float PWM_MIN_START_L =50.0f;
constexpr float PWM_MIN_RUN_L   =50.0f;


constexpr float PWM_MIN_START_R = 50.0f;
constexpr float PWM_MIN_RUN_R   = 40.0f;

// ======================================================
//                ACCELERATION LIMIT
// ======================================================

constexpr float MAX_WHEEL_ACCEL_RAD_S2 = 50.0f;

// ======================================================
//                IMU
// ======================================================

constexpr float IMU_SPIKE_THRESHOLD_RAD = 0.40f;

// ======================================================
//                YAW CORRECTION
// ======================================================

constexpr bool ENABLE_YAW_CORRECTION = false;

constexpr float YAW_CORRECTION_W_THRESHOLD = 0.05f;
constexpr float YAW_CORRECTION_KP = 2.0f;

// ======================================================
//                WHEEL PID
// ======================================================

constexpr float WHEEL_PID_KP = 30.0f;
constexpr float WHEEL_PID_KI = 0.0f;
constexpr float WHEEL_PID_KD = 0.0f;

constexpr float WHEEL_PID_RAMP_STEP = 15.0f;

constexpr float WHEEL_TRIM_L = 1.0f;
constexpr float WHEEL_TRIM_R = 0.941f;

// ======================================================
//                SERIAL TELEMETRY
// ======================================================

constexpr float ENC_TX_DT_S = 0.02f;      // 50 Hz
constexpr float IMU_TX_DT_S = 0.02f;      // 50 Hz
constexpr float ODOM_TX_DT_S = ENC_TX_DT_S;