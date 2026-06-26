#pragma once

#include "hamals_lidar_toolbox/core/ScanData.hpp"

#include <vector>
#include <unordered_map>
#include <string>

namespace hamals_lidar_toolbox
{
namespace core
{

class ScanSegmenter
{
public:
    struct Region
    {
        std::string name;
        double min_angle;
        double max_angle;
    };

    explicit ScanSegmenter(const std::vector<Region>& regions);

    std::unordered_map<std::string, std::vector<std::size_t>>
    segment(const ScanData& scan) const;

private:
    std::vector<Region> regions_;
};

} // namespace core
} // namespace hamals_lidar_toolbox
