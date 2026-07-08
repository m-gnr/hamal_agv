#include "frame_codec.h"

#include <Arduino.h>
#include <stddef.h>
#include <stdio.h>

namespace hamals {
namespace frame_codec {

uint8_t computeChecksum(const char* payload) {
    uint8_t cs = 0;
    if (!payload) {
        return cs;
    }

    for (size_t i = 0; payload[i] != '\0'; ++i) {
        cs ^= static_cast<uint8_t>(payload[i]);
    }
    return cs;
}

bool writeFrame(const char* payload) {
    if (!payload) {
        return false;
    }

    const uint8_t cs = computeChecksum(payload);

    char frame[160];
    const int f_len = snprintf(frame, sizeof(frame), "$%s*%02X\n", payload, cs);
    if (f_len <= 0 || f_len >= static_cast<int>(sizeof(frame))) {
        return false;
    }

    // Non-blocking drop strategy: keep the control loop responsive if USB-CDC
    // TX is back-pressured by the host.
    if (Serial.availableForWrite() < f_len) {
        return false;
    }

    Serial.write(reinterpret_cast<const uint8_t*>(frame), static_cast<size_t>(f_len));
    return true;
}

}  // namespace frame_codec
}  // namespace hamals
