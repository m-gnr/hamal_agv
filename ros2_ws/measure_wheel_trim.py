#!/usr/bin/env python3
"""
قياس فرق سرعة العجلتين تحت نفس PWM (open-loop) وحساب WHEEL_TRIM_R.

الاستخدام:
    source ~/hamal_eski_pi/hamal_agv/ros2_ws/install/setup.bash
    python3 measure_wheel_trim.py --duration 2
"""

import argparse
import rclpy
from rclpy.node import Node
from hamals_interfaces.msg import WheelTicks


class TrimMeasurer(Node):
    def __init__(self, duration: float, topic: str):
        super().__init__('trim_measurer')
        self.total_left = 0
        self.total_right = 0
        self.msg_count = 0
        self.sub = self.create_subscription(WheelTicks, topic, self._cb, 50)
        self.timer = self.create_timer(duration, self._finish)
        self.get_logger().info(f'جاري القياس لمدة {duration} ثانية...')

    def _cb(self, msg: WheelTicks):
        self.total_left += msg.dl
        self.total_right += msg.dr
        self.msg_count += 1

    def _finish(self):
        self.get_logger().info('--- النتيجة ---')
        self.get_logger().info(f'عدد الرسائل المستلمة: {self.msg_count}')
        self.get_logger().info(f'total_left  (dl مجموع) = {self.total_left}')
        self.get_logger().info(f'total_right (dr مجموع) = {self.total_right}')

        if self.total_right == 0 or self.total_left == 0:
            self.get_logger().error('واحد من العدّادين صفر — تأكد الإنكودر شغال.')
        else:
            trim_r = self.total_left / self.total_right
            self.get_logger().info(f'>>> WHEEL_TRIM_R المقترحة = {trim_r:.4f}')
            self.get_logger().info(f'    constexpr float WHEEL_TRIM_R = {trim_r:.4f}f;')

        rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--duration', type=float, default=5.0)
    parser.add_argument('--topic', type=str, default='/wheel_ticks')
    args = parser.parse_args()

    rclpy.init()
    node = TrimMeasurer(args.duration, args.topic)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
