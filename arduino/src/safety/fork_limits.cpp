#include "fork_limits.h"

#include <Arduino.h>
#include <stdint.h>

#include "../config/fork_config.h"

namespace hamals {
namespace fork_limits {
namespace {

bool upper_limit_ = false;
bool lower_limit_ = false;
bool upper_candidate_ = false;
bool lower_candidate_ = false;
uint8_t upper_count_ = 0;
uint8_t lower_count_ = 0;

bool readUpperRaw() {
    // NC + INPUT_PULLUP: pressed or broken wire reads HIGH, fail-safe active.
    return digitalRead(fork_config::UPPER_LIMIT_PIN) == HIGH;
}

bool readLowerRaw() {
    return digitalRead(fork_config::LOWER_LIMIT_PIN) == HIGH;
}

void updateDebounced(bool raw,
                     bool& stable,
                     bool& candidate,
                     uint8_t& count) {
    if (raw == stable) {
        candidate = raw;
        count = 0;
        return;
    }

    if (raw != candidate) {
        candidate = raw;
        count = 1;
        return;
    }

    if (count < fork_config::LIMIT_DEBOUNCE_COUNT) {
        ++count;
    }

    if (count >= fork_config::LIMIT_DEBOUNCE_COUNT) {
        stable = candidate;
        count = 0;
    }
}

}  // namespace

void begin() {
    pinMode(fork_config::UPPER_LIMIT_PIN, INPUT_PULLUP);
    pinMode(fork_config::LOWER_LIMIT_PIN, INPUT_PULLUP);

    upper_limit_ = readUpperRaw();
    lower_limit_ = readLowerRaw();
    upper_candidate_ = upper_limit_;
    lower_candidate_ = lower_limit_;
    upper_count_ = 0;
    lower_count_ = 0;
}

void update() {
    updateDebounced(readUpperRaw(), upper_limit_, upper_candidate_, upper_count_);
    updateDebounced(readLowerRaw(), lower_limit_, lower_candidate_, lower_count_);
}

bool isUpperLimitActive() {
    return upper_limit_;
}

bool isLowerLimitActive() {
    return lower_limit_;
}

bool hasLimitConflict() {
    return upper_limit_ && lower_limit_;
}

}  // namespace fork_limits
}  // namespace hamals
