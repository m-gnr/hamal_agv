#include "hamals_lidar_toolbox/core/ScanSanitizer.hpp"

#include <stdexcept>
#include <cmath>

namespace hamals_lidar_toolbox
{
namespace core
{

ScanSanitizer::ScanSanitizer(double min_range, double max_range)
    : min_range_(min_range),
      max_range_(max_range)
{
    if (min_range_ < 0.0)
    {
        throw std::invalid_argument(
            "ScanSanitizer: min_range 0'dan kucuk olamaz");
    }

    if (max_range_ <= min_range_)
    {
        throw std::invalid_argument(
            "ScanSanitizer: max_range min_range'den buyuk olmalidir");
    }
}

ScanData ScanSanitizer::sanitize(const ScanData& input) const
{
    std::vector<float> clean_ranges;
    clean_ranges.reserve(input.size());

    for (float value : input.ranges())
    {
        if (!std::isfinite(value))
        {
            clean_ranges.push_back(static_cast<float>(max_range_));
            continue;
        }

        if (value < min_range_)
        {
            clean_ranges.push_back(static_cast<float>(min_range_));
            continue;
        }

        if (value > max_range_)
        {
            clean_ranges.push_back(static_cast<float>(max_range_));
            continue;
        }

        clean_ranges.push_back(value);
    }

    return ScanData(
        std::move(clean_ranges),
        input.angleMin(),
        input.angleIncrement(),
        input.timestamp()
    );
}

} // namespace core
} // namespace hamals_lidar_toolbox
