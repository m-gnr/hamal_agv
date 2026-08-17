from glob import glob
import os
from setuptools import find_packages, setup

package_name = 'hamals_safety'
setup(name=package_name, version='0.1.0', packages=find_packages(exclude=['test']),
      data_files=[('share/ament_index/resource_index/packages', ['resource/' + package_name]),
                  ('share/' + package_name, ['package.xml', 'README.md']),
                  (os.path.join('share', package_name, 'config'), glob('config/*.yaml'))],
      install_requires=['setuptools'], zip_safe=True, maintainer='murat',
      maintainer_email='m_gnr@icloud.com', description='HAMAL safety supervisor', license='MIT',
      entry_points={'console_scripts': ['safety_node = hamals_safety.safety_node:main']})
