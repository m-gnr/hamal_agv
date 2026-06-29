from setuptools import find_packages, setup
import os
from glob import glob


def package_files(directory):
    paths = []
    for (path, _, filenames) in os.walk(directory):
        for filename in filenames:
            full_path = os.path.join(path, filename)
            paths.append(full_path)
    return paths


package_name = 'hamals_ui'

data_files = [
    ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
    ('share/' + package_name, ['package.xml']),
    (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
]

# Config files (recursive)
for f in package_files('config'):
    install_dir = os.path.join('share', package_name, os.path.dirname(f))
    data_files.append((install_dir, [f]))

# Built web assets (produced by `npm run build` → web/dist/)
if os.path.isdir('web/dist'):
    for f in package_files('web/dist'):
        install_dir = os.path.join('share', package_name, os.path.dirname(f))
        data_files.append((install_dir, [f]))

setup(
    name=package_name,
    version='0.0.1',
    packages=find_packages(exclude=['test']),
    data_files=data_files,
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='m-gnr',
    maintainer_email='m_gnr@icloud.com',
    description='HAMALS AGV jury web interface — ROS 2 bridge + Vue 3 SPA',
    license='MIT',
    extras_require={
        'test': ['pytest'],
    },
    entry_points={
        'console_scripts': [
            'ui_bridge_node = hamals_ui.ui_bridge_node:main',
        ],
    },
)
