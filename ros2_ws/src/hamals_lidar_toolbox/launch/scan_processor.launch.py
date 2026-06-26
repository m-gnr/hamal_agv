from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    config_file = os.path.join(
        get_package_share_directory('hamals_lidar_toolbox'),
        'config',
        'lidar.yaml'
    )

    return LaunchDescription([
        Node(
            package='hamals_lidar_toolbox',
            executable='scan_processor_node',
            name='scan_processor_node',
            output='screen',
            parameters=[config_file]
        )
    ])
