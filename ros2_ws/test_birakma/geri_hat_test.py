
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import math
import rclpy

from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import Bool, Int32


class GeriHatTest(Node):

    def __init__(self):

        super().__init__("geri_hat_test")

        # ==========================================================
        # GERI AYARLARI
        # ==========================================================

        self.reverse_distance = 1.0
        self.speed = 0.10

        # ==========================================================
        # LINE FOLLOW - CALISAN ON KAMERA AYARLARI
        # ==========================================================

        self.gain = 0.050
        self.deadband = 18.0
        self.smoothing = 0.35
        self.max_turn = 0.45
        self.invert = True

        # ==========================================================
        # EKSTRA YUMUSATMA
        # ==========================================================

        self.max_turn_step = 0.04

        # ==========================================================
        # DONUS
        # ==========================================================

        self.rotate_angle = math.radians(180.0)
        self.rotate_speed = 0.25
        self.rotate_min_speed = 0.08

        self.rotate_tolerance = math.radians(2.0)
        self.rotate_slow_angle = math.radians(25.0)

        # ==========================================================
        # ROS
        # ==========================================================

        self.cmd_pub = self.create_publisher(
            Twist,
            "/cmd_vel/docking",
            10
        )

        self.create_subscription(
            Odometry,
            "/odom",
            self.odom_callback,
            10
        )

        self.create_subscription(
            Bool,
            "/line/detected",
            self.line_detected_callback,
            10
        )

        self.create_subscription(
            Int32,
            "/line/error",
            self.line_error_callback,
            10
        )

        # ==========================================================
        # ODOM
        # ==========================================================

        self.x = None
        self.y = None
        self.yaw = None

        # ==========================================================
        # LINE
        # ==========================================================

        self.line_detected = False
        self.line_error = 0.0

        # ==========================================================
        # FILTER
        # ==========================================================

        self.filtered_turn = 0.0

        # ==========================================================
        # START
        # ==========================================================

        self.start_x = None
        self.start_y = None
        self.start_yaw = None

        # ==========================================================
        # STATE
        # ==========================================================

        self.state = "WAIT_ODOM"

        # ==========================================================
        # DISTANCE LOG
        # ==========================================================

        self.distance_log_step = 0.10
        self.last_distance_log = 0.0

        # ==========================================================
        # PERIODIC DEBUG LOG
        # ==========================================================

        self.last_debug_time = self.get_clock().now()

        # ==========================================================
        # ROTATION LOG
        # ==========================================================

        self.rotation_log_step = math.radians(10.0)
        self.last_rotation_log = 0.0

        # ==========================================================
        # TIMER
        # ==========================================================

        self.timer = self.create_timer(
            0.05,
            self.control_loop
        )

        # ==========================================================
        # LOG
        # ==========================================================

        self.get_logger().info(
            "================================================"
        )

        self.get_logger().info(
            "GERI HAT TEST BASLATILDI"
        )

        self.get_logger().info(
            "================================================"
        )

        self.get_logger().info(
            f"Geri mesafe : {self.reverse_distance:.2f} m"
        )

        self.get_logger().info(
            f"Geri hiz    : {self.speed:.2f} m/s"
        )

        self.get_logger().info(
            f"Gain        : {self.gain:.3f}"
        )

        self.get_logger().info(
            f"Deadband    : {self.deadband:.1f}"
        )

        self.get_logger().info(
            f"Smoothing   : {self.smoothing:.2f}"
        )

        self.get_logger().info(
            f"Max turn    : {self.max_turn:.2f}"
        )

        self.get_logger().info(
            f"Turn step   : {self.max_turn_step:.3f}"
        )

        self.get_logger().info(
            f"Invert      : {self.invert}"
        )

        self.get_logger().info(
            "Odom bekleniyor..."
        )

        self.get_logger().info(
            "================================================"
        )

    # ==============================================================
    # ODOM
    # ==============================================================

    def odom_callback(self, msg):

        self.x = float(
            msg.pose.pose.position.x
        )

        self.y = float(
            msg.pose.pose.position.y
        )

        q = msg.pose.pose.orientation

        self.yaw = math.atan2(
            2.0 * (
                q.w * q.z +
                q.x * q.y
            ),
            1.0 - 2.0 * (
                q.y * q.y +
                q.z * q.z
            )
        )

    # ==============================================================
    # LINE DETECTED
    # ==============================================================

    def line_detected_callback(self, msg):

        self.line_detected = bool(msg.data)

    # ==============================================================
    # LINE ERROR
    # ==============================================================

    def line_error_callback(self, msg):

        self.line_error = float(msg.data)

    # ==============================================================
    # ANGLE NORMALIZE
    # ==============================================================

    @staticmethod
    def normalize_angle(angle):

        while angle > math.pi:
            angle -= 2.0 * math.pi

        while angle < -math.pi:
            angle += 2.0 * math.pi

        return angle

    # ==============================================================
    # STOP
    # ==============================================================

    def stop_robot(self):

        # ROS context kapaliysa publish yapma
        if not rclpy.ok():
            return

        cmd = Twist()

        cmd.linear.x = 0.0
        cmd.linear.y = 0.0
        cmd.linear.z = 0.0

        cmd.angular.x = 0.0
        cmd.angular.y = 0.0
        cmd.angular.z = 0.0

        for _ in range(3):

            if not rclpy.ok():
                break

            self.cmd_pub.publish(cmd)

    # ==============================================================
    # LINE FOLLOW
    # ==============================================================

    def follow_line(self):

        cmd = Twist()

        # ==========================================================
        # GERI
        # ==========================================================

        cmd.linear.x = -self.speed

        # ==========================================================
        # LINE YOK
        # ==========================================================

        if not self.line_detected:

            self.filtered_turn *= 0.8

            cmd.angular.z = self.filtered_turn

            self.cmd_pub.publish(cmd)

            return

        # ==========================================================
        # ERROR
        # ==========================================================

        error = self.line_error

        # ==========================================================
        # DEAD BAND
        # ==========================================================

        if abs(error) <= self.deadband:

            corrected_error = 0.0

        elif error > 0.0:

            corrected_error = (
                error - self.deadband
            )

        else:

            corrected_error = (
                error + self.deadband
            )

        # ==========================================================
        # P CONTROL
        # ==========================================================

        turn = self.gain * corrected_error

        # ==========================================================
        # INVERT
        # ==========================================================

        if self.invert:

            turn = -turn

        # ==========================================================
        # SMOOTHING
        # ==========================================================

        target_turn = (
            self.smoothing * turn
            +
            (1.0 - self.smoothing)
            * self.filtered_turn
        )

        # ==========================================================
        # RATE LIMIT
        # ==========================================================

        difference = (
            target_turn
            -
            self.filtered_turn
        )

        difference = max(
            -self.max_turn_step,
            min(
                self.max_turn_step,
                difference
            )
        )

        self.filtered_turn += difference

        # ==========================================================
        # MAX TURN
        # ==========================================================

        self.filtered_turn = max(
            -self.max_turn,
            min(
                self.max_turn,
                self.filtered_turn
            )
        )

        # ==========================================================
        # PUBLISH
        # ==========================================================

        cmd.angular.z = self.filtered_turn

        self.cmd_pub.publish(cmd)

    # ==============================================================
    # ROTATION
    # ==============================================================

    def rotate_robot(self):

        delta_yaw = self.normalize_angle(
            self.yaw - self.start_yaw
        )

        rotated = abs(delta_yaw)

        remaining = (
            self.rotate_angle
            -
            rotated
        )

        # ==========================================================
        # FINISHED
        # ==============================================================

        if remaining <= self.rotate_tolerance:

            self.stop_robot()

            self.state = "DONE"

            self.get_logger().info(
                "================================================"
            )

            self.get_logger().info(
                "DONUS TAMAMLANDI"
            )

            self.get_logger().info(
                f"Donulen aci : "
                f"{math.degrees(rotated):.1f} deg"
            )

            self.get_logger().info(
                "TEST TAMAMLANDI"
            )

            self.get_logger().info(
                "================================================"
            )

            return

        # ==========================================================
        # ROTATION SPEED
        # ==========================================================

        if remaining > self.rotate_slow_angle:

            angular_speed = self.rotate_speed

        else:

            ratio = (
                remaining
                /
                self.rotate_slow_angle
            )

            angular_speed = (
                self.rotate_min_speed
                +
                (
                    self.rotate_speed
                    -
                    self.rotate_min_speed
                )
                *
                ratio
            )

        # ==========================================================
        # PUBLISH
        # ==========================================================

        cmd = Twist()

        cmd.linear.x = 0.0
        cmd.angular.z = angular_speed

        self.cmd_pub.publish(cmd)

        # ==========================================================
        # ROTATION LOG
        # ==========================================================

        if (
            rotated
            -
            self.last_rotation_log
            >=
            self.rotation_log_step
        ):

            self.last_rotation_log = rotated

            self.get_logger().info(
                f"DON | "
                f"{math.degrees(rotated):.0f} / "
                f"{math.degrees(self.rotate_angle):.0f} deg | "
                f"kalan="
                f"{math.degrees(remaining):.0f} deg | "
                f"speed="
                f"{angular_speed:.3f}"
            )

    # ==============================================================
    # MAIN CONTROL LOOP
    # ==============================================================

    def control_loop(self):

        # ==========================================================
        # ODOM YOK
        # ==========================================================

        if (
            self.x is None
            or self.y is None
            or self.yaw is None
        ):

            # Her saniye bilgi ver
            now = self.get_clock().now()

            if (
                now - self.last_debug_time
            ).nanoseconds >= 1_000_000_000:

                self.last_debug_time = now

                self.get_logger().warn(
                    "ODOM YOK - /odom_raw bekleniyor..."
                )

            return

        # ==========================================================
        # WAIT
        # ==========================================================

        if self.state == "WAIT_ODOM":

            self.start_x = self.x
            self.start_y = self.y

            self.state = "GERI_HAT"

            self.last_distance_log = 0.0

            self.last_debug_time = (
                self.get_clock().now()
            )

            self.get_logger().info(
                "ODOM HAZIR"
            )

            self.get_logger().info(
                f"START X = {self.start_x:.3f}"
            )

            self.get_logger().info(
                f"START Y = {self.start_y:.3f}"
            )

            self.get_logger().info(
                "GERI HAT TAKIBI BASLADI"
            )

            return

        # ==========================================================
        # GERI
        # ==========================================================

        if self.state == "GERI_HAT":

            # ======================================================
            # DISTANCE
            # ======================================================

            dx = self.x - self.start_x
            dy = self.y - self.start_y

            distance = math.hypot(
                dx,
                dy
            )

            remaining = max(
                0.0,
                self.reverse_distance
                -
                distance
            )

            # ======================================================
            # HER 10 CM LOG
            # ======================================================

            if (
                distance
                -
                self.last_distance_log
                >=
                self.distance_log_step
            ):

                self.last_distance_log = distance

                self.get_logger().info(
                    f"GERI | "
                    f"mesafe={distance:.3f} m / "
                    f"{self.reverse_distance:.2f} m | "
                    f"kalan={remaining:.3f} m | "
                    f"X={self.x:.3f} | "
                    f"Y={self.y:.3f} | "
                    f"error={self.line_error:.1f} | "
                    f"turn={self.filtered_turn:.3f}"
                )

            # ======================================================
            # HER 1 SANIYE DEBUG
            #
            # Bu kisim cok onemli.
            #
            # Robot hareket etmese bile log basar.
            # ======================================================

            now = self.get_clock().now()

            if (
                now - self.last_debug_time
            ).nanoseconds >= 1_000_000_000:

                self.last_debug_time = now

                self.get_logger().info(
                    f"DEBUG | "
                    f"distance={distance:.3f} m | "
                    f"X={self.x:.3f} | "
                    f"Y={self.y:.3f} | "
                    f"line={self.line_detected} | "
                    f"error={self.line_error:.1f} | "
                    f"turn={self.filtered_turn:.3f}"
                )

            # ======================================================
            # 1 METRE TAMAMLANDI
            # ======================================================

            if distance >= self.reverse_distance:

                self.stop_robot()

                self.get_logger().info(
                    "================================================"
                )

                self.get_logger().info(
                    "GERI HAREKET TAMAMLANDI"
                )

                self.get_logger().info(
                    f"TOPLAM MESAFE = "
                    f"{distance:.3f} m"
                )

                # ==================================================
                # START YAW
                # ==================================================

                self.start_yaw = self.yaw

                self.last_rotation_log = 0.0

                self.state = "DON_180"

                self.get_logger().info(
                    f"START YAW = "
                    f"{math.degrees(self.start_yaw):.2f} deg"
                )

                self.get_logger().info(
                    "180 DERECE SOLA DONUS BASLIYOR"
                )

                self.get_logger().info(
                    "================================================"
                )

                return

            # ======================================================
            # LINE FOLLOW
            # ======================================================

            self.follow_line()

            return

        # ==========================================================
        # ROTATE
        # ==========================================================

        if self.state == "DON_180":

            self.rotate_robot()

            return

        # ==========================================================
        # DONE
        # ==========================================================

        if self.state == "DONE":

            self.stop_robot()

            return

    # ==============================================================
    # DESTROY
    # ==============================================================

    def destroy_node(self):

        if rclpy.ok():

            self.stop_robot()

        super().destroy_node()


# ==================================================================
# MAIN
# ==================================================================

def main(args=None):

    rclpy.init(args=args)

    node = GeriHatTest()

    try:

        rclpy.spin(node)

    except KeyboardInterrupt:

        # Ctrl+C burada sadece log veriyor.
        # stop finally icinde yapilacak.
        pass

    finally:

        # Context hala aciksa STOP gonder
        if rclpy.ok():

            node.stop_robot()

        node.destroy_node()

        if rclpy.ok():

            rclpy.shutdown()


if __name__ == "__main__":

    main()
