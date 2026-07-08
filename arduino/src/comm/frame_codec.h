#pragma once

#include <stdint.h>

namespace hamals {
namespace frame_codec {

uint8_t computeChecksum(const char* payload);
bool writeFrame(const char* payload);

}  // namespace frame_codec
}  // namespace hamals
