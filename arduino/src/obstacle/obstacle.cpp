#include "obstacle.h"

// ======================================================
// CONSTRUCTOR
// ======================================================

Obstacle::Obstacle(uint8_t pin)
    : pin_(pin)
{
}

// ======================================================
// BEGIN
// ======================================================

void Obstacle::begin()
{
    pinMode(pin_, INPUT);

    detected_ = false;

    hitCount_ = 0;

    missCount_ = 0;

    lastChangeUs_ = micros();
}

// ======================================================
// UPDATE
// ======================================================

void Obstacle::update()
{
    // E18-D80NK:
    // LOW  = obstacle
    // HIGH = free

    const bool raw =
        (digitalRead(pin_) == LOW);

    // --------------------------------------------------
    // OBSTACLE
    // --------------------------------------------------

    if (raw)
    {
        hitCount_++;

        missCount_ = 0;
    }

    // --------------------------------------------------
    // NO OBSTACLE
    // --------------------------------------------------

    else
    {
        missCount_++;

        hitCount_ = 0;
    }

    // --------------------------------------------------
    // CONFIRM OBSTACLE
    // --------------------------------------------------

    if (
        hitCount_ >= STABLE_COUNT &&
        !detected_
    )
    {
        detected_ = true;

        lastChangeUs_ = micros();
    }

    // --------------------------------------------------
    // CONFIRM CLEAR
    // --------------------------------------------------

    else if (
        missCount_ >= STABLE_COUNT &&
        detected_
    )
    {
        detected_ = false;

        lastChangeUs_ = micros();
    }
}

// ======================================================
// DETECTED
// ======================================================

bool Obstacle::detected() const
{
    return detected_;
}

// ======================================================
// LAST CHANGE
// ======================================================

uint32_t Obstacle::lastChangeUs() const
{
    return lastChangeUs_;
}