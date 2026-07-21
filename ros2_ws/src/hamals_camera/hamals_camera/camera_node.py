#!/usr/bin/env python3

import cv2
import rclpy

from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from picamera2 import Picamera2


class CameraNode(Node):

    def __init__(self):
        super().__init__("camera_node")

        self.get_logger().info("===== HAMALS Camera Node Started =====")

        self._declare_parameters()
        params = self._read_parameters()

        self.fps = params["fps"]
        self.frame_id = params["frame_id"]

        self.bridge = CvBridge()

        self.publisher = self.create_publisher(
            Image,
            params["topic_name"],
            qos_profile_sensor_data
        )

        self.picam2 = self._init_camera(params)

        self.get_logger().info(
            f"Camera started: {params['image_width']}x{params['image_height']} "
            f"@ {self.fps}fps (topic={params['topic_name']}, frame_id={self.frame_id})"
        )

        self.timer = self.create_timer(
            1.0 / self.fps,
            self.publish_image
        )

    # ------------------------------------------------------------------ #
    # Setup helpers
    # ------------------------------------------------------------------ #

    def _declare_parameters(self):
        self.declare_parameter("image_width", 1280)
        self.declare_parameter("image_height", 720)
        self.declare_parameter("fps", 30.0)
        self.declare_parameter("af_mode", 2)          # 0=Manual, 1=Auto, 2=Continuous
        self.declare_parameter("lens_position", 0.0)  # sadece af_mode=0 iken kullanılır
        self.declare_parameter("topic_name", "/camera/image_raw")
        self.declare_parameter("frame_id", "camera_link")
        self.declare_parameter("camera_num", 0)

    def _read_parameters(self):
        return {
            "image_width": self.get_parameter("image_width").value,
            "image_height": self.get_parameter("image_height").value,
            "fps": self.get_parameter("fps").value,
            "af_mode": self.get_parameter("af_mode").value,
            "lens_position": self.get_parameter("lens_position").value,
            "topic_name": self.get_parameter("topic_name").value,
            "frame_id": self.get_parameter("frame_id").value,
            "camera_num": self.get_parameter("camera_num").value,
        }

    def _init_camera(self, params):
        picam2 = Picamera2(camera_num=params["camera_num"])

        frame_duration_us = int(1_000_000 / params["fps"])

        camera_controls = {
            "FrameDurationLimits": (frame_duration_us, frame_duration_us),
            "AfMode": params["af_mode"],
        }
        if params["af_mode"] == 0:  # Manuel odaklama seçildiyse lens pozisyonu gerekir
            camera_controls["LensPosition"] = params["lens_position"]

        config = picam2.create_preview_configuration(
            main={"size": (params["image_width"], params["image_height"])},
            controls=camera_controls,
        )

        picam2.configure(config)
        picam2.start()

        return picam2

    # ------------------------------------------------------------------ #
    # Runtime
    # ------------------------------------------------------------------ #

    def publish_image(self):

        try:
            frame = self.picam2.capture_array()

            # RGB -> BGR
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            msg = self.bridge.cv2_to_imgmsg(
                frame,
                encoding="bgr8"
            )

            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = self.frame_id

            self.publisher.publish(msg)

        except Exception as e:
            self.get_logger().error(f"Camera Error: {e}")

    def destroy_node(self):

        self.picam2.stop()

        super().destroy_node()


def main(args=None):

    rclpy.init(args=args)

    node = CameraNode()

    try:
        rclpy.spin(node)

    except KeyboardInterrupt:
        pass

    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()