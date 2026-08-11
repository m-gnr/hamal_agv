#!/usr/bin/env python3

import cv2
import rclpy

from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from cv_bridge import CvBridge


class CameraNode(Node):

    def __init__(self):
        super().__init__("camera_node")

        self.get_logger().info("===== HAMALS Camera Node Started (Jetson/GStreamer) =====")

        self._declare_parameters()
        params = self._read_parameters()

        self.frame_id = params["frame_id"]

        self.bridge = CvBridge()

        self.publisher = self.create_publisher(
            Image,
            params["topic_name"],
            qos_profile_sensor_data
        )

        self.cap = self._init_camera(params)

        if not self.cap.isOpened():
            self.get_logger().error(
                "Kamera acilamadi! GStreamer pipeline'i ve sensor-id'yi kontrol edin."
            )
            raise RuntimeError("Camera failed to open")

        self.get_logger().info(
            f"Camera started: {params['image_width']}x{params['image_height']} "
            f"@ {params['fps']}fps (sensor-id={params['camera_num']}, "
            f"topic={params['topic_name']}, frame_id={self.frame_id})"
        )

        self.timer = self.create_timer(
            1.0 / params["fps"],
            self.publish_image
        )

    def _declare_parameters(self):
        self.declare_parameter("image_width", 1280)
        self.declare_parameter("image_height", 720)
        self.declare_parameter("fps", 30.0)
        self.declare_parameter("topic_name", "/camera/image_raw")
        self.declare_parameter("frame_id", "camera_link")
        self.declare_parameter("camera_num", 0)
        self.declare_parameter("flip_method", 0)

    def _read_parameters(self):
        return {
            "image_width": self.get_parameter("image_width").value,
            "image_height": self.get_parameter("image_height").value,
            "fps": self.get_parameter("fps").value,
            "topic_name": self.get_parameter("topic_name").value,
            "frame_id": self.get_parameter("frame_id").value,
            "camera_num": self.get_parameter("camera_num").value,
            "flip_method": self.get_parameter("flip_method").value,
        }

    def _build_gstreamer_pipeline(self, params):
        return (
            f"nvarguscamerasrc sensor-id={params['camera_num']} ! "
            f"video/x-raw(memory:NVMM), width=(int){params['image_width']}, "
            f"height=(int){params['image_height']}, "
            f"framerate=(fraction){int(params['fps'])}/1 ! "
            f"nvvidconv flip-method={params['flip_method']} ! "
            f"video/x-raw, width=(int){params['image_width']}, "
            f"height=(int){params['image_height']}, format=(string)BGRx ! "
            f"videoconvert ! "
            f"video/x-raw, format=(string)BGR ! "
            f"appsink drop=true max-buffers=1"
        )

    def _init_camera(self, params):
        pipeline = self._build_gstreamer_pipeline(params)
        self.get_logger().info(f"GStreamer pipeline: {pipeline}")
        return cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)

    def publish_image(self):
        try:
            ret, frame = self.cap.read()

            if not ret or frame is None:
                self.get_logger().warn("Frame okunamadi (ret=False)")
                return

            msg = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = self.frame_id

            self.publisher.publish(msg)

        except Exception as e:
            self.get_logger().error(f"Camera Error: {e}")

    def destroy_node(self):
        if self.cap is not None:
            self.cap.release()
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
