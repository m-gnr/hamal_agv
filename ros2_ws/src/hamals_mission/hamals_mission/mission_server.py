#!/usr/bin/env python3
"""HAMAL otonom gorev sunucusu.

Gorev akisi
-----------
     1. START'tan D1'e dogru git                      (Nav2)
        YOLDA QR GORURSE Nav2 hedefi iptal edilir ve dogrudan cizgi
        takibine gecilir. QR gorulmeden D1'e varilirsa robot orada
        SABIT DURUP QR bekler (yedek davranis).
     2. Forklari indir -> alt limit
     3. CIZGI TAKIBI ile line_distance_m kadar ilerle -> forklar palete girer
        (cizgi hic bulunamazsa duz surus yedegi devreye girer)
     4. Forklari kaldir -> ust limit, yuk alinir
     5. (istege bagli) paletten kisa geri cikis
     6. D2'ye git                                     (Nav2 -- D1'e UGRAMADAN)
     7. D2'de 5 saniye bekle                          (kapi)
     8. B2'ye git                                     (Nav2)
     9. Forklari indir -> palet birakilir
    10. B2'den D1'e kadar GERI GERI gel               (Nav2 DEGIL, TF olcumlu)
    11. START'a don                                   (Nav2)

Tasarim notlari
---------------
* QR, START -> D1 bacaginda DINLENIR. Okundugu anda Nav2 hedefi iptal edilir,
  robot durur ve palete cizgi takibiyle girer. Yuk alindiktan sonra QR bayragi
  kapanir; yol uzerindeki diger QR'lar gorevi etkilemez.
* Palete giris CIZGI TAKIBI iledir; gidilen mesafe TF'ten olculur (sure degil).
  Cizgi hic bulunamazsa duz surus yedegine dusulur (line_fallback_straight).
* Yuk alindiktan sonra D1'e UGRANMAZ, dogrudan D2'ye gidilir.
* BASLANGIC NOKTASI: RViz'den "2D Pose Estimate" ile verilen poz START kabul
  edilir (start_from_initial_pose). Robot gorev sonunda AYNI x/y ve AYNI ACI
  degerine doner. Hic poz verilmemisse gorev basladigi andaki TF pozu alinir;
  o da yoksa launch'taki sabit start_* degerleri kullanilir.
* B2 -> D1 donusu GERI GERI surustur: robot donmez, dumduz geri gelir. Mesafe
  TF ile olculur, hedefe (D1) olan uzaklik takip edilir. Sapmayi onlemek icin
  yon (yaw) sabit tutulur.
* D1, D2'nin GERISINDEDIR (START'a daha yakin): START -> D1 -> D2 (kapi) -> B2.
* Diger hedef noktalari (D1, D2, A1, B2) parametredir; sahada olculup
  mission.launch.py icinden girilir.
* A1 yalnizca gosterim icindir: robota "A1'e git" denmez, "2 m duz ilerle"
  denir. Panel haritada A1 isaretini bu koordinattan cizer.

Servisler
---------
    /hamal/start_mission    std_srvs/srv/Trigger
    /hamal/cancel_mission   std_srvs/srv/Trigger

Yayin
-----
    /hamal/mission_status   std_msgs/String   "ASAMA|aciklama" (panel okur)
"""

import math
import threading
from typing import Optional

import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.time import Time

from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped, Twist
from nav2_msgs.action import NavigateToPose

# Nav2 hiz siniri mesajI. Eski Nav2 surumlerinde bulunmayabilir; yoksa
# QR bacagi normal Nav2 hiziyla surulur ve log'a uyari dusulur.
try:
    from nav2_msgs.msg import SpeedLimit
except ImportError:                                    # pragma: no cover
    SpeedLimit = None
from std_msgs.msg import Bool, Int32, String
from std_srvs.srv import Trigger
from tf2_ros import Buffer, TransformListener

try:
    from hamals_interfaces.msg import ForkCommand, ForkState
    FORK_INTERFACES_AVAILABLE = True
except ImportError:  # pragma: no cover
    ForkCommand = ForkState = None
    FORK_INTERFACES_AVAILABLE = False


MISSION_VERSION = '0.5.0'

#: Firmware ForkError degerleri (hamals_fork/fork_states.py ile ayni).
FORK_ERRORS = {
    1: 'gecersiz komut',
    2: 'ust limit zaman asimi',
    3: 'alt limit zaman asimi',
    4: 'limit anahtari cakismasi (ikisi birden aktif)',
    5: 'MCU zaman asimi (komut tekrari kesildi)',
}


def yaw_to_quaternion(yaw_degrees: float):
    """Sadece z ekseni etrafinda donus; zemin araci icin yeterli."""
    half = math.radians(yaw_degrees) / 2.0
    return math.sin(half), math.cos(half)


class MissionServer(Node):

    def __init__(self) -> None:
        super().__init__('hamal_mission_server')

        # ---- hedef noktalar --------------------------------------------
        # Hepsi sahada olculup mission.launch.py icinden girilir.
        # A1 yalnizca panelde gostermek icin; robot oraya "2 m duz ilerle"
        # komutuyla gider, Nav2 hedefi olarak kullanilmaz.
        for name, (x, y, yaw) in {
            'start': (0.50, -1.18, 89.9),   # yedek; normalde RViz pozu kullanilir
            'd1': (0.18, 0.28, 84.6),
            'd2': (1.95, 0.07, -3.1),
            'a1': (0.23, 1.39, 85.6),
            'b2': (3.83, 0.06, -5.8),
        }.items():
            self.declare_parameter(f'{name}_x', x)
            self.declare_parameter(f'{name}_y', y)
            self.declare_parameter(f'{name}_yaw_deg', yaw)

        self.declare_parameter('map_frame', 'map')
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('nav_action', '/navigate_to_pose')
        self.declare_parameter('nav_timeout_sec', 300.0)
        self.declare_parameter('cmd_vel_topic', '/cmd_vel')

        # ---- QR --------------------------------------------------------
        self.declare_parameter('qr_detected_topic', '/qr/detected')
        self.declare_parameter('qr_text_topic', '/qr/text')
        # Robot D1'de hareketsiz bekler; kare net oldugu icin okuma sorunsuzdur.
        self.declare_parameter('qr_wait_sec', 60.0)
        self.declare_parameter('qr_settle_sec', 0.5)

        # ---- QR yolda izleme -------------------------------------------
        # true: START -> D1 bacaginda QR dinlenir; okununca Nav2 hedefi iptal
        # edilip dogrudan cizgi takibine gecilir.
        self.declare_parameter('qr_watch_on_route', True)

        # QR ararken robot YAVAS gitmeli: QR cozuculer hareket bulanikligina
        # duyarli. Bu bacak Nav2 ile suruldugu icin hizi mission_server degil
        # Nav2 belirler; asagidaki yuzde Nav2'ye /speed_limit ile bildirilir
        # (100 = sinir yok). Bacak bitince otomatik 100'e donulur.
        self.declare_parameter('qr_speed_limit_pct', 25.0)
        self.declare_parameter('speed_limit_topic', '/speed_limit')

        # ---- CIZGI TAKIBI (palete giris) -------------------------------
        self.declare_parameter('line_error_topic', '/line/error')
        self.declare_parameter('line_detected_topic', '/line/detected')
        # Cizgi takibiyle gidilecek mesafe. Mesafe TF'ten olculur, sureyle degil.
        self.declare_parameter('line_distance_m', 1.67)
        self.declare_parameter('line_speed', 0.10)   # palete giris hizi
        # /line/error 640x480 uzayinda piksel. Sahada ayarlanan degerler:
        self.declare_parameter('line_gain', 0.0020)
        self.declare_parameter('line_deadband_px', 18.0)   # merkeze yakin kucuk hatalari yok say
        self.declare_parameter('line_smoothing', 0.25)     # 0-1, kucuk = daha yumusak
        self.declare_parameter('line_max_turn', 0.35)      # rad/s tavan
        self.declare_parameter('line_invert', False)       # ters donuyorsa true
        self.declare_parameter('line_wait_s', 3.0)         # baslangicta cizgi arama suresi
        self.declare_parameter('line_lost_s', 1.5)         # bu kadar goremezse duz devam
        # Cizgi hic bulunamazsa duz surusle devam edilsin mi?
        self.declare_parameter('line_fallback_straight', True)

        # ---- duz surus mesafeleri --------------------------------------
        # Cizgi bulunamazsa palete duz surusle girilir.
        self.declare_parameter('pickup_forward_m', 2.0)
        # Yuk alindiktan sonra paletten geri cikis. 0 = kapali (dogrudan D2).
        # Nav2 palet alaninda donmekte zorlanirsa 0.8-1.2 arasi bir deger verin.
        self.declare_parameter('pickup_reverse_m', 0.0)
        self.declare_parameter('dropoff_reverse_m', 2.0)    # B2'den geri cikma (sabit mesafe modu)
        self.declare_parameter('straight_speed', 0.30)      # m/s

        # ---- B2 -> D1 GERI GERI DONUS -------------------------------------
        # true  : B2'den D1'e kadar geri geri gelinir; mesafe TF ile olculur,
        #         hedefe olan uzaklik takip edilir (dropoff_reverse_m yok sayilir).
        # false : yalnizca dropoff_reverse_m kadar geri cikilir, sonra Nav2.
        self.declare_parameter('dropoff_reverse_to_d1', False)
        self.declare_parameter('reverse_tolerance_m', 0.20)   # D1'e bu kadar yaklasinca dur
        self.declare_parameter('reverse_max_m', 2.5)          # guvenlik: azami geri mesafe
        # Uzun geri suruste tekerlek farki sapma yapar; robot hatta tutulur.
        self.declare_parameter('reverse_yaw_hold', True)
        self.declare_parameter('reverse_yaw_gain', 1.0)       # yon hatasi kazanci
        self.declare_parameter('reverse_cross_gain', 1.2)     # yanal sapma kazanci
        self.declare_parameter('reverse_max_turn', 0.20)      # rad/s tavan
        self.declare_parameter('d1_stop_sec', 1.0)          # D1'e varinca duraklama
        self.declare_parameter('d2_wait_sec', 5.0)          # D2'de kapi beklemesi

        # ---- fork ------------------------------------------------------
        self.declare_parameter('fork_enabled', True)
        self.declare_parameter('fork_command_topic', '/fork/cmd')
        self.declare_parameter('fork_state_topic', '/fork/state')
        # Firmware her hareketi 8 sn sonunda kesiyor; sayaci STOP+yon ikilisiyle
        # periyodik sifirlayarak limit anahtarina kadar calismasini sagliyoruz.
        self.declare_parameter('fork_rearm_sec', 6.5)
        self.declare_parameter('fork_max_rearm', 8)
        self.declare_parameter('fork_wait_sec', 60.0)
        self.declare_parameter('fork_settle_sec', 0.5)

        # ---- baslangic pozu --------------------------------------------
        self.declare_parameter('initial_pose_topic', '/initialpose')
        self.declare_parameter('auto_set_initial_pose', False)
        self.declare_parameter('initial_pose_delay_sec', 3.0)
        # true: RViz'den "2D Pose Estimate" ile verilen poz START kabul edilir
        # ve gorev sonunda robot AYNI x/y/aciya dondurulur. Poz hic verilmemisse
        # gorev basladigi andaki TF pozu alinir, o da yoksa sabit start_* kullanilir.
        self.declare_parameter('start_from_initial_pose', True)

        self.map_frame = str(self.get_parameter('map_frame').value)
        self.base_frame = str(self.get_parameter('base_frame').value)

        self._lock = threading.Lock()
        self._running = False
        self._cancel_requested = False
        self._goal_handle = None
        self._worker: Optional[threading.Thread] = None

        # QR: yalnizca bekleme asamasindaki ilk okuma dikkate alinir.
        self._qr_armed = False
        self._qr_seen = False
        self._qr_text = ''
        self._fork_state = None

        # Cizgi takibi durumu
        self._line_error = 0.0
        self._line_detected = False
        self._line_last_seen = 0.0

        # RViz'den gelen baslangic pozu (x, y, yaw_derece) ve gorevde kullanilan
        # kesinlesmis START pozu.
        self._rviz_start_pose = None
        self._active_start_pose = None

        group = ReentrantCallbackGroup()
        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)

        self.status_publisher = self.create_publisher(String, '/hamal/mission_status', 10)
        self.cmd_vel_publisher = self.create_publisher(
            Twist, str(self.get_parameter('cmd_vel_topic').value), 10
        )
        self.nav_client = ActionClient(
            self, NavigateToPose, str(self.get_parameter('nav_action').value),
            callback_group=group,
        )

        self.create_subscription(
            Bool, str(self.get_parameter('qr_detected_topic').value),
            self._qr_detected_callback, 10, callback_group=group,
        )
        self.create_subscription(
            String, str(self.get_parameter('qr_text_topic').value),
            self._qr_text_callback, 10, callback_group=group,
        )
        self.create_subscription(
            Int32, str(self.get_parameter('line_error_topic').value),
            self._line_error_callback, 10, callback_group=group,
        )
        self.create_subscription(
            Bool, str(self.get_parameter('line_detected_topic').value),
            self._line_detected_callback, 10, callback_group=group,
        )

        self.fork_publisher = None
        if FORK_INTERFACES_AVAILABLE:
            self.fork_publisher = self.create_publisher(
                ForkCommand, str(self.get_parameter('fork_command_topic').value), 10
            )
            self.create_subscription(
                ForkState, str(self.get_parameter('fork_state_topic').value),
                self._fork_state_callback, 10, callback_group=group,
            )
        else:
            self.get_logger().warning(
                'hamals_interfaces bulunamadi; fork adimlari atlanacak.'
            )

        # Nav2 hiz siniri yayincisi (QR bacaginda yavaslatmak icin).
        self.speed_limit_publisher = None
        limit_topic = str(self.get_parameter('speed_limit_topic').value).strip()
        if SpeedLimit is not None and limit_topic:
            self.speed_limit_publisher = self.create_publisher(
                SpeedLimit, limit_topic, 10)
        elif SpeedLimit is None:
            self.get_logger().warning(
                'nav2_msgs/SpeedLimit bulunamadi -- QR bacagi Nav2\'nin normal '
                'hiziyla surulecek. Yavaslatmak icin nav2_params.yaml icindeki '
                'max_vel_x degerini dusurun.')

        topic = str(self.get_parameter('initial_pose_topic').value).strip()
        self.initial_pose_publisher = None
        if topic:
            self.initial_pose_publisher = self.create_publisher(
                PoseWithCovarianceStamped, topic, 10
            )
            # RViz'den verilen poz START olarak kaydedilir.
            self.create_subscription(
                PoseWithCovarianceStamped, topic,
                self._initial_pose_callback, 10, callback_group=group,
            )
            if bool(self.get_parameter('auto_set_initial_pose').value):
                self._initial_pose_timer = self.create_timer(
                    float(self.get_parameter('initial_pose_delay_sec').value),
                    self._publish_initial_pose_once, callback_group=group,
                )

        self.create_service(Trigger, '/hamal/start_mission', self.start_callback,
                            callback_group=group)
        self.create_service(Trigger, '/hamal/cancel_mission', self.cancel_callback,
                            callback_group=group)

        self._log_configuration()

    # ---------------------------------------------------------------- kurulum
    def _log_configuration(self) -> None:
        self.get_logger().info(f'HAMAL gorev sunucusu hazir (surum {MISSION_VERSION}).')
        if bool(self.get_parameter('start_from_initial_pose').value):
            self.get_logger().info(
                '  START: RViz "2D Pose Estimate" pozu kullanilacak '
                '(asagidaki sabit start_* yalnizca yedek).')
        for label in ('start', 'd1', 'a1', 'd2', 'b2'):
            x, y, yaw = self._waypoint(label)
            note = '  (yalnizca gosterim -- 2 m duz surusle gidilir)' if label == 'a1' else ''
            self.get_logger().info(
                f'  {label.upper():5s}: x={x:.2f} y={y:.2f} yaw={yaw:.1f}{note}'
            )
        if bool(self.get_parameter('dropoff_reverse_to_d1').value):
            donus = ('B2 -> birak -> D1\'e kadar GERI GERI '
                     f'(tolerans {self.get_parameter("reverse_tolerance_m").value} m, '
                     f'tavan {self.get_parameter("reverse_max_m").value} m) -> START')
        else:
            donus = (f'B2 -> birak -> {self.get_parameter("dropoff_reverse_m").value} m '
                     'geri -> D1 -> START')
        qr_mode = ('yolda QR dinlenir'
                   if bool(self.get_parameter('qr_watch_on_route').value)
                   else 'yalnizca D1\'de QR beklenir')
        back_out = float(self.get_parameter('pickup_reverse_m').value)
        cikis = f'{back_out:.2f} m geri -> ' if back_out > 0 else ''
        self.get_logger().info(
            f'  Akis: START -> D1 ({qr_mode}) -> forklar in -> '
            f'CIZGI TAKIBI {self.get_parameter("line_distance_m").value} m -> '
            f'forklar kalk -> {cikis}D2 '
            f'({self.get_parameter("d2_wait_sec").value} sn) -> ' + donus
        )
        self.get_logger().info(
            f'  Cizgi: hiz {self.get_parameter("line_speed").value} m/s, '
            f'kazanc {self.get_parameter("line_gain").value}, '
            f'olu bant {self.get_parameter("line_deadband_px").value} px, '
            f'ters {self.get_parameter("line_invert").value}')
        if bool(self.get_parameter('qr_watch_on_route').value):
            pct = float(self.get_parameter('qr_speed_limit_pct').value)
            if self.speed_limit_publisher is not None:
                self.get_logger().info(
                    f'  QR bacagi: Nav2 hizi %{pct:.0f} ile sinirlanacak, '
                    'bacak bitince %100\'e donulecek.')
            else:
                self.get_logger().warning(
                    '  QR bacagi: hiz siniri YAYINLANAMIYOR (SpeedLimit yok); '
                    'yavaslatmak icin nav2_params.yaml max_vel_x dusurun.')
        if not bool(self.get_parameter('fork_enabled').value):
            self.get_logger().warning('  FORK KAPALI: fork adimlari atlanacak.')
        self.get_logger().info(
            f'  Duz surus hizi: {self.get_parameter("straight_speed").value} m/s'
        )
        self.get_logger().info(
            '  Baslat: ros2 service call /hamal/start_mission std_srvs/srv/Trigger "{}"'
        )

    def _waypoint(self, prefix: str):
        return (
            float(self.get_parameter(f'{prefix}_x').value),
            float(self.get_parameter(f'{prefix}_y').value),
            float(self.get_parameter(f'{prefix}_yaw_deg').value),
        )

    def _publish_initial_pose_once(self) -> None:
        self._initial_pose_timer.cancel()
        x, y, yaw_deg = self._waypoint('start')
        message = PoseWithCovarianceStamped()
        message.header.frame_id = self.map_frame
        message.header.stamp = self.get_clock().now().to_msg()
        message.pose.pose.position.x = x
        message.pose.pose.position.y = y
        z, w = yaw_to_quaternion(yaw_deg)
        message.pose.pose.orientation.z = z
        message.pose.pose.orientation.w = w
        # RViz'in "2D Pose Estimate" ile kullandigi varsayilan belirsizlikler.
        message.pose.covariance[0] = 0.25
        message.pose.covariance[7] = 0.25
        message.pose.covariance[35] = 0.068
        self.initial_pose_publisher.publish(message)
        self.get_logger().info(
            f'Baslangic pozu otomatik verildi: x={x:.2f} y={y:.2f} yaw={yaw_deg:.1f}. '
            'Robot bu noktada degilse RViz\'den duzeltin.'
        )

    # -------------------------------------------------------------- callbackler
    def _qr_detected_callback(self, msg: Bool) -> None:
        # Yalnizca D1'de beklerken dikkate alinir; yol uzerindeki diger QR'lar
        # gorevi bozmasin diye bayrak kullanilir.
        if msg.data and self._qr_armed:
            self._qr_seen = True

    def _qr_text_callback(self, msg: String) -> None:
        if self._qr_armed:
            self._qr_text = str(msg.data)

    def _fork_state_callback(self, msg) -> None:
        self._fork_state = msg

    def _line_error_callback(self, msg: Int32) -> None:
        # /line/error: 640x480 uzayinda piksel. 0 = cizgi tam merkezde.
        self._line_error = float(msg.data)

    def _line_detected_callback(self, msg: Bool) -> None:
        self._line_detected = bool(msg.data)
        if self._line_detected:
            self._line_last_seen = self.now()

    def _set_nav_speed_limit(self, percent: float) -> None:
        """Nav2'ye yuzde cinsinden hiz siniri bildirir (100 = sinir yok).

        QR cozuculer hareket bulanikligina duyarli oldugu icin QR aranan
        bacakta robot yavaslatilir. Bacak bitince 100'e donulur -- aksi halde
        gorevin geri kalani da yavas kalir.
        """
        if self.speed_limit_publisher is None:
            return
        percent = max(0.0, min(100.0, float(percent)))
        msg = SpeedLimit()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = str(self.get_parameter('map_frame').value)
        msg.percentage = True
        msg.speed_limit = percent
        self.speed_limit_publisher.publish(msg)
        self.get_logger().info(f'Nav2 hiz siniri: %{percent:.0f}')

    def _initial_pose_callback(self, msg: PoseWithCovarianceStamped) -> None:
        """RViz "2D Pose Estimate" ile verilen pozu START olarak kaydeder."""
        position = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = math.degrees(2.0 * math.atan2(q.z, q.w))
        yaw = (yaw + 180.0) % 360.0 - 180.0
        self._rviz_start_pose = (float(position.x), float(position.y), yaw)
        self.get_logger().info(
            f'Baslangic pozu alindi (RViz): x={position.x:.2f} y={position.y:.2f} '
            f'yaw={yaw:.1f} -- gorev sonunda robot buraya donecek.'
        )

    def _resolve_start_pose(self):
        """START pozunu belirler: RViz pozu > anlik TF pozu > sabit parametre."""
        if bool(self.get_parameter('start_from_initial_pose').value):
            if self._rviz_start_pose is not None:
                x, y, yaw = self._rviz_start_pose
                self.get_logger().info(
                    f'START = RViz pozu (x={x:.2f} y={y:.2f} yaw={yaw:.1f})')
                return self._rviz_start_pose
            pose = self.robot_pose()
            if pose is not None:
                self.get_logger().warning(
                    'RViz pozu gelmedi; START olarak robotun SU ANKI konumu '
                    f'aliniyor (x={pose[0]:.2f} y={pose[1]:.2f} yaw={pose[2]:.1f}).')
                return pose
            self.get_logger().warning(
                'RViz pozu da TF de yok; launch\'taki sabit start_* kullanilacak.')
        return self._waypoint('start')

    # -------------------------------------------------------------- yardimcilar
    def now(self) -> float:
        return self.get_clock().now().nanoseconds / 1e9

    def status(self, stage: str, message: str) -> None:
        self.status_publisher.publish(String(data=f'{stage}|{message}'))
        self.get_logger().info(f'[{stage}] {message}')

    def robot_pose(self):
        """map cercevesinde robotun (x, y, yaw_derece) konumu."""
        for frame in (self.base_frame, 'base_footprint', 'base_link'):
            try:
                transform = self._tf_buffer.lookup_transform(self.map_frame, frame, Time())
            except Exception:  # noqa: BLE001  (TF henuz hazir degil)
                continue
            t = transform.transform.translation
            q = transform.transform.rotation
            yaw = math.degrees(2.0 * math.atan2(q.z, q.w))
            return float(t.x), float(t.y), (yaw + 180.0) % 360.0 - 180.0
        return None

    def stop_robot(self) -> None:
        self.cmd_vel_publisher.publish(Twist())

    def _sleep(self, seconds: float) -> bool:
        """Beklerken iptal kontrolu yapar. Iptal edildiyse True doner."""
        steps = max(1, int(seconds / 0.1))
        for _ in range(steps):
            if self._cancel_requested or not rclpy.ok():
                return True
            threading.Event().wait(0.1)
        return False

    def _wait_future(self, future, timeout_sec: float) -> bool:
        deadline = self.now() + timeout_sec
        while rclpy.ok():
            if future.done():
                return True
            if self._cancel_requested or self.now() > deadline:
                return False
            threading.Event().wait(0.1)
        return False

    # ----------------------------------------------------------------- servisler
    def start_callback(self, request, response):
        del request
        with self._lock:
            if self._running:
                response.success = False
                response.message = 'Gorev zaten calisiyor.'
                return response
            if not self.nav_client.wait_for_server(timeout_sec=3.0):
                response.success = False
                response.message = 'Nav2 navigate_to_pose sunucusu bulunamadi.'
                self.get_logger().error(response.message)
                return response
            self._running = True
            self._cancel_requested = False

        self._worker = threading.Thread(target=self._run_mission, daemon=True)
        self._worker.start()
        response.success = True
        response.message = 'Gorev baslatildi.'
        return response

    def cancel_callback(self, request, response):
        del request
        with self._lock:
            if not self._running:
                response.success = False
                response.message = 'Calisan gorev yok.'
                return response
            self._cancel_requested = True
            goal_handle = self._goal_handle

        if goal_handle is not None:
            goal_handle.cancel_goal_async()
        self.stop_robot()
        self._stop_fork()
        self.status('IPTAL', 'Gorev iptal ediliyor...')
        response.success = True
        response.message = 'Iptal istegi gonderildi.'
        return response

    # --------------------------------------------------------------------- gorev
    def _run_mission(self) -> None:
        try:
            forward = float(self.get_parameter('pickup_forward_m').value)
            back = float(self.get_parameter('pickup_reverse_m').value)
            drop_back = float(self.get_parameter('dropoff_reverse_m').value)

            # 0. START pozunu sabitle. RViz'den verilen poz varsa o kullanilir;
            #    gorev sonunda robot AYNI x/y ve AYNI aciya dondurulur.
            self._active_start_pose = self._resolve_start_pose()
            sx, sy, syaw = self._active_start_pose
            self.status('BASLADI',
                        f'Gorev basladi. Donus noktasi: x={sx:.2f} y={sy:.2f} '
                        f'yaw={syaw:.1f}')

            # 1. START -> D1. Yolda QR gorursek Nav2 hedefi birakilir.
            watch = bool(self.get_parameter('qr_watch_on_route').value)
            self._qr_seen = False
            self._qr_text = ''
            self._qr_armed = True          # QR artik YOLDA da dinleniyor
            try:
                # QR okunabilsin diye bu bacakta Nav2 yavaslatilir.
                if watch:
                    self._set_nav_speed_limit(
                        float(self.get_parameter('qr_speed_limit_pct').value))
                result = self._go_to('D1', self._waypoint('d1'),
                                     abort_on_qr=watch)
                if result is False:
                    return

                if result == 'ARRIVED':
                    # QR yolda gorulmedi -> yedek davranis: D1'de sabit durup bekle.
                    pause = float(self.get_parameter('d1_stop_sec').value)
                    if pause > 0 and self._sleep(pause):
                        self.status('IPTAL', 'D1\'de beklerken iptal edildi.')
                        return
                    if not self._wait_for_qr():
                        return
            finally:
                # Buradan sonraki QR'lar (yol uzerindekiler) yok sayilir ve
                # gorevin kalani normal hizda surulur.
                self._qr_armed = False
                self._set_nav_speed_limit(100.0)

            # 2. Forklari indir
            if not self._move_fork('asagi', 'FORK_INDIR', 'Forklar indiriliyor'):
                return

            # 3. CIZGI TAKIBI ile palete gir
            line_distance = float(self.get_parameter('line_distance_m').value)
            if not self._follow_line(
                    line_distance, 'CIZGI',
                    f'Cizgi takibiyle {line_distance:.2f} m ilerleniyor'):
                return

            # 4. Yuku kaldir
            if not self._move_fork('yukari', 'FORK_KALDIR',
                                   'Forklar kaldiriliyor, yuk aliniyor'):
                return

            # 5. Paletten kisa geri cikis (0 = kapali, dogrudan D2'ye gidilir).
            #    Nav2 palet alaninda donmekte zorlanirsa bu degeri buyutun.
            back_out = float(self.get_parameter('pickup_reverse_m').value)
            if back_out > 0:
                if not self._drive_straight(
                        -back_out, 'GERI_PALET',
                        f'Paletten {back_out:.2f} m geri cikiliyor'):
                    return

            # 6-7. D1'e UGRAMADAN dogrudan D2'ye git ve bekle
            if not self._go_to('D2', self._waypoint('d2')):
                return
            wait = float(self.get_parameter('d2_wait_sec').value)
            self.status('D2_BEKLE', f'D2\'de bekleniyor ({wait:.0f} sn)')
            if self._sleep(wait):
                self.status('IPTAL', 'D2\'de beklerken iptal edildi.')
                return

            # 9. B2'ye git
            if not self._go_to('B2', self._waypoint('b2')):
                return

            # 10. Yuku birak
            if not self._move_fork('asagi', 'FORK_BIRAK',
                                   'Forklar indiriliyor, yuk birakiliyor'):
                return

            # 11. B2'den D1'e kadar GERI GERI gel (donmeden, TF olcumlu)
            if bool(self.get_parameter('dropoff_reverse_to_d1').value):
                if not self._drive_reverse_to(self._waypoint('d1'), 'GERI_CIK',
                                              'B2\'den D1\'e geri geri geliniyor'):
                    return
                self.status('VARDI_D1_DONUS', 'D1\'e geri gelindi.')
            else:
                if not self._drive_straight(-drop_back, 'GERI_CIK',
                                            f'{drop_back:.1f} m geri cikiliyor'):
                    return
                if not self._go_to('D1', self._waypoint('d1'), stage='D1_DONUS'):
                    return

            # 12. START'a don -- RViz'den verilen poza, ayni aciyla
            if not self._go_to('START', self._active_start_pose):
                return

            self.status('TAMAMLANDI', 'Gorev basariyla tamamlandi.')

        except Exception as error:  # noqa: BLE001
            self.stop_robot()
            self._stop_fork()
            self.status('HATA', f'Gorev hatasi: {error}')
            self.get_logger().exception('Gorev sirasinda beklenmeyen hata')
        finally:
            self.stop_robot()
            # Gorev nasil biterse bitsin (hata/iptal dahil) Nav2 hiz sinirini
            # birak; aksi halde sonraki gorev de yavas kalir.
            self._set_nav_speed_limit(100.0)
            with self._lock:
                self._running = False
                self._goal_handle = None

    # --------------------------------------------------------------- QR bekleme
    def _wait_for_qr(self) -> bool:
        """D1'de hareketsiz bekleyip QR'in okunmasini bekler.

        Robot durdugu icin kamera net kare verir; hareket bulanikligi sorunu
        yasanmaz. Bu asamadan sonra bayrak kapatilir, yol uzerindeki diger
        QR'lar gorevi etkilemez.
        """
        self._qr_seen = False
        self._qr_text = ''
        self._qr_armed = True
        try:
            timeout = float(self.get_parameter('qr_wait_sec').value)
            self.status('BEKLIYOR_QR', f'D1\'de QR bekleniyor ({timeout:.0f} sn)')

            deadline = self.now() + timeout
            while rclpy.ok():
                if self._cancel_requested:
                    self.status('IPTAL', 'QR beklenirken iptal edildi.')
                    return False
                if self._qr_seen:
                    label = f' ("{self._qr_text}")' if self._qr_text else ''
                    self.status('QR_BULUNDU', f'QR okundu{label}.')
                    self._sleep(float(self.get_parameter('qr_settle_sec').value))
                    return True
                if self.now() > deadline:
                    break
                threading.Event().wait(0.1)

            self.status('HATA', 'QR okunamadi. Kamera ve QR node calisiyor mu?')
            return False
        finally:
            self._qr_armed = False

    # ------------------------------------------------------------------- Nav2
    def _send_goal(self, name: str, x: float, y: float, yaw_deg: float):
        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = self.map_frame
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = x
        goal.pose.pose.position.y = y
        z, w = yaw_to_quaternion(yaw_deg)
        goal.pose.pose.orientation.z = z
        goal.pose.pose.orientation.w = w

        send_future = self.nav_client.send_goal_async(goal)
        if not self._wait_future(send_future, 15.0):
            self.status('HATA', f'{name} hedefi gonderilemedi (zaman asimi).')
            return None
        goal_handle = send_future.result()
        if goal_handle is None or not goal_handle.accepted:
            self.status('HATA', f'{name} hedefi Nav2 tarafindan reddedildi.')
            return None
        with self._lock:
            self._goal_handle = goal_handle
        return goal_handle

    def _go_to(self, name: str, waypoint, stage: str = None,
               abort_on_qr: bool = False):
        """Nav2 ile hedefe gider.

        stage verilirse asama adi olarak o kullanilir. Ayni noktaya gorevin iki
        farkli bacaginda gidildiginde (D1: once gidis, sonra donus) panelin
        ilerlemeyi geri sarmamasi icin gereklidir.

        abort_on_qr=True ise yol boyunca QR dinlenir; okundugu anda Nav2 hedefi
        iptal edilir, robot durur ve 'QR' dondurulur. Donus degerleri:
            'ARRIVED' -> hedefe ulasildi
            'QR'      -> yolda QR okundu, hedef iptal edildi
            False     -> hata veya iptal
        """
        x, y, yaw_deg = waypoint
        going = f'GIDIYOR_{stage or name}'
        arrived = f'VARDI_{stage or name}'
        self.status(going, f'{name} noktasina gidiliyor (x={x:.2f} y={y:.2f})')

        goal_handle = self._send_goal(name, x, y, yaw_deg)
        if goal_handle is None:
            return False

        result_future = goal_handle.get_result_async()
        timeout = float(self.get_parameter('nav_timeout_sec').value)
        deadline = self.now() + timeout
        while rclpy.ok():
            if result_future.done():
                break
            # Yolda QR gorulduyse hedefi birak, cizgi takibine gecilecek.
            if abort_on_qr and self._qr_seen:
                goal_handle.cancel_goal_async()
                self.stop_robot()
                label = f' ("{self._qr_text}")' if self._qr_text else ''
                self.status('QR_BULUNDU',
                            f'Yolda QR okundu{label}; {name} hedefi birakildi.')
                self._sleep(float(self.get_parameter('qr_settle_sec').value))
                return 'QR'
            if self._cancel_requested or self.now() > deadline:
                goal_handle.cancel_goal_async()
                self.stop_robot()
                if self._cancel_requested:
                    self.status('IPTAL', 'Gorev iptal edildi.')
                else:
                    self.status('HATA', f'{name} hedefi zaman asimina ugradi.')
                return False
            threading.Event().wait(0.1)

        status_code = getattr(result_future.result(), 'status', 4)
        if status_code != 4:                   # 4 = SUCCEEDED
            self.status('HATA', f'{name} hedefine ulasilamadi (Nav2 durum {status_code}).')
            return False

        self.status(arrived, f'{name} noktasina ulasildi.')
        return 'ARRIVED'

    # ------------------------------------------------------------- duz surus
    def _travelled(self, origin) -> float:
        pose = self.robot_pose()
        if pose is None:
            return 0.0
        return math.hypot(pose[0] - origin[0], pose[1] - origin[1])

    def _drive_straight(self, distance_m: float, stage: str, message: str) -> bool:
        """Duz ileri/geri surer; mesafe TF ile olculur.

        distance_m negatifse geri gidilir. Nav2 kullanilmaz: robot zaten dogru
        yone bakiyor ve gidilecek yol duz. Boylece hiz ve mesafe tamamen
        buradan kontrol edilir, gereksiz hizalanma donusu olmaz.
        """
        if self._cancel_requested:
            return False

        origin = self.robot_pose()
        if origin is None:
            self.status('HATA', 'Robot konumu okunamadi (TF yok).')
            return False

        self.status(stage, message)
        speed = abs(float(self.get_parameter('straight_speed').value))
        target = abs(distance_m)
        hold_yaw = bool(self.get_parameter('reverse_yaw_hold').value)
        target_yaw = origin[2]

        command = Twist()
        command.linear.x = speed if distance_m >= 0 else -speed

        # Mesafe + guvenlik zaman asimi (beklenen surenin iki kati).
        deadline = self.now() + max(15.0, (target / max(speed, 0.01)) * 2.0)
        next_log = self.now() + 2.0
        try:
            while rclpy.ok():
                if self._cancel_requested:
                    self.status('IPTAL', 'Surus sirasinda iptal edildi.')
                    return False
                pose = self.robot_pose()
                travelled = (
                    math.hypot(pose[0] - origin[0], pose[1] - origin[1])
                    if pose is not None else 0.0
                )
                if travelled >= target:
                    self.status(stage, f'{travelled:.2f} m gidildi.')
                    return True
                if self.now() > deadline:
                    self.status('HATA', f'Surus zaman asimi ({travelled:.2f} m gidildi).')
                    return False
                if self.now() >= next_log:
                    self.get_logger().info(
                        f'[{stage}] {travelled:.2f} / {target:.2f} m')
                    next_log = self.now() + 2.0
                command.angular.z = self._yaw_hold_turn(pose, target_yaw, hold_yaw)
                # Firmware komut kesilirse motorlari durdurur; surekli yayin sart.
                self.cmd_vel_publisher.publish(command)
                threading.Event().wait(0.05)
            return False
        finally:
            self.stop_robot()

    # --------------------------------------------------------- cizgi takibi
    def _follow_line(self, distance_m: float, stage: str, message: str) -> bool:
        """Cizgi takibiyle distance_m kadar ilerler.

        Gidilen mesafe TF'ten olculur (sure DEGIL) -- hiz kalibrasyonu yanlis
        olsa bile robot dogru mesafede durur.

        Kontrol basit oransal: /line/error piksel cinsinden sapma, kucuk
        hatalar olu bantla yok sayilir, cikis yumusatilir. Bu degerler sahada
        salinim yapmayacak sekilde ayarlanmisti; yalpalarsa line_gain kucultun.

        Cizgi hic bulunamazsa (line_wait_s icinde) line_fallback_straight
        acikken duz surusle devam edilir. Yol ortasinda kaybolursa robot
        donmeyi birakip duz devam eder -- cunku kisa mesafede durmak, palete
        yarim girmis halde kalmaktan iyidir degil.
        """
        if self._cancel_requested:
            return False

        wait_s = float(self.get_parameter('line_wait_s').value)
        self.status(stage, message)

        # Cizginin gorunmesini bekle.
        deadline = self.now() + wait_s
        while rclpy.ok() and not self._line_detected:
            if self._cancel_requested:
                self.status('IPTAL', 'Cizgi beklenirken iptal edildi.')
                return False
            if self.now() > deadline:
                if bool(self.get_parameter('line_fallback_straight').value):
                    forward = float(self.get_parameter('pickup_forward_m').value)
                    self.get_logger().warning(
                        'Cizgi bulunamadi; duz surus yedegine geciliyor '
                        f'({forward:.2f} m). line_node calisiyor mu?')
                    return self._drive_straight(
                        forward, stage,
                        f'Cizgi yok -- {forward:.2f} m duz ilerleniyor')
                self.status('HATA', 'Cizgi bulunamadi. line_node calisiyor mu?')
                return False
            threading.Event().wait(0.05)

        origin = self.robot_pose()
        if origin is None:
            self.status('HATA', 'Robot konumu okunamadi (TF yok).')
            return False

        speed = abs(float(self.get_parameter('line_speed').value))
        gain = float(self.get_parameter('line_gain').value)
        deadband = abs(float(self.get_parameter('line_deadband_px').value))
        alpha = float(self.get_parameter('line_smoothing').value)
        turn_limit = abs(float(self.get_parameter('line_max_turn').value))
        invert = bool(self.get_parameter('line_invert').value)
        lost_s = float(self.get_parameter('line_lost_s').value)

        target = abs(distance_m)
        command = Twist()
        command.linear.x = speed
        turn_filtered = 0.0
        self._line_last_seen = self.now()
        # Guvenlik: beklenen surenin iki kati + 10 sn.
        safety = self.now() + (target / max(speed, 0.01)) * 2.0 + 10.0
        next_log = self.now() + 2.0
        warned_lost = False

        try:
            while rclpy.ok():
                if self._cancel_requested:
                    self.status('IPTAL', 'Cizgi takibi sirasinda iptal edildi.')
                    return False

                pose = self.robot_pose()
                travelled = (
                    math.hypot(pose[0] - origin[0], pose[1] - origin[1])
                    if pose is not None else 0.0
                )
                if travelled >= target:
                    self.status(stage, f'Cizgi takibiyle {travelled:.2f} m gidildi.')
                    return True
                if self.now() > safety:
                    self.status('HATA',
                                f'Cizgi takibi zaman asimi ({travelled:.2f} m gidildi).')
                    return False

                # Cizgi kaybolduysa donmeyi birak, duz devam et.
                line_fresh = (self.now() - self._line_last_seen) <= lost_s
                if line_fresh:
                    error = self._line_error
                    if abs(error) <= deadband:
                        error = 0.0
                    else:
                        error -= math.copysign(deadband, error)
                    raw = -gain * error
                    if invert:
                        raw = -raw
                    turn_filtered = alpha * raw + (1.0 - alpha) * turn_filtered
                    warned_lost = False
                else:
                    turn_filtered = 0.0
                    if not warned_lost:
                        self.get_logger().warning(
                            'Cizgi goruntuden cikti; duz devam ediliyor.')
                        warned_lost = True

                command.angular.z = max(-turn_limit, min(turn_limit, turn_filtered))
                if self.now() >= next_log:
                    self.get_logger().info(
                        f'[{stage}] cizgi: {travelled:.2f} / {target:.2f} m, '
                        f'hata {self._line_error:+.0f} px, '
                        f'donus {command.angular.z:+.3f} rad/s')
                    next_log = self.now() + 2.0

                self.cmd_vel_publisher.publish(command)
                threading.Event().wait(0.05)
            return False
        finally:
            self.stop_robot()

    # -------------------------------------------------- yon sabitleme + geri
    @staticmethod
    def _angle_diff(a_deg: float, b_deg: float) -> float:
        """a - b farkini -180..180 araligina indirger."""
        return (a_deg - b_deg + 180.0) % 360.0 - 180.0

    def _yaw_hold_turn(self, pose, target_yaw_deg: float, enabled: bool) -> float:
        """Robotun yonunu sabit tutmak icin gereken kucuk donus hizi.

        Uzun duz/geri suruste tekerlek farki yuzunden robot yavas yavas yana
        kayiyor. Bu oransal duzeltme yonu baslangictaki degerde tutar.
        """
        if not enabled or pose is None:
            return 0.0
        gain = float(self.get_parameter('reverse_yaw_gain').value)
        limit = abs(float(self.get_parameter('reverse_max_turn').value))
        error_rad = math.radians(self._angle_diff(target_yaw_deg, pose[2]))
        return max(-limit, min(limit, gain * error_rad))

    def _drive_reverse_to(self, target, stage: str, message: str) -> bool:
        """Hedef noktaya GERI GERI gider (robot donmez).

        Nav2 kullanilmaz: robot B2'de zaten D1'e sirtini donmus durumdadir.

        Durma karari SURE ile degil, TF'ten okunan gercek konumla verilir --
        boylece hiz kalibrasyonu yanlis olsa bile robot dogru noktada durur.

        Olcum, baslangic ile hedef arasindaki HAT UZERINDEKI ilerlemedir
        (duz cizgi uzakligi degil). Robot birkac santim yana kaysa bile
        "hedefi gectim" sanip erken durmaz.

        Yanal sapma (cross-track) ve yon hatasi kucuk bir donus komutuyla
        surekli duzeltilir; boylece 3-4 metrelik geri suruste robot hattan
        cikmaz.
        """
        if self._cancel_requested:
            return False

        origin = self.robot_pose()
        if origin is None:
            self.status('HATA', 'Robot konumu okunamadi (TF yok).')
            return False

        origin_x, origin_y = origin[0], origin[1]
        target_x, target_y = float(target[0]), float(target[1])
        length = math.hypot(target_x - origin_x, target_y - origin_y)

        tolerance = abs(float(self.get_parameter('reverse_tolerance_m').value))
        max_distance = abs(float(self.get_parameter('reverse_max_m').value))
        speed = abs(float(self.get_parameter('straight_speed').value))
        track_on = bool(self.get_parameter('reverse_yaw_hold').value)
        gain_cross = float(self.get_parameter('reverse_cross_gain').value)
        gain_yaw = float(self.get_parameter('reverse_yaw_gain').value)
        turn_limit = abs(float(self.get_parameter('reverse_max_turn').value))

        self.status(stage, f'{message} (hedefe {length:.2f} m)')
        if length <= tolerance:
            self.status(stage, 'Hedefe zaten yakin, geri surus atlandi.')
            return True
        if length > max_distance:
            self.status('HATA',
                        f'Hedef {length:.2f} m uzakta ama guvenlik tavani '
                        f'{max_distance:.2f} m. reverse_max_m degerini artirin.')
            return False

        # Hat yonu: baslangictan hedefe dogru birim vektor. Robot bu yonde
        # GERI gidecegi icin burnu bunun tam tersine bakmalidir.
        dir_x = (target_x - origin_x) / length
        dir_y = (target_y - origin_y) / length
        path_angle = math.degrees(math.atan2(dir_y, dir_x))
        desired_heading_base = path_angle + 180.0

        command = Twist()
        command.linear.x = -speed
        deadline = self.now() + max(30.0, (max_distance / max(speed, 0.01)) * 2.5)
        next_log = self.now() + 2.0
        progress = 0.0
        try:
            while rclpy.ok():
                if self._cancel_requested:
                    self.status('IPTAL', 'Geri surus sirasinda iptal edildi.')
                    return False

                pose = self.robot_pose()
                if pose is not None:
                    dx = pose[0] - origin_x
                    dy = pose[1] - origin_y
                    progress = dx * dir_x + dy * dir_y          # hat uzerinde
                    cross = dir_x * dy - dir_y * dx             # yanal sapma
                    travelled = math.hypot(dx, dy)

                    if progress >= length - tolerance:
                        self.status(
                            stage,
                            f'Hedefe ulasildi ({travelled:.2f} m geri gelindi, '
                            f'yanal sapma {cross:+.2f} m).')
                        return True
                    if progress > length + 0.15:
                        self.status(stage,
                                    f'Hedef gecildi, duruluyor ({travelled:.2f} m).')
                        return True
                    if travelled >= max_distance:
                        self.status('HATA',
                                    f'Guvenlik siniri: {travelled:.2f} m geri gidildi, '
                                    'hedefe ulasilamadi.')
                        return False
                    if self.now() >= next_log:
                        self.get_logger().info(
                            f'[{stage}] geri: {progress:.2f} / {length:.2f} m, '
                            f'yanal sapma {cross:+.2f} m')
                        next_log = self.now() + 2.0

                    if track_on:
                        # Yana kaydiysa hedef yonu biraz egerek hatta geri cek.
                        desired = desired_heading_base - math.degrees(gain_cross * cross)
                        error = math.radians(self._angle_diff(desired, pose[2]))
                        command.angular.z = max(-turn_limit,
                                                min(turn_limit, gain_yaw * error))
                    else:
                        command.angular.z = 0.0

                if self.now() > deadline:
                    self.status('HATA', 'Geri surus zaman asimi.')
                    return False

                self.cmd_vel_publisher.publish(command)
                threading.Event().wait(0.05)
            return False
        finally:
            self.stop_robot()

    # ------------------------------------------------------------------- fork
    def _fork_reached(self, direction: str) -> bool:
        state = self._fork_state
        if state is None:
            return False
        target = ForkState.AT_TOP if direction == 'yukari' else ForkState.AT_BOTTOM
        return int(state.state) == int(target)

    def _fork_error(self) -> int:
        state = self._fork_state
        return int(getattr(state, 'error_code', 0)) if state is not None else 0

    def _stop_fork(self) -> None:
        """Forku durdurur. STOP ayni zamanda ERROR durumunu temizler."""
        if self.fork_publisher is None:
            return
        for _ in range(3):
            self.fork_publisher.publish(ForkCommand(command=ForkCommand.STOP))

    def _send_fork(self, direction: str) -> None:
        """STOP + yon komutu: firmware'in hareket sayacini sifirlar."""
        move = ForkCommand.UP if direction == 'yukari' else ForkCommand.DOWN
        self.fork_publisher.publish(ForkCommand(command=ForkCommand.STOP))
        threading.Event().wait(0.12)
        self.fork_publisher.publish(ForkCommand(command=move))

    def _move_fork(self, direction: str, stage: str, message: str) -> bool:
        """Forku limit anahtarina kadar hareket ettirir.

        Firmware 8 saniyede bir hareketi kesip zaman asimi verdigi icin sayac
        dolmadan STOP+yon ikilisi gonderilerek sifirlanir.
        """
        if self._cancel_requested:
            return False

        fork_on = (
            bool(self.get_parameter('fork_enabled').value)
            and self.fork_publisher is not None
        )
        if not fork_on:
            self.status(stage, f'{message} -- ATLANDI (fork kapali)')
            return not self._sleep(1.0)

        self.status(stage, message)
        if self._fork_state is None:
            self.status('HATA', 'Fork durumu alinamiyor. fork_node calisiyor mu?')
            return False

        if self._fork_error():
            self._stop_fork()
            self._sleep(0.3)

        rearm_period = float(self.get_parameter('fork_rearm_sec').value)
        max_rearm = int(self.get_parameter('fork_max_rearm').value)
        total_timeout = float(self.get_parameter('fork_wait_sec').value)

        self._send_fork(direction)
        self._sleep(float(self.get_parameter('fork_settle_sec').value))

        deadline = self.now() + total_timeout
        next_rearm = self.now() + rearm_period
        rearm_count = 0

        while rclpy.ok():
            if self._cancel_requested:
                self._stop_fork()
                self.status('IPTAL', 'Fork hareketi sirasinda iptal edildi.')
                return False

            if self._fork_reached(direction):
                self._stop_fork()
                limit = 'ust' if direction == 'yukari' else 'alt'
                self.status(stage, f'Fork {limit} limite ulasti.')
                return True

            error_code = self._fork_error()
            # 2/3 = firmware'in kendi hareket zaman asimi; sayaci sifirlayip devam.
            if error_code in (2, 3):
                if rearm_count >= max_rearm:
                    self._stop_fork()
                    self.status('HATA',
                                'Fork limite ulasamadi; limit anahtarlarini kontrol edin.')
                    return False
                rearm_count += 1
                self._send_fork(direction)
                next_rearm = self.now() + rearm_period
            elif error_code:
                self._stop_fork()
                self.status('HATA', f'Fork hatasi: {FORK_ERRORS.get(error_code, error_code)}')
                return False

            if self.now() >= next_rearm:
                if rearm_count >= max_rearm:
                    self._stop_fork()
                    self.status('HATA',
                                'Fork limite ulasamadi; limit anahtarlarini kontrol edin.')
                    return False
                rearm_count += 1
                self._send_fork(direction)
                next_rearm = self.now() + rearm_period

            if self.now() > deadline:
                self._stop_fork()
                self.status('HATA', f'Fork {total_timeout:.0f} sn icinde limite ulasmadi.')
                return False

            threading.Event().wait(0.1)
        return False


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MissionServer()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.stop_robot()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()