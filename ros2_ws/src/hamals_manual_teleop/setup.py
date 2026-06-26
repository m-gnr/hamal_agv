from setuptools import setup
import os
from glob import glob

package_name = 'hamals_manual_teleop'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'),
            glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='m_gnr',
    maintainer_email='m_gnr@icloud.com',
    description='Minimal manual teleop publishing cmd_vel',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'teleop_node = hamals_manual_teleop.teleop_node:main',
        ],
    },
)
