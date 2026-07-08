// DENEYAP Kart 1A v2 MCU
#pragma once

// -------------------- Encoder Pins ---------------------
// Left wheel encoder
#define ENC_L_A   D12   // GPIO10 - interrupt capable - Channel A
#define ENC_L_B   D0   // GPIO1 - interrupt capable - Channel B

// Right wheel encoder
#define ENC_R_A   D13   // GPIO3  - interrupt capable - Channel A
#define ENC_R_B   D14   // GPIO8  - interrupt capable - Channel B

// -------------------- Motor Driver Pins ----------------
#define MOTOR_L_IN1  A3
#define MOTOR_L_IN2  A2

// RIGHT motor is on the remaining A0/A1 pair (keep order for now)
#define MOTOR_R_IN1  A0
#define MOTOR_R_IN2  A1

// -------------------- IMU (BNO085 - SPI) ----------------
#define IMU_CS    D4    // GPIO42 - Chip Select
#define IMU_INT   D1    // GPIO2  - Data Ready Interrupt
#define IMU_RST   D8    // GPIO38 - Reset

// -------------------- Fork / Lift Motor -----------------
// BTS7960 fork motor driver
// Note: D0/D1/D12/D13 are already used by encoders/IMU, so fork uses free pins.
#define FORK_RPWM       A5    // GPIO16 - PWM1 -> BTS7960 RPWM
#define FORK_LPWM       A4    // GPIO15 - PWM0 -> BTS7960 LPWM
#define FORK_R_EN       D10   // GPIO47 / SDA - BTS7960 R_EN    TODO: Final Mimaride Kaldırılabilir
#define FORK_L_EN       D11   // GPIO21 / SCL - BTS7960 L_EN    TODO: Final Mimaride Kaldırılabilir

// NC limit switches with INPUT_PULLUP:
// not pressed -> LOW, pressed or broken wire -> HIGH
#define FORK_LIMIT_TOP  A6    // GPIO17 - upper NC limit switch
#define FORK_LIMIT_BOT  A7    // GPIO18 - lower NC limit switch

// -------------------- Serial ---------------------------
#define SERIAL_BAUDRATE 230400
