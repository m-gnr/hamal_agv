#include "wheel_pid.h"
#include <cmath>

void WheelPID::setGains(float kp, float ki, float kd) {
    kp_ = kp;
    ki_ = ki;
    kd_ = kd;
}

void WheelPID::setOutputLimits(float min, float max) {
    min_out_ = min;
    max_out_ = max;
}

void WheelPID::setRampLimit(float max_step) {
    max_step_ = max_step;
}

// Deadzone / static friction compensation (per-wheel)
void WheelPID::setDeadzone(float pwm_start, float pwm_run, float cmd_eps, float meas_eps) {
    deadzone_enabled_ = true;
    pwm_start_ = fabs(pwm_start);
    pwm_run_   = fabs(pwm_run);
    cmd_eps_   = fabs(cmd_eps);
    meas_eps_  = fabs(meas_eps);
}

void WheelPID::reset() {
    integral_        = 0.0f;
    prev_measured_   = 0.0f;
    last_output_     = 0.0f;
}

float WheelPID::update(float target, float measured, float dt) {
    if (dt <= 0.0f)
        return last_output_;

    float error = target - measured;

    // Derivative on measurement (avoids derivative kick on target change)
    float derivative = -(measured - prev_measured_) / dt;

    // Tentative integral (used only for anti-windup check)
    float new_integral = integral_ + error * dt;

    // Raw output with tentative integral — for saturation detection only
    float raw_output =
        kp_ * error +
        ki_ * new_integral +
        kd_ * derivative;

    // Anti-windup: only integrate if not pushing further into saturation
    bool sat_high = raw_output > max_out_;
    bool sat_low  = raw_output < min_out_;

    if (!((sat_high && error > 0) || (sat_low && error < 0))) {
        integral_ = new_integral;
    }

    // Final output with (possibly held) integral
    float output =
        kp_ * error +
        ki_ * integral_ +
        kd_ * derivative;

    // Clamp
    if (output > max_out_)       output = max_out_;
    else if (output < min_out_)  output = min_out_;

    // Ramp limit (slew rate)
    float delta = output - last_output_;
    if (delta > max_step_)       output = last_output_ + max_step_;
    else if (delta < -max_step_) output = last_output_ - max_step_;

    // Deadzone / static friction compensation
    // If target is non-zero but measured is ~0, force a minimum PWM kick.
    if (deadzone_enabled_ && fabs(target) > cmd_eps_) {
        const float abs_meas = fabs(measured);
        const float abs_out  = fabs(output);
        const float min_pwm  = (abs_meas < meas_eps_) ? pwm_start_ : pwm_run_;
        if (abs_out < min_pwm) {
            output = (target >= 0.0f) ? min_pwm : -min_pwm;
        }
    }

    prev_measured_ = measured;
    last_output_   = output;

    return output;
}