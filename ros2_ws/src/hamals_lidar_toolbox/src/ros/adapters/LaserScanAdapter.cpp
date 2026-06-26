#include "hamals_lidar_toolbox/ros/adapters/LaserScanAdapter.hpp"
#include <stdexcept>

namespace hamals_lidar_toolbox
{
namespace ros
{
namespace adapters
{

core::ScanData
LaserScanAdapter::fromRosMessage(const sensor_msgs::msg::LaserScan& msg)
{
    if (msg.ranges.empty())
    {
        throw std::invalid_argument(
            "LaserScanAdapter: LaserScan message contains empty ranges");
    }

    if (msg.angle_increment == 0.0f)
    {
        throw std::invalid_argument(
            "LaserScanAdapter: angle_increment must be non-zero");
    }

    double timestamp_sec =
        static_cast<double>(msg.header.stamp.sec) +
        static_cast<double>(msg.header.stamp.nanosec) * 1e-9;

    return core::ScanData(
        msg.ranges,           
        msg.angle_min,        
        msg.angle_increment,  
        timestamp_sec         
    );
}

} // namespace adapters
} // namespace ros
} // namespace hamals_lidar_toolbox
