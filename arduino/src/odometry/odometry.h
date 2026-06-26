// src/odometry/odometry.h
#pragma once

// =======================================================
// Odometry (IMU-assisted, 2D)
// -------------------------------------------------------
// Responsibility:
//  - Integrate robot position (x, y) in world frame
//  - Use absolute yaw from IMU (already zeroed at startup)
//  - Use linear velocity v from kinematics
//
// Does NOT:
//  - Read encoders
//  - Compute yaw from wheels
//  - Handle timing or dt calculation
// =======================================================

class Odometry {
public:
    Odometry();

    // Reset pose to origin (0,0,0)
    void reset();

    // Update odometry
    //
    // v_m_s   : robot linear velocity (m/s)  -> from Kinematics
    // yaw_rad : absolute yaw (rad)           -> from IMU
    // dt_s    : delta time (seconds)
    void update(float v_m_s,
                float yaw_rad,
                float dt_s);

    float x() const;
    float y() const;
    float yaw() const;

private:
    float x_;    
    float y_;    
    float yaw_;  
};