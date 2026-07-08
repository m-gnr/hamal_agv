import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory("hamals_fork")
    config_file = os.path.join(pkg_share, "config", "fork.yaml")

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "config",
                default_value=config_file,
                description="Path to fork config file",
            ),
            Node(
                package="hamals_fork",
                executable="fork_node",
                name="hamals_fork",
                output="screen",
                parameters=[LaunchConfiguration("config")],
            ),
        ]
    )
