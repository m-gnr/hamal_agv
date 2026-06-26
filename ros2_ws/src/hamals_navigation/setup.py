from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'hamals_navigation'


def package_files(directory):
    """
    Recursively collect files under `directory` to install into share/<package_name>/<directory>/...
    """
    paths = []
    for (path, _, filenames) in os.walk(directory):
        for filename in filenames:
            full_path = os.path.join(path, filename)
            paths.append(full_path)
    return paths


data_files = [
    ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
    ('share/' + package_name, ['package.xml']),
]

# --- launch files ---
data_files.append((os.path.join('share', package_name, 'launch'),
                  glob('launch/*.py')))

# --- config files (recursive) ---
for f in package_files('config'):
    install_dir = os.path.join('share', package_name, os.path.dirname(f))
    data_files.append((install_dir, [f]))

# --- rviz files (recursive) ---
if os.path.isdir('rviz'):
    for f in package_files('rviz'):
        install_dir = os.path.join('share', package_name, os.path.dirname(f))
        data_files.append((install_dir, [f]))

# --- other optional folders (add if you use them) ---
# e.g. maps/, params/, behavior_trees/
# if os.path.isdir('maps'):
#     for f in package_files('maps'):
#         install_dir = os.path.join('share', package_name, os.path.dirname(f))
#         data_files.append((install_dir, [f]))


setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=data_files,
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='m-gnr',
    maintainer_email='m_gnr@icloud.com',
    description='HAMALS Nav2 bringup package',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [],
    },
)