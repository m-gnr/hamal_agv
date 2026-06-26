#pragma once
#include <stdint.h>

class Timing {
public:
    explicit Timing(float period_s);

    bool tick();

    float dt() const;

    void reset();

private:
    float period_s_;
    uint32_t last_us_;
    float dt_;
};