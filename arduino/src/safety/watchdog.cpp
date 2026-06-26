#include "watchdog.h"
#include <Arduino.h>

Watchdog::Watchdog(float timeout_s)
    : timeout_s_(timeout_s),
      last_feed_ms_(0)
{
}

void Watchdog::reset() {
    last_feed_ms_ = millis();
}

void Watchdog::feed() {
    last_feed_ms_ = millis();
}

float Watchdog::elapsed() const {
    return (millis() - last_feed_ms_) * 0.001f;
}

Watchdog::State Watchdog::state(float grace_s) const {
    float e = elapsed();

    if (e > timeout_s_)
        return State::TIMEOUT;

    if (e > grace_s)
        return State::GRACE;

    return State::OK;
}