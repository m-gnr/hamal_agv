import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    use_sim_time = LaunchConfiguration('use_sim_time')
    nav2_params_file = LaunchConfiguration('nav2_params_file')
    autostart = LaunchConfiguration('autostart')
    map_yaml_file = LaunchConfiguration('map')

    pkg_share = get_package_share_directory('hamals_navigation')
    nav2_params_default = os.path.join(pkg_share, 'config', 'nav2', 'nav2_params.yaml')
    nav2_bringup_share = get_package_share_directory('nav2_bringup')

    declare_args = [
        DeclareLaunchArgument('use_sim_time', default_value='false'),
        DeclareLaunchArgument('nav2_params_file', default_value=nav2_params_default),
        DeclareLaunchArgument('autostart', default_value='true'),
        DeclareLaunchArgument(
            'map',
            default_value='/home/m-gnr/maps/hamals_map.yaml',
            description='Full path to map yaml file.'
        ),
    ]

    nav2_localization = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_share, 'launch', 'localization_launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'params_file': nav2_params_file,
            'map': map_yaml_file,
            'autostart': autostart,
        }.items(),
    )

    nav2_navigation = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_share, 'launch', 'navigation_launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'params_file': nav2_params_file,
            'autostart': autostart,
            'use_composition': 'False',
        }.items(),
    )

    return LaunchDescription(declare_args + [nav2_localization, nav2_navigation])