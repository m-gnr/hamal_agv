#!/usr/bin/env python3

import math

import rclpy
from rclpy.node import Node

from hamals_interfaces.msg import WheelTicks
from nav_msgs.msg import Odometry

from .helpers.config_loader import load_config
from .helpers.debug_panels import (
    format_startup_config,
    format_debug_panel,
)


class OdometryNode(Node):

    def __init__(self):
        super().__init__('hamals_odometry')

        # ==================== CONFIG ====================
        self.cfg = load_config(self)

        # ==================== STATE ====================
        self._last_t_us = None

        # Debug counters
        self._dbg_wheel_ticks_rx = 0
        self._dbg_odom = 0
        self._dbg_odom_skipped_dt = 0
        self._dbg_last_wheel_ticks = (0, 0, 0)
        self._dbg_last_dt_s = 0.0
        self._dbg_last_odom = (0.0, 0.0)

        # ==================== ROS ====================
        self.wheel_ticks_sub = self.create_subscription(
            WheelTicks,
            self.cfg.wheel_ticks_topic,
            self.wheel_ticks_callback,
            10
        )

        self.odom_pub = self.create_publisher(
            Odometry,
            self.cfg.odom_topic,
            10
        )

        if self.cfg.debug:
            self.create_timer(1.0, self._print_debug_panel)

        self.get_logger().info(format_startup_config(self.cfg))
        self.get_logger().info("hamals_odometry started")

    # =====================================================
    # /wheel_ticks → /odom_raw
    # =====================================================
    def wheel_ticks_callback(self, msg: WheelTicks):
        self._dbg_wheel_ticks_rx += 1
        self._dbg_last_wheel_ticks = (msg.t_us, msg.dl, msg.dr)

        if self._last_t_us is None:
            self._last_t_us = msg.t_us
            return

        dt_us = (msg.t_us - self._last_t_us) & 0xFFFFFFFF
        dt = dt_us / 1e6
        self._last_t_us = msg.t_us
        self._dbg_last_dt_s = dt

        if dt <= self.cfg.enc_dt_min_s or dt > self.cfg.enc_dt_max_s:
            self._dbg_odom_skipped_dt += 1
            return

        dtheta_l = (2.0 * math.pi * msg.dl) / self.cfg.cpr_left
        dtheta_r = (2.0 * math.pi * msg.dr) / self.cfg.cpr_right

        omega_l = dtheta_l / dt
        omega_r = dtheta_r / dt

        v_l = omega_l * self.cfg.wheel_radius_m
        v_r = omega_r * self.cfg.wheel_radius_m

        v = 0.5 * (v_l + v_r)
        w = (v_r - v_l) / self.cfg.track_width_m

        self._publish_odom_raw(v, w)

    def _publish_odom_raw(self, v: float, w: float):
        odom = Odometry()
        odom.header.stamp = self.get_clock().now().to_msg()
        odom.header.frame_id = self.cfg.frame_id
        odom.child_frame_id = self.cfg.child_frame_id

        odom.pose.pose.position.x = 0.0
        odom.pose.pose.position.y = 0.0
        odom.pose.pose.position.z = 0.0

        odom.pose.pose.orientation.x = 0.0
        odom.pose.pose.orientation.y = 0.0
        odom.pose.pose.orientation.z = 0.0
        odom.pose.pose.orientation.w = 1.0

        odom.pose.covariance = self.cfg.pose_covariance
        odom.twist.covariance = self.cfg.twist_covariance

        odom.twist.twist.linear.x = v
        odom.twist.twist.angular.z = w

        self.odom_pub.publish(odom)

        self._dbg_odom += 1
        self._dbg_last_odom = (v, w)

    # =====================================================
    # DEBUG
    # =====================================================
    def _print_debug_panel(self):
        ticks_t_us, ticks_dl, ticks_dr = self._dbg_last_wheel_ticks
        odom_v, odom_w = self._dbg_last_odom

        panel = format_debug_panel(
            wheel_ticks_rx=self._dbg_wheel_ticks_rx,
            odom_published=self._dbg_odom,
            odom_skipped_dt=self._dbg_odom_skipped_dt,
            last_ticks_t_us=ticks_t_us,
            last_ticks_dl=ticks_dl,
            last_ticks_dr=ticks_dr,
            last_dt_s=self._dbg_last_dt_s,
            last_odom_v=odom_v,
            last_odom_w=odom_w,
        )

        self.get_logger().info(panel)


def main(args=None):
    rclpy.init(args=args)

    node = OdometryNode()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.destroy_node()
        rclpy.shutdown()
