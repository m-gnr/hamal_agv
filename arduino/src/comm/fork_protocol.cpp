#include "fork_protocol.h"

#include <string.h>
#include <stdint.h>

#include "../config/fork_config.h"
#include "../control/fork_controller.h"
#include "frame_codec.h"

namespace hamals {
namespace fork_protocol {

bool handleForkPayload(const char* payload) {
    if (!payload || strncmp(payload, "FORK,", 5) != 0) {
        return false;
    }

    const char* cmd = payload + 5;
    if (strcmp(cmd, "UP") == 0 ||
        strcmp(cmd, "DOWN") == 0 ||
        strcmp(cmd, "STOP") == 0) {
        fork_controller::handleForkCommand(String(cmd));
    } else {
        fork_controller::handleForkCommand(String(""));
    }

    return true;
}

bool handleForkPayload(const String& payload) {
    return handleForkPayload(payload.c_str());
}

void publishForkStateIfDue() {
    const uint32_t now = millis();
    if (now - fork_controller::getLastStatePublishMs() <
        fork_config::FORK_STATE_PERIOD_MS) {
        return;
    }

    const String payload = fork_controller::makeStatePayload();
    if (frame_codec::writeFrame(payload.c_str())) {
        fork_controller::markStatePublished();
    }
}

}  // namespace fork_protocol
}  // namespace hamals
