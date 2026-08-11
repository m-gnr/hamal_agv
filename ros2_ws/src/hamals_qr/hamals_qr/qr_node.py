#!/usr/bin/env python3

import json

import cv2
import numpy as np

import rclpy

from cv_bridge import CvBridge

from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from sensor_msgs.msg import Image
from std_msgs.msg import Bool, String

from pyzbar.pyzbar import decode as qr_decode


class QRNode(Node):

    def __init__(self):

        super().__init__("qr_node")

        self.get_logger().info("QR Node Started")

        self._declare_parameters()
        params = self._read_parameters()

        self.stable_threshold = params["stable_threshold"]
        self.process_every_n = params["process_every_n"]

        self.bridge = CvBridge()

        self.last_qr = ""
        self.last_overlay_sent = None

        self.hit_count = 0
        self.miss_count = 0
        self.stable_state = False

        self.frame_count = 0

        self.detected_publisher = self.create_publisher(
            Bool,
            params["detected_topic"],
            10
        )

        self.text_publisher = self.create_publisher(
            String,
            params["text_topic"],
            10
        )

        self.overlay_publisher = self.create_publisher(
            String,
            params["overlay_topic"],
            10
        )

        self.image_subscriber = self.create_subscription(
            Image,
            params["image_topic"],
            self.image_callback,
            qos_profile_sensor_data
        )

        self.get_logger().info(
            f"QR detection configured: stable_threshold={self.stable_threshold}, "
            f"process_every_n={self.process_every_n}"
        )

    def _declare_parameters(self):
        # Varsayılan olarak tek geçerli QR okuması görev akışını serbest bırakır.
        self.declare_parameter("stable_threshold", 1)
        self.declare_parameter("process_every_n", 3)

        self.declare_parameter("image_topic", "/camera/image_raw")
        self.declare_parameter("detected_topic", "/qr/detected")
        self.declare_parameter("text_topic", "/qr/text")
        self.declare_parameter("overlay_topic", "/qr/overlay")

    def _read_parameters(self):
        return {
            "stable_threshold": self.get_parameter("stable_threshold").value,
            "process_every_n": self.get_parameter("process_every_n").value,
            "image_topic": self.get_parameter("image_topic").value,
            "detected_topic": self.get_parameter("detected_topic").value,
            "text_topic": self.get_parameter("text_topic").value,
            "overlay_topic": self.get_parameter("overlay_topic").value,
        }

    def image_callback(self, msg):

        self.frame_count += 1

        if self.frame_count % self.process_every_n != 0:
            return

        try:

            frame = self.bridge.imgmsg_to_cv2(
                msg,
                desired_encoding="bgr8"
            )

        except Exception as e:

            self.get_logger().error(
                f"cv_bridge failed: {e}"
            )

            return

        data, points = self.detect_qr(frame)

        detected = bool(data)

        self.update_detection_state(detected)

        self.publish_text(data)

        self.publish_overlay(data, points)

    def detect_qr(self, frame):

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        decoded_objects = qr_decode(gray)

        if not decoded_objects:
            return "", None

        obj = decoded_objects[0]

        try:
            data = obj.data.decode("utf-8")
        except UnicodeDecodeError:
            data = obj.data.decode("utf-8", errors="ignore")

        points = np.array(
            [(p.x, p.y) for p in obj.polygon],
            dtype=np.float32
        )

        return data, points

    def update_detection_state(self, detected):

        if detected:

            self.hit_count += 1
            self.miss_count = 0

        else:

            self.miss_count += 1
            self.hit_count = 0

        if (
            self.hit_count >= self.stable_threshold
            and
            not self.stable_state
        ):

            self.stable_state = True
            self.get_logger().info("QR Detected")

        elif (
            self.miss_count >= self.stable_threshold
            and
            self.stable_state
        ):

            self.stable_state = False
            self.last_qr = ""

            self.get_logger().info("QR Lost")

        # Kararlı durum her işlenen karede yayımlanır. Görev düğümü QR zaten
        # görülmüşken başlarsa, yalnızca geçiş anını yayımlamak onu sonsuza
        # kadar bekletebilir.
        msg = Bool()
        msg.data = self.stable_state
        self.detected_publisher.publish(msg)

    def publish_text(self, data):

        if not data:
            return

        if data == self.last_qr:
            return

        self.last_qr = data

        msg = String()

        msg.data = data

        self.text_publisher.publish(msg)

        self.get_logger().info(
            f"QR : {data}"
        )

    def publish_overlay(self, data, points):

        if not data or points is None:
            payload = {"detected": False}

        else:

            corners = points.reshape(-1, 2).astype(int).tolist()

            payload = {
                "detected": True,
                "text": data,
                "points": corners,
                "stamp": self.get_clock().now().nanoseconds,
            }

        if payload == self.last_overlay_sent:
            return

        self.last_overlay_sent = payload

        msg = String()
        msg.data = json.dumps(payload)

        self.overlay_publisher.publish(msg)


def main(args=None):

    rclpy.init(args=args)

    node = QRNode()

    try:

        rclpy.spin(node)

    except KeyboardInterrupt:

        pass

    finally:

        node.destroy_node()

        rclpy.shutdown()


if __name__ == "__main__":
    main()
