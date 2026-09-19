"""Config-driven hierarchical mission coordinator."""

from __future__ import annotations

import asyncio
import math
import threading
import time

from geometry_msgs.msg import PoseStamped, Twist  # : Twist - QR arama/ortalama
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Odometry
import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import Bool, Int32, String
from std_srvs.srv import Trigger

from hamals_interfaces.action import Dock, ExecuteMission
from hamals_interfaces.msg import (
    DoorEvent,
    ForkCommand,
    ForkState,
    MissionState,
    MissionTask,
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
            'nav_timeout_sec': 300.0, 'dock_timeout_sec': 200.0,
            'fork_timeout_sec': 300.0, 'door_timeout_sec': 300.0,
            'max_nav_retries': 1, 'home_node': 'START', 'door_id': 'MAIN_DOOR',
            # yous: kapi QR isimleri (GetDoor bunlari donmuyor) + tesbit ayari
            'door_qr_outbound': 'KAPI1', 'door_qr_return': 'KAPI2',  # yous: resmi
            'door_return_retry_node': 'D4',  # yous: KAPI2 donus dugumu (sabit)
            'door_direct_node': 'D4',  # yous: GIDISTE izin sonrasi DOGRUDAN gidilen dugum
            # yous: yuklu iken geri surus (fork onde, yuk arkada - sartname)
            'reverse_when_loaded': True,
            'door_qr_confirm_sec': 3.0, 'door_qr_required': True,
            # yous: QR arama dongusu (D -> ara -> dur -> bulamazsa D'ye don -> tekrar)
            'qr_max_cycles': 10, 'qr_search_angular_speed': 0.30,
            'qr_search_sweep_deg': 90.0,
            # yous: (visual servo YOK - sadece detected+text ile teyit)
            # yous: baslangic QR (q1). Bos yapinca adim atlanir.
            'start_qr': 'BASLA',
            'start_qr_confirm_sec': 60.0,  # yous: BASLA cizgi takip suresi
            # yous: baslangic cizgi takibi = test scripti ile ayni ayarlar


              'line_follow_speed': 0.10,
            'line_follow_gain': 0.050,
            'line_follow_deadband_px': 18.0,
            'line_follow_smoothing': 0.35,
            'line_follow_max_turn': 0.45,
            'line_follow_invert': True,
            'line_follow_lost_sec': 1.0,



        }.items():
            self.declare_parameter(name, value)
        group = ReentrantCallbackGroup()
        self._lock = threading.RLock()
        self._mctx = None
        self._worker = None
        self._cancel = False
        self._manual_resume_required = False
        self._plc_pause_required = False
        self._plc_pause_generation = 0
        self._safety = None
        self._world_checksum = ''
        self._fork_state = None
        self._door_permission = None
        # yous: nav sirasinda QR takibi
        self._qr_detected = False
        self._qr_text = ''
        self._line_detected = False
        self._line_error = 0
        self._line_last_seen = 0.0   # yous: cizgi tazelik (docking ile ayni)
        self._odom_linear_x = 0.0
        self._odom_angular_z = 0.0
        self._odom_last_seen = None
        # yous: (sadece detected Bool + text String - detection mesaji YOK)
        self.state_pub = self.create_publisher(MissionState, '/mission/state', 10)
        self.door_pub = self.create_publisher(DoorEvent, '/mission/door_event', 10)
        self.fork_pub = self.create_publisher(ForkCommand, '/fork/cmd', 10)
        # yous: Pi vision_node kamera degistirme (Bool). True=arka, False=on.
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
        self.create_subscription(
            Bool, '/line/detected', self._line_detected_cb, 10, callback_group=group)
        self.create_subscription(
            Int32, '/line/error', self._line_error_cb, 10, callback_group=group)
        self.create_subscription(
            Odometry, '/odom', self._odom_received, 10, callback_group=group)
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
        self.create_service(Trigger, '/mission/plc_pause', self._plc_pause, callback_group=group)
        self.create_service(Trigger, '/mission/plc_resume', self._plc_resume, callback_group=group)
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
        self._qr_detected = bool(msg.data)

    def _qr_text_cb(self, msg):
        self._qr_text = str(msg.data).strip()

    def _qr_seen(self, expected_qr):
        return self._qr_detected and self._qr_text == expected_qr

    def _line_detected_cb(self, msg):
        self._line_detected = bool(msg.data)
        if self._line_detected:                       # yous
            self._line_last_seen = time.monotonic()   # yous: tazelik damgasi

    def _line_error_cb(self, msg):
        self._line_error = int(msg.data)

    def _odom_received(self, msg):
        self._odom_linear_x = float(msg.twist.twist.linear.x)
        self._odom_angular_z = float(msg.twist.twist.angular.z)
        self._odom_last_seen = time.monotonic()

    def _switch_camera(self, rear: bool):
        # yous: /fork/is_up ile Pi kamera secimi. True=arka, False=on.
        b = Bool()
        b.data = bool(rear)
        self.fork_is_up_pub.publish(b)
        self.get_logger().info(f'KAMERA -> {"ARKA" if rear else "ON"}')

    def _drive_distance_by_odom(self, distance_m, speed_mps, timeout_sec=10.0):
        # yous: odometri ile hedef mesafeyi git; line takibi burada degil.
        if abs(distance_m) < 1e-3:
            return
        direction = 1.0 if distance_m >= 0.0 else -1.0
        speed = max(0.01, abs(speed_mps)) * direction
        total = 0.0
        last_t = time.monotonic()
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            waited = self._motion_checkpoint()
            deadline += waited
            last_t += waited
            if self._odom_last_seen is None or time.monotonic() - self._odom_last_seen > 0.5:
                self._stop_cmd()
                raise MissionFailure('odometry unavailable for dropoff drive')
            dt = max(0.0, time.monotonic() - last_t)
            last_t = time.monotonic()
            total += max(0.0, direction * self._odom_linear_x) * dt
            cmd = Twist(); cmd.linear.x = speed; self.cmd_pub.publish(cmd)
            if abs(total) >= abs(distance_m):
                break
            time.sleep(0.05)
        self._stop_cmd()

    def _line_follow_until_qr(self, expected_qr, deadline, *, label='QR'):
        # yous: docking follow_line ile AYNI kontrol yasasi. QR gorulunce dur.
        speed = float(self.get_parameter('line_follow_speed').value)
        gain = float(self.get_parameter('line_follow_gain').value)
        deadband = float(self.get_parameter('line_follow_deadband_px').value)
        smoothing = float(self.get_parameter('line_follow_smoothing').value)
        max_turn = float(self.get_parameter('line_follow_max_turn').value)
        invert = bool(self.get_parameter('line_follow_invert').value)
        lost = float(self.get_parameter('line_follow_lost_sec').value)
        filtered = 0.0
        while time.monotonic() < deadline:
            deadline += self._motion_checkpoint()
            if self._qr_seen(expected_qr):
                self._stop_cmd()
                self._mctx.verified_qr = self._qr_text
                self.get_logger().info(f'{label} teyit edildi: {self._qr_text}')
                return True
            now = time.monotonic()
            line_fresh = self._line_detected and (now - self._line_last_seen) <= lost
            if line_fresh:
                err = float(self._line_error)
                if abs(err) <= deadband:
                    ce = 0.0
                elif err > 0.0:
                    ce = err - deadband
                else:
                    ce = err + deadband
                turn = gain * ce
                if invert:
                    turn = -turn
                filtered = smoothing * turn + (1.0 - smoothing) * filtered
            else:
                filtered = 0.0
            filtered = max(-max_turn, min(max_turn, filtered))
            cmd = Twist()
            cmd.linear.x = speed
            cmd.angular.z = filtered
            self.cmd_pub.publish(cmd)
            time.sleep(0.05)
        self._stop_cmd()
        return False

    # ================================================================
    # QR ACQUIRE
    # ================================================================
    def _stop_cmd(self):
        stop = Twist()
        for _ in range(3):
            self.cmd_pub.publish(stop)
            time.sleep(0.02)

    def _rotate_rel(self, angle_rad, expected_qr):
        speed = float(self.get_parameter('qr_search_angular_speed').value)
        if speed <= 0.0 or abs(angle_rad) < 1e-3:
            return False
        direction = 1.0 if angle_rad > 0 else -1.0
        deadline = time.monotonic() + abs(angle_rad) / speed
        while rclpy.ok() and time.monotonic() < deadline:
            deadline += self._motion_checkpoint()
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
        yaw = math.radians(float(self.get_parameter('qr_search_sweep_deg').value))
        self._set_phase('QR_SEARCH', f'searching QR {expected_qr}')
        for target in (-yaw, 2.0 * yaw, -yaw):
            if self._rotate_rel(target, expected_qr):
                return True
        return False

    def _confirm_start_qr(self, expected_qr):
        self._qr_detected = False
        self._qr_text = ''
        deadline = time.monotonic() + float(
            self.get_parameter('start_qr_confirm_sec').value)
        self._set_phase('START_QR_SEARCH', f'follow line to find QR {expected_qr}')
        if self._line_follow_until_qr(expected_qr, deadline, label='BASLA'):
            return
        raise MissionFailure(f'QR {expected_qr} baslangicta gorulmedi')

    def _acquire_qr(self, expected_qr, start_node, goal_node, loaded,
                    retry_override=None):
        cycles = int(self.get_parameter('qr_max_cycles').value)
        for attempt in range(cycles + 1):
            if self._cancel:
                raise MissionFailure('mission canceled')
            route = self._route(start_node, goal_node, loaded)
            self._navigate_route(route, stop_qr=expected_qr)
            if retry_override:
                retry_node = retry_override
            else:
                retry_node = self._mctx.route[-2] if len(self._mctx.route) >= 2 \
                    else start_node
            if self._qr_seen(expected_qr):
                self._stop_cmd()
                return
            if self._sweep_search(expected_qr):
                self._stop_cmd()
                return
            if attempt < cycles:
                self.get_logger().warning(
                    f'QR {expected_qr} bulunamadi - {retry_node} donuluyor '
                    f'(deneme {attempt + 1}/{cycles})')
                self._navigate_route(self._route(goal_node, retry_node, loaded))
                start_node = retry_node
        raise MissionFailure(f'QR {expected_qr} bulunamadi ({cycles} deneme)')

    # ================================================================
    # SERVICE READY
    # ================================================================
    def _svc_ready(self, client, timeout=5.0):
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
        self._stop_cmd()
        self._stop_fork()
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
        self._wait_ready_state()
        response.success = True
        response.message = f'resumed by {request.operator_id or "operator"}'
        return response

    def _plc_pause(self, _request, response):
        with self._lock:
            if self._mctx is None:
                response.message = 'no active mission'
                return response
            if self._mctx.top_state == MissionState.WAITING_PLC:
                response.message = 'door permission is separate from PLC pause'
                return response
            if not self._plc_pause_required:
                self._plc_pause_required = True
                self._plc_pause_generation += 1
            self._wait_ready_state()
        self._stop_cmd()
        self._stop_fork()
        response.success = True
        response.message = 'PLC pause requested'
        return response

    def _plc_resume(self, _request, response):
        with self._lock:
            if self._mctx is None:
                response.message = 'no active mission'
                return response
            if self._safety and self._safety.estop_active:
                response.message = 'emergency stop active'
                return response
            self._plc_pause_required = False
            self._wait_ready_state()
            response.success = True
            response.message = 'PLC hold released; safety and manual holds remain active'
        return response

    def _wait_ready_state(self):
        """Reflect the highest-priority hold without clearing any other hold."""
        if self._mctx is None:
            return False
        safety = self._safety
        if safety and safety.estop_active:
            self._mctx.top_state = MissionState.EMERGENCY_STOP
            self._mctx.pause_reason = safety.reason
        elif (safety and safety.manual_mode) or self._manual_resume_required:
            self._mctx.top_state = MissionState.PAUSED_MANUAL
            self._mctx.pause_reason = safety.reason if safety and safety.manual_mode else 'operator pause'
        elif safety and not safety.motion_allowed:
            self._mctx.top_state = MissionState.PAUSED_OBSTACLE
            self._mctx.pause_reason = safety.reason
        elif self._plc_pause_required:
            self._mctx.top_state = MissionState.PAUSED_PLC
            self._mctx.pause_reason = 'PLC WAIT'
        else:
            self._mctx.top_state = MissionState.EXECUTING
            self._mctx.pause_reason = ''
            return True
        return False

    def _set_phase(self, phase, message='', target=''):
        self._mctx.phase = phase
        self._mctx.message = message
        self._mctx.active_target = target
        self._wait_ready_state()
        self._publish_state()

    def _wait_ready(self):
        started = time.monotonic()
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
                self._manual_resume_required = True
            if self._wait_ready_state():
                return time.monotonic() - started
            self._stop_cmd()
            time.sleep(0.05)

    def _motion_checkpoint(self, stop_fork=False):
        """Stop direct motion on any hold; return time spent waiting."""
        if self._cancel:
            self._stop_cmd()
            raise MissionFailure('mission canceled')
        if self._wait_ready_state():
            return 0.0
        self._stop_cmd()
        if stop_fork:
            self._stop_fork()
        return self._wait_ready()

    def _stop_fork(self):
        stop = ForkCommand()
        stop.command = ForkCommand.STOP
        self.fork_pub.publish(stop)

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
        for index, (node_id, pose) in enumerate(route[1:], start=1):
            self._mctx.route_index = index
            stopped = self._navigate(node_id, pose, stop_qr=stop_qr)
            if stopped:
                self.get_logger().info(f'QR {stop_qr} goruldu - nav durduruldu')
                return True
            self.get_logger().info(f'{node_id} duragi: 5sn bekleniyor...')
            self._hold_duration(5.0)
        return False

    def _hold_duration(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            deadline += self._motion_checkpoint()
            time.sleep(0.05)

    def _cancel_for_plc(self, handle, result_future, label):
        """Do not restart an action until its server has acknowledged cancellation."""
        canceled = self._wait_future(handle.cancel_goal_async(), 5.0, f'{label} cancel')
        if not canceled.goals_canceling and not result_future.done():
            raise MissionFailure(f'{label} cancellation not acknowledged')
        self._wait_future(result_future, 10.0, f'{label} canceled result')

    def _navigate(self, node_id, pose, stop_qr=None):
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
        # yous: YUKLU iken 180 ekle -> robot ters yone bakar, RPP geri surer
        theta = pose.theta
        if self._mctx.carrying_load and bool(
                self.get_parameter('reverse_when_loaded').value):
            theta = pose.theta + math.pi
        goal.pose.pose.orientation.z = math.sin(theta / 2.0)
        goal.pose.pose.orientation.w = math.cos(theta / 2.0)
        retries = 0
        while retries <= int(self.get_parameter('max_nav_retries').value):
            self._wait_ready()
            generation = self._plc_pause_generation
            goal.pose.header.stamp = self.get_clock().now().to_msg()
            sent = self._wait_future(
                self.nav_client.send_goal_async(goal), 10.0, 'send Nav2 goal')
            if sent.accepted:
                result_future = sent.get_result_async()
                deadline = time.monotonic() + float(
                    self.get_parameter('nav_timeout_sec').value)
                while rclpy.ok() and not result_future.done():
                    if self._plc_pause_generation != generation:
                        self._cancel_for_plc(sent, result_future, 'Nav2')
                        self._wait_ready()
                        break
                    if self._cancel:
                        sent.cancel_goal_async()
                        raise MissionFailure('mission canceled')
                    if time.monotonic() >= deadline:
                        sent.cancel_goal_async()
                        raise MissionFailure(f'Nav2 timeout for {node_id}')
                    if stop_qr and self._qr_seen(stop_qr):
                        self.get_logger().info(
                            f'QR {stop_qr} goruldu - {node_id} iptale ediliyor')
                        sent.cancel_goal_async()
                        time.sleep(0.2)
                        return True
                    time.sleep(0.05)
                else:
                    result = result_future.result()
                    if result and result.status == 4:
                        return False
                    retries += 1
                    self._mctx.retry_count += 1
                    continue
                # PLC cancellation: same semantic target, no retry consumed.
                continue
            retries += 1
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
        while True:
            self._wait_ready()
            generation = self._plc_pause_generation
            sent = self._wait_future(
                self.dock_client.send_goal_async(goal), 10.0, 'send dock goal')
            if not sent.accepted:
                raise MissionFailure('dock goal rejected')
            result_future = sent.get_result_async()
            deadline = time.monotonic() + float(self.get_parameter('dock_timeout_sec').value)
            while rclpy.ok() and not result_future.done():
                if self._plc_pause_generation != generation:
                    self._cancel_for_plc(sent, result_future, 'dock')
                    self._wait_ready()
                    break
                if self._cancel:
                    sent.cancel_goal_async()
                    raise MissionFailure('mission canceled')
                if time.monotonic() >= deadline:
                    sent.cancel_goal_async()
                    raise MissionFailure('dock timeout')
                time.sleep(0.05)
            else:
                result = result_future.result()
                if result.status != 4 or not result.result.success:
                    raise MissionFailure(result.result.message)
                self._mctx.verified_qr = station.expected_qr
                return

    def _send_fork(self, command):
        self._stop_fork()
        self._hold_duration(0.5)
        self._wait_ready()
        msg = ForkCommand()
        msg.command = command
        self.fork_pub.publish(msg)

    def _move_fork(self, command, expected_state, phase):
        self._wait_ready()
        self._set_phase(phase, phase.replace('_', ' ').lower())
        self._send_fork(command)
        generation = self._plc_pause_generation
        deadline = time.monotonic() + float(
            self.get_parameter('fork_timeout_sec').value)
        while time.monotonic() < deadline:
            if not self._wait_ready_state() or self._plc_pause_generation != generation:
                self._stop_fork()
                deadline += self._wait_ready()
                generation = self._plc_pause_generation
                if self._fork_state and self._fork_state.state == expected_state:
                    return
                self._send_fork(command)
            if self._fork_state and self._fork_state.state == expected_state:
                stop = ForkCommand()
                stop.command = ForkCommand.STOP
                self.fork_pub.publish(stop)
                self.get_logger().info(f'{phase} tamamlandi')
                return
            if self._fork_state and self._fork_state.state == ForkState.ERROR:
                ec = self._fork_state.error_code
                if ec in (ForkState.ERROR_TOP_TIMEOUT,
                           ForkState.ERROR_BOTTOM_TIMEOUT):
                    self._send_fork(command)
                else:
                    raise MissionFailure(f'fork error {ec}')
            time.sleep(0.05)
        raise MissionFailure(f'{phase} timeout')

    def _confirm_door_qr(self, expected_qr, start_node, door_node, loaded,
                         retry_override=None):
        if not expected_qr:
            if bool(self.get_parameter('door_qr_required').value):
                raise MissionFailure('door QR is required but not configured')
            return True, ''
        self._set_phase('CONFIRM_DOOR_QR', f'searching door QR {expected_qr}',
                        expected_qr)
        self._acquire_qr(expected_qr, start_node, door_node, loaded,
                         retry_override=retry_override)
        data = self._qr_text
        self._mctx.verified_qr = data
        self.get_logger().info(f'kapi QR dogrulandi: {data}')
        return True, data

    def _dropoff_custom(self, station, approach_node, loaded):
        # yous: TESLIMAT sirasi:
        #   1) Robot YUKLU -> arka kamera zaten aktif (is_up=True). QR OKU.
        #   2) /dock action: cizgiyi ARKAYA takip et 70 cm + 180 don.
        #   3) Yuku indir.
        #   4) On kameraya gec (is_up=False) -> EVE ON ile doner.
        expected_qr = str(station.expected_qr)

        # yous: yuklu -> arka kamera garanti (QR arka kamerada okunur)
        self._switch_camera(rear=True)

        self._confirm_door_qr(expected_qr, approach_node, approach_node, loaded)

        self._set_phase('DROP_OFF_CUSTOM', f'dropoff QR {expected_qr} confirmed')

        # ================================================================
        # GERI HAT TAKIBI ARTIK DOCKING KATMANINDA.
        # Mission burada sadece /dock action'i cagirir.
        # Docking: arka kamera + 70cm geri hat + 180 derece sola donus.
        # Sonrasinda mission ayni fork ve kamera adimlarina devam eder.
        # ================================================================
        self._dock(station, 'dropoff')

        # yous: yuku indir
        self._move_fork(ForkCommand.DOWN, ForkState.AT_BOTTOM, 'LOWER_LOAD')
        self._mctx.carrying_load = False
        # yous: yuk yok + eve ON ile don -> on kamera
        self._switch_camera(rear=True)
        return

    def _door(self, outbound, expected_qr=None):
        if bool(self.get_parameter('door_qr_required').value):
            if not expected_qr or not str(expected_qr).strip():
                raise MissionFailure('door QR is required but not configured')
            if not self._qr_seen(str(expected_qr).strip()):
                raise MissionFailure(
                    f'door QR {expected_qr} not confirmed before PLC request')

        # yous: her durakta QR onayindan sonra 3 saniye bekle, sonra PLC'ye istek gonder
        self.get_logger().info(
            f'waiting 3s before PLC door request ({"outbound" if outbound else "return"})')
        self._hold_duration(3.0)

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
            if self._cancel:
                raise MissionFailure('mission canceled')
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
            self._plc_pause_required = False
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
            direct_node = str(self.get_parameter('door_direct_node').value)  # yous: D4

            # yous: baslangicta ON kamera (yuk yok)
            self._switch_camera(rear=False)

            _start_qr = str(self.get_parameter('start_qr').value)
            if _start_qr:
                self.get_logger().info(f'BASLA teyit ediliyor ({_start_qr})')
                self._confirm_start_qr(_start_qr)

            self._acquire_qr(pickup.expected_qr, home, pickup.approach_node, False)

            self._move_fork(ForkCommand.DOWN, ForkState.AT_BOTTOM, 'LOWER_FORK')
            self._dock(pickup, 'pickup')
            self._move_fork(ForkCommand.UP, ForkState.AT_TOP, 'LIFT_LOAD')
            self._mctx.carrying_load = True
            # yous: yuklu -> arka kamera (geri surus, sartname)
            self._switch_camera(rear=True)

            # yous: GIDIS - KAPI1 ZORUNLU, sonra kapi izni beklenir.
            _door_out_qr = str(self.get_parameter('door_qr_outbound').value)
            self._confirm_door_qr(_door_out_qr, pickup.approach_node, west, True)
            self._door(True, _door_out_qr)
            self._navigate_route(self._route(west, east, True))
            self._navigate_route(self._route(east, direct_node, True))  # yous: DOGRUDAN D4

            self._acquire_qr(dropoff.expected_qr, direct_node, dropoff.approach_node, True)

            self._dropoff_custom(dropoff, dropoff.approach_node, True)
            self._set_phase('REPORT_DELIVERED', 'load delivered')

            # yous: DONUS - KAPI2 ZORUNLU, sonra kapi izni beklenir.
            _door_ret_qr = str(self.get_parameter('door_qr_return').value)
            _ret_node = str(self.get_parameter('door_return_retry_node').value)
            self._confirm_door_qr(_door_ret_qr, dropoff.approach_node, east, False,
                                  retry_override=_ret_node or None)
            self._door(False, _door_ret_qr)
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
                self._plc_pause_required = False

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
