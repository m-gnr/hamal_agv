#include "hamals_lidar_toolbox/core/ScanMetrics.hpp"

#include <limits>
#include <cmath>

namespace hamals_lidar_toolbox
{
namespace core
{

std::unordered_map<std::string, RegionMetrics>
ScanMetrics::compute(
    const ScanData& scan,
    const std::unordered_map<std::string, std::vector<std::size_t>>& segments)
{
    std::unordered_map<std::string, RegionMetrics> result;

    constexpr double SENSOR_MIN = 0.12;   // LDS-01
    constexpr double EPS = 1e-4;

    for (const auto& pair : segments)
    {
        const std::string& region_name = pair.first;
        const std::vector<std::size_t>& indices = pair.second;

        RegionMetrics metrics{};
        metrics.count = 0;
        metrics.min_distance = std::numeric_limits<double>::infinity();
        metrics.mean_distance = 0.0;

        double sum = 0.0;
        std::size_t valid_count = 0;
        double min_val = std::numeric_limits<double>::infinity();

        for (std::size_t idx : indices)
        {
            double distance = static_cast<double>(scan.ranges()[idx]);

            if (!std::isfinite(distance))
                continue;

            if (distance <= 0.0)
                continue;

            if (distance <= SENSOR_MIN + EPS)
                continue;

            if (distance < min_val)
                min_val = distance;

            sum += distance;
            valid_count++;
        }

        if (valid_count > 0)
        {
            metrics.count = valid_count;
            metrics.min_distance = min_val;
            metrics.mean_distance = sum / static_cast<double>(valid_count);
        }
        else
        {
            metrics.count = 0;
            metrics.min_distance = std::numeric_limits<double>::infinity();
            metrics.mean_distance = 0.0;
        }

        result[region_name] = metrics;
    }

    return result;
}

} // namespace core
} // namespace hamals_lidar_toolbox