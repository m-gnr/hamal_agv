#include "hamals_lidar_toolbox/ros/rviz/RvizDebugPublisher.hpp"

#include <cmath>
#include <string>

#include <geometry_msgs/msg/point.hpp>
#include <visualization_msgs/msg/marker.hpp>


namespace hamals_lidar_toolbox::ros::rviz
{

RvizDebugPublisher::RvizDebugPublisher(rclcpp::Node& node)
{
  pub_ = node.create_publisher<visualization_msgs::msg::MarkerArray>(
      "/scan/debug_markers", 10);
}

void RvizDebugPublisher::publishEmpty()
{
  visualization_msgs::msg::MarkerArray arr;
  pub_->publish(arr);
}


visualization_msgs::msg::Marker
RvizDebugPublisher::createFanMarker(
    const std::string& ns,
    int id,
    double angle_min,
    double angle_max,
    double radius,
    bool has_obstacle)
{
  visualization_msgs::msg::Marker fan;

  fan.header.frame_id = "base_link";
  fan.header.stamp = rclcpp::Clock().now();

  fan.ns = ns;
  fan.id = id;

  fan.type = visualization_msgs::msg::Marker::LINE_STRIP;
  fan.action = visualization_msgs::msg::Marker::ADD;
  fan.scale.x = 0.03;

  if (has_obstacle) {
    fan.color.r = 1.0;
    fan.color.g = 0.0;
  } else {
    fan.color.r = 0.0;
    fan.color.g = 1.0;
  }
  fan.color.b = 0.0;
  fan.color.a = 1.0;

  geometry_msgs::msg::Point center;
  center.x = 0.0;
  center.y = 0.0;
  center.z = 0.0;
  fan.points.push_back(center);

  constexpr int STEPS = 30;
  double step = (angle_max - angle_min) / STEPS;

  for (int i = 0; i <= STEPS; ++i)
  {
    double a = angle_min + i * step;

    geometry_msgs::msg::Point p;
    p.x = radius * std::cos(a);
    p.y = radius * std::sin(a);
    p.z = 0.0;

    fan.points.push_back(p);
  }

  fan.points.push_back(center);

  return fan;
}

void RvizDebugPublisher::publishRegionFan(
    const std::string& region_name,
    double angle_min,
    double angle_max,
    double radius,
    bool has_obstacle)
{
  visualization_msgs::msg::MarkerArray arr;

  if (angle_min <= angle_max)
  {
    arr.markers.push_back(
        createFanMarker(
            region_name,
            0,
            angle_min,
            angle_max,
            radius,
            has_obstacle));
  }
  else
  {
    arr.markers.push_back(
        createFanMarker(
            region_name,
            0,
            angle_min,
            M_PI,
            radius,
            has_obstacle));

    arr.markers.push_back(
        createFanMarker(
            region_name,
            1,
            -M_PI,
            angle_max,
            radius,
            has_obstacle));
  }

  pub_->publish(arr);
}

}  // namespace hamals_lidar_toolbox::ros::rviz
