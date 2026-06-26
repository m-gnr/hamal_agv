#ifndef ENCODER_H
#define ENCODER_H

#include <Arduino.h>

class Encoder {
public:
    Encoder(uint8_t pinA, uint8_t pinB, int direction = 1);
    void begin();
    int32_t readDelta();    
    int32_t readTotal();    
    void reset();

private:
    const uint8_t pinA_;
    const uint8_t pinB_;
    const int direction_;   
    volatile int32_t count_ = 0;   
    int32_t last_count_ = 0;       

    void IRAM_ATTR handleISR_A();
    void IRAM_ATTR handleISR_B();

    friend void IRAM_ATTR encoderISR_1A();
    friend void IRAM_ATTR encoderISR_1B();
    friend void IRAM_ATTR encoderISR_2A();
    friend void IRAM_ATTR encoderISR_2B();
};

#endif