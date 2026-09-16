from glob import glob

from setuptools import find_packages, setup

package_name = 'hamals_vision'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='hamal',
    maintainer_email='root@todo.todo',
    description='HAMAL birlesik gorus dugumu (kamera + cizgi + QR).',
    license='MIT',
    extras_require={'test': ['pytest']},
    entry_points={
        'console_scripts': [
            'vision_node = hamals_vision.vision_node:main',
        ],
    },
)
