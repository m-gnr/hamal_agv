#include "serial_comm.h"
#include <string.h>
#include <Arduino.h>
#include <stdio.h>

// -------------------- PARSER STATE --------------------

namespace {
    enum class ParseState {
        WAIT_START,
        READ_PAYLOAD,
        READ_CHECKSUM_1,
        READ_CHECKSUM_2
    };
}

// -------------------- INTERNAL STATE ------------------

static ParseState state_ = ParseState::WAIT_START;
static uint8_t calc_checksum_ = 0;
static uint8_t recv_checksum_ = 0;

// -------------------- UTILS ---------------------------

static bool hexNibble(char c, uint8_t& out) {
    if (c >= '0' && c <= '9') { out = (uint8_t)(c - '0'); return true; }
    if (c >= 'A' && c <= 'F') { out = (uint8_t)(c - 'A' + 10); return true; }
    if (c >= 'a' && c <= 'f') { out = (uint8_t)(c - 'a' + 10); return true; }
    return false;
}

// -------------------- SERIAL COMM ---------------------

void SerialComm::begin(unsigned long baud) {
    (void)baud;
    last_cmd_.valid = false;
}

void SerialComm::update() {
    while (Serial.available()) {
        char c = Serial.read();
        processChar(c);
    }
}

void SerialComm::processChar(char c) {
    switch (state_) {

        case ParseState::WAIT_START:
            if (c == '$') {
                this->payload_len_ = 0;
                calc_checksum_ = 0;
                state_ = ParseState::READ_PAYLOAD;
            }
            break;

        case ParseState::READ_PAYLOAD:
            if (c == '*') {
                this->payload_[this->payload_len_] = '\0';
                state_ = ParseState::READ_CHECKSUM_1;
            } else {
                if (this->payload_len_ < SerialComm::RX_BUF_SIZE - 1) {
                    this->payload_[this->payload_len_++] = c;
                    calc_checksum_ ^= (uint8_t)c;
                } else {
                    // overflow → reset parser
                    this->payload_len_ = 0;
                    state_ = ParseState::WAIT_START;
                }
            }
            break;

        case ParseState::READ_CHECKSUM_1:
            // Ignore line endings if present
            if (c == '\r' || c == '\n') {
                state_ = ParseState::WAIT_START;
                break;
            }

            {
                uint8_t nib = 0;
                if (!hexNibble(c, nib)) {
                    state_ = ParseState::WAIT_START;
                    break;
                }

                recv_checksum_ = (uint8_t)(nib << 4);
                state_ = ParseState::READ_CHECKSUM_2;
            }
            break;

        case ParseState::READ_CHECKSUM_2:
            // Ignore line endings if present
            if (c == '\r' || c == '\n') {
                state_ = ParseState::WAIT_START;
                break;
            }

            {
                uint8_t nib = 0;
                if (!hexNibble(c, nib)) {
                    state_ = ParseState::WAIT_START;
                    break;
                }

                recv_checksum_ |= nib;
            }

            // Expect newline next but validate immediately
            if (recv_checksum_ == calc_checksum_) {
                parsePayload(this->payload_);
            }

            state_ = ParseState::WAIT_START;
            break;
    }
}

void SerialComm::parsePayload(const char* payload) {
    // Expected format: CMD,v,w
    if (strncmp(payload, "CMD,", 4) == 0) {
        float v, w;
        if (sscanf(payload + 4, "%f,%f", &v, &w) == 2) {
            last_cmd_.v = v;
            last_cmd_.w = w;
            last_cmd_.valid = true;
        }
    }
}

bool SerialComm::hasCmdVel() const {
    return last_cmd_.valid;
}

CmdVel SerialComm::getCmdVel() {
    last_cmd_.valid = false;
    return last_cmd_;
}

void SerialComm::sendEnc(uint32_t t_us, int32_t dl, int32_t dr) {
    // Build payload
    char payload[64];
    const int p_len = snprintf(payload, sizeof(payload),
                               "ENC,%lu,%ld,%ld",
                               (unsigned long)t_us,
                               (long)dl,
                               (long)dr);
    if (p_len <= 0 || p_len >= (int)sizeof(payload)) {
        return;
    }

    // XOR checksum over payload
    uint8_t cs = 0;
    for (int i = 0; i < p_len; ++i) {
        cs ^= (uint8_t)payload[i];
    }

    // Build full frame
    char frame[96];
    const int f_len = snprintf(frame, sizeof(frame), "$%s*%02X\n", payload, cs);
    if (f_len <= 0 || f_len >= (int)sizeof(frame)) {
        return;
    }

    // NON-BLOCKING DROP STRATEGY:
    // If the USB-CDC TX buffer is low (host stalled), skip this telemetry frame
    // so the control loop never blocks.
    if (Serial.availableForWrite() < f_len) {
        return;
    }

    Serial.write((const uint8_t*)frame, (size_t)f_len);
}

void SerialComm::sendImu(uint32_t t_us, float gz, float ax, float ay, float az) {
    // Build payload
    char payload[96];
    const int p_len = snprintf(payload, sizeof(payload),
                            "IMU,%lu,%.4f,%.4f,%.4f,%.4f",  // %.6f → %.4f
                            (unsigned long)t_us,
                            gz, ax, ay, az);
    if (p_len <= 0 || p_len >= (int)sizeof(payload)) {
        return;
    }

    // XOR checksum over payload
    uint8_t cs = 0;
    for (int i = 0; i < p_len; ++i) {
        cs ^= (uint8_t)payload[i];
    }

    // Build full frame
    char frame[128];
    const int f_len = snprintf(frame, sizeof(frame), "$%s*%02X\n", payload, cs);
    if (f_len <= 0 || f_len >= (int)sizeof(frame)) {
        return;
    }

    // NON-BLOCKING DROP STRATEGY:
    // If the USB-CDC TX buffer is low (host stalled), skip this telemetry frame
    // so the control loop never blocks.
    if (Serial.availableForWrite() < f_len) {
        return;
    }

    Serial.write((const uint8_t*)frame, (size_t)f_len);
}