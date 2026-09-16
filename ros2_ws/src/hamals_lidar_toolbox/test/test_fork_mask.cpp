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

static double frontMinimum(bool mask_active, float inside, float outside)
{
    const ScanData scan({inside, outside}, 0.0, 0.4, 0.0);
    const ScanSegmenter segmenter({{"front", -0.785, 0.785}});
    const ScanSegmenter::Region mask{"fork_mask", -0.20, 0.20};
    const auto segments = segmenter.segment(scan, mask_active ? &mask : nullptr);
    const auto metrics = ScanMetrics::compute(scan, segments);
    ObstacleDetector detector;
    detector.setDangerDistance(0.17);
    const auto obstacles = detector.detect(metrics);
    check(obstacles.at("front").has_obstacle == (obstacles.at("front").min_distance < 0.17));
    return obstacles.at("front").min_distance;
}

int main()
{
    const auto start = ForkMaskState::TimePoint{};
    const auto at = [&](int milliseconds) {
        return start + std::chrono::milliseconds(milliseconds);
    };

    ForkMaskState state(true, 0.5);
    check(!state.active(at(0))); // No ForkState received.
    check(frontMinimum(state.active(at(0)), 0.15f, 1.0f) < 0.17);

    state.receive(true, at(0));
    check(!state.active(at(0))); // Fork at lower limit.
    check(frontMinimum(state.active(at(0)), 0.15f, 1.0f) < 0.17);

    state.receive(false, at(0));
    check(state.active(at(0)));
    check(frontMinimum(state.active(at(0)), 0.15f, 1.0f) == 1.0);
    check(std::fabs(frontMinimum(state.active(at(0)), 0.15f, 0.16f) - 0.16) < 1e-6);

    ForkMaskState disabled(false, 0.5);
    disabled.receive(false, at(0));
    check(!disabled.active(at(0)));
    check(frontMinimum(disabled.active(at(0)), 0.15f, 1.0f) < 0.17);

    check(!state.stale(at(500))); // Exact timeout boundary is still fresh.
    check(state.active(at(500)));
    check(state.stale(at(501)));
    check(!state.active(at(501)));
    check(frontMinimum(state.active(at(501)), 0.15f, 1.0f) < 0.17);

    state.receive(true, at(600));
    check(!state.active(at(600))); // false -> true immediately disables mask.
    check(frontMinimum(state.active(at(600)), 0.15f, 1.0f) < 0.17);
    state.receive(false, at(601));
    check(state.active(at(601))); // true -> false immediately enables mask.
    check(frontMinimum(state.active(at(601)), 0.15f, 1.0f) == 1.0);

    // The same angle logic still supports wrap-around and normalized angles.
    const ScanSegmenter wrap_segmenter({{"rear", 2.356, -2.356}});
    const ScanData wrap_scan({1.0f, 1.0f}, 3.0, 0.4, 0.0);
    check(wrap_segmenter.segment(wrap_scan).at("rear").size() == 2);

    return 0;
}
