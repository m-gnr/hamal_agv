#include "imu.h"
#include <Arduino.h>
#include <SPI.h>
#include <cmath>
#include "../config/config_robot.h"

IMU::IMU(uint8_t cs_pin,
         uint8_t int_pin,
         uint8_t rst_pin)
    : cs_(cs_pin),
      int_(int_pin),
      rst_(rst_pin),
      bno08x_(rst_pin)
{
}

bool IMU::begin()
{
    if (!bno08x_.begin_SPI(cs_, int_, &SPI, 3000000)) {
        return false;
    }

    const uint32_t report_period_us = static_cast<uint32_t>(IMU_TX_DT_S * 1e6f);

    bno08x_.enableReport(SH2_GYROSCOPE_CALIBRATED, report_period_us);
    bno08x_.enableReport(SH2_LINEAR_ACCELERATION, report_period_us);

    delay(200);

    gz_ = 0.0f;
    ax_ = 0.0f;
    ay_ = 0.0f;
    az_ = 0.0f;

    return true;
}

void IMU::update()
{
    if (!bno08x_.getSensorEvent(&sensorValue_)) {
        return;
    }

    switch (sensorValue_.sensorId) {
        case SH2_GYROSCOPE_CALIBRATED:
            gz_ = sensorValue_.un.gyroscope.z;
            break;

        case SH2_LINEAR_ACCELERATION:
            ax_ = sensorValue_.un.linearAcceleration.x;
            ay_ = sensorValue_.un.linearAcceleration.y;
            az_ = sensorValue_.un.linearAcceleration.z;
            break;

        default:
            break;
    }
}

float IMU::getGz() const { return gz_; }
float IMU::getAx() const { return ax_; }
float IMU::getAy() const { return ay_; }
float IMU::getAz() const { return az_; }