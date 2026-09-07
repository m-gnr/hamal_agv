import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from sensor_msgs.msg import CompressedImage


class CameraRelay(Node):
    def __init__(self):
        super().__init__('camera_relay')

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10
        )

        self.sub = self.create_subscription(
            CompressedImage,
            '/camera/image_raw/compressed',
            self.callback,
            qos
        )

        self.pub = self.create_publisher(
            CompressedImage,
            '/laptop/camera/compressed',
            qos
        )

        self.get_logger().info(
            'Camera relay: /camera/image_raw/compressed -> '
            '/laptop/camera/compressed'
        )

    def callback(self, msg):
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = CameraRelay()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
