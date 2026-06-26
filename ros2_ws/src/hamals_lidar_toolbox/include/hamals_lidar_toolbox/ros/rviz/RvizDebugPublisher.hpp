#pragma once

#include <string>
#include <memory>

#include <rclcpp/rclcpp.hpp>
#include <visualization_msgs/msg/marker_array.hpp>
#include <visualization_msgs/msg/marker.hpp>

namespace hamals_lidar_toolbox::ros::rviz
{

class RvizDebugPublisher
{
public:
  explicit RvizDebugPublisher(rclcpp::Node& node);

  void publishEmpty();

  void publishRegionFan(
      const std::string& region_name,
      double angle_min,
      double angle_max,
      double radius,
      bool has_obstacle);

private:
  visualization_msgs::msg::Marker createFanMarker(
      const std::string& ns,
      int id,
      double angle_min,
      double angle_max,
      double radius,
      bool has_obstacle);

  rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr pub_;
};

}  // namespace hamals_lidar_toolbox::ros::rviz
