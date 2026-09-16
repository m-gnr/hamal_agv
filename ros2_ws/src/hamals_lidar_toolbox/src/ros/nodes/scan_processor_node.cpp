#include "hamals_lidar_toolbox/ros/nodes/scan_processor_node.hpp"

#include <cmath>
#include <stdexcept>

using std::placeholders::_1;

ScanProcessorNode::ScanProcessorNode(const rclcpp::NodeOptions& options)
: rclcpp::Node("scan_processor_node", options)
{
    this->declare_parameter<double>("danger_distance");
    this->declare_parameter<double>("scan.min_range");
    this->declare_parameter<double>("scan.max_range");

    this->declare_parameter<double>("regions.front.min");
    this->declare_parameter<double>("regions.front.max");
    this->declare_parameter<double>("regions.left.min");
    this->declare_parameter<double>("regions.left.max");
    this->declare_parameter<double>("regions.right.min");
    this->declare_parameter<double>("regions.right.max");
    this->declare_parameter<double>("regions.rear.min");
    this->declare_parameter<double>("regions.rear.max");

    this->declare_parameter<bool>("debug.enable_rviz", false);
    this->declare_parameter<bool>("fork_mask.enabled", true);
    this->declare_parameter<double>("fork_mask.min", -0.20);
    this->declare_parameter<double>("fork_mask.max", 0.20);
    this->declare_parameter<double>("fork_mask.state_timeout", 0.5);

    double danger_distance =
        this->get_parameter("danger_distance").as_double();

    double min_range =
        this->get_parameter("scan.min_range").as_double();

    double max_range =
        this->get_parameter("scan.max_range").as_double();

    debug_rviz_enabled_ =
        this->get_parameter("debug.enable_rviz").as_bool();

    const double state_timeout =
        this->get_parameter("fork_mask.state_timeout").as_double();
    fork_mask_angles_ = {
        "fork_mask",
        this->get_parameter("fork_mask.min").as_double(),
        this->get_parameter("fork_mask.max").as_double()
    };
    if (!std::isfinite(state_timeout) || state_timeout < 0.0 ||
        !std::isfinite(fork_mask_angles_.min_angle) ||
        !std::isfinite(fork_mask_angles_.max_angle))
    {
        throw std::invalid_argument("fork_mask parameters must be finite and timeout nonnegative");
    }
    fork_mask_state_ = std::make_unique<
        hamals_lidar_toolbox::core::ForkMaskState>(
            this->get_parameter("fork_mask.enabled").as_bool(), state_timeout);

    sanitizer_ = std::make_unique<
        hamals_lidar_toolbox::core::ScanSanitizer>(min_range, max_range);

    segmenter_ = std::make_unique<
        hamals_lidar_toolbox::core::ScanSegmenter>(createRegionsFromParams());

    obstacle_detector_ = std::make_unique<
        hamals_lidar_toolbox::core::ObstacleDetector>();

    obstacle_detector_->setDangerDistance(danger_distance);

    if (debug_rviz_enabled_)
    {
        rviz_debug_ = std::make_unique<
            hamals_lidar_toolbox::ros::rviz::RvizDebugPublisher>(*this);
    }

    scan_subscriber_ =
        this->create_subscription<sensor_msgs::msg::LaserScan>(
            "/scan",
            rclcpp::SensorDataQoS(),
            std::bind(&ScanProcessorNode::scanCallback, this, _1));

    // ForkNode publishes with the default reliable, keep-last depth 10 QoS.
    fork_state_subscriber_ =
        this->create_subscription<hamals_interfaces::msg::ForkState>(
            "/fork/state", 10,
            std::bind(&ScanProcessorNode::forkStateCallback, this, _1));

    obstacle_state_pub_ =
        this->create_publisher<hamals_interfaces::msg::ObstacleState>(
            "/scan/obstacle_state", 10);

    RCLCPP_INFO(
        this->get_logger(),
        "ScanProcessorNode started (rviz debug = %s)",
        debug_rviz_enabled_ ? "ON" : "OFF");
}

void ScanProcessorNode::forkStateCallback(
    const hamals_interfaces::msg::ForkState::ConstSharedPtr msg)
{
    fork_mask_state_->receive(
        msg->lower_limit,
        hamals_lidar_toolbox::core::ForkMaskState::Clock::now());
}

void ScanProcessorNode::scanCallback(
    const sensor_msgs::msg::LaserScan::SharedPtr msg)
{
    auto scan =
        hamals_lidar_toolbox::ros::adapters::LaserScanAdapter::fromRosMessage(*msg);

    const auto now = hamals_lidar_toolbox::core::ForkMaskState::Clock::now();
    const bool fork_mask_active = fork_mask_state_->active(now);
    if (fork_mask_active != fork_mask_was_active_)
    {
        if (fork_mask_active)
        {
            RCLCPP_INFO(this->get_logger(), "Fork lidar mask ACTIVE");
        }
        else if (fork_mask_state_->stale(now))
        {
            RCLCPP_WARN(this->get_logger(), "Fork state STALE - lidar mask disabled");
        }
        else
        {
            RCLCPP_INFO(this->get_logger(), "Fork lidar mask INACTIVE");
        }
        fork_mask_was_active_ = fork_mask_active;
    }

    auto segments = segmenter_->segment(
        scan, fork_mask_active ? &fork_mask_angles_ : nullptr);

    auto clean_scan = sanitizer_->sanitize(scan);

    auto metrics =
        hamals_lidar_toolbox::core::ScanMetrics::compute(clean_scan, segments);

    auto obstacle_map =
        obstacle_detector_->detect(metrics);

    if (debug_rviz_enabled_ && rviz_debug_)
    {
        for (const auto& [region_name, state] : obstacle_map)
        {
            const std::string min_key = "regions." + region_name + ".min";
            const std::string max_key = "regions." + region_name + ".max";

            rviz_debug_->publishRegionFan(
                region_name,
                this->get_parameter(min_key).as_double(),
                this->get_parameter(max_key).as_double(),
                state.min_distance,
                state.has_obstacle
            );
        }
    }

    hamals_interfaces::msg::ObstacleState out_msg;

    for (const auto& [region, state] : obstacle_map)
    {
        hamals_interfaces::msg::ObstacleRegionState r;
        r.region = region;
        r.has_obstacle = state.has_obstacle;
        r.min_distance = state.min_distance;
        out_msg.regions.push_back(r);
    }

    obstacle_state_pub_->publish(out_msg);
}

std::vector<hamals_lidar_toolbox::core::ScanSegmenter::Region>
ScanProcessorNode::createRegionsFromParams() const
{
    using Region = hamals_lidar_toolbox::core::ScanSegmenter::Region;

    return {
        {
            "front",
            this->get_parameter("regions.front.min").as_double(),
            this->get_parameter("regions.front.max").as_double()
        },
        {
            "left",
            this->get_parameter("regions.left.min").as_double(),
            this->get_parameter("regions.left.max").as_double()
        },
        {
            "right",
            this->get_parameter("regions.right.min").as_double(),
            this->get_parameter("regions.right.max").as_double()
        },
        {
            "rear",
            this->get_parameter("regions.rear.min").as_double(),
            this->get_parameter("regions.rear.max").as_double()
        }
    };
}

int main(int argc, char ** argv)
{
    rclcpp::init(argc, argv);
    auto node = std::make_shared<ScanProcessorNode>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
