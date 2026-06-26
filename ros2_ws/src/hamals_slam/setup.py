from setuptools import setup
import os
from glob import glob

package_name = 'hamals_slam'

setup(
    name=package_name,
    version='0.0.0',

    packages=[],

    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),

        ('share/' + package_name, ['package.xml']),

        (os.path.join('share', package_name, 'launch'),
            glob('launch/*.py')),

        (os.path.join('share', package_name, 'config'),
            glob('config/*.yaml')),
    ],

    install_requires=['setuptools'],
    zip_safe=True,

    maintainer='m_gnr',
    maintainer_email='m_gnr@icloud.com',
    description='SLAM configuration package for HAMALS robot (slam_toolbox)',
    license='MIT',
)