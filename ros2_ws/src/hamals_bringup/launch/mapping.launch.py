"""Mapping profile: hardware IO, EKF, SLAM, map save and manual control."""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def _include(package, filename):
    return IncludeLaunchDescription(PythonLaunchDescriptionSource(
        os.path.join(get_package_share_directory(package), 'launch', filename)))


def generate_launch_description():
    bringup = get_package_share_directory('hamals_bringup')
    safety = get_package_share_directory('hamals_safety')
    return LaunchDescription([
        _include('hamals_bringup', 'slam_bringup.launch.py'),
        _include('hamals_lidar_toolbox', 'scan_processor.launch.py'),
        Node(package='hamals_safety', executable='safety_node', name='hamals_safety',
             parameters=[os.path.join(safety, 'config', 'safety.yaml')], output='screen'),
        Node(package='twist_mux', executable='twist_mux', name='twist_mux',
             parameters=[os.path.join(bringup, 'config', 'twist_mux.yaml')],
             remappings=[('/cmd_vel_out', '/cmd_vel')], output='screen'),
        Node(
            package='hamals_map_tools',
            executable='map_save_server',
            name='map_save_server',
            output='screen',
        ),
        Node(
            package='hamals_manual_teleop',
            executable='teleop_node',
            name='teleop_node',
            output='screen',
        ),
    ])
