from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

from ament_index_python.packages import get_package_share_directory

import os


def generate_launch_description():
    localization_share = get_package_share_directory('hamals_localization')
    description_share = get_package_share_directory('hamals_robot_description')
    slam_share = get_package_share_directory('hamals_slam')

    ekf_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(localization_share, 'launch', 'ekf.launch.py')
        )
    )

    description_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(description_share, 'launch', 'display.launch.py')
        )
    )

    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(slam_share, 'launch', 'slam.launch.py')
        )
    )

    return LaunchDescription([
        ekf_launch,
        description_launch,
        slam_launch,
    ])