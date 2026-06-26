#!/usr/bin/env python3

from pathlib import Path
import yaml


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PACKAGE_ROOT / "config" / "robot_dimensions.yaml"
OUTPUT_PATH = PACKAGE_ROOT / "models" / "hamals_robot" / "model.sdf"


def fmt_xyz(values):
    return f"{values[0]} {values[1]} {values[2]}"


def fmt_pose(xyz, rpy=None):
    if rpy is None:
        rpy = [0.0, 0.0, 0.0]
    return f"{xyz[0]} {xyz[1]} {xyz[2]} {rpy[0]} {rpy[1]} {rpy[2]}"


def material_rgba(config, key):
    color = config["materials"][key]["color"]
    return f"{color[0]} {color[1]} {color[2]} {color[3]}"


def inertia_xml(config, key):
    inertial = config["inertial"][key]

    return f"""
      <inertial>
        <mass>{inertial["mass"]}</mass>
        <inertia>
          <ixx>{inertial["ixx"]}</ixx>
          <ixy>{inertial["ixy"]}</ixy>
          <ixz>{inertial["ixz"]}</ixz>
          <iyy>{inertial["iyy"]}</iyy>
          <iyz>{inertial["iyz"]}</iyz>
          <izz>{inertial["izz"]}</izz>
        </inertia>
      </inertial>"""


def box_link(name, pose, size, material, inertial_xml):
    return f"""
    <link name="{name}">
      <pose>{pose}</pose>
{inertial_xml}

      <collision name="{name}_collision">
        <geometry>
          <box>
            <size>{size}</size>
          </box>
        </geometry>
      </collision>

      <visual name="{name}_visual">
        <geometry>
          <box>
            <size>{size}</size>
          </box>
        </geometry>
        <material>
          <ambient>{material}</ambient>
          <diffuse>{material}</diffuse>
        </material>
      </visual>
    </link>
"""


def cylinder_link(name, pose, radius, length, material, inertial_xml):
    return f"""
    <link name="{name}">
      <pose>{pose}</pose>
{inertial_xml}

      <collision name="{name}_collision">
        <geometry>
          <cylinder>
            <radius>{radius}</radius>
            <length>{length}</length>
          </cylinder>
        </geometry>
      </collision>

      <visual name="{name}_visual">
        <geometry>
          <cylinder>
            <radius>{radius}</radius>
            <length>{length}</length>
          </cylinder>
        </geometry>
        <material>
          <ambient>{material}</ambient>
          <diffuse>{material}</diffuse>
        </material>
      </visual>
    </link>
"""


def sphere_link(name, pose, radius, material, inertial_xml):
    return f"""
    <link name="{name}">
      <pose>{pose}</pose>
{inertial_xml}

      <collision name="{name}_collision">
        <geometry>
          <sphere>
            <radius>{radius}</radius>
          </sphere>
        </geometry>
      </collision>

      <visual name="{name}_visual">
        <geometry>
          <sphere>
            <radius>{radius}</radius>
          </sphere>
        </geometry>
        <material>
          <ambient>{material}</ambient>
          <diffuse>{material}</diffuse>
        </material>
      </visual>
    </link>
"""


def fixed_joint(name, parent, child):
    return f"""
    <joint name="{name}" type="fixed">
      <parent>{parent}</parent>
      <child>{child}</child>
    </joint>
"""


def revolute_joint(name, parent, child, axis):
    return f"""
    <joint name="{name}" type="revolute">
      <parent>{parent}</parent>
      <child>{child}</child>
      <axis>
        <xyz>{fmt_xyz(axis)}</xyz>
        <limit>
          <lower>-1e16</lower>
          <upper>1e16</upper>
        </limit>
      </axis>
    </joint>
"""


def prismatic_joint(name, parent, child, axis, limit):
    return f"""
    <joint name="{name}" type="prismatic">
      <parent>{parent}</parent>
      <child>{child}</child>
      <axis>
        <xyz>{fmt_xyz(axis)}</xyz>
        <limit>
          <lower>{limit["lower"]}</lower>
          <upper>{limit["upper"]}</upper>
          <effort>{limit["effort"]}</effort>
          <velocity>{limit["velocity"]}</velocity>
        </limit>
      </axis>
    </joint>
"""


def main():
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    frames = config["robot"]["frames"]

    base = config["base"]
    left_drive = config["wheels"]["left_drive"]
    right_drive = config["wheels"]["right_drive"]
    caster = config["caster"]["rear_center"]
    mast = config["forklift"]["mast"]
    carriage = config["forklift"]["carriage"]
    forks = config["forklift"]["forks"]
    lidar_mount = config["lidar_mount"]
    lidar = config["lidar"]

    base_pose = fmt_pose(base["origin"]["xyz"], base["origin"]["rpy"])

    left_wheel_pose = fmt_pose([
        base["origin"]["xyz"][0] + left_drive["origin"]["xyz"][0],
        base["origin"]["xyz"][1] + left_drive["origin"]["xyz"][1],
        base["origin"]["xyz"][2] + left_drive["origin"]["xyz"][2],
    ], left_drive["origin"]["rpy"])

    right_wheel_pose = fmt_pose([
        base["origin"]["xyz"][0] + right_drive["origin"]["xyz"][0],
        base["origin"]["xyz"][1] + right_drive["origin"]["xyz"][1],
        base["origin"]["xyz"][2] + right_drive["origin"]["xyz"][2],
    ], right_drive["origin"]["rpy"])

    caster_pose = fmt_pose([
        base["origin"]["xyz"][0] + caster["origin"]["xyz"][0],
        base["origin"]["xyz"][1] + caster["origin"]["xyz"][1],
        base["origin"]["xyz"][2] + caster["origin"]["xyz"][2],
    ], caster["origin"]["rpy"])

    mast_pose = fmt_pose([
        base["origin"]["xyz"][0] + mast["origin"]["xyz"][0],
        base["origin"]["xyz"][1] + mast["origin"]["xyz"][1],
        base["origin"]["xyz"][2] + mast["origin"]["xyz"][2],
    ], mast["origin"]["rpy"])

    carriage_pose = fmt_pose([
        base["origin"]["xyz"][0] + mast["origin"]["xyz"][0] + carriage["origin"]["xyz"][0],
        base["origin"]["xyz"][1] + mast["origin"]["xyz"][1] + carriage["origin"]["xyz"][1],
        base["origin"]["xyz"][2] + mast["origin"]["xyz"][2] + carriage["origin"]["xyz"][2],
    ], carriage["origin"]["rpy"])

    left_fork_pose = fmt_pose([
        base["origin"]["xyz"][0] + mast["origin"]["xyz"][0] + carriage["origin"]["xyz"][0] + forks["left"]["origin"]["xyz"][0],
        base["origin"]["xyz"][1] + mast["origin"]["xyz"][1] + carriage["origin"]["xyz"][1] + forks["left"]["origin"]["xyz"][1],
        base["origin"]["xyz"][2] + mast["origin"]["xyz"][2] + carriage["origin"]["xyz"][2] + forks["left"]["origin"]["xyz"][2],
    ], forks["left"]["origin"]["rpy"])

    right_fork_pose = fmt_pose([
        base["origin"]["xyz"][0] + mast["origin"]["xyz"][0] + carriage["origin"]["xyz"][0] + forks["right"]["origin"]["xyz"][0],
        base["origin"]["xyz"][1] + mast["origin"]["xyz"][1] + carriage["origin"]["xyz"][1] + forks["right"]["origin"]["xyz"][1],
        base["origin"]["xyz"][2] + mast["origin"]["xyz"][2] + carriage["origin"]["xyz"][2] + forks["right"]["origin"]["xyz"][2],
    ], forks["right"]["origin"]["rpy"])

    lidar_mount_pose = fmt_pose([
        base["origin"]["xyz"][0] + lidar_mount["origin"]["xyz"][0],
        base["origin"]["xyz"][1] + lidar_mount["origin"]["xyz"][1],
        base["origin"]["xyz"][2] + lidar_mount["origin"]["xyz"][2],
    ], lidar_mount["origin"]["rpy"])

    lidar_pose = fmt_pose([
        base["origin"]["xyz"][0] + lidar_mount["origin"]["xyz"][0] + lidar["origin"]["xyz"][0],
        base["origin"]["xyz"][1] + lidar_mount["origin"]["xyz"][1] + lidar["origin"]["xyz"][1],
        base["origin"]["xyz"][2] + lidar_mount["origin"]["xyz"][2] + lidar["origin"]["xyz"][2],
    ], lidar["origin"]["rpy"])

    mast_left_column = mast["columns"]["left"]
    mast_right_column = mast["columns"]["right"]

    base_size = f'{base["length"]} {base["width"]} {base["height"]}'
    mast_collision_size = f'{mast["depth"]} {mast["width"]} {mast["height"]}'
    carriage_size = f'{carriage["depth"]} {carriage["width"]} {carriage["height"]}'
    fork_size = f'{forks["length"]} {forks["width"]} {forks["height"]}'

    sdf = f"""<?xml version="1.0" ?>
<sdf version="1.9">
  <model name="{config["robot"]["name"]}">
    <pose>0 0 0 0 0 0</pose>

{box_link(frames["base_link"], base_pose, base_size, material_rgba(config, "base"), inertia_xml(config, "base"))}

{cylinder_link(frames["left_drive_wheel_link"], left_wheel_pose, left_drive["radius"], left_drive["width"], material_rgba(config, "wheels"), inertia_xml(config, "wheel"))}
{revolute_joint(left_drive["joint"]["name"], frames["base_link"], frames["left_drive_wheel_link"], left_drive["joint"]["axis"])}

{cylinder_link(frames["right_drive_wheel_link"], right_wheel_pose, right_drive["radius"], right_drive["width"], material_rgba(config, "wheels"), inertia_xml(config, "wheel"))}
{revolute_joint(right_drive["joint"]["name"], frames["base_link"], frames["right_drive_wheel_link"], right_drive["joint"]["axis"])}

{sphere_link(frames["rear_center_caster_link"], caster_pose, caster["radius"], material_rgba(config, "caster"), inertia_xml(config, "caster"))}
{fixed_joint(caster["joint"]["name"], frames["base_link"], frames["rear_center_caster_link"])}

    <link name="{frames["forklift_mast_link"]}">
      <pose>{mast_pose}</pose>
{inertia_xml(config, "forklift_mast")}

      <collision name="forklift_mast_collision">
        <geometry>
          <box>
            <size>{mast_collision_size}</size>
          </box>
        </geometry>
      </collision>

      <visual name="left_mast_column_visual">
        <pose>{fmt_pose(mast_left_column["origin"]["xyz"], mast_left_column["origin"]["rpy"])}</pose>
        <geometry>
          <box>
            <size>{mast_left_column["depth"]} {mast_left_column["width"]} {mast_left_column["height"]}</size>
          </box>
        </geometry>
        <material>
          <ambient>{material_rgba(config, "forklift_mast")}</ambient>
          <diffuse>{material_rgba(config, "forklift_mast")}</diffuse>
        </material>
      </visual>

      <visual name="right_mast_column_visual">
        <pose>{fmt_pose(mast_right_column["origin"]["xyz"], mast_right_column["origin"]["rpy"])}</pose>
        <geometry>
          <box>
            <size>{mast_right_column["depth"]} {mast_right_column["width"]} {mast_right_column["height"]}</size>
          </box>
        </geometry>
        <material>
          <ambient>{material_rgba(config, "forklift_mast")}</ambient>
          <diffuse>{material_rgba(config, "forklift_mast")}</diffuse>
        </material>
      </visual>
    </link>
{fixed_joint(mast["joint"]["name"], frames["base_link"], frames["forklift_mast_link"])}

{box_link(frames["fork_carriage_link"], carriage_pose, carriage_size, material_rgba(config, "fork_carriage"), inertia_xml(config, "fork_carriage"))}
{prismatic_joint(carriage["joint"]["name"], frames["forklift_mast_link"], frames["fork_carriage_link"], carriage["joint"]["axis"], carriage["joint"]["limit"])}

{box_link(frames["left_fork_link"], left_fork_pose, fork_size, material_rgba(config, "forks"), inertia_xml(config, "fork"))}
{fixed_joint(forks["left"]["joint"]["name"], frames["fork_carriage_link"], frames["left_fork_link"])}

{box_link(frames["right_fork_link"], right_fork_pose, fork_size, material_rgba(config, "forks"), inertia_xml(config, "fork"))}
{fixed_joint(forks["right"]["joint"]["name"], frames["fork_carriage_link"], frames["right_fork_link"])}

{cylinder_link(frames["lidar_mount_link"], lidar_mount_pose, lidar_mount["radius"], lidar_mount["height"], material_rgba(config, "lidar_mount"), inertia_xml(config, "lidar_mount"))}
{fixed_joint(lidar_mount["joint"]["name"], frames["base_link"], frames["lidar_mount_link"])}

{cylinder_link(frames["lidar_link"], lidar_pose, lidar["radius"], lidar["height"], material_rgba(config, "lidar"), inertia_xml(config, "lidar"))}
{fixed_joint(lidar["joint"]["name"], frames["lidar_mount_link"], frames["lidar_link"])}

  </model>
</sdf>
"""

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(sdf, encoding="utf-8")

    print(f"Generated: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()