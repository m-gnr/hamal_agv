#pragma once

#include <chrono>

namespace hamals_lidar_toolbox
{
namespace core
{

class ForkMaskState
{
public:
    using Clock = std::chrono::steady_clock;
    using TimePoint = Clock::time_point;

    ForkMaskState(bool enabled, double timeout_seconds)
        : enabled_(enabled), timeout_seconds_(timeout_seconds) {}

    void receive(bool lower_limit, TimePoint received_at)
    {
        lower_limit_ = lower_limit;
        received_at_ = received_at;
        received_ = true;
    }

    bool stale(TimePoint now) const
    {
        // The state remains fresh exactly at the timeout boundary.
        return received_ &&
            std::chrono::duration<double>(now - received_at_).count() > timeout_seconds_;
    }

    bool active(TimePoint now) const
    {
        return enabled_ && received_ && !stale(now) && !lower_limit_;
    }

private:
    bool enabled_;
    double timeout_seconds_;
    bool received_{false};
    bool lower_limit_{true};
    TimePoint received_at_{};
};

} // namespace core
} // namespace hamals_lidar_toolbox
