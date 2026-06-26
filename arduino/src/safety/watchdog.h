#pragma once
#include <stdint.h>

class Watchdog {
public:
    enum class State {
        OK,
        GRACE,
        TIMEOUT
    };

    explicit Watchdog(float timeout_s);

    void reset();
    void feed();

    float elapsed() const;
    State state(float grace_s) const;

private:
    float timeout_s_;
    uint32_t last_feed_ms_;
};