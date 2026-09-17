"""Nav2 map saver and its fixed-destination GUI service."""

from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='nav2_map_server',
            executable='map_saver_server',
            name='map_saver',
            output='screen',
            parameters=[{'save_map_timeout': 20.0}],
        ),
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_map_saver',
            output='screen',
            parameters=[{'autostart': True, 'node_names': ['map_saver']}],
        ),
        Node(
            package='hamals_map_tools',
            executable='map_save_server',
            name='map_save_service_node',
            output='screen',
        ),
    ])
