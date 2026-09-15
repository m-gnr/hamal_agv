"""PLC bridge. transport=mock (test) | udp (resmi ek sartname).

UDP: PLC server 192.168.100.100:1515. Robot->PLC PAKET_TX (7B) 1 Hz,
PLC->Robot PAKET_RX (3B). 1 sn RX yoksa baglanti koptu.

PAKET_TX (<BBBhh): Byte0 durum(1-8), Byte1 alim(1-3), Byte2 birak(1-3),
  Byte3-4 X=int16(x*100), Byte5-6 Y=int16(y*100).
PAKET_RX: Byte0 alim, Byte1 birak, Byte2 kontrol(1 bekle, 2 basla/devam).

TX ve RX AYRI thread'ler (TX kesin 1 Hz; RX bloklamaz).
"""

import itertools
import socket
import struct
import threading
import time

import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger

from nav_msgs.msg import Odometry
from hamals_interfaces.msg import DoorEvent, MissionState, MissionTask, PlcState

PICKUP_TO_BYTE = {'A1': 1, 'A2': 2, 'A3': 3}
DROPOFF_TO_BYTE = {'B1': 1, 'B2': 2, 'B3': 3}
BYTE_TO_PICKUP = {1: 'A1', 2: 'A2', 3: 'A3'}
BYTE_TO_DROPOFF = {1: 'B1', 2: 'B2', 3: 'B3'}


class PlcBridgeNode(Node):
    def __init__(self):
        super().__init__('hamals_plc_bridge')
        self.declare_parameter('transport', 'mock')      # mock | udp
        self.declare_parameter('mock_pickup', 'A1')
        self.declare_parameter('mock_dropoff', 'B1')
        self.declare_parameter('auto_grant_door', True)
        self.declare_parameter('plc_ip', '192.168.100.100')
        self.declare_parameter('plc_port', 1515)
        self.declare_parameter('tx_rate_hz', 1.0)
        self.declare_parameter('rx_timeout_sec', 1.0)
        self.declare_parameter('pose_topic', '/odom')
        self.declare_parameter('door_id', 'MAIN_DOOR')

        self.counter = itertools.count(1)
        self.active_task_id = ''
        self.last_rx = ''
        self.last_tx = ''

        self._lock = threading.RLock()
        self._status_byte = 1
        self._mission_state = MissionState.IDLE
        self._cur_pickup = 0
        self._cur_dropoff = 0
        self._x = 0.0
        self._y = 0.0
        self._last_plc_task = None
        self._at_door = False
        self._door_task_id = ''
        self._door_outbound = True
        self._door_permission_active = False
        self._connected = False
        self._sock = None
        self._stop = False

        self.task_pub = self.create_publisher(MissionTask, '/plc/mission_task', 10)
        self.state_pub = self.create_publisher(PlcState, '/plc/state', 10)
        self.door_pub = self.create_publisher(DoorEvent, '/plc/door_event', 10)
        self.create_subscription(DoorEvent, '/mission/door_event', self._door_request, 10)
        self.create_subscription(MissionState, '/mission/state', self._mission_state_cb, 10)
        self.create_subscription(
            Odometry, str(self.get_parameter('pose_topic').value), self._pose_cb, 10)
        self.create_service(Trigger, '/plc/mock/submit_task', self._submit_task)
        self.create_timer(0.5, self._publish_state)

        if str(self.get_parameter('transport').value) == 'udp':
            self._start_udp()

    # ---------------- UDP: TX ve RX ayri thread ----------------
    def _start_udp(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.settimeout(float(self.get_parameter('rx_timeout_sec').value))
        threading.Thread(target=self._tx_loop, daemon=True).start()
        threading.Thread(target=self._rx_loop, daemon=True).start()
        self.get_logger().info('PLC UDP transport started (TX+RX threads)')

    def _tx_loop(self):
        ip = str(self.get_parameter('plc_ip').value)
        port = int(self.get_parameter('plc_port').value)
        period = 1.0 / max(0.1, float(self.get_parameter('tx_rate_hz').value))
        while rclpy.ok() and not self._stop:
            t0 = time.monotonic()
            try:
                self._sock.sendto(self._build_tx(), (ip, port))
            except OSError as exc:
                self.get_logger().warning(f'PLC TX error: {exc}')
            dt = period - (time.monotonic() - t0)
            if dt > 0:
                time.sleep(dt)

    def _rx_loop(self):
        while rclpy.ok() and not self._stop:
            try:
                data, _ = self._sock.recvfrom(64)
                self._connected = True
                self._handle_rx(data)
            except socket.timeout:
                self._connected = False
                self.last_rx = 'RX timeout (1s) - baglanti koptu'
            except OSError as exc:
                self._connected = False
                self.get_logger().error(f'PLC RX error: {exc}')
                time.sleep(0.2)

    def _build_tx(self):
        with self._lock:
            status = int(self._status_byte) & 0xFF
            pickup = int(self._cur_pickup) & 0xFF
            dropoff = int(self._cur_dropoff) & 0xFF
            xi = int(self._x * 100.0)
            yi = int(self._y * 100.0)
        xi = max(-32768, min(32767, xi))
        yi = max(-32768, min(32767, yi))
        self.last_tx = f'TX st={status} pu={pickup} do={dropoff} x={xi} y={yi}'
        return struct.pack('<BBBhh', status, pickup, dropoff, xi, yi)

    def _handle_rx(self, data):
        if len(data) < 3:
            self.last_rx = f'RX kisa ({len(data)} byte)'
            return
        pickup_b, dropoff_b, control = data[0], data[1], data[2]
        self.last_rx = f'RX pu={pickup_b} do={dropoff_b} ctrl={control}'
        pickup = BYTE_TO_PICKUP.get(pickup_b)
        dropoff = BYTE_TO_DROPOFF.get(dropoff_b)

        with self._lock:
            waiting_door = self._at_door

        # robot kapida bekliyorsa ctrl=2 = DOOR;
        # degilse ctrl=2 = MISSION. Ayni pakette ikisi olmaz.
        if control == 2 and waiting_door:
            self._grant_door()
            return

        # yeni gorev: ayni gorev tekrarlanabilir, ama sadece mission idle/hatali
        # durumda. Exec durumunda tekrar BASLA ignorlenir; robot hala islemde.
        if control == 2 and pickup and dropoff:
            key = (pickup, dropoff)
            state = self._mission_state
            allow_repeat = (
                key == self._last_plc_task and
                state in (MissionState.IDLE, MissionState.ERROR, MissionState.EMERGENCY_STOP)
            )
            if key != self._last_plc_task or allow_repeat:
                self._last_plc_task = key
                task = MissionTask()
                task.stamp = self.get_clock().now().to_msg()
                task.task_id = f'plc-{next(self.counter):04d}'
                task.pickup_id = pickup
                task.dropoff_id = dropoff
                task.source = 'plc_udp'
                self.active_task_id = task.task_id
                self.task_pub.publish(task)
                self.get_logger().info(
                    f'PLC gorev: {task.task_id} {pickup}->{dropoff} | state={state}')

    def _grant_door(self):
        granted = DoorEvent()
        granted.stamp = self.get_clock().now().to_msg()
        granted.task_id = self._door_task_id
        granted.door_id = str(self.get_parameter('door_id').value)
        granted.event = DoorEvent.PERMISSION_GRANTED
        granted.outbound = self._door_outbound
        self.door_pub.publish(granted)
        with self._lock:
            self._at_door = False
            self._door_permission_active = True
        self.last_rx = 'DOOR GRANTED'
        self.get_logger().info('PLC kapi izni verildi')

    # ---------------- ROS girdileri ----------------
    def _mission_state_cb(self, msg):
        st = msg.state
        loaded = bool(msg.carrying_load)
        phase = str(msg.phase)
        if st == MissionState.IDLE:
            status = 1
        elif st == MissionState.WAITING_PLC:
            status = 5
        elif st == MissionState.ERROR:
            status = 7
        elif st == MissionState.EMERGENCY_STOP:
            status = 8
        elif 'COMPLETE' in phase or 'REPORT' in phase:
            status = 6
        elif st == MissionState.EXECUTING:
            status = 4 if loaded else 3
        else:
            status = 2
        with self._lock:
            if st == MissionState.IDLE:
                self._last_plc_task = None
            self._status_byte = status
            self._mission_state = st
            self._cur_pickup = PICKUP_TO_BYTE.get(msg.pickup_id, 0)
            self._cur_dropoff = DROPOFF_TO_BYTE.get(msg.dropoff_id, 0)

    def _pose_cb(self, msg):
        with self._lock:
            self._x = float(msg.pose.pose.position.x)
            self._y = float(msg.pose.pose.position.y)

    def _door_request(self, msg):
        self.last_tx = f'DOOR {msg.door_id} event={msg.event}'
        if msg.event == DoorEvent.PASSED:
            with self._lock:
                self._door_permission_active = False
            return
        if msg.event != DoorEvent.ARRIVED:
            return
        if str(self.get_parameter('transport').value) == 'udp':
            with self._lock:
                self._at_door = True
                self._door_task_id = msg.task_id
                self._door_outbound = msg.outbound
            return
        if not bool(self.get_parameter('auto_grant_door').value):
            return
        self._door_task_id = msg.task_id
        self._door_outbound = msg.outbound
        self._grant_door()

    def _submit_task(self, request, response):
        if str(self.get_parameter('transport').value) != 'mock':
            response.message = 'mock task service disabled for non-mock transport'
            return response
        task = MissionTask()
        task.stamp = self.get_clock().now().to_msg()
        task.task_id = f'mock-{next(self.counter):04d}'
        task.pickup_id = str(self.get_parameter('mock_pickup').value)
        task.dropoff_id = str(self.get_parameter('mock_dropoff').value)
        task.source = 'mock_plc'
        self.active_task_id = task.task_id
        self.last_rx = f'TASK {task.task_id} {task.pickup_id}->{task.dropoff_id}'
        self.task_pub.publish(task)
        response.success = True
        response.message = task.task_id
        return response

    def _publish_state(self):
        msg = PlcState()
        msg.stamp = self.get_clock().now().to_msg()
        transport = str(self.get_parameter('transport').value)
        if transport == 'udp':
            msg.connection_state = PlcState.CONNECTED if self._connected else PlcState.ERROR
            if not self._connected:
                msg.error_message = 'PLC UDP: baglanti yok / RX timeout'
        else:
            msg.connection_state = PlcState.CONNECTED
        with self._lock:
            msg.door_permission = self._door_permission_active
        msg.active_task_id = self.active_task_id
        msg.last_rx = self.last_rx
        msg.last_tx = self.last_tx
        self.state_pub.publish(msg)

    def destroy_node(self):
        self._stop = True
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = PlcBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
