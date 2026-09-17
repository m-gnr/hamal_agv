from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os



def generate_launch_description():
    pkg_share = get_package_share_directory('hamals_slam')

    slam_config = os.path.join(
        pkg_share,
        'config',
        'slam.yaml'
    )

    slam_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[slam_config]
    )

    map_save_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('hamals_map_tools'),
            'launch', 'map_save.launch.py')))

    return LaunchDescription([
        slam_node,
        map_save_launch
    ])
