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

// -------------------- Serial ---------------------------
#define SERIAL_BAUDRATE 230400
