#include "timing.h"
#include <Arduino.h>

Timing::Timing(float period_s)
    : period_s_(period_s),
      last_us_(0),
      dt_(0.0f)
{
}

bool Timing::tick()
{
    uint32_t now_us = micros();

    if (last_us_ == 0) {
        last_us_ = now_us;
        return false;
    }

    uint32_t elapsed_us = now_us - last_us_;  // overflow-safe (uint32_t)
    uint32_t period_us  = static_cast<uint32_t>(period_s_ * 1e6f);

    if (elapsed_us < period_us)
        return false;

    dt_ = elapsed_us * 1e-6f;   
    last_us_ = now_us;

    return true;
}

float Timing::dt() const
{
    return dt_;
}

void Timing::reset()
{
    last_us_ = 0;
    dt_ = 0.0f;
}