#pragma once

#include <string>
#include <unordered_map>

#include "hamals_lidar_toolbox/core/ScanMetrics.hpp"

namespace hamals_lidar_toolbox
{
namespace core
{

struct ObstacleState
{
    bool has_obstacle;
    double min_distance;
};

using ObstacleMap = std::unordered_map<std::string, ObstacleState>;

class ObstacleDetector
{
public:
    ObstacleDetector() = default;

    void setDangerDistance(double distance);

    ObstacleMap detect(
        const std::unordered_map<std::string, RegionMetrics>& metrics) const;

private:
    double danger_distance_{0.5};
};

} // namespace core
} // namespace hamals_lidar_toolbox
