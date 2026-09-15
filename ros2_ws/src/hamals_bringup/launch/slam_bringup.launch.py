from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

from launch.substitutions import Command, PathJoinSubstitution

from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

from ament_index_python.packages import get_package_share_directory

import os


def generate_launch_description():

    # ============================================================
    # Package Shares
    # ============================================================

    bringup_share = get_package_share_directory(
        'hamals_bringup'
    )

    state_estimation_share = get_package_share_directory(
        'hamals_state_estimation'
    )

    slam_share = get_package_share_directory(
        'hamals_slam'
    )

    # ============================================================
    # Robot Description / TF
    #
    # Mapping mode competition.launch.py olmadan çalıştığı için
    # robot_state_publisher burada ayrıca başlatılmalıdır.
    #
    # URDF üzerinden:
    #   base_footprint
    #   base_link
    #   lidar_link
    # gibi robotun sabit TF'leri yayınlanır.
    # ============================================================

    robot_description_file = PathJoinSubstitution([
        FindPackageShare('hamals_robot_description'),
        'urdf',
        'hamals_robot.urdf.xacro',
    ])

    robot_description = ParameterValue(
        Command([
            'xacro ',
            robot_description_file
        ]),
        value_type=str
    )

    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[
            {
                'robot_description': robot_description
            }
        ],
    )

    # ============================================================
    # Robot IO
    #
    # robot_io_bringup.launch.py starts:
    #
    #   serial_bridge
    #   odometry
    #   sllidar
    #   laser filter
    #   twist_mux
    #
    # LiDAR:
    #
    #   /scan_raw
    #       ↓
    #   laser_filter
    #       ↓
    #   /scan
    #
    # ============================================================

    robot_io_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                bringup_share,
                'launch',
                'robot_io_bringup.launch.py'
            )
        )
    )

    # ============================================================
    # EKF
    #
    # Robotun encoder/IMU odometrisini filtreler.
    #
    # Beklenen TF:
    #
    #   odom
    #     ↓
    #   base_footprint
    #
    # ============================================================

    ekf_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                state_estimation_share,
                'launch',
                'ekf.launch.py'
            )
        )
    )

    # ============================================================
    # SLAM Toolbox
    #
    # Kullanır:
    #
    #   /scan
    #   odom
    #   TF
    #
    # Üretir:
    #
    #   /map
    #
    # ve:
    #
    #   map
    #    ↓
    #   odom
    #
    # ============================================================

    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                slam_share,
                'launch',
                'slam.launch.py'
            )
        )
    )

    # ============================================================
    # Launch
    #
    # Final TF chain:
    #
    #   map
    #    ↓
    #   odom
    #    ↓
    #   base_footprint
    #    ↓
    #   base_link
    #    ↓
    #   lidar_link
    #
    # ============================================================

    return LaunchDescription([

        # Robot URDF / Static TF
        robot_state_publisher_node,

        # Serial + Odometry + LiDAR + Filter + Twist Mux
        robot_io_launch,

        # EKF
        ekf_launch,

        # SLAM Toolbox
        slam_launch,

    ])