#include "odometry.h"
#include <cmath>

Odometry::Odometry()
    : x_(0.0f), y_(0.0f), yaw_(0.0f) {}

void Odometry::reset() {
    x_ = 0.0f;
    y_ = 0.0f;
    yaw_ = 0.0f;
}

void Odometry::update(float v_m_s, float yaw_rad, float dt_s) {
    if (dt_s <= 0.0f)
        return;

    // Yaw comes directly from IMU (absolute, already zeroed)
    yaw_ = yaw_rad;

    // Integrate position in world frame
    x_ += v_m_s * std::cos(yaw_) * dt_s;
    y_ += v_m_s * std::sin(yaw_) * dt_s;
}

float Odometry::x() const {
    return x_;
}

float Odometry::y() const {
    return y_;
}

float Odometry::yaw() const {
    return yaw_;
}
