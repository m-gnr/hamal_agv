
#!/usr/bin/env python3

from __future__ import annotations

import threading
import time

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry  # yous: pickup 12cm nudge icin
from std_msgs.msg import Bool, Int32

from hamals_interfaces.action import Dock


class DockingNode(Node):
    """HAMAL docking - cizgi takibi + yuk (MZ80).

    /dock beklenir, bosta hicbir cmd yayinlanmaz.
      - pickup : cizgiyi takip et -> MZ80 hedefi gorunce DUR -> succeed.
                 yous: cizgi biter ve MZ80 GELMEZSE -> odometri ile 12cm
                 ilerle -> DUR -> succeed.
      - dropoff: cizgiyi takip et -> cizgi bitince (kaybolunca) DUR -> succeed.
    Dropoff'un mesafe/donus/yuk-birakma kismi MISSION katmaninda yapilir.
    """

    def __init__(self):
        super().__init__("hamals_docking")

        # Line follow (kucuk calisan script ile AYNI degerler)

        
        self.speed = 0.06
        self.gain = 0.045
        self.deadband = 6.0
        self.smoothing = 0.35
        self.max_turn = 0.30
        self.invert = True
        self.line_lost_sec = 5.0
        # Extra smoothing / angular acceleration limit
        self.max_turn_step = 0.04

        # pickup icin MZ80; dropoff cizgi bitince biter.
        self.pickup_arm_time_s = 2.0
        self.dropoff_lost_grace_s = 1.0
        self.timeout_sec = 120.0

        # : pickup - cizgi bitince MZ80 yoksa odometri ile ilerle
        self.pickup_nudge_distance_m = 0.12
        self.pickup_nudge_speed = 0.08
        self.odom_timeout_sec = 0.5

        # ==================================================
        # DROPOFF / GERI HAT TAKIBI + 180 DERECE DONUS
        # Bu degerler basarili geri hat testindeki ayarlardir.
        # ==================================================
        self.dropoff_follow_distance_m = 1.0 # 
        self.dropoff_follow_speed = 0.10
        self.dropoff_turn_speed = 0.25
        self.dropoff_line_invert = True
        self.dropoff_timeout_sec = 60.0
        self.dropoff_turn_timeout_sec = 60.0

        # MZ80
        self.mz80_active_low = False

        # =========================
        # STATE
        # =========================
        self.lock = threading.RLock()
        self.action_running = False
        self.active = False

        self.line_detected = False
        self.error = 0.0
        self.line_last_seen = 0.0

        self.mz80_detected = False
        self.mz80_armed = False

        self.filtered_turn = 0.0

        # : odometri
        # Pickup 12cm nudge hiz kontrolunde kullanilir.
        # Dropoff geri hareket mesafesi ve 180 derece donus de burada takip edilir.
        self.odom_linear_x = 0.0
        self.odom_angular_z = 0.0
        self.odom_x = 0.0
        self.odom_y = 0.0
        self.odom_last_seen = None

        self.cb_group = ReentrantCallbackGroup()

        self.cmd_pub = self.create_publisher(
            Twist, "/cmd_vel/docking", 10
        )

        self.create_subscription(
            Bool, "/line/detected",
            self.line_detected_callback, 10,
            callback_group=self.cb_group,
        )
        self.create_subscription(
            Int32, "/line/error",
            self.line_error_callback, 10,
            callback_group=self.cb_group,
        )
        self.create_subscription(
            Bool, "/proximity/raw",
            self.mz80_callback, 10,
            callback_group=self.cb_group,
        )
        self.create_subscription(
            Odometry, "/odom",
            self.odom_callback, 10,
            callback_group=self.cb_group,
        )

        self.action_server = ActionServer(
            self,
            Dock,
            "/dock",
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=self.cb_group,
        )

        self.get_logger().info(
            "DOCKING READY | waits for /dock | LINE FOLLOW + MZ80 "
            "| pickup 12cm nudge (odom)"
        )

    # ==================================================
    # ACTION CALLBACKS
    # ==================================================

    def goal_callback(self, goal_request):
        with self.lock:
            if self.action_running:
                self.get_logger().warning("DOCK REJECTED: already running")
                return GoalResponse.REJECT
            self.action_running = True

        self.get_logger().info(
            f"DOCK GOAL | station={goal_request.station_id} | "
            f"operation={goal_request.operation}"
        )
        return GoalResponse.ACCEPT

    def cancel_callback(self, goal_handle):
        self.get_logger().warning("DOCK CANCEL REQUESTED")
        return CancelResponse.ACCEPT

    # ==================================================
    # SENSOR CALLBACKS
    # ==================================================

    def line_detected_callback(self, msg):
        with self.lock:
            self.line_detected = bool(msg.data)
            if self.line_detected:
                self.line_last_seen = time.monotonic()

    def line_error_callback(self, msg):
        with self.lock:
            self.error = float(msg.data)

    def mz80_callback(self, msg):
        raw = bool(msg.data)
        detected = (not raw) if self.mz80_active_low else raw
        with self.lock:
            self.mz80_detected = detected and self.mz80_armed

    def odom_callback(self, msg):
        # Odometry:
        # - pickup nudge icin linear.x
        # - dropoff geri mesafe icin x/y
        # - dropoff 180 derece donus icin angular.z
        with self.lock:
            self.odom_linear_x = float(msg.twist.twist.linear.x)
            self.odom_angular_z = float(msg.twist.twist.angular.z)
            self.odom_x = float(msg.pose.pose.position.x)
            self.odom_y = float(msg.pose.pose.position.y)
            self.odom_last_seen = time.monotonic()

    # ==================================================
    # STOP
    # ==================================================

    def stop_robot(self):
        cmd = Twist()
        for _ in range(3):
            self.cmd_pub.publish(cmd)
            time.sleep(0.02)

    # ==================================================
    # yous: pickup - odometri ile duz ilerle (12cm), sonra dur
    # ==================================================

    def drive_forward_odom(self, goal_handle, distance_m, speed):
        with self.lock:
            odom_seen = self.odom_last_seen
        if odom_seen is None:
            self.get_logger().error("NUDGE ABORT | odom yok")
            return False

        travelled = 0.0
        last_t = time.monotonic()
        deadline = time.monotonic() + 8.0
        self.get_logger().info(f"PICKUP NUDGE | {distance_m:.2f} m (odom)")

        while rclpy.ok() and time.monotonic() < deadline:
            if goal_handle.is_cancel_requested:
                self.stop_robot()
                return False

            now = time.monotonic()
            with self.lock:
                vx = self.odom_linear_x
                odom_last = self.odom_last_seen

            if odom_last is None or now - odom_last > self.odom_timeout_sec:
                self.stop_robot()
                self.get_logger().error("NUDGE ABORT | odom bayat")
                return False

            dt = max(0.0, now - last_t)
            last_t = now
            travelled += max(0.0, vx) * dt

            if travelled >= distance_m:
                break

            cmd = Twist()
            cmd.linear.x = speed
            self.cmd_pub.publish(cmd)
            time.sleep(0.05)

        self.stop_robot()
        self.get_logger().info(f"PICKUP NUDGE DONE | {travelled:.2f} m")
        return True

    # ==================================================
    # DROPOFF GERI HAT TAKIBI
    # ==================================================

    def follow_reverse_line(self, goal_handle):
        # ==================================================
        # GERI HAT SARTLARI
        # ==================================================
        # 1) Arka kamera ile cizgiyi takip et.
        # 2) Robot linear.x NEGATIF olacak.
        # 3) Mesafe /odom pozisyonundan hesaplanir.
        # 4) 100 cm tamamlaninca robot DURUR.
        # 5) Sonra ayni /odom kullanilarak 180 derece SOLA doner.
        # 6) Basarili geri testte kullanilan smooth ayarlari korunur:
        #    gain=0.050, deadband=18, smoothing=0.35,
        #    max_turn=0.45, max_turn_step=0.04, invert=True.
        with self.lock:
            start_x = self.odom_x
            start_y = self.odom_y
            self.filtered_turn = 0.0
            self.active = True

        start_time = time.monotonic()
        last_log = start_time

        self.get_logger().info("DROPOFF GERI HAT TAKIBI BASLADI")
        self.get_logger().info(
            f"HEDEF MESAFE: {self.dropoff_follow_distance_m:.2f} m"
        )

        try:
            while rclpy.ok():
                if goal_handle.is_cancel_requested:
                    self.stop_robot()
                    return False, "cancelled"

                now = time.monotonic()

                if now - start_time > self.dropoff_timeout_sec:
                    self.stop_robot()
                    self.get_logger().error("DROPOFF GERI HAT TIMEOUT")
                    return False, "reverse line follow timeout"

                with self.lock:
                    line_detected = self.line_detected
                    error = self.error
                    line_last_seen = self.line_last_seen
                    x = self.odom_x
                    y = self.odom_y
                    odom_last = self.odom_last_seen

                if odom_last is None or now - odom_last > self.odom_timeout_sec:
                    self.stop_robot()
                    self.get_logger().error("DROPOFF ABORT | odom bayat")
                    return False, "odometry unavailable"

                # Baslangictan olan gercek x/y displacement.
                distance = ((x - start_x) ** 2 + (y - start_y) ** 2) ** 0.5

                # 100 cm tamamlandiysa dur ve basarili don.
                if distance >= self.dropoff_follow_distance_m:
                    self.stop_robot()
                    self.get_logger().info(
                        "========================================"
                    )
                    self.get_logger().info("DROPOFF GERI HAREKET TAMAMLANDI")
                    self.get_logger().info(
                        f"TOPLAM MESAFE = {distance:.3f} m"
                    )
                    return True, "dropoff reverse line distance complete"

                line_fresh = (
                    line_detected
                    and now - line_last_seen <= self.line_lost_sec
                )

                # ==================================================
                # GERI HAT LINE CONTROLLER
                # Front controller ile ayni mantik + rate limit.
                # Sadece linear.x negatiftir ve invert bagimsizdir.
                # ==================================================
                if line_fresh:
                    if abs(error) <= self.deadband:
                        corrected_error = 0.0
                    elif error > 0.0:
                        corrected_error = error - self.deadband
                    else:
                        corrected_error = error + self.deadband

                    turn = self.gain * corrected_error

                    if self.dropoff_line_invert:
                        turn = -turn

                    # Ilk smoothing
                    target_turn = (
                        self.smoothing * turn
                        + (1.0 - self.smoothing) * self.filtered_turn
                    )

                    # Extra rate limit: ani saga/sola kirma engellenir.
                    turn_difference = target_turn - self.filtered_turn
                    turn_difference = max(
                        -self.max_turn_step,
                        min(self.max_turn_step, turn_difference),
                    )
                    self.filtered_turn += turn_difference
                else:
                    # Cizgi gecici olarak kaybolursa direksiyonu sifirla.
                    self.filtered_turn = 0.0

                self.filtered_turn = max(
                    -self.max_turn,
                    min(self.max_turn, self.filtered_turn)
                )

                cmd = Twist()
                if line_fresh:
                    cmd.linear.x = -abs(self.dropoff_follow_speed)
                    cmd.angular.z = self.filtered_turn
                else:
                    # Cizgi kayipsa ileri/geri hareket etme.
                    cmd.linear.x = 0.0
                    cmd.angular.z = 0.0

                self.cmd_pub.publish(cmd)

                if now - last_log >= 1.0:
                    self.get_logger().info(
                        f"GERI DEBUG | distance={distance:.3f} m | "
                        f"X={x:.3f} | Y={y:.3f} | "
                        f"line={line_fresh} | error={error:.1f} | "
                        f"turn={self.filtered_turn:.3f}"
                    )
                    last_log = now

                time.sleep(0.05)

            self.stop_robot()
            return False, "ROS shutdown"

        finally:
            with self.lock:
                self.active = False
            self.stop_robot()

    def rotate_dropoff_180(self, goal_handle):
        # ==================================================
        # DROPOFF DONUS SARTI
        # Geri hat tamamlandiktan sonra yerinde 180 derece SOLA don.
        # Aci /odom angular.z uzerinden olculur.
        # ==================================================
        with self.lock:
            start_angular_z = self.odom_angular_z
            self.odom_start_yaw = None

        # Baslangic yaw'i quaternion'dan okumak yerine,
        # /odom angular.z integrasyonu ile aciyi olcuyoruz.
        total_angle = 0.0
        last_t = time.monotonic()
        start_time = last_t
        last_log_deg = 0

        self.get_logger().info("180 DERECE SOLA DONUS BASLIYOR")

        try:
            while rclpy.ok():
                if goal_handle.is_cancel_requested:
                    self.stop_robot()
                    return False, "cancelled"

                now = time.monotonic()

                if now - start_time > self.dropoff_turn_timeout_sec:
                    self.stop_robot()
                    self.get_logger().error("DROPOFF DONUS TIMEOUT")
                    return False, "180 degree turn timeout"

                with self.lock:
                    angular_z = self.odom_angular_z
                    odom_last = self.odom_last_seen

                if odom_last is None or now - odom_last > self.odom_timeout_sec:
                    self.stop_robot()
                    self.get_logger().error("DONUS ABORT | odom bayat")
                    return False, "odometry unavailable during turn"

                dt = max(0.0, now - last_t)
                last_t = now

                # Sadece SOL donusu sayiyoruz.
                total_angle += max(0.0, angular_z) * dt
                turned_deg = min(180.0, total_angle * 180.0 / 3.141592653589793)

                remaining_deg = max(0.0, 180.0 - turned_deg)

                # Hedefe yaklastikca hizi dusur.
                if remaining_deg > 30.0:
                    turn_speed = self.dropoff_turn_speed
                elif remaining_deg > 15.0:
                    turn_speed = 0.17
                else:
                    turn_speed = 0.10

                if total_angle >= 3.141592653589793:
                    break

                cmd = Twist()
                cmd.angular.z = turn_speed
                self.cmd_pub.publish(cmd)

                if turned_deg - last_log_deg >= 10.0:
                    self.get_logger().info(
                        f"DON | {turned_deg:.0f} / 180 deg | "
                        f"kalan={remaining_deg:.0f} deg | "
                        f"speed={turn_speed:.3f}"
                    )
                    last_log_deg = int(turned_deg / 10.0) * 10

                time.sleep(0.05)

            self.stop_robot()
            final_deg = min(180.0, total_angle * 180.0 / 3.141592653589793)
            self.get_logger().info("DROPOFF DONUS TAMAMLANDI")
            self.get_logger().info(f"Donulen aci : {final_deg:.1f} deg")
            return True, "dropoff 180 degree turn complete"

        finally:
            self.stop_robot()

    # ==================================================
    # LINE FOLLOW (kucuk calisan script ile AYNI yasa)
    # ==================================================

    def follow_line(self, goal_handle, operation: str):
        is_pickup = operation == "pickup"
        is_dropoff = operation == "dropoff"

        if not is_pickup and not is_dropoff:
            return False, f"unknown operation: {operation}"

        with self.lock:
            self.active = True
            self.mz80_armed = False
            self.mz80_detected = False
            self.filtered_turn = 0.0
            self.line_last_seen = time.monotonic()

        start_time = time.monotonic()

        self.get_logger().info(f"LINE FOLLOW START | op={operation}")

        try:
            while rclpy.ok():
                if goal_handle.is_cancel_requested:
                    return False, "cancelled"

                now = time.monotonic()
                elapsed = now - start_time

                if elapsed > self.timeout_sec:
                    self.get_logger().error("LINE FOLLOW TIMEOUT")
                    return False, "timeout"

                with self.lock:
                    line_detected = self.line_detected
                    error = self.error
                    line_last_seen = self.line_last_seen
                    mz80_armed = self.mz80_armed
                    mz80_detected = self.mz80_detected

                line_fresh = (
                    line_detected
                    and now - line_last_seen <= self.line_lost_sec
                )

                # ---- pickup: ZAMAN ile arm, MZ80 ile bitir ----
                if is_pickup:
                    if not mz80_armed and elapsed >= self.pickup_arm_time_s:
                        with self.lock:
                            self.mz80_armed = True
                        self.get_logger().info("MZ80 ARMED")

                    if mz80_detected:
                        self.get_logger().info(
                            "PICKUP COMPLETE | MZ80 confirmed"
                        )
                        return True, "pickup MZ80 confirmed"

                    # yous: cizgi bitti + MZ80 YOK -> odometri ile 12cm ilerle -> dur
                    if mz80_armed and not line_fresh:
                        self.get_logger().info(
                            "PICKUP LINE END | MZ80 yok -> 12cm ilerle"
                        )
                        if self.drive_forward_odom(
                            goal_handle,
                            self.pickup_nudge_distance_m,
                            self.pickup_nudge_speed,
                        ):
                            return True, "pickup nudged (no MZ80)"
                        return False, "pickup nudge failed"

                # ---- dropoff: SADECE cizgi takip; cizgi bitince DUR ----
                else:
                    if not line_fresh and elapsed >= self.dropoff_lost_grace_s:
                        self.get_logger().info(
                            "DROPOFF LINE END | line lost -> stop"
                        )
                        return True, "dropoff line end"

                # ---- KANITLANMIS cizgi takibi ----
                if line_fresh:
                    if abs(error) <= self.deadband:
                        corrected_error = 0.0
                    elif error > 0.0:
                        corrected_error = error - self.deadband
                    else:
                        corrected_error = error + self.deadband

                    turn = self.gain * corrected_error
                    if self.invert:
                        turn = -turn

                    # ==================================================
                    # FIRST SMOOTHING
                    # ==================================================

                    target_turn = (
                        self.smoothing * turn
                        + (1.0 - self.smoothing) * self.filtered_turn
                    )

                    # ==================================================
                    # EXTRA RATE LIMIT
            
                    # ==================================================

                    turn_difference = target_turn - self.filtered_turn

                    turn_difference = max(
                        -self.max_turn_step,
                        min(
                            self.max_turn_step,
                            turn_difference,
                        ),
                    )

                    self.filtered_turn += turn_difference
                else:
                    self.filtered_turn = 0.0

                self.filtered_turn = max(
                    -self.max_turn,
                    min(self.max_turn, self.filtered_turn)
                )

                cmd = Twist()
                if line_fresh:
                    cmd.linear.x = self.speed
                    cmd.angular.z = self.filtered_turn
                else:
                    cmd.linear.x = 0.0
                    cmd.angular.z = 0.0
                self.cmd_pub.publish(cmd)

                time.sleep(0.05)

            return False, "ROS shutdown"

        finally:
            with self.lock:
                self.active = False
            self.stop_robot()

    # ==================================================
    # EXECUTE
    # ==================================================

    def execute_callback(self, goal_handle):
        operation = str(goal_handle.request.operation).strip().lower()

        try:
            self.get_logger().info("========================================")
            self.get_logger().info(
                f"DOCK START | station={goal_handle.request.station_id} | "
                f"op={operation}"
            )

            if operation not in ("pickup", "dropoff"):
                goal_handle.abort()
                return Dock.Result(
                    success=False,
                    message=f"unknown operation: {operation}",
                )

            # Pickup: mevcut on kamera line-follow + MZ80 mantigi.
            # Dropoff: geri kamera line-follow + 70cm + 180 derece donus.
            if operation == "dropoff":
                success, message = self.follow_reverse_line(goal_handle)
                if success:
                    success, message = self.rotate_dropoff_180(goal_handle)
            else:
                success, message = self.follow_line(goal_handle, operation)

            if success:
                self.get_logger().info(f"DOCK SUCCESS | {message}")
                goal_handle.succeed()
                return Dock.Result(success=True, message=message)

            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                return Dock.Result(success=False, message="cancelled")

            self.get_logger().error(f"DOCK FAILURE | {message}")
            goal_handle.abort()
            return Dock.Result(success=False, message=message)

        except Exception as exc:
            self.get_logger().error(f"DOCKING EXCEPTION: {exc}")
            goal_handle.abort()
            return Dock.Result(success=False, message=str(exc))

        finally:
            self.stop_robot()
            with self.lock:
                self.action_running = False
                self.active = False
                self.mz80_armed = False
                self.mz80_detected = False

    def destroy_node(self):
        self.stop_robot()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = DockingNode()
    executor = MultiThreadedExecutor(num_threads=4)
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
