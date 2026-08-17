"""Action server turning QR/line perception into bounded docking motion."""

import asyncio
import time

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.node import Node
from std_msgs.msg import Bool, Int32

from hamals_interfaces.action import Dock
from hamals_interfaces.msg import QrDetection


class DockingNode(Node):
    def __init__(self):
        super().__init__('hamals_docking')
        for name, value in {'speed_mps': 0.10, 'gain': 0.002, 'max_turn_rps': 0.30,
                            'pickup_distance_m': 1.50, 'dropoff_distance_m': 1.50,
                            'timeout_sec': 30.0,
                            'line_lost_sec': 0.75}.items():
            self.declare_parameter(name, value)
        self.declare_parameter('supported_profiles', ['pickup_default', 'dropoff_default'])
        self.qr = None
        self.line_detected = False
        self.line_error = 0
        self.line_seen_at = 0.0
        self.position = None
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel/docking', 10)
        self.create_subscription(QrDetection, '/qr/detection', self._qr, 10)
        self.create_subscription(Bool, '/line/detected', self._line_detected, 10)
        self.create_subscription(Int32, '/line/error', self._line_error, 10)
        self.create_subscription(Odometry, '/odom', self._odom, 10)
        self.server = ActionServer(self, Dock, '/dock', execute_callback=self._execute,
                                   goal_callback=lambda _: GoalResponse.ACCEPT,
                                   cancel_callback=lambda _: CancelResponse.ACCEPT)

    def _qr(self, msg):
        self.qr = msg

    def _line_detected(self, msg):
        self.line_detected = bool(msg.data)
        if self.line_detected:
            self.line_seen_at = time.monotonic()

    def _line_error(self, msg):
        self.line_error = int(msg.data)

    def _odom(self, msg):
        self.position = (float(msg.pose.pose.position.x), float(msg.pose.pose.position.y))

    def _stop(self):
        self.cmd_pub.publish(Twist())

    async def _execute(self, handle):
        if handle.request.profile not in self.get_parameter('supported_profiles').value:
            handle.abort()
            return Dock.Result(success=False, message=f'unknown docking profile: {handle.request.profile}')
        expected = handle.request.expected_qr
        timeout = float(self.get_parameter('timeout_sec').value)
        started = time.monotonic()
        while time.monotonic() - started < timeout:
            if handle.is_cancel_requested:
                self._stop()
                handle.canceled()
                return Dock.Result(success=False, message='canceled')
            qr_ok = self.qr is not None and self.qr.detected and self.qr.payload == expected
            feedback = Dock.Feedback(phase='verify_qr', qr_verified=qr_ok,
                                     line_detected=self.line_detected)
            handle.publish_feedback(feedback)
            if qr_ok:
                break
            await asyncio.sleep(0.05)
        else:
            handle.abort()
            return Dock.Result(success=False, message=f'expected QR not seen: {expected}')
        distance_parameter = 'pickup_distance_m' if handle.request.operation == 'pickup' else 'dropoff_distance_m'
        target = float(self.get_parameter(distance_parameter).value)
        speed = float(self.get_parameter('speed_mps').value)
        if self.position is None:
            handle.abort()
            return Dock.Result(success=False, message='odometry unavailable')
        start_position = self.position
        drive_started = time.monotonic()
        self.line_seen_at = drive_started
        distance = 0.0
        while distance < target and time.monotonic() - drive_started < timeout:
            if handle.is_cancel_requested:
                self._stop(); handle.canceled()
                return Dock.Result(success=False, message='canceled')
            if not self.line_detected and time.monotonic() - self.line_seen_at > float(
                    self.get_parameter('line_lost_sec').value):
                self._stop(); handle.abort()
                return Dock.Result(success=False, message='line lost')
            cmd = Twist()
            cmd.linear.x = speed
            turn = -float(self.line_error) * float(self.get_parameter('gain').value)
            limit = float(self.get_parameter('max_turn_rps').value)
            cmd.angular.z = max(-limit, min(limit, turn))
            self.cmd_pub.publish(cmd)
            distance = ((self.position[0] - start_position[0]) ** 2 +
                        (self.position[1] - start_position[1]) ** 2) ** 0.5
            feedback = Dock.Feedback(phase='follow_line', qr_verified=True,
                                     line_detected=self.line_detected,
                                     distance_travelled_m=distance)
            handle.publish_feedback(feedback)
            await asyncio.sleep(0.05)
        self._stop()
        if distance < target:
            handle.abort()
            return Dock.Result(success=False, message='docking distance timeout')
        handle.succeed()
        return Dock.Result(success=True, message='docking completed')


def main(args=None):
    rclpy.init(args=args)
    node = DockingNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
