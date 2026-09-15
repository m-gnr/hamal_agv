#!/usr/bin/env python3

import math
import time

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient

from geometry_msgs.msg import Twist, PoseStamped
from nav2_msgs.action import NavigateToPose

from std_msgs.msg import Bool, Int32, String


class SimpleMission(Node):

    def __init__(self):
        super().__init__('simple_a1_b1_mission')

        # ============================================================
        # NAV2
        # ============================================================

        self.nav = ActionClient(
            self,
            NavigateToPose,
            '/navigate_to_pose'
        )

        # ============================================================
        # MOTION
        # ============================================================

        self.cmd_pub = self.create_publisher(
            Twist,
            '/cmd_vel/manual',
            10
        )

        # ============================================================
        # QR
        # ============================================================

        self.qr_text = ''

        self.create_subscription(
            String,
            '/qr/text',
            self.qr_callback,
            10
        )

        # ============================================================
        # LINE
        # ============================================================

        self.line_detected = False
        self.line_error = 0

        self.create_subscription(
            Bool,
            '/line/detected',
            self.line_detected_callback,
            10
        )

        self.create_subscription(
            Int32,
            '/line/error',
            self.line_error_callback,
            10
        )

        self.get_logger().info('======================================')
        self.get_logger().info(' SIMPLE A1 -> B1 MISSION')
        self.get_logger().info('======================================')

    # ================================================================
    # QR
    # ================================================================

    def qr_callback(self, msg):
        self.qr_text = msg.data.strip()

    # ================================================================
    # LINE
    # ================================================================

    def line_detected_callback(self, msg):
        self.line_detected = msg.data

    def line_error_callback(self, msg):
        self.line_error = msg.data

    # ================================================================
    # STOP
    # ================================================================

    def stop(self):

        cmd = Twist()

        for _ in range(10):
            self.cmd_pub.publish(cmd)
            time.sleep(0.02)

    # ================================================================
    # CREATE POSE
    # ================================================================

    def pose(self, x, y, yaw_deg):

        p = PoseStamped()

        p.header.frame_id = 'map'
        p.header.stamp = self.get_clock().now().to_msg()

        p.pose.position.x = x
        p.pose.position.y = y
        p.pose.position.z = 0.0

        yaw = math.radians(yaw_deg)

        p.pose.orientation.z = math.sin(yaw / 2.0)
        p.pose.orientation.w = math.cos(yaw / 2.0)

        return p

    # ================================================================
    # NAVIGATE
    # ================================================================

    def navigate(self, x, y, yaw):

        self.get_logger().info(
            f'NAV -> x={x:.3f} y={y:.3f} yaw={yaw:.1f}'
        )

        if not self.nav.wait_for_server(timeout_sec=5.0):

            self.get_logger().error(
                'Nav2 action server unavailable'
            )

            return False

        goal = NavigateToPose.Goal()

        goal.pose = self.pose(
            x,
            y,
            yaw
        )

        future = self.nav.send_goal_async(goal)

        rclpy.spin_until_future_complete(
            self,
            future
        )

        handle = future.result()

        if handle is None or not handle.accepted:

            self.get_logger().error(
                'Navigation goal rejected'
            )

            return False

        self.get_logger().info(
            'Navigation goal accepted'
        )

        result_future = handle.get_result_async()

        while rclpy.ok() and not result_future.done():

            rclpy.spin_once(
                self,
                timeout_sec=0.05
            )

        result = result_future.result()

        if result is None:

            self.get_logger().error(
                'Navigation result unavailable'
            )

            return False

        status = result.status

        # Nav2 SUCCEEDED = 4
        if status == 4:

            self.get_logger().info(
                'Navigation completed'
            )

            return True

        self.get_logger().warn(
            f'Navigation finished with status {status}'
        )

        return False

    # ================================================================
    # WAIT QR
    # ================================================================

    def wait_qr(self, expected, timeout=30.0):

        self.get_logger().info(
            f'Waiting for QR: {expected}'
        )

        start = time.monotonic()

        while rclpy.ok():

            rclpy.spin_once(
                self,
                timeout_sec=0.05
            )

            if self.qr_text == expected:

                self.get_logger().info(
                    f'QR FOUND: {expected}'
                )

                return True

            if time.monotonic() - start > timeout:

                self.get_logger().error(
                    f'QR TIMEOUT: {expected}'
                )

                return False

        return False

    # ================================================================
    # FOLLOW LINE
    # ================================================================

    def follow_line(self, distance=0.60, speed=0.05):

        self.get_logger().info(
            f'FOLLOW LINE START | distance={distance:.2f}m'
        )

        # We do not use odometry distance here.
        #
        # Instead we run the line-follow command for
        # an estimated time.
        #
        # 0.60m / 0.05m/s = 12 seconds

        duration = distance / speed

        start = time.monotonic()

        while rclpy.ok():

            rclpy.spin_once(
                self,
                timeout_sec=0.01
            )

            elapsed = time.monotonic() - start

            if elapsed >= duration:
                break

            # --------------------------------------------------------
            # LINE CONTROL
            # --------------------------------------------------------

            error = float(self.line_error)

            # P controller
            turn = -error * 0.002

            # Limit turning
            turn = max(
                -0.30,
                min(0.30, turn)
            )

            cmd = Twist()

            cmd.linear.x = speed
            cmd.angular.z = turn

            self.cmd_pub.publish(cmd)

            time.sleep(0.05)

        self.stop()

        self.get_logger().info(
            'FOLLOW LINE COMPLETE'
        )

        return True

    # ================================================================
    # MISSION
    # ================================================================

    def run_mission(self):

        # ============================================================
        # A1 APPROACH
        # ============================================================

        self.get_logger().info(
            'STEP 1: Going to A1_APPROACH'
        )

        ok = self.navigate(
            1.006,
            -0.339,
            -85.9
        )

        if not ok:
            return False

        # ============================================================
        # TEKNOFEST
        # ============================================================

        self.get_logger().info(
            'STEP 2: Looking for TEKNOFEST'
        )

        if not self.wait_qr(
            'TEKNOFEST',
            30.0
        ):
            return False

        # ============================================================
        # QR FOUND -> FOLLOW LINE IMMEDIATELY
        # ============================================================

        self.get_logger().info(
            'TEKNOFEST FOUND!'
        )

        self.get_logger().info(
            'Starting line following immediately'
        )

        self.follow_line(
            distance=0.60,
            speed=0.05
        )

        # ============================================================
        # B1 APPROACH
        # ============================================================

        self.get_logger().info(
            'STEP 3: Going to B1_APPROACH'
        )

        ok = self.navigate(
            -2.019,
            -1.026,
            -178.5
        )

        if not ok:
            return False

        # ============================================================
        # B1 QR
        # ============================================================

        self.get_logger().info(
            'STEP 4: Looking for kapi_on'
        )

        if not self.wait_qr(
            'kapi_on',
            30.0
        ):
            return False

        self.get_logger().info(
            'kapi_on FOUND!'
        )

        # ============================================================
        # FOLLOW LINE TO B1
        # ============================================================

        self.follow_line(
            distance=0.60,
            speed=0.05
        )

        # ============================================================
        # COMPLETE
        # ============================================================

        self.stop()

        self.get_logger().info(
            '======================================'
        )

        self.get_logger().info(
            'MISSION A1 -> B1 COMPLETE'
        )

        self.get_logger().info(
            '======================================'
        )

        return True


def main(args=None):

    rclpy.init(args=args)

    node = SimpleMission()

    try:

        success = node.run_mission()

        if success:
            node.get_logger().info(
                'MISSION SUCCESS'
            )
        else:
            node.get_logger().error(
                'MISSION FAILED'
            )

    except KeyboardInterrupt:

        node.get_logger().warn(
            'MISSION INTERRUPTED'
        )

    finally:

        node.stop()

        node.destroy_node()

        rclpy.shutdown()


if __name__ == '__main__':
    main()
