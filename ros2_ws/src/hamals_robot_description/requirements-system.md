# HAMALS Robot Description - System Requirements

This package is tested on macOS with RoboStack / conda ROS 2 environment.

## Required ROS 2 / Gazebo tools

The following commands/packages must be available in the active ROS 2 environment:

- ros2
- colcon
- xacro
- robot_state_publisher
- joint_state_publisher_gui
- rviz2
- gz / Gazebo Sim
- ros_gz_sim
- ros_gz_bridge
- ros_gz_interfaces
- ros_gz_image

## Python requirements

Install Python dependencies with:

```bash
conda activate ros2
pip install -r requirements.txt