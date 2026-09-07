import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool

from hamals_interfaces.msg import ForkCommand


class ProximityMonitorNode(Node):

    def __init__(self):
        super().__init__('proximity_monitor')

        # --------------------------------------------------
        # PARAMETRELER
        # --------------------------------------------------

        self.declare_parameter('required_hits', 3)
        self.declare_parameter('required_misses', 3)
        self.declare_parameter('sensor_timeout_sec', 0.5)
        self.declare_parameter('active_low', False)

        # --------------------------------------------------
        # PARAMETRELERİ OKU VE SINIRLA
        # --------------------------------------------------

        self.required_hits = max(
            1,
            int(self.get_parameter('required_hits').value)
        )

        self.required_misses = max(
            1,
            int(self.get_parameter('required_misses').value)
        )

        self.sensor_timeout_sec = max(
            0.1,
            float(self.get_parameter('sensor_timeout_sec').value)
        )

        self.active_low = bool(
            self.get_parameter('active_low').value
        )

        # --------------------------------------------------
        # DURUM DEĞİŞKENLERİ
        # --------------------------------------------------

        self.filtered_state = False

        self.hit_count = 0
        self.miss_count = 0

        self.last_message_time = None
        self.previous_alive_state = None
        self.received_first_message = False

        # Docking proximity kontrolü başlangıçta kapalı.
        self.enabled = False

        # --------------------------------------------------
        # SUBSCRIBERS
        # --------------------------------------------------

        # Serial bridge tarafından yayınlanan ham proximity bilgisi
        self.create_subscription(
            Bool,
            '/proximity/raw',
            self._raw_callback,
            10
        )

        # Docking node çizgi takibine geçince proximity aktif edilir.
        self.create_subscription(
            Bool,
            '/proximity/enable',
            self._enable_callback,
            10
        )

        # Fork yukarı kalkmaya başladığında proximity devreden çıkar.
        self.create_subscription(
            ForkCommand,
            '/fork/cmd',
            self._fork_command_callback,
            10
        )

        # --------------------------------------------------
        # PUBLISHERS
        # --------------------------------------------------

        self.detected_pub = self.create_publisher(
            Bool,
            '/proximity/detected',
            10
        )

        self.alive_pub = self.create_publisher(
            Bool,
            '/proximity/alive',
            10
        )

        # --------------------------------------------------
        # TIMER
        # --------------------------------------------------

        self.timer = self.create_timer(
            0.1,
            self._timer_callback
        )

        self.get_logger().info(
            'Proximity monitor started'
        )

    # ------------------------------------------------------
    # PROXIMITY AKTİF / PASİF
    # ------------------------------------------------------

    def _enable_callback(self, msg: Bool):

        new_state = bool(msg.data)

        if new_state == self.enabled:
            return

        self.enabled = new_state

        self.filtered_state = False
        self.hit_count = 0
        self.miss_count = 0

        if self.enabled:
            self.get_logger().info(
                'Proximity enabled'
            )
        else:
            self.get_logger().info(
                'Proximity disabled'
            )

        self._publish_detected()

    # ------------------------------------------------------
    # FORK KOMUTU
    # ------------------------------------------------------

    def _fork_command_callback(self, msg: ForkCommand):

        # Fork yukarı kalkmaya başladığında proximity artık
        # docking bitiş kararı vermemeli.
        if int(msg.command) == int(ForkCommand.UP):

            if self.enabled:
                self.enabled = False

                self.filtered_state = False
                self.hit_count = 0
                self.miss_count = 0

                self.get_logger().info(
                    'Proximity disabled: fork lifting started'
                )

                self._publish_detected()

    # ------------------------------------------------------
    # HAM PROXIMITY VERİSİ
    # ------------------------------------------------------

    def _raw_callback(self, msg: Bool):

        self.last_message_time = time.monotonic()
        self.received_first_message = True

        # Proximity pasifken veri hattını takip ediyoruz fakat
        # docking için detected=True üretilmesine izin vermiyoruz.
        if not self.enabled:

            self.filtered_state = False
            self.hit_count = 0
            self.miss_count = 0

            self._publish_detected()
            return

        raw_state = bool(msg.data)

        if self.active_low:
            detected = not raw_state
        else:
            detected = raw_state

        # --------------------------------------------------
        # HEDEF ALGILANIYOR
        # --------------------------------------------------

        if detected:

            self.hit_count += 1
            self.miss_count = 0

            if (
                not self.filtered_state
                and self.hit_count >= self.required_hits
            ):
                self.filtered_state = True

                self.get_logger().info(
                    'Proximity target detected'
                )

        # --------------------------------------------------
        # HEDEF ALGILANMIYOR
        # --------------------------------------------------

        else:

            self.miss_count += 1
            self.hit_count = 0

            if (
                self.filtered_state
                and self.miss_count >= self.required_misses
            ):
                self.filtered_state = False

                self.get_logger().info(
                    'Proximity target cleared'
                )

        self._publish_detected()

    # ------------------------------------------------------
    # BAĞLANTI / TIMEOUT KONTROLÜ
    # ------------------------------------------------------

    def _timer_callback(self):

        now = time.monotonic()

        if self.last_message_time is None:
            alive = False

        else:
            elapsed = now - self.last_message_time

            alive = (
                elapsed <= self.sensor_timeout_sec
            )

        # --------------------------------------------------
        # ALIVE DURUM DEĞİŞİMİ
        # --------------------------------------------------

        if alive != self.previous_alive_state:

            if alive:

                self.get_logger().info(
                    'Proximity data online'
                )

            elif self.received_first_message:

                self.get_logger().warning(
                    'Proximity data timeout'
                )

            self.previous_alive_state = alive

        # --------------------------------------------------
        # VERİ AKIŞI KESİLDİYSE
        # --------------------------------------------------

        if not alive:

            self.filtered_state = False
            self.hit_count = 0
            self.miss_count = 0

        # --------------------------------------------------
        # ALIVE YAYINI
        # --------------------------------------------------

        alive_msg = Bool()
        alive_msg.data = alive

        self.alive_pub.publish(alive_msg)

        self._publish_detected()

    # ------------------------------------------------------
    # DETECTED YAYINI
    # ------------------------------------------------------

    def _publish_detected(self):

        detected_msg = Bool()
        detected_msg.data = self.filtered_state

        self.detected_pub.publish(detected_msg)


def main(args=None):

    rclpy.init(args=args)

    node = ProximityMonitorNode()

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