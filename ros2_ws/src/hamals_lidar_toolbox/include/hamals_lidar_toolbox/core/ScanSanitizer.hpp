#pragma once

#include "hamals_lidar_toolbox/core/ScanData.hpp"

namespace hamals_lidar_toolbox
{
namespace core
{

class ScanSanitizer
{
public:
    ScanSanitizer(double min_range, double max_range);

    ScanData sanitize(const ScanData& input) const;

private:
    double min_range_;
    double max_range_;
};

} // namespace core
} // namespace hamals_lidar_toolbox
