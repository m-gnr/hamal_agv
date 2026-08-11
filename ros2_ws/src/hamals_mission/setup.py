import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'hamals_mission'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='hamal',
    maintainer_email='al_dokan_20@hotmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'mission_server = hamals_mission.mission_server:main',
            'goto_b = hamals_mission.goto_b:main',
            'test_goto = hamals_mission.test_goto:main',
            "waypoint_helper = hamals_mission.waypoint_helper:main",
        ],
    },
)
