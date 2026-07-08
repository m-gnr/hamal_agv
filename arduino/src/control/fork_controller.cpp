#include "fork_controller.h"

#include <Arduino.h>

#include "../config/fork_config.h"
#include "../motor/fork_motor.h"
#include "../safety/fork_limits.h"

namespace hamals {
namespace fork_controller {
namespace {

ForkState fork_state_ = IDLE;
ForkError fork_error_ = ERROR_NONE;
uint32_t last_command_time_ms_ = 0;
uint32_t motion_start_ms_ = 0;
uint32_t last_state_publish_ms_ = 0;

bool isMovingState() {
    return fork_state_ == MOVING_UP || fork_state_ == MOVING_DOWN;
}

void setError(ForkError error) {
    fork_motor::motorStop();
    fork_state_ = ERROR;
    fork_error_ = error;
}

void stopAndSet(ForkState state, ForkError error) {
    fork_motor::motorStop();
    fork_state_ = state;
    fork_error_ = error;
}

bool applyLimitConflictIfNeeded() {
    if (!fork_limits::hasLimitConflict()) {
        return false;
    }

    setError(ERROR_LIMIT_CONFLICT);
    return true;
}

void handleStop() {
    last_command_time_ms_ = millis();
    stopAndSet(IDLE, ERROR_NONE);
    motion_start_ms_ = 0;
}

void handleUp() {
    last_command_time_ms_ = millis();
    const bool already_moving_up = fork_state_ == MOVING_UP;

    if (applyLimitConflictIfNeeded()) {
        return;
    }

    if (fork_limits::isUpperLimitActive()) {
        stopAndSet(AT_TOP, ERROR_NONE);
        return;
    }

    fork_motor::motorUp();
    fork_state_ = MOVING_UP;
    fork_error_ = ERROR_NONE;
    if (!already_moving_up) {
        motion_start_ms_ = millis();
    }
}

void handleDown() {
    last_command_time_ms_ = millis();
    const bool already_moving_down = fork_state_ == MOVING_DOWN;

    if (applyLimitConflictIfNeeded()) {
        return;
    }

    if (fork_limits::isLowerLimitActive()) {
        stopAndSet(AT_BOTTOM, ERROR_NONE);
        return;
    }

    fork_motor::motorDown();
    fork_state_ = MOVING_DOWN;
    fork_error_ = ERROR_NONE;
    if (!already_moving_down) {
        motion_start_ms_ = millis();
    }
}

}  // namespace

void begin() {
    fork_motor::motorStop();
    fork_limits::update();

    fork_state_ = IDLE;
    fork_error_ = ERROR_NONE;
    last_command_time_ms_ = millis();
    motion_start_ms_ = 0;
    last_state_publish_ms_ = 0;
}

void update() {
    fork_limits::update();

    if (applyLimitConflictIfNeeded()) {
        return;
    }

    const uint32_t now = millis();

    if (fork_state_ == MOVING_UP && fork_limits::isUpperLimitActive()) {
        stopAndSet(AT_TOP, ERROR_NONE);
        return;
    }

    if (fork_state_ == MOVING_DOWN && fork_limits::isLowerLimitActive()) {
        stopAndSet(AT_BOTTOM, ERROR_NONE);
        return;
    }

    if (fork_state_ == MOVING_UP &&
        now - motion_start_ms_ > fork_config::FORK_MAX_UP_TIME_MS) {
        setError(ERROR_TOP_TIMEOUT);
        return;
    }

    if (fork_state_ == MOVING_DOWN &&
        now - motion_start_ms_ > fork_config::FORK_MAX_DOWN_TIME_MS) {
        setError(ERROR_BOTTOM_TIMEOUT);
        return;
    }

    if (isMovingState() &&
        now - last_command_time_ms_ > fork_config::FORK_CMD_TIMEOUT_MS) {
        setError(ERROR_MCU_TIMEOUT);
    }
}

void handleForkCommand(const String& cmd) {
    fork_limits::update();

    String normalized = cmd;
    normalized.trim();
    normalized.toUpperCase();

    if (fork_state_ == ERROR) {
        if (normalized == "STOP") {
            handleStop();
        } else {
            fork_motor::motorStop();
        }
        return;
    }

    if (normalized == "STOP") {
        handleStop();
    } else if (normalized == "UP") {
        handleUp();
    } else if (normalized == "DOWN") {
        handleDown();
    } else {
        setError(ERROR_INVALID_COMMAND);
    }
}

ForkState getState() {
    return fork_state_;
}

ForkError getError() {
    return fork_error_;
}

bool isMoving() {
    return isMovingState();
}

bool isUpperLimitActive() {
    return fork_limits::isUpperLimitActive();
}

bool isLowerLimitActive() {
    return fork_limits::isLowerLimitActive();
}

uint32_t getLastStatePublishMs() {
    return last_state_publish_ms_;
}

void markStatePublished() {
    last_state_publish_ms_ = millis();
}

String makeStatePayload() {
    String payload = "FORK_STATE,";
    payload += String(static_cast<uint32_t>(micros()));
    payload += ",";
    payload += String(static_cast<int>(fork_state_));
    payload += ",";
    payload += (isUpperLimitActive() ? "1" : "0");
    payload += ",";
    payload += (isLowerLimitActive() ? "1" : "0");
    payload += ",";
    payload += String(static_cast<int>(fork_error_));
    return payload;
}

}  // namespace fork_controller
}  // namespace hamals
