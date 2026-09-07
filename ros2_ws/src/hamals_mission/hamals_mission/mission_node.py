"""Config-driven hierarchical mission coordinator."""

from __future__ import annotations

import asyncio
import math
import threading
import time

from geometry_msgs.msg import PoseStamped, Twist  # yous: Twist - QR arama/ortalama
from nav2_msgs.action import NavigateToPose
import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Bool, String

from hamals_interfaces.action import Dock, ExecuteMission
from hamals_interfaces.msg import (
    DoorEvent,
    ForkCommand,
    ForkState,
    MissionState,
    MissionTask,
    QrDetection,
    SafetyState,
    WorldModelState,
)
from hamals_interfaces.srv import (
    GetDoor,
    GetStation,
    PauseMission,
    PlanSemanticRoute,
    ResumeMission,
)
from .mission_context import MissionContext


class MissionFailure(RuntimeError):
    """Controlled failure which transitions the FSM to ERROR."""


class MissionNode(Node):
    def __init__(self):
        super().__init__('hamals_mission')
        for name, value in {
            'nav_timeout_sec': 180.0, 'dock_timeout_sec': 45.0,
            'fork_timeout_sec': 60.0, 'door_timeout_sec': 120.0,
            'max_nav_retries': 1, 'home_node': 'START', 'door_id': 'MAIN_DOOR',
            # yous: kapi QR isimleri (GetDoor bunlari donmuyor) + tesbit ayari
            'door_qr_outbound': 'KAPI1', 'door_qr_return': 'KAPI2',  # yous: resmi
            'door_qr_confirm_sec': 5.0, 'door_qr_required': False,
            # yous: QR arama dongusu (D -> ara -> dur -> bulamazsa D'ye don -> tekrar)
            'qr_max_cycles': 2, 'qr_search_angular_speed': 0.30,
            'qr_search_sweep_deg': 90.0,
            # yous: visual servo (ortalama) - /qr/detection.x
            'qr_vs_kp': 1.2, 'qr_vs_max_turn': 0.35, 'qr_vs_center_tol_m': 0.04,
            'qr_vs_min_confidence': 0.15, 'qr_vs_invert': False,
            'qr_vs_lost_sec': 1.0, 'qr_vs_center_timeout_sec': 6.0,
            'qr_detection_fresh_sec': 0.4,
        }.items():
            self.declare_parameter(name, value)
        group = ReentrantCallbackGroup()
        self._lock = threading.RLock()
        self._mctx = None
        self._worker = None
        self._cancel = False
        self._manual_resume_required = False
        self._safety = None
        self._world_checksum = ''
        self._fork_state = None
        self._door_permission = None
        # yous: nav sirasinda QR takibi
        self._qr_detected = False
        self._qr_text = ''
        # yous: /qr/detection (x konum) - visual servo icin
        self._qr_det = None
        self._qr_det_time = 0.0
        self.state_pub = self.create_publisher(MissionState, '/mission/state', 10)
        self.door_pub = self.create_publisher(DoorEvent, '/mission/door_event', 10)
        self.fork_pub = self.create_publisher(ForkCommand, '/fork/cmd', 10)
        # yous: Pi vision_node kamera degistirme (Bool)
        self.fork_is_up_pub = self.create_publisher(Bool, '/fork/is_up', 10)
        # yous: QR arama/ortalama icin dogrudan hiz (twist_mux uzerinden)
        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel/docking', 10)
        self.create_subscription(
            MissionTask, '/plc/mission_task', self._task_received, 10, callback_group=group)
        self.create_subscription(
            SafetyState, '/safety/state', self._safety_received, 10, callback_group=group)
        self.create_subscription(
            ForkState, '/fork/state', self._fork_received, 10, callback_group=group)
        self.create_subscription(
            DoorEvent, '/plc/door_event', self._door_received, 10, callback_group=group)
        self.create_subscription(
            WorldModelState, '/world_model/state', self._world_received, 10, callback_group=group)
        # yous: QR subscription - nav sirasinda QR gorulurse dur
        self.create_subscription(
            Bool, '/qr/detected', self._qr_detected_cb, 10, callback_group=group)
        self.create_subscription(
            String, '/qr/text', self._qr_text_cb, 10, callback_group=group)
        # yous: QR goreli konum (x) - visual servo ile ortalama
        self.create_subscription(
            QrDetection, '/qr/detection', self._qr_detection_cb, 10, callback_group=group)
        self.station_client = self.create_client(
            GetStation, '/world_model/get_station', callback_group=group)
        self.door_client = self.create_client(
            GetDoor, '/world_model/get_door', callback_group=group)
        self.route_client = self.create_client(
            PlanSemanticRoute, '/world_model/plan_route', callback_group=group)
        self.nav_client = ActionClient(
            self, NavigateToPose, '/navigate_to_pose', callback_group=group)
        self.dock_client = ActionClient(self, Dock, '/dock', callback_group=group)
        self.create_service(PauseMission, '/mission/pause', self._pause, callback_group=group)
        self.create_service(ResumeMission, '/mission/resume', self._resume, callback_group=group)
        self.action_server = ActionServer(
            self, ExecuteMission, '/mission/execute',
            execute_callback=self._execute_action,
            goal_callback=self._goal_callback,
            cancel_callback=lambda _: CancelResponse.ACCEPT,
            callback_group=group)
        self.create_timer(0.25, self._publish_state, callback_group=group)

    # ================================================================
    # QR CALLBACKS
    # ================================================================
    def _qr_detected_cb(self, msg):
        # yous: /qr/detected - Bool
        self._qr_detected = bool(msg.data)

    def _qr_text_cb(self, msg):
        # yous: /qr/text - String
        self._qr_text = str(msg.data).strip()

    def _qr_seen(self, expected_qr):
        # yous: beklenen QR goruldu mu?
        return self._qr_detected and self._qr_text == expected_qr

    # ================================================================
    # QR ACQUIRE  (yous)  -  BUTUN QR MANTIGI BURADA (dock'ta degil)
    #   D -> hedefe git (yolda ara) -> bulamazsa sag/sol tara ->
    #   bulamazsa D'ye don + tekrar (qr_max_cycles) -> bulunca ORTALA.
    #   Ortalandiktan sonra donen -> dock (sadece hat takibi) cagrilir.
    # ================================================================
    def _qr_detection_cb(self, msg):
        # yous: /qr/detection - QrDetection (x,y,z,yaw_deg,confidence)
        self._qr_det = msg
        if msg.detected:
            self._qr_det_time = time.monotonic()

    def _stop_cmd(self):
        # yous: yumusak degil, kesin dur (birkac sifir Twist)
        stop = Twist()
        for _ in range(3):
            self.cmd_pub.publish(stop)
            time.sleep(0.02)

    def _detection_fresh(self):
        det = self._qr_det
        if det is None or not det.detected:
            return False
        if (time.monotonic() - self._qr_det_time
                > float(self.get_parameter('qr_detection_fresh_sec').value)):
            return False
        return float(det.confidence) >= float(
            self.get_parameter('qr_vs_min_confidence').value)

    def _rotate_rel(self, angle_rad, expected_qr):
        # yous: zaman tabanli goreli donme; QR gorulunce True
        speed = float(self.get_parameter('qr_search_angular_speed').value)
        if speed <= 0.0 or abs(angle_rad) < 1e-3:
            return False
        direction = 1.0 if angle_rad > 0 else -1.0
        deadline = time.monotonic() + abs(angle_rad) / speed
        while rclpy.ok() and time.monotonic() < deadline:
            if self._cancel:
                self._stop_cmd()
                raise MissionFailure('mission canceled')
            if self._qr_seen(expected_qr):
                self._stop_cmd()
                return True
            cmd = Twist()
            cmd.angular.z = direction * speed
            self.cmd_pub.publish(cmd)
            time.sleep(0.03)
        self._stop_cmd()
        return False

    def _sweep_search(self, expected_qr):
        # yous: sag -> sol(merkezden gecerek) -> merkez
        yaw = math.radians(float(self.get_parameter('qr_search_sweep_deg').value))
        self._set_phase('QR_SEARCH', f'searching QR {expected_qr}')
        for target in (-yaw, 2.0 * yaw, -yaw):
            if self._rotate_rel(target, expected_qr):
                return True
        return False

    def _visual_center(self, expected_qr):
        # yous: /qr/detection.x ile QR'a dogru donerek ortala
        kp = float(self.get_parameter('qr_vs_kp').value)
        mx = float(self.get_parameter('qr_vs_max_turn').value)
        tol = float(self.get_parameter('qr_vs_center_tol_m').value)
        invert = bool(self.get_parameter('qr_vs_invert').value)
        lost = float(self.get_parameter('qr_vs_lost_sec').value)
        to = float(self.get_parameter('qr_vs_center_timeout_sec').value)
        self._set_phase('QR_CENTER', f'centering QR {expected_qr}')
        deadline = time.monotonic() + to
        last_seen = time.monotonic()
        while rclpy.ok():
            if self._cancel:
                self._stop_cmd()
                raise MissionFailure('mission canceled')
            if time.monotonic() > deadline:
                self._stop_cmd()
                return False
            if self._detection_fresh():
                last_seen = time.monotonic()
                x = float(self._qr_det.x)
                if self._qr_seen(expected_qr) and abs(x) <= tol:
                    self._stop_cmd()
                    self.get_logger().info(f'QR {expected_qr} ortalandi')
                    return True
                turn = -kp * x
                if invert:
                    turn = -turn
                turn = max(-mx, min(mx, turn))
                cmd = Twist()
                cmd.angular.z = turn
                self.cmd_pub.publish(cmd)
            else:
                if time.monotonic() - last_seen > lost:
                    self._stop_cmd()
                    return False
                self.cmd_pub.publish(Twist())
            time.sleep(0.03)
        return False

    def _acquire_qr(self, expected_qr, start_node, goal_node, loaded):
        # yous: tam dongu. Ortalandiktan sonra doner (dock'a hazir).
        cycles = int(self.get_parameter('qr_max_cycles').value)
        for attempt in range(cycles + 1):
            if self._cancel:
                raise MissionFailure('mission canceled')
            # 1) D'den hedefe git, yolda QR ararken (stop_qr Nav2'yi durdurur)
            self._navigate_route(
                self._route(start_node, goal_node, loaded), stop_qr=expected_qr)
            # 2) QR gorunuyorsa ortala
            if self._qr_seen(expected_qr):
                if self._visual_center(expected_qr):
                    return
            # 3) varista gorulmedi -> sag/sol tara, bulunca ortala
            if self._sweep_search(expected_qr):
                if self._visual_center(expected_qr):
                    return
            # 4) bulunamadi -> D'ye don, tekrar (son deneme haric)
            if attempt < cycles:
                self.get_logger().warning(
                    f'QR {expected_qr} bulunamadi - {start_node} donuluyor '
                    f'(deneme {attempt + 1}/{cycles})')
                self._navigate_route(self._route(goal_node, start_node, loaded))
        raise MissionFailure(f'QR {expected_qr} bulunamadi ({cycles} deneme)')

    # ================================================================
    # SERVICE READY
    # ================================================================
    def _svc_ready(self, client, timeout=5.0):
        # yous: wait_for_service context catismasini onler
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if client.service_is_ready():
                return True
            time.sleep(0.05)
        return client.service_is_ready()

    def _goal_callback(self, _goal):
        with self._lock:
            busy = self._worker is not None or self._mctx is not None
            return GoalResponse.REJECT if busy else GoalResponse.ACCEPT

    async def _execute_action(self, handle):
        worker = asyncio.create_task(
            asyncio.to_thread(self._run_task, handle.request.task))
        while not worker.done():
            if handle.is_cancel_requested:
                self._cancel = True
            handle.publish_feedback(
                ExecuteMission.Feedback(state=self._state_message()))
            await asyncio.sleep(0.1)
        success, message = await worker
        if handle.is_cancel_requested:
            handle.canceled()
        elif success:
            handle.succeed()
        else:
            handle.abort()
        return ExecuteMission.Result(
            success=success,
            final_state='COMPLETED' if success else 'ERROR',
            message=message)

    def _task_received(self, task):
        with self._lock:
            if self._worker is not None or self._mctx is not None:
                self.get_logger().warning(
                    f'Ignoring task {task.task_id}: mission busy')
                return
            self._worker = threading.Thread(
                target=self._run_task, args=(task,), daemon=True)
            self._worker.start()

    def _world_received(self, msg):
        if msg.valid:
            self._world_checksum = msg.config_checksum

    def _fork_received(self, msg):
        self._fork_state = msg

    def _door_received(self, msg):
        if msg.event == DoorEvent.PERMISSION_GRANTED:
            self._door_permission = (msg.task_id, msg.outbound)

    def _safety_received(self, msg):
        previous_manual = self._safety.manual_mode if self._safety else False
        self._safety = msg
        if previous_manual and not msg.manual_mode:
            self._manual_resume_required = True

    def _pause(self, request, response):
        if self._mctx is None:
            response.message = 'no active mission'
            return response
        self._mctx.pause_reason = request.reason or 'operator pause'
        self._mctx.top_state = MissionState.PAUSED_MANUAL
        self._manual_resume_required = True
        response.success = True
        response.message = 'paused'
        return response

    def _resume(self, request, response):
        if self._mctx is None:
            response.message = 'no active mission'
            return response
        if self._safety is None or not self._safety.motion_allowed:
            response.message = 'safety conditions do not allow resume'
            return response
        self._manual_resume_required = False
        self._mctx.pause_reason = ''
        self._mctx.top_state = MissionState.EXECUTING
        response.success = True
        response.message = f'resumed by {request.operator_id or "operator"}'
        return response

    def _set_phase(self, phase, message='', target=''):
        self._mctx.phase = phase
        self._mctx.message = message
        self._mctx.active_target = target
        self._mctx.top_state = MissionState.EXECUTING
        self._publish_state()

    def _wait_ready(self):
        while rclpy.ok():
            if self._cancel:
                raise MissionFailure('mission canceled')
            safety = self._safety
            if safety and safety.estop_active:
                self._mctx.top_state = MissionState.EMERGENCY_STOP
                raise MissionFailure('emergency stop active')
            if safety and safety.state == SafetyState.SENSOR_STALE:
                raise MissionFailure(safety.reason or 'critical safety sensor stale')
            if safety and safety.manual_mode:
                self._mctx.top_state = MissionState.PAUSED_MANUAL
                self._mctx.pause_reason = safety.reason
                self._manual_resume_required = True
            elif safety and not safety.motion_allowed:
                self._mctx.top_state = MissionState.PAUSED_OBSTACLE
                self._mctx.pause_reason = safety.reason
            elif not self._manual_resume_required:
                self._mctx.top_state = MissionState.EXECUTING
                self._mctx.pause_reason = ''
                return
            time.sleep(0.05)

    def _wait_future(self, future, timeout, label):
        deadline = time.monotonic() + timeout
        while rclpy.ok() and not future.done():
            if self._cancel:
                raise MissionFailure('mission canceled')
            if time.monotonic() >= deadline:
                raise MissionFailure(f'{label} timeout')
            time.sleep(0.02)
        result = future.result()
        if result is None:
            raise MissionFailure(f'{label} failed')
        return result

    def _station(self, station_id):
        if not self._svc_ready(self.station_client):
            raise MissionFailure('world model station service unavailable')
        request = GetStation.Request()
        request.station_id = station_id
        response = self._wait_future(
            self.station_client.call_async(request), 5.0, 'get station')
        if not response.found:
            raise MissionFailure(response.message)
        return response.station

    def _route(self, start_id, goal_id, loaded):
        if not self._svc_ready(self.route_client):
            raise MissionFailure('world model route service unavailable')
        request = PlanSemanticRoute.Request()
        request.start_id = start_id
        request.goal_id = goal_id
        request.carrying_load = loaded
        response = self._wait_future(
            self.route_client.call_async(request), 5.0, 'plan route')
        if not response.success:
            raise MissionFailure(response.message)
        self._mctx.route = list(response.node_ids)
        return list(zip(response.node_ids, response.poses))

    def _door_model(self):
        if not self._svc_ready(self.door_client):
            raise MissionFailure('world model door service unavailable')
        request = GetDoor.Request()
        request.door_id = str(self.get_parameter('door_id').value)
        response = self._wait_future(
            self.door_client.call_async(request), 5.0, 'get door')
        if not response.found:
            raise MissionFailure(response.message)
        return response.door

    def _navigate_route(self, route, stop_qr=None):
        # yous: stop_qr verilirse QR gorulunce nav iptal edilir
        for index, (node_id, pose) in enumerate(route[1:], start=1):
            self._mctx.route_index = index
            stopped = self._navigate(node_id, pose, stop_qr=stop_qr)
            if stopped:
                self.get_logger().info(f'QR {stop_qr} goruldu - nav durduruldu')
                return True
            # yous: her durakta 5 saniye bekle (stabilizasyon)
            self.get_logger().info(f'{node_id} duragi: 5sn bekleniyor...')
            time.sleep(5.0)
        return False

    def _navigate(self, node_id, pose, stop_qr=None):
        # yous: stop_qr verilirse nav sirasinda QR gorulunce iptal et
        self._wait_ready()
        phase = 'MOVE_LOADED' if self._mctx.carrying_load else 'MOVE_EMPTY'
        self._set_phase(phase, f'navigating to {node_id}', node_id)
        if not self.nav_client.wait_for_server(timeout_sec=10.0):
            raise MissionFailure('Nav2 action unavailable')
        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = pose.x
        goal.pose.pose.position.y = pose.y
        goal.pose.pose.orientation.z = math.sin(pose.theta / 2.0)
        goal.pose.pose.orientation.w = math.cos(pose.theta / 2.0)
        for _ in range(int(self.get_parameter('max_nav_retries').value) + 1):
            sent = self._wait_future(
                self.nav_client.send_goal_async(goal), 10.0, 'send Nav2 goal')
            if sent.accepted:
                result_future = sent.get_result_async()
                deadline = time.monotonic() + float(
                    self.get_parameter('nav_timeout_sec').value)
                while rclpy.ok() and not result_future.done():
                    if self._cancel:
                        sent.cancel_goal_async()
                        raise MissionFailure('mission canceled')
                    if time.monotonic() >= deadline:
                        sent.cancel_goal_async()
                        raise MissionFailure(f'Nav2 timeout for {node_id}')
                    # yous: nav sirasinda QR gorulurse aninda dur
                    if stop_qr and self._qr_seen(stop_qr):
                        self.get_logger().info(
                            f'QR {stop_qr} goruldu - {node_id} iptale ediliyor')
                        sent.cancel_goal_async()
                        time.sleep(0.2)
                        return True
                    time.sleep(0.05)
                result = result_future.result()
                if result and result.status == 4:
                    return False
            self._mctx.retry_count += 1
        raise MissionFailure(f'Nav2 failed for {node_id}')

    def _dock(self, station, operation):
        self._wait_ready()
        self._mctx.expected_qr = station.expected_qr
        self._set_phase(
            f'DOCK_{operation.upper()}',
            f'docking at {station.id}', station.id)
        if not self.dock_client.wait_for_server(timeout_sec=10.0):
            raise MissionFailure('dock action unavailable')
        goal = Dock.Goal()
        goal.station_id = station.id
        goal.operation = operation
        goal.expected_qr = station.expected_qr
        goal.profile = station.docking_profile
        sent = self._wait_future(
            self.dock_client.send_goal_async(goal), 10.0, 'send dock goal')
        if not sent.accepted:
            raise MissionFailure('dock goal rejected')
        result = self._wait_future(
            sent.get_result_async(),
            float(self.get_parameter('dock_timeout_sec').value), 'dock')
        if result.status != 4 or not result.result.success:
            raise MissionFailure(result.result.message)
        self._mctx.verified_qr = station.expected_qr

    def _send_fork(self, command):
        # yous: fork_node ERROR durumunu sifirla, sonra komutu gonder
        # fork_node keepalive'i devralir (200ms arayla tekrar gonderir)
        stop = ForkCommand()
        stop.command = ForkCommand.STOP
        self.fork_pub.publish(stop)
        time.sleep(0.5)  # yous: IDLE'a gecmesi icin bekle
        msg = ForkCommand()
        msg.command = command
        self.fork_pub.publish(msg)

    def _move_fork(self, command, expected_state, phase):
        self._wait_ready()
        self._set_phase(phase, phase.replace('_', ' ').lower())
        # yous: once STOP (ERROR sifirla) sonra komut gonder
        # fork_node keepalive otomatik tekrar gonderir - biz sadece hedef bekliyoruz
        self._send_fork(command)
        deadline = time.monotonic() + float(
            self.get_parameter('fork_timeout_sec').value)
        while time.monotonic() < deadline:
            if self._fork_state and self._fork_state.state == expected_state:
                # yous: limite ulasti - durdur
                stop = ForkCommand()
                stop.command = ForkCommand.STOP
                self.fork_pub.publish(stop)
                self.get_logger().info(f'{phase} tamamlandi')
                return
            if self._fork_state and self._fork_state.state == ForkState.ERROR:
                ec = self._fork_state.error_code
                # yous: limit switch timeout (2,3) = henuz ulasmamiş, devam et
                if ec in (ForkState.ERROR_TOP_TIMEOUT,
                           ForkState.ERROR_BOTTOM_TIMEOUT):
                    # yous: tekrar gonder - keepalive durmuş olabilir
                    self._send_fork(command)
                else:
                    raise MissionFailure(f'fork error {ec}')
            time.sleep(0.05)
        raise MissionFailure(f'{phase} timeout')

    def _confirm_door_qr(self, expected_qr):
        # yous: kapi QR'ini DOGRULA (hat takibi YOK, hareket YOK - pasif izleme).
        # stop_qr yaklasirken zaten QR gorulunce Nav2'yi durdurur; burada
        # gorulen QR'i teyit ediyoruz. DONER: (bool, okunan_qr_data)
        if not expected_qr:
            return True, ''
        self._set_phase('CONFIRM_DOOR_QR', f'confirming door QR {expected_qr}',
                        expected_qr)
        deadline = time.monotonic() + float(
            self.get_parameter('door_qr_confirm_sec').value)
        while time.monotonic() < deadline:
            if self._cancel:
                raise MissionFailure('mission canceled')
            if self._qr_seen(expected_qr):
                data = self._qr_text
                self._mctx.verified_qr = data
                self.get_logger().info(f'kapi QR dogrulandi: {data}')
                return True, data
            time.sleep(0.05)
        # yous: gorulemedi
        if bool(self.get_parameter('door_qr_required').value):
            raise MissionFailure(f'door QR {expected_qr} not confirmed')
        self.get_logger().warning(
            f'kapi QR {expected_qr} gorulemedi - koordinatla devam ediliyor')
        return False, ''

    def _door(self, outbound):
        self._wait_ready()
        phase = 'REQUEST_DOOR_OUTBOUND' if outbound else 'REQUEST_DOOR_RETURN'
        self._set_phase(phase, 'waiting for PLC door permission')
        self._mctx.top_state = MissionState.WAITING_PLC
        self._door_permission = None
        event = DoorEvent()
        event.stamp = self.get_clock().now().to_msg()
        event.task_id = self._mctx.task_id
        event.door_id = str(self.get_parameter('door_id').value)
        event.event, event.outbound = DoorEvent.ARRIVED, outbound
        self.door_pub.publish(event)
        deadline = time.monotonic() + float(
            self.get_parameter('door_timeout_sec').value)
        while time.monotonic() < deadline:
            if self._door_permission == (self._mctx.task_id, outbound):
                self._mctx.top_state = MissionState.EXECUTING
                return
            time.sleep(0.05)
        raise MissionFailure('PLC door permission timeout')

    def _run_task(self, task):
        with self._lock:
            if self._mctx is not None:
                return False, 'mission busy'
            self._cancel = False
            self._mctx = MissionContext(
                task_id=task.task_id,
                pickup_id=task.pickup_id,
                dropoff_id=task.dropoff_id,
                top_state=MissionState.EXECUTING,
                config_checksum=self._world_checksum)
        try:
            self._set_phase('VALIDATE_TASK', 'validating task')
            pickup, dropoff = (
                self._station(task.pickup_id),
                self._station(task.dropoff_id))
            if pickup.type != 'pickup' or dropoff.type != 'dropoff':
                raise MissionFailure('invalid pickup/dropoff station types')
            home = str(self.get_parameter('home_node').value)
            door = self._door_model()
            west, east = door.west_node, door.east_node

            # yous: TUM QR mantigi burada - ara+dur+bulamazsa D'ye don+tekrar+ortala
            self._acquire_qr(pickup.expected_qr, home, pickup.approach_node, False)

            self._move_fork(ForkCommand.DOWN, ForkState.AT_BOTTOM, 'LOWER_FORK')
            self._dock(pickup, 'pickup')
            self._move_fork(ForkCommand.UP, ForkState.AT_TOP, 'LIFT_LOAD')
            _b = Bool(); _b.data = True
            self.fork_is_up_pub.publish(_b)   # yous: yuklu -> Pi arka kamera
            self._mctx.carrying_load = True
            # yous: kapiya (west) giderken q5 gorulurse Nav2 durur, sonra teyit
            _door_out_qr = str(self.get_parameter('door_qr_outbound').value)
            self._navigate_route(
                self._route(pickup.approach_node, west, True),
                stop_qr=_door_out_qr)
            self._confirm_door_qr(_door_out_qr)   # yous: q5 dogrula (hat yok)
            self._door(True)
            self._navigate_route(self._route(west, east, True))

            # yous: dropoff QR - ayni tam dongu (D=east), sonra ortala
            self._acquire_qr(dropoff.expected_qr, east, dropoff.approach_node, True)

            self._dock(dropoff, 'dropoff')
            self._move_fork(ForkCommand.DOWN, ForkState.AT_BOTTOM, 'LOWER_LOAD')
            _b2 = Bool(); _b2.data = False
            self.fork_is_up_pub.publish(_b2)  # yous: yuksuz -> Pi on kamera
            self._mctx.carrying_load = False
            self._set_phase('REPORT_DELIVERED', 'load delivered')
            # yous: donuste kapiya (east) giderken q6 gorulurse dur, sonra teyit
            _door_ret_qr = str(self.get_parameter('door_qr_return').value)
            self._navigate_route(
                self._route(dropoff.approach_node, east, False),
                stop_qr=_door_ret_qr)
            self._confirm_door_qr(_door_ret_qr)   # yous: q6 dogrula (hat yok)
            self._door(False)
            self._navigate_route(self._route(east, west, False))
            self._navigate_route(self._route(west, home, False))
            self._set_phase('REPORT_COMPLETE', 'mission completed', home)
            return True, 'mission completed'
        except Exception as error:
            self._mctx.top_state = MissionState.ERROR
            self._mctx.error_code = type(error).__name__
            self._mctx.message = str(error)
            import traceback
            self.get_logger().error(
                f'Mission {task.task_id} failed: {error}\n'
                f'{traceback.format_exc()}')
            return False, str(error)
        finally:
            stop = ForkCommand()
            stop.command = ForkCommand.STOP
            self.fork_pub.publish(stop)
            self._publish_state()
            time.sleep(0.1)
            with self._lock:
                self._mctx = None
                self._worker = None

    def _state_message(self):
        msg = MissionState()
        msg.stamp = self.get_clock().now().to_msg()
        context = self._mctx
        if context is None:
            msg.state = MissionState.IDLE
            msg.phase = 'IDLE'
            msg.message = 'ready for task'
            msg.config_checksum = self._world_checksum
        else:
            msg.state = context.top_state
            fields = (
                'phase', 'task_id', 'pickup_id', 'dropoff_id',
                'active_target', 'expected_qr', 'verified_qr',
                'pause_reason', 'error_code', 'message', 'config_checksum')
            for field in fields:
                setattr(msg, field, getattr(context, field))
            msg.carrying_load = context.carrying_load
            msg.retry_count = context.retry_count
            msg.elapsed_s = time.monotonic() - context.started_at
        return msg

    def _publish_state(self):
        msg = self._state_message()
        self.state_pub.publish(msg)
        return msg


def main(args=None):
    rclpy.init(args=args)
    node = MissionNode()
    executor = MultiThreadedExecutor(num_threads=6)
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()
