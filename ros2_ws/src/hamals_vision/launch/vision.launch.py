from pathlib import Path

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

from launch_ros.actions import Node


def generate_launch_description():
    share = Path(get_package_share_directory('hamals_vision'))
    default_params = str(share / 'config' / 'vision.yaml')

    params_arg = DeclareLaunchArgument(
        'params_file',
        default_value=default_params,
        description='vision_node parametre dosyasi',
    )

    log_level_arg = DeclareLaunchArgument(
        'log_level',
        default_value='info',
        description='debug | info | warn | error',
    )

    vision = Node(
        package='hamals_vision',
        executable='vision_node',
        name='vision_node',
        output='screen',
        emulate_tty=True,
        parameters=[LaunchConfiguration('params_file')],
        arguments=[
            '--ros-args', '--log-level',
            ['vision_node:=', LaunchConfiguration('log_level')],
        ],
    )

    return LaunchDescription([params_arg, log_level_arg, vision])
