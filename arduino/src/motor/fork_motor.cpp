#include "fork_motor.h"

#include <Arduino.h>

#include "../config/fork_config.h"

namespace hamals {
namespace fork_motor {

void begin() {
    pinMode(fork_config::RPWM_PIN, OUTPUT);
    pinMode(fork_config::LPWM_PIN, OUTPUT);
    //pinMode(fork_config::R_EN_PIN, OUTPUT);
    //pinMode(fork_config::L_EN_PIN, OUTPUT);

    //digitalWrite(fork_config::R_EN_PIN, HIGH);
    //digitalWrite(fork_config::L_EN_PIN, HIGH);

    motorStop();
}

void motorUp() {
    // If real hardware direction is reversed, swap RPWM/LPWM usage here only.
    analogWrite(fork_config::RPWM_PIN, fork_config::FORK_PWM);
    analogWrite(fork_config::LPWM_PIN, 0);
}

void motorDown() {
    analogWrite(fork_config::RPWM_PIN, 0);
    analogWrite(fork_config::LPWM_PIN, fork_config::FORK_PWM);
}

void motorStop() {
    analogWrite(fork_config::RPWM_PIN, 0);
    analogWrite(fork_config::LPWM_PIN, 0);
}

}  // namespace fork_motor
}  // namespace hamals

