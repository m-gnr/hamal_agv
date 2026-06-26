import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import sys
import termios
import tty
import select


class TeleopNode(Node):
    def __init__(self):
        super().__init__('teleop_node')

        self.declare_parameter('publish_rate_hz', 20.0)
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')

        self.declare_parameter('linear_speed', 0.1)
        self.declare_parameter('linear_min', 0.0)
        self.declare_parameter('linear_max', 0.3)
        self.declare_parameter('linear_step', 0.05)

        self.declare_parameter('angular_speed', 0.5)
        self.declare_parameter('angular_min', 0.0)
        self.declare_parameter('angular_max', 1.5)
        self.declare_parameter('angular_step', 0.1)

        self.declare_parameter('key_forward', 'w')
        self.declare_parameter('key_backward', 's')
        self.declare_parameter('key_left', 'a')
        self.declare_parameter('key_right', 'd')
        self.declare_parameter('key_stop', 'x')

        self.linear_speed = self.get_parameter('linear_speed').value
        self.angular_speed = self.get_parameter('angular_speed').value

        self.current_linear_cmd = 0.0
        self.current_angular_cmd = 0.0

        cmd_vel_topic = self.get_parameter('cmd_vel_topic').value
        self.pub = self.create_publisher(Twist, cmd_vel_topic, 10)

        rate = self.get_parameter('publish_rate_hz').value
        self.timer = self.create_timer(1.0 / rate, self.loop)

        self.settings = termios.tcgetattr(sys.stdin)

        self.get_logger().info(f"""
===============================
hamals_manual_teleop (LATCHED)

Publishing topic:
  {cmd_vel_topic}

Move (one press = keep moving):
  {self.get_parameter('key_forward').value} : forward
  {self.get_parameter('key_backward').value} : backward
  {self.get_parameter('key_left').value} : rotate left
  {self.get_parameter('key_right').value} : rotate right
  {self.get_parameter('key_stop').value} : EMERGENCY STOP

Speed adjust:
  1 : linear down
  2 : linear up
  3 : angular down
  4 : angular up
===============================
""")

    def get_key(self):
        tty.setraw(sys.stdin.fileno())
        rlist, _, _ = select.select([sys.stdin], [], [], 0.1)  # 👈 KRİTİK
        key = sys.stdin.read(1) if rlist else None
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.settings)
        return key


    def clamp(self, value, min_v, max_v):
        return max(min_v, min(value, max_v))

    def loop(self):
        key = self.get_key()

        if key:
            if key == '1':
                self.linear_speed -= self.get_parameter('linear_step').value
            elif key == '2':
                self.linear_speed += self.get_parameter('linear_step').value
            elif key == '3':
                self.angular_speed -= self.get_parameter('angular_step').value
            elif key == '4':
                self.angular_speed += self.get_parameter('angular_step').value

            self.linear_speed = self.clamp(
                self.linear_speed,
                self.get_parameter('linear_min').value,
                self.get_parameter('linear_max').value
            )
            self.angular_speed = self.clamp(
                self.angular_speed,
                self.get_parameter('angular_min').value,
                self.get_parameter('angular_max').value
            )

            if key == self.get_parameter('key_forward').value:
                self.current_linear_cmd = self.linear_speed
                self.current_angular_cmd = 0.0
            elif key == self.get_parameter('key_backward').value:
                self.current_linear_cmd = -self.linear_speed
                self.current_angular_cmd = 0.0
            elif key == self.get_parameter('key_left').value:
                self.current_linear_cmd = 0.0
                self.current_angular_cmd = self.angular_speed
            elif key == self.get_parameter('key_right').value:
                self.current_linear_cmd = 0.0
                self.current_angular_cmd = -self.angular_speed
            elif key == self.get_parameter('key_stop').value:
                self.current_linear_cmd = 0.0
                self.current_angular_cmd = 0.0

        msg = Twist()
        msg.linear.x = self.current_linear_cmd
        msg.linear.y = 0.0
        msg.linear.z = 0.0
        msg.angular.x = 0.0
        msg.angular.y = 0.0
        msg.angular.z = self.current_angular_cmd
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = TeleopNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
