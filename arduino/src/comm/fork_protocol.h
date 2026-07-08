#pragma once

#include <Arduino.h>

namespace hamals {
namespace fork_protocol {

bool handleForkPayload(const char* payload);
bool handleForkPayload(const String& payload);
void publishForkStateIfDue();

}  // namespace fork_protocol
}  // namespace hamals
