from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    pkg_share = get_package_share_directory('hamals_localization')

    params_file = os.path.join(
        pkg_share,
        'config',
        'ekf.yaml'
    )

    # NOTE:
    #   - EKF publishes TF: odom -> base_footprint (publish_tf: true)
    #   - We remap the default output topic (/odometry/filtered) to /odom
    return LaunchDescription([
        Node(
            package='robot_localization',
            executable='ekf_node',
            name='ekf_filter_node',
            output='screen',
            parameters=[params_file],
            remappings=[
                ('/odometry/filtered', '/odom'),
            ],
        ),
    ])