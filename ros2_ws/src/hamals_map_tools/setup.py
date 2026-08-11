from setuptools import find_packages, setup


package_name = "hamals_map_tools"


setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(exclude=["test"]),
    data_files=[
        (
            "share/ament_index/resource_index/packages",
            ["resource/" + package_name],
        ),
        (
            "share/" + package_name,
            ["package.xml"],
        ),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="hamal",
    maintainer_email="hamal@todo.todo",
    description="HAMAL web panel harita kaydetme servisi",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            (
                "map_save_server = "
                "hamals_map_tools.map_save_server:main"
            ),
        ],
    },
)
