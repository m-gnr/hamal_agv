"""Launch the config-driven mission coordinator."""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    default = os.path.join(
        get_package_share_directory('hamals_mission'),
        'config',
        'mission_policy.yaml',
    )
    return LaunchDescription([
        DeclareLaunchArgument('config', default_value=default),
        Node(package='hamals_mission', executable='mission_server', name='hamals_mission',
             output='screen', parameters=[LaunchConfiguration('config')]),
    ])
