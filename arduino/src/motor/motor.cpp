#include "motor.h"
#include <Arduino.h>

// PWM config
static constexpr uint32_t PWM_FREQ = 20000;   // 20 kHz
static constexpr uint8_t  PWM_RES  = 8;       // 8-bit → 0-255

static uint8_t next_channel = 0;

Motor::Motor(uint8_t in1,
             uint8_t in2,
             int pwm_max)
    : in1_(in1),
      in2_(in2),
      pwm_max_(pwm_max)
{
    pwm_channel_1_ = next_channel++;
    pwm_channel_2_ = next_channel++;
}

void Motor::begin()
{
    pinMode(in1_, OUTPUT);
    pinMode(in2_, OUTPUT);

    ledcSetup(pwm_channel_1_, PWM_FREQ, PWM_RES);
    ledcSetup(pwm_channel_2_, PWM_FREQ, PWM_RES);

    ledcAttachPin(in1_, pwm_channel_1_);
    ledcAttachPin(in2_, pwm_channel_2_);

    stop();
}

void Motor::setPWM(int pwm)
{
    if (pwm > pwm_max_)  pwm = pwm_max_;
    if (pwm < -pwm_max_) pwm = -pwm_max_;

    if (pwm > 0) {
        ledcWrite(pwm_channel_1_, pwm);
        ledcWrite(pwm_channel_2_, 0);
    }
    else if (pwm < 0) {
        ledcWrite(pwm_channel_1_, 0);
        ledcWrite(pwm_channel_2_, -pwm);
    }
    else {
        stop();
    }
}

void Motor::stop()
{
    ledcWrite(pwm_channel_1_, 0);
    ledcWrite(pwm_channel_2_, 0);
}