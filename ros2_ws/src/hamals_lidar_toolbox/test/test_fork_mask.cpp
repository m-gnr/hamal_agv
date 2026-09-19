#include "hamals_lidar_toolbox/core/ForkMaskState.hpp"
#include "hamals_lidar_toolbox/core/ObstacleDetector.hpp"
#include "hamals_lidar_toolbox/core/ScanData.hpp"
#include "hamals_lidar_toolbox/core/ScanMetrics.hpp"
#include "hamals_lidar_toolbox/core/ScanSegmenter.hpp"

#include <chrono>
#include <cmath>
#include <stdexcept>
#include <vector>

#define check(condition) do { if (!(condition)) throw std::runtime_error(#condition); } while (false)

using hamals_lidar_toolbox::core::ForkMaskState;
using hamals_lidar_toolbox::core::ObstacleDetector;
using hamals_lidar_toolbox::core::ScanData;
using hamals_lidar_toolbox::core::ScanMetrics;
using hamals_lidar_toolbox::core::ScanSegmenter;

static void checkObstacles(const ForkMaskState& state, ForkMaskState::TimePoint now,
                           bool front_dangerous)
{
    // Both ends of the scan belong to the wrap-around front region.
    const ScanData scan({0.15f, 1.0f, 1.0f, 0.16f, 1.0f, 1.0f, 0.35f,
                         1.0f, 1.0f, 0.16f, 1.0f, 1.0f, 0.16f}, -3.0, 0.5, 0.0);
    const ScanSegmenter segmenter({
        {"rear", -0.785, 0.785},
        {"right", 0.785, 2.356},
        {"left", -2.356, -0.785},
        {"front", 2.356, -2.356}
    });
    const auto segments = segmenter.segment(scan, state.active(now) ? "front" : "");
    check(segments.at("front").empty() == state.active(now));
    check(segments.at("rear").size() == 3);
    check(segments.at("left").size() == 3);
    check(segments.at("right").size() == 3);

    const auto metrics = ScanMetrics::compute(scan, segments);
    ObstacleDetector detector;
    detector.setDangerDistance(0.17);
    detector.setRegionDangerDistance("rear", 0.40);
    const auto obstacles = detector.detect(metrics);
    check(obstacles.at("front").has_obstacle == front_dangerous);
    check(obstacles.at("rear").has_obstacle); // Region-specific threshold.
    check(obstacles.at("left").has_obstacle);
    check(obstacles.at("right").has_obstacle);
    if (state.active(now))
    {
        check(metrics.at("front").count == 0);
        check(std::isinf(obstacles.at("front").min_distance));
    }
}

int main()
{
    const auto start = ForkMaskState::TimePoint{};
    const auto at = [&](int milliseconds) {
        return start + std::chrono::milliseconds(milliseconds);
    };

    ForkMaskState state(true, 0.5);
    check(!state.active(at(0))); // No ForkState received.
    checkObstacles(state, at(0), true);

    state.receive(true, at(0));
    check(!state.active(at(0))); // Fork at lower limit.
    checkObstacles(state, at(0), true);

    state.receive(false, at(0));
    check(state.active(at(0)));
    checkObstacles(state, at(0), false);

    ForkMaskState disabled(false, 0.5);
    disabled.receive(false, at(0));
    check(!disabled.active(at(0)));
    checkObstacles(disabled, at(0), true);

    check(!state.stale(at(500))); // Exact timeout boundary is still fresh.
    checkObstacles(state, at(500), false);
    check(state.stale(at(501)));
    check(!state.active(at(501)));
    checkObstacles(state, at(501), true);

    state.receive(true, at(600));
    checkObstacles(state, at(600), true);
    state.receive(false, at(601));
    checkObstacles(state, at(601), false);

    // A-D: normal switch behavior and independent, narrow escape override.
    for (bool lower : {false, true})
    {
        ForkMaskState escape(true, 0.5, 1.0);
        escape.receive(lower, at(0));
        escape.receiveEscape(false, at(0));
        check(escape.active(at(0)) == !lower);
        check(!escape.escapeActive(at(0)));
        escape.receiveEscape(true, at(0));
        check(escape.escapeActive(at(0)));
        check(escape.active(at(0)) == !lower);
        check(escape.escapeActive(at(1000)));
        // E: stale override falls back to a freshly received switch state.
        escape.receive(lower, at(1001));
        check(!escape.escapeActive(at(1001)));
        check(escape.active(at(1001)) == !lower);
        escape.receiveEscape(true, at(1100));
        escape.receiveEscape(false, at(1101));
        check(!escape.escapeActive(at(1101)));
    }
    disabled.receiveEscape(true, at(0));
    check(!disabled.escapeActive(at(0)));

    // Escape excludes only +/-0.20 rad around the fork at pi. Front beams
    // outside that sector, and every other region, still detect obstacles.
    const ScanData scan({0.15f, 0.15f, 0.15f, 0.15f, 0.15f, 0.15f, 0.15f,
                         0.15f, 0.15f, 0.15f, 0.15f, 0.15f, 0.15f}, -3.0, 0.5, 0.0);
    const ScanSegmenter segmenter({
        {"rear", -0.785, 0.785}, {"right", 0.785, 2.356},
        {"left", -2.356, -0.785}, {"front", 2.356, -2.356}
    });
    const ScanSegmenter::Region mask{"escape", M_PI - 0.20, -M_PI + 0.20};
    const auto segments = segmenter.segment(scan, "", &mask);
    check(segments.at("front").size() == 2); // +/-2.5 stay visible.
    check(segments.at("rear").size() == 3);
    check(segments.at("left").size() == 3);
    check(segments.at("right").size() == 3);
    ObstacleDetector detector;
    detector.setDangerDistance(0.17);
    const auto obstacles = detector.detect(ScanMetrics::compute(scan, segments));
    for (const auto* region : {"front", "rear", "left", "right"})
    {
        check(obstacles.at(region).has_obstacle);
    }

    return 0;
}
