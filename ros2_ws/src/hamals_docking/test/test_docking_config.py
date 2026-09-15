import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rclpy
from hamals_docking.docking_node import DockingNode


def test_dropoff_reverse_line_distance_uses_profile_value():
    rclpy.init()
    try:
        node = DockingNode()
        assert node.dropoff_follow_distance_m == pytest.approx(1.20, rel=0.0, abs=1e-6)
        node.destroy_node()
    finally:
        if rclpy.ok():
            rclpy.shutdown()
