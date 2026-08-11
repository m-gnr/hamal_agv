// DENEYAP Kart 1A v2 MCU
#pragma once

// -------------------- Encoder Pins ---------------------
// Left wheel encoder  yous degisti b=sari=>13
#define ENC_L_A   D14  // GPIO10 - interrupt capable - Channel A
#define ENC_L_B   D13  // GPIO1 - interrupt capable - Channel B

// Right wheel encoder
#define ENC_R_A   D11  // GPIO3  - interrupt capable - Channel A
#define ENC_R_B   D10   // GPIO8  - interrupt capable - Channel B

// -------------------- Motor Driver Pins ----------------
#define MOTOR_L_IN1  A2
#define MOTOR_L_IN2  A3

// RIGHT motor is on the remaining A0/A1 pair (keep order for now)
#define MOTOR_R_IN1  A0
#define MOTOR_R_IN2  A1

// -------------------- IMU (BNO085 - SPI) ----------------
#define IMU_CS    D4    // GPIO42 - Chip Select
#define IMU_INT   D1    // GPIO2  - Data Ready Interrupt
#define IMU_RST   D8   // GPIO38 - Reset

#define IMU_SCK   D5    //GPIO26 - SCK
#define IMU_MISO  D6    //GPIO27 - MISO SDA
#define IMU_MOSI  D7    //GPIO28 - MOSI SCL

// -------------------- Fork / Lift Motor -----------------
// BTS7960 fork motor driver
// Note: D0/D1/D12/D13 are already used by encoders/IMU, so fork uses free pins.
#define FORK_RPWM       A5    // GPIO16 - PWM1 -> BTS7960 RPWM
#define FORK_LPWM       A4    // GPIO15 - PWM0 -> BTS7960 LPWM

// NC limit switches with INPUT_PULLUP:
// not pressed -> LOW, pressed or broken wire -> HIGH
#define FORK_LIMIT_TOP  A6    // GPIO17 - upper NC limit switch
#define FORK_LIMIT_BOT  A7    // GPIO18 - lower NC limit switch

// Manuel/Otonom switch INPUT_PULLUP:
// #define MANUEL D11
// #define OTONOM D12
// -------------------- Serial ---------------------------
#define SERIAL_BAUDRATE 230400
