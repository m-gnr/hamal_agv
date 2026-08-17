"""Fail-safe aggregation of E-stop, mode switch and obstacle state."""

import math
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from hamals_interfaces.msg import ObstacleState, SafetyState


class SafetyNode(Node):
    def __init__(self):
        super().__init__('hamals_safety')
        self.declare_parameter('obstacle_clear_sec', 0.75)
        self.declare_parameter('obstacle_stale_sec', 1.0)
        self.declare_parameter('require_obstacle_heartbeat', True)
        self.declare_parameter('initial_mode', 'auto')
        self.estop = False
        self.manual = str(self.get_parameter('initial_mode').value).lower() != 'auto'
        self.obstacle = False
        self.min_distance = math.inf
        self.last_obstacle_msg = 0.0
        self.clear_since = time.monotonic()
        self.state_pub = self.create_publisher(SafetyState, '/safety/state', 10)
        self.lock_pub = self.create_publisher(Bool, '/safety/lock', 10)
        self.create_subscription(Bool, '/estop', self._estop, 10)
        self.create_subscription(String, '/switch/mode', self._mode, 10)
        self.create_subscription(ObstacleState, '/scan/obstacle_state', self._obstacles, 10)
        self.create_timer(0.05, self._tick)

    def _estop(self, msg):
        self.estop = bool(msg.data)

    def _mode(self, msg):
        self.manual = str(msg.data).strip().lower() != 'auto'

    def _obstacles(self, msg):
        now = time.monotonic()
        active = [region for region in msg.regions if region.has_obstacle]
        self.last_obstacle_msg = now
        self.min_distance = min((float(region.min_distance) for region in active), default=math.inf)
        if active:
            self.obstacle = True
            self.clear_since = now
        elif now - self.clear_since >= float(self.get_parameter('obstacle_clear_sec').value):
            self.obstacle = False

    def _tick(self):
        stale = bool(self.get_parameter('require_obstacle_heartbeat').value) and (
            time.monotonic() - self.last_obstacle_msg >
            float(self.get_parameter('obstacle_stale_sec').value)
        )
        state = SafetyState.SAFE
        reason = ''
        if self.estop:
            state, reason = SafetyState.ESTOP, 'emergency stop active'
        elif self.manual:
            state, reason = SafetyState.MANUAL, 'manual mode active'
        elif stale:
            state, reason = SafetyState.SENSOR_STALE, 'obstacle heartbeat stale'
        elif self.obstacle:
            state, reason = SafetyState.OBSTACLE, 'obstacle detected'
        allowed = state == SafetyState.SAFE
        self.lock_pub.publish(Bool(data=not allowed))
        msg = SafetyState()
        msg.stamp = self.get_clock().now().to_msg()
        msg.state = state
        msg.motion_allowed = allowed
        msg.estop_active = self.estop
        msg.manual_mode = self.manual
        msg.obstacle_active = self.obstacle
        msg.obstacle_distance_m = float(self.min_distance if math.isfinite(self.min_distance) else -1.0)
        msg.reason = reason
        self.state_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = SafetyNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
