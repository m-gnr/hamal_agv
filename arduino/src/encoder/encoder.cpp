#include "encoder.h"
#include <Arduino.h>
#include "soc/gpio_struct.h"

static Encoder* encoder_instance_1 = nullptr;
static Encoder* encoder_instance_2 = nullptr;

void IRAM_ATTR encoderISR_1A() { if (encoder_instance_1) encoder_instance_1->handleISR_A(); }
void IRAM_ATTR encoderISR_1B() { if (encoder_instance_1) encoder_instance_1->handleISR_B(); }
void IRAM_ATTR encoderISR_2A() { if (encoder_instance_2) encoder_instance_2->handleISR_A(); }
void IRAM_ATTR encoderISR_2B() { if (encoder_instance_2) encoder_instance_2->handleISR_B(); }

Encoder::Encoder(uint8_t pinA, uint8_t pinB, int direction)
    : pinA_(pinA), pinB_(pinB), direction_(direction) {}

void Encoder::begin() {
    pinMode(pinA_, INPUT_PULLUP);
    pinMode(pinB_, INPUT_PULLUP);

    if (encoder_instance_1 == nullptr) {
        encoder_instance_1 = this;
        attachInterrupt(digitalPinToInterrupt(pinA_), encoderISR_1A, CHANGE);
        attachInterrupt(digitalPinToInterrupt(pinB_), encoderISR_1B, CHANGE);
    }
    else if (encoder_instance_2 == nullptr) {
        encoder_instance_2 = this;
        attachInterrupt(digitalPinToInterrupt(pinA_), encoderISR_2A, CHANGE);
        attachInterrupt(digitalPinToInterrupt(pinB_), encoderISR_2B, CHANGE);
    }
    else {
        Serial.println("ERROR: Too many Encoder instances!");
    }
}

void IRAM_ATTR Encoder::handleISR_A() {
    uint32_t gpio = GPIO.in;                
    bool a = (gpio >> pinA_) & 1u;
    bool b = (gpio >> pinB_) & 1u;
    count_ += direction_ * ((a == b) ? -1 : 1);
}

void IRAM_ATTR Encoder::handleISR_B() {
    uint32_t gpio = GPIO.in;
    bool a = (gpio >> pinA_) & 1u;
    bool b = (gpio >> pinB_) & 1u;
    count_ += direction_ * ((a == b) ? 1 : -1);
}

int32_t Encoder::readDelta() {
    noInterrupts();
    int32_t current = count_;
    int32_t delta   = current - last_count_;
    last_count_     = current;
    interrupts();
    return delta;
}

int32_t Encoder::readTotal() {
    noInterrupts();
    int32_t total = count_;
    interrupts();
    return total;
}

void Encoder::reset() {
    noInterrupts();
    count_      = 0;
    last_count_ = 0;
    interrupts();
}