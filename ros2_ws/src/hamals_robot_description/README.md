# hamals_robot_description

`hamals_robot_description` is a ROS 2 `ament_python` package for the HAMALS forklift-style AGV robot description.

It is used to visualize the robot model in RViz, run the robot in a Gazebo Sim world, manage robot geometry from one YAML configuration file, and generate the Gazebo SDF model automatically from that YAML file.

Example development paths may be `~/develop/ros2_ws` for the ROS 2 workspace and `~/develop/ros2_ws/hamals_robot_description` for this package.

## Features

- HAMALS forklift-style AGV robot description
- RViz visualization using URDF/Xacro
- Gazebo Sim world with the robot model
- Geometry managed from `config/robot_dimensions.yaml`
- Automatic Gazebo SDF generation
- Gazebo workflow script for common server, GUI, update, check, and clean tasks

## Repository Structure

```text
hamals_robot_description/
├── config/
│   └── robot_dimensions.yaml
├── launch/
│   ├── display.launch.py
│   └── gazebo.launch.py
├── models/
│   └── hamals_robot/
│       ├── model.config
│       └── model.sdf
├── scripts/
│   ├── generate_gazebo_model.py
│   └── hamals_gazebo.sh
├── urdf/
│   └── hamals_robot.urdf.xacro
├── worlds/
│   └── hamals_empty.world.sdf
└── requirements.txt
```

Important files:

- `config/robot_dimensions.yaml`: main source of robot dimensions. Treat this as the single source of truth.
- `urdf/hamals_robot.urdf.xacro`: main URDF/Xacro model used by RViz and `robot_state_publisher`.
- `models/hamals_robot/model.sdf`: generated Gazebo model file. Do not edit this manually.
- `models/hamals_robot/model.config`: Gazebo model metadata.
- `worlds/hamals_empty.world.sdf`: Gazebo world file. It includes the robot using `model://hamals_robot`.
- `launch/display.launch.py`: launches RViz visualization.
- `launch/gazebo.launch.py`: starts Gazebo server and `robot_state_publisher`. Keep this file because the shell workflow script calls it.
- `scripts/generate_gazebo_model.py`: reads `config/robot_dimensions.yaml` and generates `models/hamals_robot/model.sdf`.
- `scripts/hamals_gazebo.sh`: main Gazebo workflow script.
- `requirements.txt`: Python pip dependencies.

## Coordinate Convention

- `+X`: forward / fork direction
- `+Y`: left
- `+Z`: up
- `base_footprint`: ground reference frame
- `base_link`: main robot body reference frame

The robot structure includes the main chassis/body, left and right drive wheels, rear caster wheel, forklift mast, moving carriage, left and right forks, and a top-mounted lidar.

## Requirements

- ROS 2
- `colcon`
- `xacro`
- `robot_state_publisher`
- `joint_state_publisher_gui`
- RViz2
- Gazebo Sim / `gz`
- `ros_gz_sim`
- PyYAML

## Python Dependencies

Install the Python dependencies from the package directory:

```bash
cd <path_to_hamals_robot_description>
conda activate ros2
pip install -r requirements.txt
```

`requirements.txt` currently contains:

```text
PyYAML>=6.0
```

## Build

Build the package from the workspace root:

```bash
cd <your_ros2_workspace>
rm -rf build install log
colcon build --packages-select hamals_robot_description
source install/setup.zsh
```

## Usage

### RViz Visualization

```bash
cd <your_ros2_workspace>
source install/setup.zsh
ros2 launch hamals_robot_description display.launch.py
```

RViz is used to inspect the URDF/Xacro model, TF tree, links, joints, wheels, lidar, mast, carriage, and forks. RViz does not run physics simulation.

### Gazebo Server

```bash
cd <path_to_hamals_robot_description>
./scripts/hamals_gazebo.sh server
```

This generates the Gazebo model from YAML, rebuilds the workspace, and starts the Gazebo server.

### Gazebo GUI

```bash
cd <path_to_hamals_robot_description>
./scripts/hamals_gazebo.sh gui
```

This starts the Gazebo GUI with the correct model path.

### Update Model and Rebuild

```bash
cd <path_to_hamals_robot_description>
./scripts/hamals_gazebo.sh update
```

Use this after editing `config/robot_dimensions.yaml`.

### Check Robot

```bash
cd <path_to_hamals_robot_description>
./scripts/hamals_gazebo.sh check
```

This checks whether `hamals_robot` exists in the Gazebo world.

### Clean Gazebo Processes

```bash
cd <path_to_hamals_robot_description>
./scripts/hamals_gazebo.sh clean
```

This stops Gazebo-related processes started by the workflow.

## YAML to SDF Workflow

The robot geometry workflow is:

1. Edit `config/robot_dimensions.yaml`.
2. Generate `models/hamals_robot/model.sdf`.
3. Rebuild the ROS 2 workspace.
4. Start Gazebo.

`config/robot_dimensions.yaml` is the geometry source. `models/hamals_robot/model.sdf` is generated from it and should not be edited manually.

After changing geometry, run:

```bash
cd <path_to_hamals_robot_description>
./scripts/hamals_gazebo.sh server
```

The script will regenerate `model.sdf`, rebuild the workspace, and start the Gazebo server.

## macOS Notes

On macOS, run the Gazebo server and GUI separately.

Terminal 1:

```bash
cd <path_to_hamals_robot_description>
./scripts/hamals_gazebo.sh server
```

Terminal 2:

```bash
cd <path_to_hamals_robot_description>
./scripts/hamals_gazebo.sh gui
```

If the Gazebo GUI has Qt conflicts, run the GUI command from a clean terminal outside the ROS conda environment.

## Development Notes

- `config/robot_dimensions.yaml` is the single source of truth for geometry.
- `models/hamals_robot/model.sdf` is generated and should not be manually edited.
- `scripts/hamals_gazebo.sh` is the recommended Gazebo entry point.
- `launch/gazebo.launch.py` should remain because the shell script calls it.
- RViz is for model inspection; Gazebo is for simulation.
