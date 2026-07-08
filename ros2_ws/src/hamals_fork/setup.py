from setuptools import find_packages, setup

package_name = 'hamals_fork'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
        ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/config', ['config/fork.yaml']),
        ('share/' + package_name + '/launch', ['launch/fork.launch.py']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='murat',
    maintainer_email='m_gnr@icloud.com',
    description='Timer-based fork control node for Hamal AGV',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'fork_node = hamals_fork.main:main',
        ],
    },
)
