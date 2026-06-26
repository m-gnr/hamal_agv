#pragma once

class VelocityCmd {
public:
    VelocityCmd(float wheel_radius_m,
                float track_width_m);

    void setTarget(float v_m_s,
                   float w_rad_s);

    void update(float dt);

    void getWheelTargets(float& omega_left,
                         float& omega_right) const;

    float getTargetAngular() const;

    void reset();

private:
    float wheel_radius_;
    float track_width_;

    float desired_omega_left_  = 0.0f;
    float desired_omega_right_ = 0.0f;

    float current_omega_left_  = 0.0f;
    float current_omega_right_ = 0.0f;
};