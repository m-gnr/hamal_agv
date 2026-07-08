from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from ament_index_python.packages import get_package_share_directory

import os


def generate_launch_description():
    pkg_share = get_package_share_directory('hamals_odometry')
    default_params_file = os.path.join(pkg_share, 'config', 'params.yaml')
    params_file = LaunchConfiguration('params_file')

    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file',
            default_value=default_params_file,
            description='Path to hamals_odometry parameter file.',
        ),
        Node(
            package='hamals_odometry',
            executable='odometry_node',
            name='hamals_odometry',
            output='screen',
            parameters=[params_file],
        ),
    ])
