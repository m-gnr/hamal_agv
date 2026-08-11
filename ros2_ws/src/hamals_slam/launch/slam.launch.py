from launch import LaunchDescription
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

#abdulllah ekledi 
    map_saver_node = Node(
                package='hamals_map_tools',
                executable='map_save_server',
                name='hamal_map_save_server',
                output='screen',
            )

    return LaunchDescription([
        slam_node,
        map_saver_node       
    ])