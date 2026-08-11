from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    camera_share = get_package_share_directory('hamals_camera')
    line_share = get_package_share_directory('hamals_line')
    qr_share = get_package_share_directory('hamals_qr')

    camera_config = os.path.join(camera_share, 'config', 'camera_params.yaml')
    line_config = os.path.join(line_share, 'config', 'line_params.yaml')
    qr_config = os.path.join(qr_share, 'config', 'qr_params.yaml')

    camera_node = Node(
        package='hamals_camera',
        executable='camera_node',
        name='camera_node',
        output='screen',
        parameters=[camera_config],
    )

    line_node = Node(
        package='hamals_line',
        executable='line_node',
        name='line_node',
        output='screen',
        parameters=[line_config],
    )

    qr_node = Node(
        package='hamals_qr',
        executable='qr_node',
        name='qr_node',
        output='screen',
        parameters=[qr_config],
    )

    return LaunchDescription([
        camera_node,
        line_node,
        qr_node,
    ])
