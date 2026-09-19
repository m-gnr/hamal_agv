#include "hamals_lidar_toolbox/core/ObstacleDetector.hpp"

#include <stdexcept>
#include <string>
#include <unordered_map>

#define check(condition) do { if (!(condition)) throw std::runtime_error(#condition); } while (false)

using hamals_lidar_toolbox::core::ObstacleDetector;
using hamals_lidar_toolbox::core::RegionMetrics;

static bool isDangerous(const ObstacleDetector& detector, const std::string& region, double distance)
{
    const std::unordered_map<std::string, RegionMetrics> metrics = {
        {region, {1, distance, distance}}
    };
    return detector.detect(metrics).at(region).has_obstacle;
}

int main()
{
    ObstacleDetector detector;
    detector.setDangerDistance(0.17);
    detector.setRegionDangerDistance("rear", 0.40);

    check(isDangerous(detector, "rear", 0.35));
    check(!isDangerous(detector, "rear", 0.45));
    check(isDangerous(detector, "front", 0.16));
    check(!isDangerous(detector, "front", 0.20));
    check(isDangerous(detector, "left", 0.16));
    check(!isDangerous(detector, "left", 0.20));
    check(isDangerous(detector, "right", 0.16));
    check(!isDangerous(detector, "right", 0.20));

    ObstacleDetector without_overrides;
    without_overrides.setDangerDistance(0.17);
    check(!isDangerous(without_overrides, "rear", 0.35));
    check(isDangerous(without_overrides, "rear", 0.16));

    // The ROS state callback switches only the configured front threshold.
    detector.setRegionDangerDistance("front", 0.85);
    check(isDangerous(detector, "front", 0.50));
    check(!isDangerous(detector, "front", 0.90));
    check(isDangerous(detector, "front", 0.849));
    check(!isDangerous(detector, "front", 0.85)); // Strict < boundary.
    check(!isDangerous(detector, "front", 0.851));

    for (double front_threshold : {0.04, 0.85, 0.04, 0.85})
    {
        detector.setRegionDangerDistance("front", front_threshold);
        check(isDangerous(detector, "front", 0.50) == (front_threshold == 0.85));
        check(!isDangerous(detector, "front", 0.90));
        check(!isDangerous(detector, "front", 0.10));
        // Preserve the existing sensor minimum filter, including below/at/above 4 cm.
        check(!isDangerous(detector, "front", 0.039));
        check(!isDangerous(detector, "front", 0.04));
        check(!isDangerous(detector, "front", 0.041));
        check(!isDangerous(detector, "front", 0.12));
        check(isDangerous(detector, "rear", 0.35));
        check(!isDangerous(detector, "rear", 0.40));
        for (const auto* side : {"left", "right"})
        {
            check(isDangerous(detector, side, 0.16));
            check(!isDangerous(detector, side, 0.17));
        }
    }

    return 0;
}
