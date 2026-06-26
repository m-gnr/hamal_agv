from launch import LaunchDescription
from launch.actions import ExecuteProcess, SetEnvironmentVariable
from launch.substitutions import Command, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    package_share = FindPackageShare("hamals_robot_description")

    robot_description_file = PathJoinSubstitution([
        package_share,
        "urdf",
        "hamals_robot.urdf.xacro"
    ])

    world_file = PathJoinSubstitution([
        package_share,
        "worlds",
        "hamals_empty.world.sdf"
    ])

    model_resource_path = PathJoinSubstitution([
        package_share,
        "models"
    ])

    set_gz_resource_path = SetEnvironmentVariable(
        name="GZ_SIM_RESOURCE_PATH",
        value=model_resource_path
    )

    robot_description = ParameterValue(
        Command([
            "xacro ",
            robot_description_file
        ]),
        value_type=str
    )

    robot_state_publisher = Node(
        package="robot_state_publisher",
        executable="robot_state_publisher",
        parameters=[
            {
                "robot_description": robot_description,
                "publish_frequency": 50.0
            }
        ],
        output="screen"
    )

    gazebo_server = ExecuteProcess(
        cmd=[
            "gz",
            "sim",
            "-s",
            "-r",
            world_file
        ],
        output="screen"
    )

    return LaunchDescription([
        set_gz_resource_path,
        gazebo_server,
        robot_state_publisher
    ])