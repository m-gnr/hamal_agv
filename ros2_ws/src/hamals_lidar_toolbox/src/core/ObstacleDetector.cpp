#include "hamals_lidar_toolbox/core/ObstacleDetector.hpp"

#include <limits>
#include <cmath>

namespace hamals_lidar_toolbox
{
namespace core
{

void ObstacleDetector::setDangerDistance(double distance)
{
    danger_distance_ = distance;
}

ObstacleMap ObstacleDetector::detect(
    const std::unordered_map<std::string, RegionMetrics>& metrics) const
{
    ObstacleMap result;

    // LDS-01 için fiziksel minimum
    // İstersen bunu ileride parametre yapabiliriz
    constexpr double SENSOR_MIN = 0.12;
    constexpr double EPS = 1e-4;

    for (const auto& [region, region_metrics] : metrics)
    {
        ObstacleState state;
        state.min_distance = region_metrics.min_distance;

        if (region_metrics.count == 0)
        {
            state.has_obstacle = false;
        }
        else if (region_metrics.min_distance <= SENSOR_MIN + EPS)
        {
            state.has_obstacle = false;
        }
        else if (region_metrics.min_distance < danger_distance_)
        {
            state.has_obstacle = true;
        }
        else
        {
            state.has_obstacle = false;
        }

        result[region] = state;
    }

    return result;
}

} // namespace core
} // namespace hamals_lidar_toolbox