#pragma once
#include <Arduino.h>
#include <cstddef>
#include <cstdint>

// -------------------- DATA -----------------------------
struct CmdVel {
    float v = 0.0f;
    float w = 0.0f;
    bool  valid = false;
};

// -------------------- CLASS ----------------------------
class SerialComm {
public:
    // Note: Serial.begin(baud) is done in main; this just resets internal state
    void begin(unsigned long baud);
    void update();

    bool hasCmdVel() const;
    CmdVel getCmdVel();   // returns last cmd and clears valid flag

    // MCU -> ROS telemetry (custom serial protocol)
    // $ENC,t_us,dl,dr*CS\n
    void sendEnc(uint32_t t_us,
                 int32_t dl,
                 int32_t dr);

    // $IMU,t_us,gz,ax,ay,az*CS\n
    void sendImu(uint32_t t_us,
                 float gz,
                 float ax,
                 float ay,
                 float az);

private:
    static constexpr size_t RX_BUF_SIZE = 128;

    char   payload_[RX_BUF_SIZE]{};
    size_t payload_len_ = 0;

    CmdVel last_cmd_;

    // Internal helpers
    void processChar(char c);
    void parsePayload(const char* payload);


};

