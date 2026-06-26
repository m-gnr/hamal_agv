#pragma once
#include <stdint.h>

class Motor {
public:
    Motor(uint8_t in1,
          uint8_t in2,
          int pwm_max);

    void begin();
    void setPWM(int pwm);
    void stop();

private:
    uint8_t in1_;
    uint8_t in2_;
    int pwm_max_;

    uint8_t pwm_channel_1_;
    uint8_t pwm_channel_2_;
};