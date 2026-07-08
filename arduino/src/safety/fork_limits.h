#pragma once

namespace hamals {
namespace fork_limits {

void begin();
void update();
bool isUpperLimitActive();
bool isLowerLimitActive();
bool hasLimitConflict();

}  // namespace fork_limits
}  // namespace hamals
