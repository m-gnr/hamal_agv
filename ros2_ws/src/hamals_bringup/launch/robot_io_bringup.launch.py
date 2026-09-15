from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node

from ament_index_python.packages import get_package_share_directory

import os


def launch_setup(context, *args, **kwargs):

    # ============================================================
    # Package shares
    # ============================================================

    bringup_share = get_package_share_directory(
        'hamals_bringup'
    )

    serial_bridge_share = get_package_share_directory(
        'hamals_serial_bridge'
    )

    odometry_share = get_package_share_directory(
        'hamals_odometry'
    )

    # ============================================================
    # Robot Description / TF
    # TF publishing is handled once by the top-level competition launch.
    # ============================================================

    # display_launch intentionally removed to avoid duplicate
    # robot_state_publisher instances.

    # ============================================================
    # Serial Bridge
    # ============================================================

    serial_bridge_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                serial_bridge_share,
                'launch',
                'serial_bridge.launch.py'
            )
        )
    )

    # ============================================================
    # Odometry
    # ============================================================

    odometry_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                odometry_share,
                'launch',
                'odometry.launch.py'
            )
        )
    )

    # ============================================================
    # LiDAR
    # ============================================================

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
            ('scan', 'scan_raw'),
        ]
    )

    # ============================================================
    # LiDAR Filter
    # ============================================================

    laser_filter_config = os.path.join(
        bringup_share,
        'config',
        'laser_filters.yaml'
    )

    laser_filter_node = Node(
        package='laser_filters',
        executable='scan_to_scan_filter_chain',
        name='scan_to_scan_filter_chain',
        output='screen',
        parameters=[
            laser_filter_config
        ],
        remappings=[
            ('scan', 'scan_raw'),
            ('scan_filtered', 'scan'),
        ]
    )

    # ============================================================
    # Twist Mux
    #
    # Inputs:
    #   /cmd_vel          -> Navigation
    #   /cmd_vel/docking  -> Docking
    #
    # Output:
    #   /cmd_vel/selected -> Serial Bridge AUTO input
    # Manual teleop goes directly to the bridge on /cmd_vel/manual_teleop.
    # ============================================================

    twist_mux_config = os.path.join(
        bringup_share,
        'config',
        'twist_mux.yaml'
    )

    twist_mux_node = Node(
        package='twist_mux',
        executable='twist_mux',
        name='twist_mux',
        output='screen',
        parameters=[
            twist_mux_config
        ],
        remappings=[
            ('cmd_vel_out', '/cmd_vel/selected'),
        ]
    )

    # ============================================================
    # Launch everything
    # ============================================================

    return [
        serial_bridge_launch,
        odometry_launch,
        lidar_node,
        laser_filter_node,
        twist_mux_node,
    ]


def generate_launch_description():

    return LaunchDescription([
        OpaqueFunction(function=launch_setup)
    ])