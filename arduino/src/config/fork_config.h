#pragma once

#include <Arduino.h>
#include <stdint.h>

#include "config_pins.h"

namespace hamals {
namespace fork_config {

constexpr int RPWM_PIN = FORK_RPWM;
constexpr int LPWM_PIN = FORK_LPWM;
//constexpr int R_EN_PIN = FORK_R_EN;
//constexpr int L_EN_PIN = FORK_L_EN;
constexpr int UPPER_LIMIT_PIN = FORK_LIMIT_TOP;
constexpr int LOWER_LIMIT_PIN = FORK_LIMIT_BOT;

constexpr uint8_t FORK_PWM = 180;

// 10 Hz state publish rate.
constexpr uint32_t FORK_STATE_PERIOD_MS = 100;

// Movement command watchdog. During motion, repeated FORK commands or STOP
// must keep arriving; otherwise the motor is stopped fail-safe.
constexpr uint32_t FORK_CMD_TIMEOUT_MS = 1000;

// TODO: Measure real end-to-end fork travel time on hardware and calibrate.
// Too short causes false timeout; too long delays fail-safe behavior.
constexpr uint32_t FORK_MAX_UP_TIME_MS = 8000;
constexpr uint32_t FORK_MAX_DOWN_TIME_MS = 8000;

// Consecutive identical reads required before accepting a limit state change.
constexpr uint8_t LIMIT_DEBOUNCE_COUNT = 3;

}  // namespace fork_config
}  // namespace hamals
