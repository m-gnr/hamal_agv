#!/usr/bin/env python3

import json

import cv2
import numpy as np

import rclpy

from cv_bridge import CvBridge

from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from sensor_msgs.msg import Image
from std_msgs.msg import Bool, Int32, String


class LineNode(Node):

    def __init__(self):

        super().__init__("line_node")

        self.get_logger().info("Line Node Started")

        self._declare_parameters()
        params = self._read_parameters()

        self.row_ratio = params["row_ratio"]
        self.blur_size = params["blur_size"]
        self.kernel_size = params["kernel_size"]
        self.threshold_value = params["threshold_value"]
        self.stable_threshold = params["stable_threshold"]
        self.process_every_n = params["process_every_n"]

        self.bridge = CvBridge()

        self.last_overlay_sent = None

        self.hit_count = 0
        self.miss_count = 0
        self.stable_state = False

        self.frame_count = 0

        self.error_publisher = self.create_publisher(
            Int32,
            params["error_topic"],
            10
        )

        self.detected_publisher = self.create_publisher(
            Bool,
            params["detected_topic"],
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
            f"Line detection configured: row_ratio={self.row_ratio}, "
            f"stable_threshold={self.stable_threshold}, "
            f"process_every_n={self.process_every_n}"
        )

    # ------------------------------------------------------------------ #
    # Setup helpers
    # ------------------------------------------------------------------ #

    def _declare_parameters(self):
        self.declare_parameter("row_ratio", 0.90)
        self.declare_parameter("blur_size", [7, 7])
        self.declare_parameter("kernel_size", [7, 7])
        self.declare_parameter("threshold_value", 100)
        self.declare_parameter("stable_threshold", 5)
        self.declare_parameter("process_every_n", 1)

        self.declare_parameter("image_topic", "/camera/image_raw")
        self.declare_parameter("error_topic", "/line/error")
        self.declare_parameter("detected_topic", "/line/detected")
        self.declare_parameter("overlay_topic", "/line/overlay")

    def _read_parameters(self):
        blur = self.get_parameter("blur_size").value
        kernel = self.get_parameter("kernel_size").value

        return {
            "row_ratio": self.get_parameter("row_ratio").value,
            "blur_size": tuple(blur),
            "kernel_size": tuple(kernel),
            "threshold_value": self.get_parameter("threshold_value").value,
            "stable_threshold": self.get_parameter("stable_threshold").value,
            "process_every_n": self.get_parameter("process_every_n").value,
            "image_topic": self.get_parameter("image_topic").value,
            "error_topic": self.get_parameter("error_topic").value,
            "detected_topic": self.get_parameter("detected_topic").value,
            "overlay_topic": self.get_parameter("overlay_topic").value,
        }

    # ------------------------------------------------------------------ #
    # Runtime
    # ------------------------------------------------------------------ #

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

        error, points, detected = self.process_frame(frame)

        self.update_detection_state(detected)

        if detected:

            err_msg = Int32()
            err_msg.data = int(error)

            self.error_publisher.publish(err_msg)

        self.publish_overlay(detected, points)

    def process_frame(self, frame):

        h, w = frame.shape[:2]
        image_center = w // 2

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        blur = cv2.GaussianBlur(gray, self.blur_size, 0)

        _, binary = cv2.threshold(
            blur,
            self.threshold_value,
            255,
            cv2.THRESH_BINARY_INV
        )

        kernel = cv2.getStructuringElement(
            cv2.MORPH_RECT,
            self.kernel_size
        )

        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        row = int(h * self.row_ratio)

        line = binary[row]
        white = np.where(line == 255)[0]

        if len(white) == 0:
            return 0, None, False

        left = int(white[0])
        right = int(white[-1])
        center = (left + right) // 2
        error = center - image_center

        points = {
            "row": row,
            "left": left,
            "right": right,
            "center": center,
            "image_center": image_center,
        }

        return error, points, True

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

            self.get_logger().info("Line Detected")

        elif (
            self.miss_count >= self.stable_threshold
            and
            self.stable_state
        ):

            self.stable_state = False

            self.get_logger().info("Line Lost")

        # Her frame'de sürekli yayınlanıyor (sadece durum değişince değil).
        # Bu sayede SerialBridge/watchdog gibi tüketiciler node'un "canlı"
        # olduğunu sabit bir hızda kontrol edebilir; durum değişikliği
        # (edge) dakikalarca gelmese bile.
        msg = Bool()
        msg.data = self.stable_state
        self.detected_publisher.publish(msg)

    def publish_overlay(self, detected, points):

        if not detected or points is None:
            payload = {"detected": False}

        else:
            payload = {"detected": True, **points}

        if payload == self.last_overlay_sent:
            return

        self.last_overlay_sent = payload

        msg = String()
        msg.data = json.dumps(payload)

        self.overlay_publisher.publish(msg)


def main(args=None):

    rclpy.init(args=args)

    node = LineNode()

    try:

        rclpy.spin(node)

    except KeyboardInterrupt:

        pass

    finally:

        node.destroy_node()

        rclpy.shutdown()


if __name__ == "__main__":
    main()