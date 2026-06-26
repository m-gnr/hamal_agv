from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    pkg_share = get_package_share_directory('hamals_slam')

    params_file = os.path.join(pkg_share, 'config', 'localization.yaml')

    # Kullanıcı home altında maps klasörü
    maps_dir = os.path.join(os.path.expanduser('~'), 'maps')
    os.makedirs(maps_dir, exist_ok=True)

    # slam_toolbox localization için base name (uzantısız)
    # Dosyalar şöyle olmalı:
    #   ~/maps/hamals_map.posegraph
    #   ~/maps/hamals_map.data
    map_base = os.path.join(maps_dir, 'hamals_map')

    return LaunchDescription([
        Node(
            package='slam_toolbox',
            executable='localization_slam_toolbox_node',
            name='slam_toolbox',
            output='screen',
            parameters=[
                params_file,
                {
                    # slam_toolbox mapper_params_localization.yaml içinde kullanılan isim
                    'map_file_name': map_base,
                }
            ],
        )
    ])