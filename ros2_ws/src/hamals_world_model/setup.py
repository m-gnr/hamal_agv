from glob import glob
import os
from setuptools import find_packages, setup

package_name = 'hamals_world_model'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
        (os.path.join('share', package_name, 'config', 'profiles'), glob('config/profiles/*.yaml')),
        (os.path.join('share', package_name, 'config', 'fields'), glob('config/fields/*.yaml')),
    ],
    install_requires=['setuptools', 'PyYAML'],
    zip_safe=True,
    maintainer='murat',
    maintainer_email='m_gnr@icloud.com',
    description='Validated semantic world model for HAMAL AGV',
    license='MIT',
    tests_require=['pytest'],
    entry_points={'console_scripts': ['world_model_node = hamals_world_model.world_model_node:main']},
)
