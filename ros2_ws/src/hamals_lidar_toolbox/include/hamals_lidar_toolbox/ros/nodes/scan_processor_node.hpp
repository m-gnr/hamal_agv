#pragma once

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/laser_scan.hpp>

#include "hamals_lidar_toolbox/ros/adapters/LaserScanAdapter.hpp"

#include "hamals_lidar_toolbox/core/ScanSanitizer.hpp"
#include "hamals_lidar_toolbox/core/ScanSegmenter.hpp"
#include "hamals_lidar_toolbox/core/ScanMetrics.hpp"
#include "hamals_lidar_toolbox/core/ObstacleDetector.hpp"
#include "hamals_lidar_msgs/msg/obstacle_state.hpp"

#include "hamals_lidar_toolbox/ros/rviz/RvizDebugPublisher.hpp"

#include <memory>
#include <vector>

class ScanProcessorNode : public rclcpp::Node
{
public:
    explicit ScanProcessorNode(
        const rclcpp::NodeOptions& options = rclcpp::NodeOptions());

private:
    std::vector<hamals_lidar_toolbox::core::ScanSegmenter::Region>
    createRegionsFromParams() const;

    void scanCallback(const sensor_msgs::msg::LaserScan::SharedPtr msg);

    rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr
        scan_subscriber_;

    rclcpp::Publisher<
        hamals_lidar_msgs::msg::ObstacleState
    >::SharedPtr obstacle_state_pub_;

    std::unique_ptr<hamals_lidar_toolbox::core::ScanSanitizer> sanitizer_;
    std::unique_ptr<hamals_lidar_toolbox::core::ScanSegmenter> segmenter_;
    std::unique_ptr<hamals_lidar_toolbox::core::ObstacleDetector> obstacle_detector_;

    bool debug_rviz_enabled_{false};

    std::unique_ptr<
        hamals_lidar_toolbox::ros::rviz::RvizDebugPublisher
    > rviz_debug_;
};
