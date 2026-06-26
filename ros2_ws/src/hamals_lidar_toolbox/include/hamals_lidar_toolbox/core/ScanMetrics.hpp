#pragma once

#include "hamals_lidar_toolbox/core/ScanData.hpp"

#include <unordered_map>
#include <vector>
#include <string>
#include <cstddef>
#include <limits>

namespace hamals_lidar_toolbox
{
namespace core
{

struct RegionMetrics
{
    std::size_t count = 0;
    double min_distance = std::numeric_limits<double>::infinity();
    double mean_distance = std::numeric_limits<double>::infinity();
};

class ScanMetrics
{
public:
    static std::unordered_map<std::string, RegionMetrics>
    compute(
        const ScanData& scan,
        const std::unordered_map<std::string, std::vector<std::size_t>>& segments
    );
};

} // namespace core
} // namespace hamals_lidar_toolbox
