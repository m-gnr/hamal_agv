from setuptools import setup
import os
from glob import glob

package_name = 'hamals_localization'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],

    data_files=[
        # ROS 2 package index
        (
            'share/ament_index/resource_index/packages',
            ['resource/' + package_name]
        ),

        # package.xml
        (
            'share/' + package_name,
            ['package.xml']
        ),

        # launch files
        (
            os.path.join('share', package_name, 'launch'),
            glob('launch/*.py')
        ),

        # config files (odom_tf.yaml, slam.yaml, vb.)
        (
            os.path.join('share', package_name, 'config'),
            glob('config/*.yaml')
        ),
    ],

    install_requires=['setuptools'],
    zip_safe=True,

    maintainer='m_gnr',
    maintainer_email='m_gnr@icloud.com',

    description=(
        'hamals_localization: '
        'EKF-based odom fusion layer (robot_localization). '
        'Publishes TF (odom -> base_footprint) and /odom for SLAM/Nav2.'
    ),

    license='MIT',

    entry_points={
        'console_scripts': [],
    },
)