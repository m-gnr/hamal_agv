from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

from ament_index_python.packages import get_package_share_directory

import os
import yaml


def launch_setup(context, *args, **kwargs):
    bringup_share = get_package_share_directory('hamals_bringup')
    serial_bridge_share = get_package_share_directory('hamals_serial_bridge')

    config_file = os.path.join(bringup_share, 'config', 'robot_io.yaml')

    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    robot_io_cfg = config['robot_io']
    lidar_cfg = robot_io_cfg['lidar']

    serial_bridge_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(serial_bridge_share, 'launch', 'serial_bridge.launch.py')
        )
    )

    lidar_node = Node(
        package='hls_lfcd_lds_driver',
        executable='hlds_laser_publisher',
        name='hlds_laser_publisher',
        output='screen',
        parameters=[
            {
                'port': lidar_cfg['port'],
                'frame_id': lidar_cfg['frame_id'],
            }
        ]
    )

    return [
        serial_bridge_launch,
        lidar_node,
    ]


def generate_launch_description():
    return LaunchDescription([
        OpaqueFunction(function=launch_setup)
    ])