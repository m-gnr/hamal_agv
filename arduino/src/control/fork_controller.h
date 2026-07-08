#pragma once

#include <Arduino.h>
#include <stdint.h>

namespace hamals {
namespace fork_controller {

enum ForkState : uint8_t {
    IDLE = 0,
    MOVING_UP = 1,
    MOVING_DOWN = 2,
    AT_TOP = 3,
    AT_BOTTOM = 4,
    ERROR = 5
};

enum ForkError : uint8_t {
    ERROR_NONE = 0,
    ERROR_INVALID_COMMAND = 1,
    ERROR_TOP_TIMEOUT = 2,
    ERROR_BOTTOM_TIMEOUT = 3,
    ERROR_LIMIT_CONFLICT = 4,
    ERROR_MCU_TIMEOUT = 5
};

void begin();
void update();
void handleForkCommand(const String& cmd);
ForkState getState();
ForkError getError();
bool isMoving();
bool isUpperLimitActive();
bool isLowerLimitActive();
uint32_t getLastStatePublishMs();
void markStatePublished();
String makeStatePayload();

}  // namespace fork_controller
}  // namespace hamals
