#pragma once

#include <Arduino.h>

// ======================================================
// E18-D80NK IR OBSTACLE SENSOR
//
// LOW  = obstacle detected
// HIGH = no obstacle
//
// The sensor is read digitally.
// A small filter is used to reject noise.
// ======================================================

class Obstacle
{
public:

    explicit Obstacle(uint8_t pin);

    void begin();

    void update();

    bool detected() const;

    uint32_t lastChangeUs() const;

private:

    uint8_t pin_;

    bool detected_ = false;

    uint32_t lastChangeUs_ = 0;

    static constexpr uint8_t STABLE_COUNT = 3;

    uint8_t hitCount_ = 0;

    uint8_t missCount_ = 0;
};