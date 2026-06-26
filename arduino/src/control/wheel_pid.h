#pragma once

class WheelPID {
public:
    void setGains(float kp, float ki, float kd);
    void setOutputLimits(float min, float max);
    void setRampLimit(float max_step);

    // Deadzone / static friction compensation (per-wheel)
    // pwm_start: minimum PWM to start moving from standstill
    // pwm_run:   minimum PWM to keep moving once already rotating
    // cmd_eps:   minimum commanded omega to consider as "moving"
    // meas_eps:  measured omega threshold to treat as standstill
    void setDeadzone(float pwm_start, float pwm_run,
                     float cmd_eps = 0.05f,
                     float meas_eps = 0.20f);

    void reset();
    float update(float target, float measured, float dt);

private:
    float kp_            = 0.0f;
    float ki_            = 0.0f;
    float kd_            = 0.0f;

    // safe default
    float min_out_       = -255.0f;
    float max_out_       =  255.0f;
    float max_step_      =  10.0f;

    float integral_      = 0.0f;
    float prev_measured_ = 0.0f;     // derivative kick fix
    float last_output_   = 0.0f;

    // Deadzone settings
    bool  deadzone_enabled_ = false;
    float pwm_start_        = 0.0f;
    float pwm_run_          = 0.0f;
    float cmd_eps_          = 0.05f;
    float meas_eps_         = 0.20f;
};