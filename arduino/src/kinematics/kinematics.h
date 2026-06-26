#pragma once

#include <stdint.h>

struct KinematicsInput {
    int32_t delta_left;     
    int32_t delta_right;    
    float   dt;             
};

struct KinematicsOutput {
    float omega_left;       // rad/s
    float omega_right;      // rad/s
    float v;                // m/s
    float w;                // rad/s
};

class Kinematics {
public:
    Kinematics(int32_t encoder_cpr_left,
               int32_t encoder_cpr_right,
               float   wheel_radius,
               float   track_width);

    KinematicsOutput update(const KinematicsInput& input);

private:
    int32_t encoder_cpr_left_;
    int32_t encoder_cpr_right_;
    float   wheel_radius_;
    float   track_width_;
};