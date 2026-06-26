#include "velocity_cmd.h"
#include "../config/config_robot.h"
#include <cmath>

template <typename T>
static inline T clamp(T value, T min_val, T max_val)
{
    if (value < min_val) return min_val;
    if (value > max_val) return max_val;
    return value;
}

VelocityCmd::VelocityCmd(float wheel_radius_m,
                         float track_width_m)
    : wheel_radius_(wheel_radius_m),
      track_width_(track_width_m) {}

// ------------------------------------------------------
// setTarget()
// ------------------------------------------------------
void VelocityCmd::setTarget(float v_m_s,
                            float w_rad_s)
{
    // Robot-level clamp
    v_m_s   = clamp(v_m_s,  -MAX_LINEAR_M_S,   MAX_LINEAR_M_S);
    w_rad_s = clamp(w_rad_s, -MAX_ANGULAR_RAD_S, MAX_ANGULAR_RAD_S);

    // Differential drive inverse kinematics
    desired_omega_left_ =
        (v_m_s - (w_rad_s * track_width_ * 0.5f)) / wheel_radius_;

    desired_omega_right_ =
        (v_m_s + (w_rad_s * track_width_ * 0.5f)) / wheel_radius_;

    // Wheel speed clamp
    desired_omega_left_ =
        clamp(desired_omega_left_,  -MAX_WHEEL_RAD_S, MAX_WHEEL_RAD_S);

    desired_omega_right_ =
        clamp(desired_omega_right_, -MAX_WHEEL_RAD_S, MAX_WHEEL_RAD_S);
}

// ------------------------------------------------------
// update()
// ------------------------------------------------------
void VelocityCmd::update(float dt)
{
    if (dt <= 0.0f)
        return;

    const float max_step = MAX_WHEEL_ACCEL_RAD_S2 * dt;

    // Left wheel
    float error_left = desired_omega_left_ - current_omega_left_;
    if (error_left > max_step)
        current_omega_left_ += max_step;
    else if (error_left < -max_step)
        current_omega_left_ -= max_step;
    else
        current_omega_left_ = desired_omega_left_;

    // Right wheel
    float error_right = desired_omega_right_ - current_omega_right_;
    if (error_right > max_step)
        current_omega_right_ += max_step;
    else if (error_right < -max_step)
        current_omega_right_ -= max_step;
    else
        current_omega_right_ = desired_omega_right_;

    // Safety clamp
    current_omega_left_ =
        clamp(current_omega_left_,  -MAX_WHEEL_RAD_S, MAX_WHEEL_RAD_S);
    current_omega_right_ =
        clamp(current_omega_right_, -MAX_WHEEL_RAD_S, MAX_WHEEL_RAD_S);
}

// ------------------------------------------------------
// getWheelTargets()
// ------------------------------------------------------
void VelocityCmd::getWheelTargets(float& omega_left,
                                  float& omega_right) const
{
    omega_left  = current_omega_left_;
    omega_right = current_omega_right_;
}


float VelocityCmd::getTargetAngular() const
{
    return (desired_omega_right_ - desired_omega_left_)
           * wheel_radius_ / track_width_;
}

// ------------------------------------------------------
// reset()
// ------------------------------------------------------
void VelocityCmd::reset()
{
    desired_omega_left_  = 0.0f;
    desired_omega_right_ = 0.0f;
    current_omega_left_  = 0.0f;
    current_omega_right_ = 0.0f;
}