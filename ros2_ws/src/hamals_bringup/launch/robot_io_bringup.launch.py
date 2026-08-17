from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

from ament_index_python.packages import get_package_share_directory

import os


def launch_setup(context, *args, **kwargs):
    bringup_share = get_package_share_directory('hamals_bringup')
    serial_bridge_share = get_package_share_directory('hamals_serial_bridge')
    odometry_share = get_package_share_directory('hamals_odometry')

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
                'serial_port': '/dev/ttyUSB0',
                'serial_baudrate': 1000000,
                'frame_id': 'lidar_link',
                'inverted': False,
                'angle_compensate': True,
                'scan_mode': 'DenseBoost',
            }
        ],
        remappings=[
            ('scan', 'scan_raw'),   # ham (filtresiz) veri burada yayinlanir
        ]
    )

    laser_filter_config = os.path.join(bringup_share, 'config', 'laser_filters.yaml')

    laser_filter_node = Node(
        package='laser_filters',
        executable='scan_to_scan_filter_chain',
        name='scan_to_scan_filter_chain',
        output='screen',
        parameters=[laser_filter_config],
        remappings=[
            ('scan', 'scan_raw'),      # girdi: ham veri
            ('scan_filtered', 'scan'),  # cikti: slam_toolbox'un bekledigi /scan
        ]
    )

    return [
        serial_bridge_launch,
        odometry_launch,
        lidar_node,
        laser_filter_node,
    ]


def generate_launch_description():
    return LaunchDescription([
        OpaqueFunction(function=launch_setup)
    ])
