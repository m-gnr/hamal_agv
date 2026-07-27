from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource

from ament_index_python.packages import get_package_share_directory

import os


def generate_launch_description():
    bringup_share = get_package_share_directory('hamals_bringup')
    localization_share = get_package_share_directory('hamals_state_estimation')
   
    slam_share = get_package_share_directory('hamals_slam')

    robot_io_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(bringup_share, 'launch', 'robot_io_bringup.launch.py')
        )
    )

    ekf_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(localization_share, 'launch', 'ekf.launch.py')
        )
    )



    slam_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(slam_share, 'launch', 'slam.launch.py')
        )
    )

    return LaunchDescription([
        robot_io_launch,
        ekf_launch,
     
        slam_launch,
    ])
