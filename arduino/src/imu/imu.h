#pragma once

#include <Arduino.h>
#include <Adafruit_BNO08x.h>

class IMU {
public:
    IMU(uint8_t cs_pin,
        uint8_t int_pin,
        uint8_t rst_pin);

    bool begin();
    void update();

    float getGz() const;
    float getAx() const;
    float getAy() const;
    float getAz() const;

    volatile bool dataReady = false;

private:
    uint8_t cs_;
    uint8_t int_;
    uint8_t rst_;

    Adafruit_BNO08x bno08x_;
    sh2_SensorValue_t sensorValue_;

    float gz_ = 0.0f;
    float ax_ = 0.0f;
    float ay_ = 0.0f;
    float az_ = 0.0f;
};