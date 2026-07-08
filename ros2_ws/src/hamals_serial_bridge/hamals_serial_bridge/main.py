#!/usr/bin/env python3

import threading
import time

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from hamals_interfaces.msg import WheelTicks
from sensor_msgs.msg import Imu

import serial

from .parser import LineParser
from .protocol import encode_cmd

from .helpers.config_loader import load_config
from .helpers.debug_panels import (
    format_startup_config,
    format_debug_panel,
)


class SerialBridgeNode(Node):

    def __init__(self):
        super().__init__('hamals_serial_bridge')

        # ==================== CONFIG ====================
        self.cfg = load_config(self)

        # ==================== STATE ====================
        self._last_cmd_time = time.time()
        self._last_cmd_send_time = 0.0
        self._deadman_active = False
        self._running = True

        self._cmd_send_min_interval = (
            1.0 / float(self.cfg.cmd_vel_rate_limit_hz)
            if self.cfg.cmd_vel_rate_limit_hz > 0
            else 0.0
        )

        self._last_sent_cmd_v = None
        self._last_sent_cmd_w = None
        self._last_sent_cmd_time = 0.0

        # Debug counters
        self._dbg_tx = 0
        self._dbg_tx_skipped_dedup = 0
        self._dbg_tx_skipped_ratelimit = 0
        self._dbg_wheel_ticks_tx = 0
        self._dbg_last_cmd = (0.0, 0.0)
        self._dbg_last_wheel_ticks = (0, 0, 0)
        self._dbg_rx_bytes = 0
        self._dbg_rx_frames = 0
        self._dbg_rx_invalid = 0

        # ==================== SERIAL ====================
        self.ser = None
        self._tx_lock = threading.Lock()
        self.parser = LineParser()

        self._connect_serial()
        self._reset_mcu()

        # ==================== ROS ====================
        self.cmd_sub = self.create_subscription(
            Twist,
            self.cfg.cmd_vel_topic,
            self.cmd_vel_callback,
            10
        )

        self.wheel_ticks_pub = self.create_publisher(
            WheelTicks,
            self.cfg.wheel_ticks_topic,
            10
        )

        self.imu_pub = self.create_publisher(
            Imu,
            self.cfg.imu_topic,
            10
        )

        if self.cfg.debug:
            self.create_timer(1.0, self._print_debug_panel)

        self.create_timer(0.05, self._check_cmd_timeout)

        self._rx_thread = threading.Thread(
            target=self.serial_rx_loop,
            daemon=True
        )
        self._rx_thread.start()

        self.get_logger().info(format_startup_config(self.cfg))
        self.get_logger().info("hamals_serial_bridge started")

    # =====================================================
    # SERIAL
    # =====================================================
    def _connect_serial(self):
        self.ser = serial.Serial(
            port=self.cfg.port,
            baudrate=self.cfg.baudrate,
            timeout=self.cfg.timeout_ms / 1000.0
        )

        self.get_logger().info(
            f"Serial connected: {self.cfg.port} @ {self.cfg.baudrate}"
        )

    def _reset_mcu(self):
        if not self.cfg.reset_on_startup:
            return

        self.get_logger().info("Resetting MCU via DTR")

        self.ser.dtr = False
        time.sleep(self.cfg.reset_pulse_ms / 1000.0)

        self.ser.dtr = True
        time.sleep(self.cfg.reset_boot_wait_ms / 1000.0)

    def _serial_write(self, data: bytes) -> bool:
        if not self.ser or not self.ser.is_open:
            return False

        try:
            with self._tx_lock:
                self.ser.write(data)
            return True

        except Exception as e:
            self.get_logger().warn(
                f"Serial write error: {e}",
                throttle_duration_sec=5.0
            )
            return False

    # =====================================================
    # CMD HELPERS
    # =====================================================
    @staticmethod
    def _is_stop_cmd(v: float, w: float) -> bool:
        return abs(v) < 1e-6 and abs(w) < 1e-6

    def _send_cmd(self, v: float, w: float) -> bool:
        packet = encode_cmd(v, w).encode('utf-8')

        if self._serial_write(packet):
            self._dbg_tx += 1
            self._last_sent_cmd_v = v
            self._last_sent_cmd_w = w
            self._last_sent_cmd_time = time.time()
            return True

        return False

    def _maybe_send_cmd(self, v: float, w: float, force: bool = False):
        now = time.time()

        if force:
            if self._send_cmd(v, w):
                self._last_cmd_send_time = now
            return

        if self._last_sent_cmd_v is None or self._last_sent_cmd_w is None:
            if self._send_cmd(v, w):
                self._last_cmd_send_time = now
            return

        prev_stop = self._is_stop_cmd(
            self._last_sent_cmd_v,
            self._last_sent_cmd_w
        )
        new_stop = self._is_stop_cmd(v, w)

        # stop <-> movement geçişleri kritik, rate-limit'e takılmasın
        if prev_stop != new_stop:
            if self._send_cmd(v, w):
                self._last_cmd_send_time = now
            return

        if not self.cfg.cmd_dedup_enabled:
            if self._is_rate_limited(now):
                self._dbg_tx_skipped_ratelimit += 1
                return

            if self._send_cmd(v, w):
                self._last_cmd_send_time = now
            return

        changed = self._cmd_changed(v, w)

        if changed:
            if self._is_rate_limited(now):
                self._dbg_tx_skipped_ratelimit += 1
                return

            if self._send_cmd(v, w):
                self._last_cmd_send_time = now
            return

        resend_due = (
            (now - self._last_sent_cmd_time) * 1000.0
            >= self.cfg.cmd_force_resend_ms
        )

        if resend_due:
            if self._send_cmd(v, w):
                self._last_cmd_send_time = now
        else:
            self._dbg_tx_skipped_dedup += 1

    def _is_rate_limited(self, now: float) -> bool:
        if self._cmd_send_min_interval <= 0.0:
            return False

        return (now - self._last_cmd_send_time) < self._cmd_send_min_interval

    def _cmd_changed(self, v: float, w: float) -> bool:
        dv = abs(v - self._last_sent_cmd_v)
        dw = abs(w - self._last_sent_cmd_w)

        return (
            dv > self.cfg.cmd_dedup_eps_v
            or dw > self.cfg.cmd_dedup_eps_w
        )

    # =====================================================
    # TIMEOUT
    # =====================================================
    def _check_cmd_timeout(self):
        timeout = (
            time.time() - self._last_cmd_time
            > self.cfg.cmd_vel_timeout_ms / 1000.0
        )

        if timeout and not self._deadman_active:
            self._maybe_send_cmd(0.0, 0.0, force=True)
            self._deadman_active = True

        elif not timeout:
            self._deadman_active = False

    # =====================================================
    # ROS → MCU
    # =====================================================
    def cmd_vel_callback(self, msg: Twist):
        v = msg.linear.x
        w = msg.angular.z

        self._last_cmd_time = time.time()
        self._dbg_last_cmd = (v, w)

        self._maybe_send_cmd(v, w, force=False)

    # =====================================================
    # MCU → ROS
    # =====================================================
    def serial_rx_loop(self):
        while rclpy.ok() and self._running:
            try:
                self._read_serial_once()

                while self.ser.in_waiting > 0:
                    self._read_serial_once()

            except Exception as e:
                self.get_logger().warn(
                    f"RX error: {e}",
                    throttle_duration_sec=5.0
                )
                time.sleep(0.1)

    def _read_serial_once(self):
        raw = self.ser.read_until(b'\n', size=256)

        if not raw:
            return

        decoded = raw.decode('utf-8', errors='ignore')
        messages = self.parser.push(decoded)

        for msg in messages:
            self.handle_serial_message(msg)

        self._update_rx_debug_stats()

    def _update_rx_debug_stats(self):
        self._dbg_rx_bytes = self.parser.bytes_received
        self._dbg_rx_frames = self.parser.valid_frames
        self._dbg_rx_invalid = self.parser.invalid_frames

    def handle_serial_message(self, msg: dict):
        msg_type = msg.get('type')

        if msg_type == 'enc':
            self._publish_wheel_ticks(msg)

        elif msg_type == 'imu':
            self._publish_imu(msg)

    # =====================================================
    # ENC → /wheel_ticks
    # =====================================================
    def _publish_wheel_ticks(self, msg: dict):
        ticks_msg = WheelTicks()
        ticks_msg.header.stamp = self.get_clock().now().to_msg()
        ticks_msg.t_us = msg.get('t_us', 0)
        ticks_msg.dl = msg.get('dl', 0)
        ticks_msg.dr = msg.get('dr', 0)

        self.wheel_ticks_pub.publish(ticks_msg)

        self._dbg_wheel_ticks_tx += 1
        self._dbg_last_wheel_ticks = (
            ticks_msg.t_us,
            ticks_msg.dl,
            ticks_msg.dr,
        )

    # =====================================================
    # IMU → /imu/data
    # =====================================================
    def _publish_imu(self, msg: dict):
        imu_msg = Imu()
        imu_msg.header.stamp = self.get_clock().now().to_msg()
        imu_msg.header.frame_id = self.cfg.imu_frame_id

        # Orientation yok demek.
        imu_msg.orientation_covariance[0] = -1.0

        imu_msg.angular_velocity.x = 0.0
        imu_msg.angular_velocity.y = 0.0
        imu_msg.angular_velocity.z = msg.get('gz', 0.0)

        imu_msg.angular_velocity_covariance = [
            float(self.cfg.imu_ang_vel_cov_diag[0]), 0.0, 0.0,
            0.0, float(self.cfg.imu_ang_vel_cov_diag[1]), 0.0,
            0.0, 0.0, float(self.cfg.imu_ang_vel_cov_diag[2]),
        ]

        if self.cfg.publish_linear_accel:
            imu_msg.linear_acceleration.x = msg.get('ax', 0.0)
            imu_msg.linear_acceleration.y = msg.get('ay', 0.0)
            imu_msg.linear_acceleration.z = msg.get('az', 0.0)
        else:
            imu_msg.linear_acceleration.x = 0.0
            imu_msg.linear_acceleration.y = 0.0
            imu_msg.linear_acceleration.z = 0.0

        imu_msg.linear_acceleration_covariance = [
            float(self.cfg.imu_lin_acc_cov_diag[0]), 0.0, 0.0,
            0.0, float(self.cfg.imu_lin_acc_cov_diag[1]), 0.0,
            0.0, 0.0, float(self.cfg.imu_lin_acc_cov_diag[2]),
        ]

        self.imu_pub.publish(imu_msg)

    # =====================================================
    # DEBUG
    # =====================================================
    def _print_debug_panel(self):
        cmd_v, cmd_w = self._dbg_last_cmd
        ticks_t_us, ticks_dl, ticks_dr = self._dbg_last_wheel_ticks

        panel = format_debug_panel(
            tx_packets=self._dbg_tx,
            tx_dedup_skipped=self._dbg_tx_skipped_dedup,
            tx_ratelimit_skipped=self._dbg_tx_skipped_ratelimit,
            wheel_ticks_published=self._dbg_wheel_ticks_tx,
            rx_bytes=self._dbg_rx_bytes,
            rx_valid_frames=self._dbg_rx_frames,
            rx_invalid_frames=self._dbg_rx_invalid,
            deadman_active=self._deadman_active,
            last_cmd_v=cmd_v,
            last_cmd_w=cmd_w,
            last_ticks_t_us=ticks_t_us,
            last_ticks_dl=ticks_dl,
            last_ticks_dr=ticks_dr,
        )

        self.get_logger().info(panel)

    # =====================================================
    # SHUTDOWN
    # =====================================================
    def destroy_node(self):
        self._running = False

        if self.ser and self.ser.is_open:
            self.ser.close()

        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)

    node = SerialBridgeNode()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.destroy_node()
        rclpy.shutdown()
