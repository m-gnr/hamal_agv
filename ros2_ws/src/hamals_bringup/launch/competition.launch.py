"""Single top-level launch for the competition robot."""

import os

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription

from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription

from launch.conditions import IfCondition, UnlessCondition

from launch.launch_description_sources import PythonLaunchDescriptionSource

from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution

from launch_ros.actions import Node

from launch_ros.parameter_descriptions import ParameterValue

from launch_ros.substitutions import FindPackageShare


def include(package, filename, **arguments):

    launch_file = os.path.join(
        get_package_share_directory(package),
        'launch',
        filename
    )

    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(launch_file),
        launch_arguments=arguments.items(),
    )


def generate_launch_description():

    bringup = get_package_share_directory('hamals_bringup')

    world = get_package_share_directory('hamals_world_model')

    plc = get_package_share_directory('hamals_plc_bridge')

    safety = get_package_share_directory('hamals_safety')

    docking = get_package_share_directory('hamals_docking')

    mission = get_package_share_directory('hamals_mission')

    slam = get_package_share_directory('hamals_slam')

    robot_description_file = PathJoinSubstitution([
        FindPackageShare('hamals_robot_description'),
        'urdf',
        'hamals_robot.urdf.xacro',
    ])

    robot_description = ParameterValue(
        Command(['xacro ', robot_description_file]),
        value_type=str
    )

    with_hardware = LaunchConfiguration('with_hardware')

    with_ui = LaunchConfiguration('with_ui')

    with_vision = LaunchConfiguration('with_vision')

    return LaunchDescription([

        # ========================================================
        # Launch Arguments
        # ========================================================

        DeclareLaunchArgument(
            'with_hardware',
            default_value='true'
        ),

        DeclareLaunchArgument(
            'with_ui',
            default_value='false'
        ),

        DeclareLaunchArgument(
            'with_vision',
            default_value='false'
        ),

        DeclareLaunchArgument(
            'plc_config',
            default_value=os.path.join(
                plc,
                'config',
                'competition.yaml'
            )
        ),

        DeclareLaunchArgument(
            'world_profile',
            default_value=os.path.join(
                world,
                'config',
                'profiles',
                'competition.yaml'
            ),
        ),

        DeclareLaunchArgument(
            'map',
            default_value=os.path.join(
                slam,
                'maps',
                'map.yaml'
            )
        ),

        # ========================================================
        # Robot Description / TF
        # ========================================================

        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            parameters=[
                {
                    'robot_description': robot_description
                }
            ],
            output='screen'
        ),

        # ========================================================
        # Hardware IO
        #
        # robot_io_bringup now also starts twist_mux.
        # ========================================================

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(
                    bringup,
                    'launch',
                    'robot_io_bringup.launch.py'
                )
            ),
            condition=IfCondition(with_hardware)
        ),

        # ========================================================
        # EKF
        # ========================================================

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(
                    get_package_share_directory(
                        'hamals_state_estimation'
                    ),
                    'launch',
                    'ekf.launch.py',
                )
            ),
            condition=IfCondition(with_hardware)
        ),

        # ========================================================
        # Navigation
        # ========================================================

        include(
            'hamals_navigation',
            'navigation.launch.py',
            map=LaunchConfiguration('map')
        ),

        # ========================================================
        # Vision
        # ========================================================

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(
                    get_package_share_directory(
                        'hamals_camera'
                    ),
                    'launch',
                    'vision_bringup.launch.py',
                )
            ),
            condition=IfCondition(with_vision)
        ),

        # ========================================================
        # LiDAR Toolbox
        # ========================================================

        include(
            'hamals_lidar_toolbox',
            'scan_processor.launch.py'
        ),

        # ========================================================
        # Fork
        # ========================================================

        include(
            'hamals_fork',
            'fork.launch.py'
        ),

        # ========================================================
        # World Model
        # ========================================================

        Node(
            package='hamals_world_model',
            executable='world_model_node',
            name='hamals_world_model',
            output='screen',
            parameters=[
                {
                    'profile': LaunchConfiguration(
                        'world_profile'
                    )
                }
            ],
        ),

        # ========================================================
        # Safety
        # ========================================================

        Node(
            package='hamals_safety',
            executable='safety_node',
            name='hamals_safety',
            output='screen',
            parameters=[
                os.path.join(
                    safety,
                    'config',
                    'safety.yaml'
                )
            ],
        ),

        # ========================================================
        # Docking
        # ========================================================

        Node(
            package='hamals_docking',
            executable='docking_node',
            name='hamals_docking',
            output='screen',
            parameters=[
                os.path.join(
                    docking,
                    'config',
                    'docking_profiles.yaml'
                )
            ],
        ),

        # ========================================================
        # PLC Bridge
        # ========================================================

        Node(
            package='hamals_plc_bridge',
            executable='plc_bridge_node',
            name='hamals_plc_bridge',
            output='screen',
            parameters=[
                LaunchConfiguration('plc_config')
            ],
        ),

        # ========================================================
        # Twist Mux - Simulation Only
        #
        # Real robot:
        #   robot_io_bringup.launch.py starts twist_mux.
        #
        # Simulation:
        #   with_hardware=false, so robot_io is not started.
        #   Therefore twist_mux is started here instead.
        # ========================================================

        Node(
            package='twist_mux',
            executable='twist_mux',
            name='twist_mux',
            output='screen',
            parameters=[
                os.path.join(
                    bringup,
                    'config',
                    'twist_mux.yaml'
                )
            ],
            remappings=[
                ('cmd_vel_out', '/cmd_vel/selected')
            ],
            condition=UnlessCondition(with_hardware),
        ),

        # ========================================================
        # Mission Server
        # ========================================================

        Node(
            package='hamals_mission',
            executable='mission_server',
            name='hamals_mission',
            output='screen',
            parameters=[
                os.path.join(
                    mission,
                    'config',
                    'mission_policy.yaml'
                )
            ],
        ),

        # ========================================================
        # UI
        # ========================================================

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(
                    get_package_share_directory(
                        'hamals_ui'
                    ),
                    'launch',
                    'ui.launch.py',
                )
            ),
            launch_arguments={
                'mode': 'live'
            }.items(),
            condition=IfCondition(with_ui),
        ),

    ])