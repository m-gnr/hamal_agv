import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool


class ProximityMonitorNode(Node):

    def __init__(self):
        super().__init__('proximity_monitor')

        # --------------------------------------------------
        # PARAMETRELER
        # --------------------------------------------------

        # Hedef algılandı demek için gereken
        # ardışık pozitif sensör okuması
        self.declare_parameter('required_hits', 3)

        # Hedef artık algılanmıyor demek için gereken
        # ardışık negatif sensör okuması
        self.declare_parameter('required_misses', 3)

        # Bu süre boyunca yeni sensör verisi gelmezse
        # proximity veri hattı kullanılamıyor kabul edilir.
        self.declare_parameter('sensor_timeout_sec', 0.5)

        # Sensör çıkışı ters mantıkla çalışıyorsa True yapılır.
        #
        # False:
        #   hedef yok  -> False
        #   hedef var  -> True
        #
        # True:
        #   hedef yok  -> True
        #   hedef var  -> False
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

        # Filtrelenmiş hedef algılama sonucu
        self.filtered_state = False

        # Ardışık True / False sayaçları
        self.hit_count = 0
        self.miss_count = 0

        # En son ham proximity mesajının geldiği zaman
        self.last_message_time = None

        # Önceki veri-hattı durumu
        self.previous_alive_state = None

        # En az bir sensör mesajı alındı mı?
        self.received_first_message = False

        # --------------------------------------------------
        # SUBSCRIBER
        # --------------------------------------------------

        # Serial bridge tarafından yayınlanan ham proximity bilgisi
        self.create_subscription(
            Bool,
            '/proximity/raw',
            self._raw_callback,
            10
        )

        # --------------------------------------------------
        # PUBLISHER
        # --------------------------------------------------

        # Filtrelenmiş hedef algılama sonucu
        self.detected_pub = self.create_publisher(
            Bool,
            '/proximity/detected',
            10
        )

        # Proximity verisi düzenli olarak geliyor mu?
        self.alive_pub = self.create_publisher(
            Bool,
            '/proximity/alive',
            10
        )

        # --------------------------------------------------
        # TIMER
        # --------------------------------------------------

        # 10 Hz bağlantı / timeout kontrolü
        self.timer = self.create_timer(
            0.1,
            self._timer_callback
        )

        self.get_logger().info(
            'Proximity monitor started'
        )

    # ------------------------------------------------------
    # HAM PROXIMITY VERİSİ
    # ------------------------------------------------------

    def _raw_callback(self, msg: Bool):

        # Yeni veri geldiği zamanı kaydet
        self.last_message_time = time.monotonic()

        # Artık en az bir gerçek mesaj aldığımızı biliyoruz
        self.received_first_message = True

        raw_state = bool(msg.data)

        # Sensör çıkışı active-low ise mantığı ters çevir
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

            # Yeterli sayıda ardışık pozitif okuma geldiyse
            # hedefi doğrula.
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

            # Yeterli sayıda ardışık negatif okuma geldiyse
            # hedef artık yok kabul edilir.
            if (
                self.filtered_state
                and self.miss_count >= self.required_misses
            ):
                self.filtered_state = False

                self.get_logger().info(
                    'Proximity target cleared'
                )

        # Güncel filtrelenmiş sonucu yayınla
        self._publish_detected()

    # ------------------------------------------------------
    # BAĞLANTI / TIMEOUT KONTROLÜ
    # ------------------------------------------------------

    def _timer_callback(self):

        now = time.monotonic()

        # Daha önce hiç sensör verisi gelmediyse
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

                # Daha önce veri gelip daha sonra kesildiyse
                # gerçek bir timeout durumu var.
                self.get_logger().warning(
                    'Proximity data timeout'
                )

            self.previous_alive_state = alive

        # --------------------------------------------------
        # VERİ AKIŞI KESİLDİYSE
        # --------------------------------------------------

        if not alive:

            # Eski bir True bilgisinin bellekte kalmasını
            # kesin olarak engelle.
            self.filtered_state = False

            self.hit_count = 0
            self.miss_count = 0

        # --------------------------------------------------
        # ALIVE YAYINI
        # --------------------------------------------------

        alive_msg = Bool()
        alive_msg.data = alive

        self.alive_pub.publish(alive_msg)

        # Detected durumunu da düzenli olarak yayınla.
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