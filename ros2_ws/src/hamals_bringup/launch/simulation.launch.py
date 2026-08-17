"""Simulation profile using Gazebo, mock PLC and the real mission control plane."""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource


def generate_launch_description():
    gazebo_launch = os.path.join(
        get_package_share_directory('hamals_robot_description'),
        'launch',
        'gazebo.launch.py',
    )
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(gazebo_launch)
    )
    competition_launch = os.path.join(
        get_package_share_directory('hamals_bringup'),
        'launch',
        'competition.launch.py',
    )
    simulation_profile = os.path.join(
        get_package_share_directory('hamals_world_model'),
        'config',
        'profiles',
        'simulation.yaml',
    )
    competition = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(competition_launch),
        launch_arguments={
            'with_hardware': 'false',
            'with_ui': 'true',
            'with_vision': 'false',
            'world_profile': simulation_profile,
        }.items(),
    )
    return LaunchDescription([gazebo, competition])
