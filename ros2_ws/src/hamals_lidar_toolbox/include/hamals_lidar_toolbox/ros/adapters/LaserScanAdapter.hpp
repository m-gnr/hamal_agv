#pragma once

#include "hamals_lidar_toolbox/core/ScanData.hpp"

#include <sensor_msgs/msg/laser_scan.hpp>

namespace hamals_lidar_toolbox
{
namespace ros
{
namespace adapters
{

class LaserScanAdapter
{
public:
    static core::ScanData
    fromRosMessage(const sensor_msgs::msg::LaserScan& msg);
};

} // namespace adapters
} // namespace ros
} // namespace hamals_lidar_toolbox
