from setuptools import setup
from glob import glob
import os

package_name = "hamals_robot_description"

setup(
    name=package_name,
    version="0.0.1",
    packages=[],
    data_files=[
        ("share/ament_index/resource_index/packages", [
            os.path.join("resource", package_name)
        ]),
        ("share/" + package_name, [
            "package.xml"
        ]),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
        (os.path.join("share", package_name, "urdf"), glob("urdf/*.xacro")),
        (os.path.join("share", package_name, "launch"), glob("launch/*.py")),
        (os.path.join("share", package_name, "rviz"), glob("rviz/*.rviz")),
        (os.path.join("share", package_name, "worlds"), glob("worlds/*.sdf")),
        (os.path.join("share", package_name, "models", "hamals_robot"), glob("models/hamals_robot/*")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Murat Güner",
    maintainer_email="m_gnr@icloud.com",
    description="HAMALS forklift AGV robot description package",
    license="MIT",
    entry_points={
        "console_scripts": [
        ],
    },
)