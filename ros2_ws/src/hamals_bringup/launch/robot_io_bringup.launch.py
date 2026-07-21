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
    odometry_share = get_package_share_directory('hamals_odometry')

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

    odometry_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(odometry_share, 'launch', 'odometry.launch.py')
        )
    )

    lidar_node = Node(
        package='sllidar_ros2',
        executable='sllidar_node',
        name='sllidar_node',
        output='screen',
        parameters=[
            {
                'channel_type': 'serial',
                'serial_port': lidar_cfg['port'],
                'serial_baudrate': 1000000,
                'frame_id': lidar_cfg['frame_id'],
                'inverted': False,
                'angle_compensate': True,
                'scan_mode': 'DenseBoost',
            }
        ]
    )

    return [
        serial_bridge_launch,
        odometry_launch,
        lidar_node,
    ]


def generate_launch_description():
    return LaunchDescription([
        OpaqueFunction(function=launch_setup)
    ])
