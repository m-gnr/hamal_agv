#pragma once

#include <chrono>
#include <cmath>
#include <stdexcept>

namespace hamals_lidar_toolbox
{
namespace core
{

// Access is serialized by the scan processor's default callback group.
class LineFollowState
{
public:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;

    explicit LineFollowState(double timeout_seconds) : timeout_seconds_(timeout_seconds)
    {
        if (!std::isfinite(timeout_seconds_) || timeout_seconds_ <= 0.0)
        {
            throw std::invalid_argument(
                "line_follow.state_timeout_sec must be finite and positive");
        }
    }

    void receive(bool requested, TimePoint now)
    {
        requested_ = requested;
        last_seen_ = now;
    }

    bool stale(TimePoint now) const
    {
        return requested_ &&
            std::chrono::duration<double>(now - last_seen_).count() > timeout_seconds_;
    }

    bool active(TimePoint now) const
    {
        return requested_ && !stale(now);
    }

private:
    double timeout_seconds_;
    bool requested_{false};
    TimePoint last_seen_{};
};

} // namespace core
} // namespace hamals_lidar_toolbox
