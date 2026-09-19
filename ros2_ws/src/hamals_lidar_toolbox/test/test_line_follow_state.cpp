#include "hamals_lidar_toolbox/core/LineFollowState.hpp"
#include "hamals_lidar_toolbox/core/ObstacleDetector.hpp"

#include <limits>
#include <stdexcept>

#define check(condition) do { if (!(condition)) throw std::runtime_error(#condition); } while (false)

using hamals_lidar_toolbox::core::LineFollowState;
using hamals_lidar_toolbox::core::ObstacleDetector;

int main()
{
    const auto start = LineFollowState::TimePoint{};
    const auto at = [&](int ms) { return start + std::chrono::milliseconds(ms); };
    LineFollowState state(0.5);
    ObstacleDetector detector;
    detector.setRegionDangerDistance("left", 0.20);
    detector.setRegionDangerDistance("right", 0.20);
    detector.setRegionDangerDistance("rear", 0.80);
    const auto verify = [&](int ms, bool active) {
        check(state.active(at(ms)) == active);
        detector.setRegionDangerDistance("front", state.active(at(ms)) ? 0.04 : 0.85);
        const auto obstacles = detector.detect({
            {"front", {1, 0.50, 0.50}}, {"left", {1, 0.15, 0.15}},
            {"right", {1, 0.15, 0.15}}, {"rear", {1, 0.50, 0.50}}});
        check(obstacles.at("front").has_obstacle == !active);
        for (const auto* other : {"left", "right", "rear"})
            check(obstacles.at(other).has_obstacle);
    };

    verify(0, false); // No message, normal profile.
    state.receive(true, at(0));
    verify(0, true);
    for (int ms = 100; ms <= 1000; ms += 100)
    {
        state.receive(true, at(ms));
        verify(ms, true);
    }
    verify(1500, true); // age == timeout remains fresh.
    verify(1501, false); // Crash/lost False: no message needed to expire.
    check(state.stale(at(1501)));
    verify(10000, false);
    state.receive(true, at(10100));
    verify(10100, true);
    state.receive(false, at(10101));
    verify(10101, false); // Explicit False takes effect immediately.
    check(!state.stale(at(10101)));

    LineFollowState restarted(0.5);
    check(!restarted.active(at(20000)));
    restarted.receive(true, at(20100)); // Next heartbeat after subscriber restart.
    check(restarted.active(at(20100)));
    check(!restarted.active(at(20601)));

    for (double invalid : {0.0, -0.5, std::numeric_limits<double>::infinity(),
                           std::numeric_limits<double>::quiet_NaN()})
    {
        bool rejected = false;
        try { LineFollowState bad(invalid); }
        catch (const std::invalid_argument&) { rejected = true; }
        check(rejected);
    }
    return 0;
}
