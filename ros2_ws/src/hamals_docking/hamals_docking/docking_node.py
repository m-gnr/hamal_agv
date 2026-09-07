#!/usr/bin/env python3

from __future__ import annotations

import math
import threading
import time

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import Bool, Float32, Int32, String

from hamals_interfaces.action import Dock
from hamals_interfaces.msg import QrDetection  # yous: /qr/detection (x, yaw, conf)


class DockingNode(Node):

    def __init__(self):
        super().__init__("hamals_docking")

        # ============================================================
        # PARAMETERS
        # ============================================================

        self.declare_parameter("speed_mps", 0.10)

        self.declare_parameter("line_gain", 0.0015)
        self.declare_parameter("line_deadband_px", 18.0)
        self.declare_parameter("line_smoothing", 0.35)
        self.declare_parameter("line_max_turn", 0.20)
        self.declare_parameter("line_invert", False)

        self.declare_parameter("line_lost_sec", 0.75)

        self.declare_parameter("timeout_sec", 60.0)

        self.declare_parameter("qr_wait_sec", 3.0)

        # Maximum age of the latest /proximity/alive message.
        # Prevents a stale True from being accepted if the proximity node stops.
        self.declare_parameter("proximity_alive_timeout_sec", 0.5)

        # Distance gate for MZ80 arming. The distance is integrated from
        # encoder-derived forward velocity on the configured odometry topic.
        self.declare_parameter("proximity_arm_distance_m", 0.50)
        self.declare_parameter("proximity_odom_topic", "/odom_raw")
        self.declare_parameter("proximity_odom_timeout_sec", 0.5)
        self.declare_parameter("proximity_enable_refresh_sec", 0.2)

        # Dropoff completes by encoder-derived travelled distance.
        # MZ80 stays disabled for the entire dropoff docking operation.
        self.declare_parameter("dropoff_line_distance_m", 1.50)

        # QR SEARCH
        self.declare_parameter(
            "max_search_attempts",
            3
        )

        self.declare_parameter(
            "search_timeout_sec",
            12.0
        )

        self.declare_parameter(
            "search_angular_speed",
            0.18
        )

        self.declare_parameter(
            "search_angles_deg",
            [
                60.0,
                -120.0,
                120.0,
                -120.0,
                120.0,
            ]
        )

        # yous: VISUAL SERVO - /qr/detection.x ile QR'a dogru donerek ortala
        self.declare_parameter("vs_enabled", True)       # false -> sadece donerek arama
        self.declare_parameter("vs_kp", 1.2)             # rad/s her metre yanal
        self.declare_parameter("vs_max_turn", 0.35)      # rad/s tavan
        self.declare_parameter("vs_center_tol_m", 0.04)  # |x|<tol -> ortalanmis
        self.declare_parameter("vs_min_confidence", 0.15)
        self.declare_parameter("vs_invert", False)       # ters donerse true yap
        self.declare_parameter("vs_creep_mps", 0.0)      # servo sirasinda ileri (ops.)
        self.declare_parameter("vs_lost_sec", 1.0)       # tespit kaybi -> taramaya don
        self.declare_parameter("vs_center_timeout_sec", 6.0)
        self.declare_parameter("detection_fresh_sec", 0.4)

        # ============================================================
        # STATE
        # ============================================================

        self.qr_detected = False
        self.qr_text = ""

        # yous: /qr/detection son mesaji + tazelik zamani
        self.qr_det = None
        self.qr_det_time = 0.0

        self.line_detected = False
        self.line_error = 0.0
        self.line_last_seen = time.monotonic()

        self.proximity_detected = False
        self.proximity_alive = False
        self.proximity_alive_last_seen = None

        self.proximity_odom_linear_x = 0.0
        self.proximity_odom_last_seen = None

        self.action_running = False

        self.lock = threading.RLock()

        # ============================================================
        # CALLBACK GROUP
        # ============================================================

        self.callback_group = ReentrantCallbackGroup()

        # ============================================================
        # PUBLISHER
        # ============================================================

        self.cmd_pub = self.create_publisher(
            Twist,
            "/cmd_vel/docking",
            10,
        )

        self.proximity_enable_pub = self.create_publisher(
            Bool,
            "/proximity/enable",
            10,
        )

        # ============================================================
        # QR
        # ============================================================

        self.create_subscription(
            Bool,
            "/qr/detected",
            self.qr_detected_callback,
            10,
            callback_group=self.callback_group,
        )

        self.create_subscription(
            String,
            "/qr/text",
            self.qr_text_callback,
            10,
            callback_group=self.callback_group,
        )

        # yous: QR goreli konum/aci (visual servo icin)
        self.create_subscription(
            QrDetection,
            "/qr/detection",
            self.qr_detection_callback,
            10,
            callback_group=self.callback_group,
        )

        # ============================================================
        # LINE
        # ============================================================

        self.create_subscription(
            Bool,
            "/line/detected",
            self.line_detected_callback,
            10,
            callback_group=self.callback_group,
        )

        self.create_subscription(
            Int32,
            "/line/error",
            self.line_error_callback,
            10,
            callback_group=self.callback_group,
        )

        # ============================================================
        # PROXIMITY
        # ============================================================

        self.create_subscription(
            Bool,
            "/proximity/detected",
            self.proximity_detected_callback,
            10,
            callback_group=self.callback_group,
        )

        self.create_subscription(
            Bool,
            "/proximity/alive",
            self.proximity_alive_callback,
            10,
            callback_group=self.callback_group,
        )

        self.create_subscription(
            Odometry,
            str(self.get_parameter("proximity_odom_topic").value),
            self.proximity_odom_callback,
            10,
            callback_group=self.callback_group,
        )

        # ============================================================
        # ACTION SERVER
        # ============================================================

        self.action_server = ActionServer(
            self,
            Dock,
            "/dock",
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=self.callback_group,
        )

        self.get_logger().info(
            "================================================"
        )
        self.get_logger().info(
            "HAMALS DOCKING STARTED"
        )
        self.get_logger().info(
            "QR SEARCH + LINE FOLLOWING"
        )
        self.get_logger().info(
            "PICKUP SUCCESS = PROXIMITY | DROPOFF SUCCESS = DISTANCE"
        )
        self.get_logger().info(
            "================================================"
        )

    # ================================================================
    # GOAL CALLBACK
    # ================================================================

    def goal_callback(self, goal_request):

        with self.lock:

            if self.action_running:

                self.get_logger().warning(
                    "DOCK GOAL REJECTED: "
                    "another docking action is running"
                )

                return GoalResponse.REJECT

            self.action_running = True

        self.get_logger().info(
            f"DOCK GOAL RECEIVED | "
            f"station={goal_request.station_id} | "
            f"operation={goal_request.operation} | "
            f"QR={goal_request.expected_qr}"
        )

        return GoalResponse.ACCEPT

    # ================================================================
    # CANCEL
    # ================================================================

    def cancel_callback(self, goal_handle):

        self.get_logger().warning(
            "DOCK CANCEL REQUESTED"
        )

        return CancelResponse.ACCEPT

    # ================================================================
    # QR DETECTED
    # ================================================================

    def qr_detected_callback(self, msg):

        with self.lock:

            self.qr_detected = bool(msg.data)

    # ================================================================
    # QR TEXT
    # ================================================================

    def qr_text_callback(self, msg):

        with self.lock:

            self.qr_text = msg.data.strip()

    # yous: /qr/detection callback
    def qr_detection_callback(self, msg):

        with self.lock:

            self.qr_det = msg

            if msg.detected:

                self.qr_det_time = time.monotonic()

    # ================================================================
    # LINE DETECTED
    # ================================================================

    def line_detected_callback(self, msg):

        with self.lock:

            self.line_detected = bool(msg.data)

            if self.line_detected:

                self.line_last_seen = time.monotonic()

    # ================================================================
    # LINE ERROR
    # ================================================================

    def line_error_callback(self, msg):

        with self.lock:

            self.line_error = float(msg.data)

    # ================================================================
    # PROXIMITY
    # ================================================================

    def proximity_detected_callback(self, msg):

        with self.lock:

            self.proximity_detected = bool(msg.data)

    def proximity_alive_callback(self, msg):

        with self.lock:

            self.proximity_alive = bool(msg.data)
            self.proximity_alive_last_seen = time.monotonic()

    def proximity_odom_callback(self, msg):

        with self.lock:

            self.proximity_odom_linear_x = float(
                msg.twist.twist.linear.x
            )
            self.proximity_odom_last_seen = time.monotonic()

    def set_proximity_enabled(self, enabled):

        msg = Bool()
        msg.data = bool(enabled)

        self.proximity_enable_pub.publish(msg)

    # ================================================================
    # STOP
    # ================================================================

    def stop_robot(self):

        cmd = Twist()

        for _ in range(5):

            self.cmd_pub.publish(cmd)

            time.sleep(0.02)

    # ================================================================
    # RESET SENSORS
    # ================================================================

    def reset_runtime_state(self):

        with self.lock:

            self.qr_detected = False
            self.qr_text = ""

            self.line_detected = False
            self.line_error = 0.0
            self.line_last_seen = time.monotonic()

            self.proximity_detected = False

    # ================================================================
    # QR CHECK
    # ================================================================

    def qr_is_correct(self, expected_qr):

        with self.lock:

            if not self.qr_detected:
                return False

            detected_text = self.qr_text.strip()
            expected_text = expected_qr.strip()

            if not detected_text:
                return False

            return detected_text == expected_text

    # ================================================================
    # FIND QR  (yous)
    # Her QR yaklasmasinda cagrilir. Once pasif izleme + gorulurse
    # visual servo (akilli), sonra donerek arama (yedek).
    # DONER: (found: bool, qr_data: str)
    # ================================================================

    def _qr_text_now(self):
        with self.lock:
            return self.qr_text

    def _detection_fresh(self):
        with self.lock:
            det = self.qr_det
            t = self.qr_det_time
        if det is None or not det.detected:
            return False
        if time.monotonic() - t > float(
                self.get_parameter("detection_fresh_sec").value):
            return False
        return float(det.confidence) >= float(
            self.get_parameter("vs_min_confidence").value)

    def _visual_servo(self, goal_handle, expected_qr):
        # QR'a dogru donerek ortala. found+ortalanmis -> True
        kp = float(self.get_parameter("vs_kp").value)
        max_turn = float(self.get_parameter("vs_max_turn").value)
        tol = float(self.get_parameter("vs_center_tol_m").value)
        creep = float(self.get_parameter("vs_creep_mps").value)
        invert = bool(self.get_parameter("vs_invert").value)
        lost = float(self.get_parameter("vs_lost_sec").value)
        vs_to = float(self.get_parameter("vs_center_timeout_sec").value)

        self.get_logger().info("VISUAL SERVO | centering QR")
        t_end = time.monotonic() + vs_to
        last_seen = time.monotonic()

        while rclpy.ok():
            if goal_handle.is_cancel_requested:
                self.stop_robot()
                return False
            if time.monotonic() > t_end:
                self.stop_robot()
                return False

            if self._detection_fresh():
                last_seen = time.monotonic()
                with self.lock:
                    lateral = float(self.qr_det.x)  # metre, kamera cercevesi
                if self.qr_is_correct(expected_qr) and abs(lateral) <= tol:
                    self.stop_robot()
                    return True
                turn = -kp * lateral       # x>0 (sagda) -> saga don
                if invert:
                    turn = -turn
                turn = max(-max_turn, min(max_turn, turn))
                cmd = Twist()
                cmd.linear.x = creep
                cmd.angular.z = turn
                self.cmd_pub.publish(cmd)
            else:
                if time.monotonic() - last_seen > lost:
                    self.stop_robot()
                    return False
                self.cmd_pub.publish(Twist())

            time.sleep(0.03)

        return False

    def find_qr(self, goal_handle, expected_qr):
        vs_on = bool(self.get_parameter("vs_enabled").value)

        self.get_logger().info(
            f"FIND QR | expected={expected_qr} | vs={vs_on}")

        # zaten dogru gorunuyorsa
        if self.qr_is_correct(expected_qr):
            return True, self._qr_text_now()

        # 1) pasif izleme (Nav2 paralel) + gorulurse visual servo
        wait = float(self.get_parameter("qr_wait_sec").value)
        end = time.monotonic() + wait
        while rclpy.ok() and time.monotonic() < end:
            if goal_handle.is_cancel_requested:
                self.stop_robot()
                return False, self._qr_text_now()
            if self.qr_is_correct(expected_qr):
                return True, self._qr_text_now()
            if vs_on and self._detection_fresh():
                if self._visual_servo(goal_handle, expected_qr):
                    return True, self._qr_text_now()
                break  # servo bitti/kayip -> donerek aramaya gec
            time.sleep(0.03)

        # 2) donerek arama (mevcut search_qr, kor durum yedegi)
        ok, _msg = self.search_qr(goal_handle, expected_qr)
        return bool(ok), self._qr_text_now()

    # ================================================================
    # WAIT FOR QR
    # ================================================================

    def wait_for_qr(
        self,
        goal_handle,
        expected_qr,
    ):

        wait_sec = float(
            self.get_parameter(
                "qr_wait_sec"
            ).value
        )

        self.get_logger().info(
            "================================================"
        )

        self.get_logger().info(
            f"QR INITIAL SEARCH | "
            f"expected={expected_qr}"
        )

        self.get_logger().info(
            f"waiting={wait_sec:.2f}s"
        )

        self.get_logger().info(
            "================================================"
        )

        start = time.monotonic()

        while rclpy.ok():

            if goal_handle.is_cancel_requested:

                self.stop_robot()

                return False, "cancelled"

            if self.qr_is_correct(expected_qr):

                self.get_logger().info(
                    f"QR FOUND | {expected_qr}"
                )

                return True, "QR confirmed"

            if (
                time.monotonic()
                - start
                >= wait_sec
            ):

                return False, "QR not found"

            time.sleep(0.03)

        return False, "ROS shutdown"

    # ================================================================
    # ROTATION
    # ================================================================

    def rotate_relative(
        self,
        goal_handle,
        angle_deg,
    ):

        angular_speed = float(
            self.get_parameter(
                "search_angular_speed"
            ).value
        )

        if angular_speed <= 0.0:

            return False, "invalid search angular speed"

        angle_rad = math.radians(
            abs(angle_deg)
        )

        direction = (
            1.0
            if angle_deg > 0.0
            else -1.0
        )

        duration = (
            angle_rad
            / angular_speed
        )

        self.get_logger().info(
            f"QR SEARCH ROTATION | "
            f"{angle_deg:.1f} deg | "
            f"{duration:.2f}s"
        )

        start = time.monotonic()

        while rclpy.ok():

            if goal_handle.is_cancel_requested:

                self.stop_robot()

                return False, "cancelled"

            if (
                time.monotonic()
                - start
                >= duration
            ):

                self.stop_robot()

                return True, "rotation completed"

            if self.qr_is_correct(
                self._search_expected_qr
            ):

                self.stop_robot()

                return True, "QR found during rotation"

            cmd = Twist()

            cmd.linear.x = 0.0

            cmd.angular.z = (
                direction
                * angular_speed
            )

            self.cmd_pub.publish(cmd)

            time.sleep(0.02)

        self.stop_robot()

        return False, "ROS shutdown"

    # ================================================================
    # SEARCH QR
    # ================================================================

    def search_qr(
        self,
        goal_handle,
        expected_qr,
    ):

        self._search_expected_qr = expected_qr

        max_attempts = int(
            self.get_parameter(
                "max_search_attempts"
            ).value
        )

        search_timeout = float(
            self.get_parameter(
                "search_timeout_sec"
            ).value
        )

        angles = list(
            self.get_parameter(
                "search_angles_deg"
            ).value
        )

        self.get_logger().info(
            "================================================"
        )

        self.get_logger().info(
            f"QR SEARCH START | "
            f"expected={expected_qr}"
        )

        self.get_logger().info(
            f"attempts={max_attempts}"
        )

        self.get_logger().info(
            f"angles={angles}"
        )

        self.get_logger().info(
            "================================================"
        )

        search_start = time.monotonic()

        for attempt in range(
            1,
            max_attempts + 1,
        ):

            self.get_logger().info(
                f"QR SEARCH ATTEMPT "
                f"{attempt}/{max_attempts}"
            )

            # --------------------------------------------------------
            # Check before rotating
            # --------------------------------------------------------

            if self.qr_is_correct(
                expected_qr
            ):

                self.stop_robot()

                return True, "QR found"

            # --------------------------------------------------------
            # Search pattern
            # --------------------------------------------------------

            for angle in angles:

                if goal_handle.is_cancel_requested:

                    self.stop_robot()

                    return False, "cancelled"

                if (
                    time.monotonic()
                    - search_start
                    > search_timeout
                ):

                    self.stop_robot()

                    self.get_logger().warning(
                        "QR SEARCH TIMEOUT"
                    )

                    return False, "QR search timeout"

                if self.qr_is_correct(
                    expected_qr
                ):

                    self.stop_robot()

                    return True, "QR found"

                ok, message = (
                    self.rotate_relative(
                        goal_handle,
                        float(angle),
                    )
                )

                if not ok:

                    self.stop_robot()

                    return False, message

                if self.qr_is_correct(
                    expected_qr
                ):

                    self.stop_robot()

                    self.get_logger().info(
                        f"QR FOUND DURING SEARCH | "
                        f"{expected_qr}"
                    )

                    return True, "QR found"

            self.stop_robot()

            time.sleep(0.20)

        self.stop_robot()

        self.get_logger().warning(
            f"QR SEARCH FAILED | "
            f"expected={expected_qr}"
        )

        return False, "QR not found after search"

    # ================================================================
    # LINE FOLLOW
    # ================================================================

    def follow_line(
        self,
        goal_handle,
        operation,
    ):

        speed = float(
            self.get_parameter(
                "speed_mps"
            ).value
        )

        gain = float(
            self.get_parameter(
                "line_gain"
            ).value
        )

        deadband = float(
            self.get_parameter(
                "line_deadband_px"
            ).value
        )

        smoothing = float(
            self.get_parameter(
                "line_smoothing"
            ).value
        )

        max_turn = float(
            self.get_parameter(
                "line_max_turn"
            ).value
        )

        invert = bool(
            self.get_parameter(
                "line_invert"
            ).value
        )

        line_lost_sec = float(
            self.get_parameter(
                "line_lost_sec"
            ).value
        )

        timeout_sec = float(
            self.get_parameter(
                "timeout_sec"
            ).value
        )

        proximity_alive_timeout_sec = max(
            0.1,
            float(
                self.get_parameter(
                    "proximity_alive_timeout_sec"
                ).value
            )
        )

        proximity_arm_distance_m = max(
            0.0,
            float(
                self.get_parameter(
                    "proximity_arm_distance_m"
                ).value
            )
        )

        proximity_odom_timeout_sec = max(
            0.1,
            float(
                self.get_parameter(
                    "proximity_odom_timeout_sec"
                ).value
            )
        )

        proximity_enable_refresh_sec = max(
            0.05,
            float(
                self.get_parameter(
                    "proximity_enable_refresh_sec"
                ).value
            )
        )

        dropoff_line_distance_m = max(
            0.0,
            float(
                self.get_parameter(
                    "dropoff_line_distance_m"
                ).value
            )
        )

        is_pickup = operation == "pickup"
        is_dropoff = operation == "dropoff"

        if not is_pickup and not is_dropoff:

            self.stop_robot()
            self.set_proximity_enabled(False)

            self.get_logger().error(
                f"UNKNOWN DOCKING OPERATION | {operation}"
            )

            return False, f"unknown docking operation: {operation}"

        start_time = time.monotonic()

        filtered_turn = 0.0

        # Distance starts at the first fresh line. Both operations use the
        # encoder-derived /odom_raw linear velocity for travelled distance.
        distance_tracking = False
        travelled_distance_m = 0.0
        distance_last_time = None

        # Pickup only: MZ80 is armed after proximity_arm_distance_m.
        proximity_armed = False
        proximity_enable_last_publish = None

        with self.lock:

            self.proximity_detected = False

        # Dropoff never uses MZ80 as a docking completion source.
        self.set_proximity_enabled(False)

        self.get_logger().info(
            "================================================"
        )

        self.get_logger().info(
            f"LINE FOLLOW START | operation={operation}"
        )

        self.get_logger().info(
            f"speed={speed:.3f}"
        )

        self.get_logger().info(
            f"gain={gain:.5f}"
        )

        self.get_logger().info(
            f"max_turn={max_turn:.3f}"
        )

        if is_pickup:

            self.get_logger().info(
                "PICKUP MODE | "
                "proximity=waiting_for_arm_distance | "
                f"arm_distance={proximity_arm_distance_m:.3f}m"
            )

        else:

            self.get_logger().info(
                "DROPOFF MODE | proximity=disabled | "
                f"finish_distance={dropoff_line_distance_m:.3f}m"
            )

        self.get_logger().info(
            "================================================"
        )

        while rclpy.ok():

            # --------------------------------------------------------
            # CANCEL
            # --------------------------------------------------------

            if goal_handle.is_cancel_requested:

                self.stop_robot()
                self.set_proximity_enabled(False)

                return False, "cancelled"

            # --------------------------------------------------------
            # TIMEOUT
            # --------------------------------------------------------

            if (
                time.monotonic()
                - start_time
                > timeout_sec
            ):

                self.stop_robot()
                self.set_proximity_enabled(False)

                self.get_logger().error(
                    "LINE FOLLOW TIMEOUT"
                )

                return False, "docking timeout"

            # --------------------------------------------------------
            # STATE
            # --------------------------------------------------------

            with self.lock:

                line_detected = (
                    self.line_detected
                )

                error = self.line_error

                last_seen = (
                    self.line_last_seen
                )

                proximity_alive = (
                    self.proximity_alive
                )

                proximity_alive_last_seen = (
                    self.proximity_alive_last_seen
                )

                proximity_detected = (
                    self.proximity_detected
                )

                proximity_odom_linear_x = (
                    self.proximity_odom_linear_x
                )

                proximity_odom_last_seen = (
                    self.proximity_odom_last_seen
                )

            now = time.monotonic()

            # --------------------------------------------------------
            # LINE FRESHNESS
            # --------------------------------------------------------

            line_fresh = (
                line_detected
                and
                (
                    now
                    - last_seen
                    <= line_lost_sec
                )
            )

            # --------------------------------------------------------
            # ODOM FRESHNESS / DISTANCE TRACKING
            # --------------------------------------------------------

            odom_fresh = (
                proximity_odom_last_seen is not None
                and (
                    now
                    - proximity_odom_last_seen
                    <= proximity_odom_timeout_sec
                )
            )

            # Distance begins exactly when the first fresh line is acquired.
            if line_fresh and not distance_tracking:

                if not odom_fresh:

                    self.stop_robot()
                    self.set_proximity_enabled(False)

                    self.get_logger().error(
                        "DOCKING DISTANCE ODOM UNAVAILABLE OR STALE"
                    )

                    return False, "docking distance odom unavailable or stale"

                distance_tracking = True
                distance_last_time = now
                travelled_distance_m = 0.0

                if is_pickup:
                    target_distance_m = proximity_arm_distance_m
                    tracking_label = "PICKUP MZ80 ARM DISTANCE"
                else:
                    target_distance_m = dropoff_line_distance_m
                    tracking_label = "DROPOFF FINISH DISTANCE"

                self.get_logger().info(
                    f"{tracking_label} TRACKING STARTED | "
                    f"target={target_distance_m:.3f}m"
                )

            # After line tracking starts, distance is measured from encoder-derived
            # forward velocity. Odom must remain fresh until the relevant criterion
            # has been reached.
            distance_needed = (
                is_dropoff
                or (is_pickup and not proximity_armed)
            )

            if distance_tracking and distance_needed:

                if not odom_fresh:

                    self.stop_robot()
                    self.set_proximity_enabled(False)

                    self.get_logger().error(
                        "DOCKING DISTANCE ODOM UNAVAILABLE OR STALE"
                    )

                    return False, "docking distance odom unavailable or stale"

                dt = max(
                    0.0,
                    now - distance_last_time
                )
                distance_last_time = now

                # Reverse motion is not counted toward forward docking distance.
                forward_speed = max(
                    0.0,
                    proximity_odom_linear_x
                )

                travelled_distance_m += (
                    forward_speed * dt
                )

            # --------------------------------------------------------
            # PICKUP: MZ80 COMPLETION
            # --------------------------------------------------------

            if is_pickup:

                # Pickup requires a healthy, fresh proximity stream.
                proximity_alive_fresh = (
                    proximity_alive_last_seen is not None
                    and (
                        now
                        - proximity_alive_last_seen
                        <= proximity_alive_timeout_sec
                    )
                )

                if not proximity_alive or not proximity_alive_fresh:

                    self.stop_robot()
                    self.set_proximity_enabled(False)

                    self.get_logger().error(
                        "PROXIMITY DATA UNAVAILABLE OR STALE"
                    )

                    return False, "proximity unavailable or stale"

                # MZ80 becomes a docking decision source only after the configured
                # forward distance has been completed, and only while line is fresh.
                if (
                    distance_tracking
                    and not proximity_armed
                    and line_fresh
                    and travelled_distance_m
                    >= proximity_arm_distance_m
                ):

                    self.set_proximity_enabled(True)
                    proximity_armed = True
                    proximity_enable_last_publish = now

                    self.get_logger().info(
                        "PROXIMITY ENABLED | "
                        f"travelled={travelled_distance_m:.3f}m | "
                        f"target={proximity_arm_distance_m:.3f}m"
                    )

                # Refresh enable=True while armed so a short monitor restart or
                # missed volatile message cannot silently leave it disabled.
                if (
                    proximity_armed
                    and (
                        proximity_enable_last_publish is None
                        or now - proximity_enable_last_publish
                        >= proximity_enable_refresh_sec
                    )
                ):

                    self.set_proximity_enabled(True)
                    proximity_enable_last_publish = now

                if proximity_armed and proximity_detected:

                    self.stop_robot()
                    self.set_proximity_enabled(False)

                    self.get_logger().info(
                        "================================================"
                    )

                    self.get_logger().info(
                        "PICKUP PROXIMITY TARGET DETECTED"
                    )

                    self.get_logger().info(
                        "DOCKING SUCCESS"
                    )

                    self.get_logger().info(
                        "================================================"
                    )

                    return True, "pickup proximity detected"

            # --------------------------------------------------------
            # DROPOFF: DISTANCE COMPLETION, NO MZ80
            # --------------------------------------------------------

            else:

                # MZ80 must remain passive for the entire dropoff docking.
                # Completion depends only on encoder-derived forward travel.
                if (
                    distance_tracking
                    and travelled_distance_m
                    >= dropoff_line_distance_m
                ):

                    self.stop_robot()
                    self.set_proximity_enabled(False)

                    self.get_logger().info(
                        "================================================"
                    )

                    self.get_logger().info(
                        "DROPOFF DISTANCE REACHED | "
                        f"travelled={travelled_distance_m:.3f}m | "
                        f"target={dropoff_line_distance_m:.3f}m"
                    )

                    self.get_logger().info(
                        "DOCKING SUCCESS"
                    )

                    self.get_logger().info(
                        "================================================"
                    )

                    return True, "dropoff distance reached"

            # --------------------------------------------------------
            # LINE CONTROL
            # --------------------------------------------------------

            if line_fresh:

                if (
                    abs(error)
                    <= deadband
                ):

                    corrected_error = 0.0

                elif error > 0:

                    corrected_error = (
                        error
                        - deadband
                    )

                else:

                    corrected_error = (
                        error
                        + deadband
                    )

                turn = (
                    -gain
                    * corrected_error
                )

                if invert:

                    turn = -turn

                # Safety
                smoothing = max(
                    0.0,
                    min(
                        1.0,
                        smoothing
                    )
                )

                filtered_turn = (
                    smoothing
                    * turn
                    +
                    (1.0 - smoothing)
                    * filtered_turn
                )

            else:

                filtered_turn = 0.0

            # --------------------------------------------------------
            # TURN LIMIT
            # --------------------------------------------------------

            filtered_turn = max(
                -max_turn,
                min(
                    max_turn,
                    filtered_turn
                )
            )

            # --------------------------------------------------------
            # COMMAND
            # --------------------------------------------------------

            cmd = Twist()

            cmd.linear.x = speed

            cmd.angular.z = (
                filtered_turn
            )

            self.cmd_pub.publish(cmd)

            time.sleep(0.05)

        self.stop_robot()
        self.set_proximity_enabled(False)

        return False, "ROS shutdown"

    # ================================================================
    # EXECUTE
    # ================================================================

    def execute_callback(
        self,
        goal_handle,
    ):

        expected_qr = str(
            goal_handle.request.expected_qr
        ).strip()

        operation = str(
            goal_handle.request.operation
        ).strip().lower()

        profile = str(
            goal_handle.request.profile
        ).strip()

        try:

            self.get_logger().info(
                "================================================"
            )

            self.get_logger().info(
                "DOCK ACTION START"
            )

            self.get_logger().info(
                f"station="
                f"{goal_handle.request.station_id}"
            )

            self.get_logger().info(
                f"operation={operation}"
            )

            self.get_logger().info(
                f"expected_qr={expected_qr}"
            )

            self.get_logger().info(
                f"profile={profile}"
            )

            self.get_logger().info(
                "================================================"
            )

            # ========================================================
            # OPERATION
            # ========================================================

            if operation not in (
                "pickup",
                "dropoff",
            ):

                self.stop_robot()
                self.set_proximity_enabled(False)

                self.get_logger().error(
                    f"UNKNOWN DOCKING OPERATION | {operation}"
                )

                goal_handle.abort()

                return Dock.Result(
                    success=False,
                    message=f"unknown docking operation: {operation}",
                )

            # ========================================================
            # RESET
            # ========================================================

            self.reset_runtime_state()
            self.set_proximity_enabled(False)

            # ========================================================
            # yous: QR ARTIK DOCKING'DE YOK.
            # Mission QR'i bulur + ortalar, sonra dock'u cagirir.
            # Docking dogrudan hat takibine gecer.
            # ========================================================

            # ========================================================
            # LINE FOLLOW
            # ========================================================

            success, message = (
                self.follow_line(
                    goal_handle,
                    operation,
                )
            )

            # ========================================================
            # STOP
            # ========================================================

            self.stop_robot()

            # ========================================================
            # SUCCESS
            # ========================================================

            if success:

                self.get_logger().info(
                    "================================================"
                )

                self.get_logger().info(
                    f"DOCK SUCCESS | "
                    f"{message}"
                )

                self.get_logger().info(
                    "================================================"
                )

                goal_handle.succeed()

                return Dock.Result(
                    success=True,
                    message=message,
                )

            # ========================================================
            # CANCEL
            # ========================================================

            if goal_handle.is_cancel_requested:

                goal_handle.canceled()

                return Dock.Result(
                    success=False,
                    message="cancelled",
                )

            # ========================================================
            # FAILURE
            # ========================================================

            self.get_logger().error(
                f"DOCK FAILURE | "
                f"{message}"
            )

            goal_handle.abort()

            return Dock.Result(
                success=False,
                message=message,
            )

        except Exception as exc:

            self.stop_robot()
            self.set_proximity_enabled(False)

            self.get_logger().error(
                f"DOCKING EXCEPTION: {exc}"
            )

            if goal_handle.is_cancel_requested:

                goal_handle.canceled()

                return Dock.Result(
                    success=False,
                    message="cancelled",
                )

            goal_handle.abort()

            return Dock.Result(
                success=False,
                message=str(exc),
            )

        finally:

            self.stop_robot()
            self.set_proximity_enabled(False)

            with self.lock:

                self.action_running = False

                self.qr_detected = False
                self.qr_text = ""

                self.proximity_detected = False

    # ================================================================
    # DESTROY
    # ================================================================

    def destroy_node(self):

        self.stop_robot()
        self.set_proximity_enabled(False)

        super().destroy_node()


# ====================================================================
# MAIN
# ====================================================================

def main(args=None):

    rclpy.init(args=args)

    node = DockingNode()

    executor = MultiThreadedExecutor(
        num_threads=4
    )

    executor.add_node(node)

    try:

        executor.spin()

    except KeyboardInterrupt:

        pass

    finally:

        node.stop_robot()

        executor.shutdown()

        node.destroy_node()

        if rclpy.ok():

            rclpy.shutdown()


if __name__ == "__main__":
    main()
