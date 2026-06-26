from launch import LaunchDescription
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

    joint_state_publisher_gui = Node(
        package="joint_state_publisher_gui",
        executable="joint_state_publisher_gui",
        parameters=[
            {
                "robot_description": robot_description
            }
        ],
        output="screen"
    )

    rviz = Node(
        package="rviz2",
        executable="rviz2",
        output="screen"
    )

    return LaunchDescription([
        joint_state_publisher_gui,
        robot_state_publisher,
        rviz
    ])