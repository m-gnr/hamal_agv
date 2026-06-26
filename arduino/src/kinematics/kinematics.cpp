#include "kinematics.h"
#include <cmath>

Kinematics::Kinematics(int32_t encoder_cpr_left,
                       int32_t encoder_cpr_right,
                       float   wheel_radius,
                       float   track_width)
    : encoder_cpr_left_(encoder_cpr_left),
      encoder_cpr_right_(encoder_cpr_right),
      wheel_radius_(wheel_radius),
      track_width_(track_width) {}


KinematicsOutput Kinematics::update(const KinematicsInput& input) {
    KinematicsOutput out{};

    if (input.dt <= 0.0f) {
        return out;
    }

    // --------------------
    // Pulse -> wheel angle
    // --------------------
    const float pulses_to_rad_left =
        (2.0f * static_cast<float>(M_PI)) /
        static_cast<float>(encoder_cpr_left_);

    const float pulses_to_rad_right =
        (2.0f * static_cast<float>(M_PI)) /
        static_cast<float>(encoder_cpr_right_);

    const float angle_left =
        static_cast<float>(input.delta_left) * pulses_to_rad_left;

    const float angle_right =
        static_cast<float>(input.delta_right) * pulses_to_rad_right;

    // --------------------
    // Wheel angular speed
    // --------------------
    out.omega_left  = angle_left  / input.dt;
    out.omega_right = angle_right / input.dt;

    // --------------------
    // Wheel linear speed
    // --------------------
    const float v_left  = out.omega_left  * wheel_radius_;
    const float v_right = out.omega_right * wheel_radius_;

    // --------------------
    // Robot velocities
    // --------------------
    out.v = (v_left + v_right) * 0.5f;
    out.w = (v_right - v_left) / track_width_;

    return out;
}