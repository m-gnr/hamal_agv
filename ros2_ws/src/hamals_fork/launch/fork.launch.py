from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

import os


def generate_launch_description():
    config_file = os.path.join(
        get_package_share_directory('hamals_fork'),
        'config',
        'fork.yaml'
    )

    fork_node = Node(
        package='hamals_fork',
        executable='fork_node',
        name='hamals_fork_node',
        output='screen',
        parameters=[config_file],
    )

    return LaunchDescription([
        fork_node
    ])