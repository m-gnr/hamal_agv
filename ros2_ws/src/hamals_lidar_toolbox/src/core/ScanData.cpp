// Sensörden gelen tek bir frame'i c++ nesnesine çevirir
#include "hamals_lidar_toolbox/core/ScanData.hpp"

#include <stdexcept>
#include <cmath>
#include <utility>

namespace hamals_lidar_toolbox
{
namespace core
{

ScanData::ScanData(
    std::vector<float> ranges,
    double angle_min,
    double angle_increment,
    double timestamp)
    : ranges_(std::move(ranges)),
      angle_min_(angle_min),
      angle_increment_(angle_increment),
      timestamp_(timestamp)
{
    if (ranges_.empty())
    {
        throw std::invalid_argument("ScanData: ranges cannot be empty");
    }

    if (angle_increment_ <= 0.0)
    {
        throw std::invalid_argument("ScanData: angle_increment must be > 0");
    }

    if (!std::isfinite(angle_min_))
    {
        throw std::invalid_argument("ScanData: angle_min must be finite");
    }

    if (!std::isfinite(timestamp_))
    {
        throw std::invalid_argument("ScanData: timestamp must be finite");
    }
}

const std::vector<float>& ScanData::ranges() const
{
    return ranges_;
}

double ScanData::angleMin() const
{
    return angle_min_;
}

double ScanData::angleIncrement() const
{
    return angle_increment_;
}

std::size_t ScanData::size() const
{
    return ranges_.size();
}

double ScanData::timestamp() const
{
    return timestamp_;
}

} // namespace core
} // namespace lidar_scan_core
