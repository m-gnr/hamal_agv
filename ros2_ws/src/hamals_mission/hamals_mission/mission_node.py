"""Config-driven hierarchical mission coordinator."""

from __future__ import annotations

import asyncio
import math
import threading
import time

from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
import rclpy
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

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
            'nav_timeout_sec': 180.0, 'dock_timeout_sec': 45.0,
            'fork_timeout_sec': 60.0, 'door_timeout_sec': 120.0,
            'max_nav_retries': 1, 'home_node': 'START', 'door_id': 'MAIN_DOOR',
        }.items():
            self.declare_parameter(name, value)
        group = ReentrantCallbackGroup()
        self._lock = threading.RLock()
        self.context = None
        self._worker = None
        self._cancel = False
        self._manual_resume_required = False
        self._safety = None
        self._world_checksum = ''
        self._fork_state = None
        self._door_permission = None
        self.state_pub = self.create_publisher(MissionState, '/mission/state', 10)
        self.door_pub = self.create_publisher(DoorEvent, '/mission/door_event', 10)
        self.fork_pub = self.create_publisher(ForkCommand, '/fork/cmd', 10)
        self.create_subscription(
            MissionTask, '/plc/mission_task', self._task_received, 10, callback_group=group
        )
        self.create_subscription(
            SafetyState, '/safety/state', self._safety_received, 10, callback_group=group
        )
        self.create_subscription(
            ForkState, '/fork/state', self._fork_received, 10, callback_group=group
        )
        self.create_subscription(
            DoorEvent, '/plc/door_event', self._door_received, 10, callback_group=group
        )
        self.create_subscription(
            WorldModelState,
            '/world_model/state',
            self._world_received,
            10,
            callback_group=group,
        )
        self.station_client = self.create_client(
            GetStation, '/world_model/get_station', callback_group=group
        )
        self.door_client = self.create_client(
            GetDoor, '/world_model/get_door', callback_group=group
        )
        self.route_client = self.create_client(
            PlanSemanticRoute, '/world_model/plan_route', callback_group=group
        )
        self.nav_client = ActionClient(
            self, NavigateToPose, '/navigate_to_pose', callback_group=group
        )
        self.dock_client = ActionClient(self, Dock, '/dock', callback_group=group)
        self.create_service(PauseMission, '/mission/pause', self._pause, callback_group=group)
        self.create_service(ResumeMission, '/mission/resume', self._resume, callback_group=group)
        self.action_server = ActionServer(
            self, ExecuteMission, '/mission/execute', execute_callback=self._execute_action,
            goal_callback=self._goal_callback, cancel_callback=lambda _: CancelResponse.ACCEPT,
            callback_group=group,
        )
        self.create_timer(0.25, self._publish_state, callback_group=group)

    def _goal_callback(self, _goal):
        with self._lock:
            busy = self._worker is not None or self.context is not None
            return GoalResponse.REJECT if busy else GoalResponse.ACCEPT

    async def _execute_action(self, handle):
        worker = asyncio.create_task(asyncio.to_thread(self._run_task, handle.request.task))
        while not worker.done():
            if handle.is_cancel_requested:
                self._cancel = True
            handle.publish_feedback(ExecuteMission.Feedback(state=self._state_message()))
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
            message=message,
        )

    def _task_received(self, task):
        with self._lock:
            if self._worker is not None or self.context is not None:
                self.get_logger().warning(f'Ignoring task {task.task_id}: mission busy')
                return
            self._worker = threading.Thread(target=self._run_task, args=(task,), daemon=True)
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
        if self.context is None:
            response.message = 'no active mission'
            return response
        self.context.pause_reason = request.reason or 'operator pause'
        self.context.top_state = MissionState.PAUSED_MANUAL
        self._manual_resume_required = True
        response.success = True
        response.message = 'paused'
        return response

    def _resume(self, request, response):
        if self.context is None:
            response.message = 'no active mission'
            return response
        if self._safety is None or not self._safety.motion_allowed:
            response.message = 'safety conditions do not allow resume'
            return response
        self._manual_resume_required = False
        self.context.pause_reason = ''
        self.context.top_state = MissionState.EXECUTING
        response.success = True
        response.message = f'resumed by {request.operator_id or "operator"}'
        return response

    def _set_phase(self, phase, message='', target=''):
        self.context.phase = phase
        self.context.message = message
        self.context.active_target = target
        self.context.top_state = MissionState.EXECUTING
        self._publish_state()

    def _wait_ready(self):
        while rclpy.ok():
            if self._cancel:
                raise MissionFailure('mission canceled')
            safety = self._safety
            if safety and safety.estop_active:
                self.context.top_state = MissionState.EMERGENCY_STOP
                raise MissionFailure('emergency stop active')
            if safety and safety.state == SafetyState.SENSOR_STALE:
                raise MissionFailure(safety.reason or 'critical safety sensor stale')
            if safety and safety.manual_mode:
                self.context.top_state = MissionState.PAUSED_MANUAL
                self.context.pause_reason = safety.reason
                self._manual_resume_required = True
            elif safety and not safety.motion_allowed:
                self.context.top_state = MissionState.PAUSED_OBSTACLE
                self.context.pause_reason = safety.reason
            elif not self._manual_resume_required:
                self.context.top_state = MissionState.EXECUTING
                self.context.pause_reason = ''
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
        if not self.station_client.wait_for_service(timeout_sec=5.0):
            raise MissionFailure('world model station service unavailable')
        request = GetStation.Request()
        request.station_id = station_id
        response = self._wait_future(self.station_client.call_async(request), 5.0, 'get station')
        if not response.found:
            raise MissionFailure(response.message)
        return response.station

    def _route(self, start_id, goal_id, loaded):
        if not self.route_client.wait_for_service(timeout_sec=5.0):
            raise MissionFailure('world model route service unavailable')
        request = PlanSemanticRoute.Request()
        request.start_id, request.goal_id, request.carrying_load = start_id, goal_id, loaded
        response = self._wait_future(self.route_client.call_async(request), 5.0, 'plan route')
        if not response.success:
            raise MissionFailure(response.message)
        self.context.route = list(response.node_ids)
        return list(zip(response.node_ids, response.poses))

    def _door_model(self):
        if not self.door_client.wait_for_service(timeout_sec=5.0):
            raise MissionFailure('world model door service unavailable')
        request = GetDoor.Request()
        request.door_id = str(self.get_parameter('door_id').value)
        response = self._wait_future(self.door_client.call_async(request), 5.0, 'get door')
        if not response.found:
            raise MissionFailure(response.message)
        return response.door

    def _navigate_route(self, route):
        for index, (node_id, pose) in enumerate(route[1:], start=1):
            self.context.route_index = index
            self._navigate(node_id, pose)

    def _navigate(self, node_id, pose):
        self._wait_ready()
        phase = 'MOVE_LOADED' if self.context.carrying_load else 'MOVE_EMPTY'
        self._set_phase(phase, f'navigating to {node_id}', node_id)
        if not self.nav_client.wait_for_server(timeout_sec=10.0):
            raise MissionFailure('Nav2 action unavailable')
        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x, goal.pose.pose.position.y = pose.x, pose.y
        goal.pose.pose.orientation.z = math.sin(pose.theta / 2.0)
        goal.pose.pose.orientation.w = math.cos(pose.theta / 2.0)
        for _ in range(int(self.get_parameter('max_nav_retries').value) + 1):
            sent = self._wait_future(self.nav_client.send_goal_async(goal), 10.0, 'send Nav2 goal')
            if sent.accepted:
                result = self._wait_future(
                    sent.get_result_async(),
                    float(self.get_parameter('nav_timeout_sec').value),
                    'Nav2 goal',
                )
                if result.status == 4:
                    return
            self.context.retry_count += 1
        raise MissionFailure(f'Nav2 failed for {node_id}')

    def _dock(self, station, operation):
        self._wait_ready()
        self.context.expected_qr = station.expected_qr
        self._set_phase(f'DOCK_{operation.upper()}', f'docking at {station.id}', station.id)
        if not self.dock_client.wait_for_server(timeout_sec=10.0):
            raise MissionFailure('dock action unavailable')
        goal = Dock.Goal()
        goal.station_id = station.id
        goal.operation = operation
        goal.expected_qr = station.expected_qr
        goal.profile = station.docking_profile
        sent = self._wait_future(self.dock_client.send_goal_async(goal), 10.0, 'send dock goal')
        if not sent.accepted:
            raise MissionFailure('dock goal rejected')
        result = self._wait_future(
            sent.get_result_async(),
            float(self.get_parameter('dock_timeout_sec').value),
            'dock',
        )
        if result.status != 4 or not result.result.success:
            raise MissionFailure(result.result.message)
        self.context.verified_qr = station.expected_qr

    def _move_fork(self, command, expected_state, phase):
        self._wait_ready()
        self._set_phase(phase, phase.replace('_', ' ').lower())
        msg = ForkCommand()
        msg.command = command
        self.fork_pub.publish(msg)
        deadline = time.monotonic() + float(self.get_parameter('fork_timeout_sec').value)
        while time.monotonic() < deadline:
            if self._fork_state and self._fork_state.state == ForkState.ERROR:
                raise MissionFailure(f'fork error {self._fork_state.error_code}')
            if self._fork_state and self._fork_state.state == expected_state:
                return
            time.sleep(0.05)
        raise MissionFailure(f'{phase} timeout')

    def _door(self, outbound):
        self._wait_ready()
        phase = 'REQUEST_DOOR_OUTBOUND' if outbound else 'REQUEST_DOOR_RETURN'
        self._set_phase(phase, 'waiting for PLC door permission')
        self.context.top_state = MissionState.WAITING_PLC
        self._door_permission = None
        event = DoorEvent()
        event.stamp = self.get_clock().now().to_msg()
        event.task_id = self.context.task_id
        event.door_id = str(self.get_parameter('door_id').value)
        event.event, event.outbound = DoorEvent.ARRIVED, outbound
        self.door_pub.publish(event)
        deadline = time.monotonic() + float(self.get_parameter('door_timeout_sec').value)
        while time.monotonic() < deadline:
            if self._door_permission == (self.context.task_id, outbound):
                self.context.top_state = MissionState.EXECUTING
                return
            time.sleep(0.05)
        raise MissionFailure('PLC door permission timeout')

    def _run_task(self, task):
        with self._lock:
            if self.context is not None:
                return False, 'mission busy'
            self._cancel = False
            self.context = MissionContext(
                task_id=task.task_id,
                pickup_id=task.pickup_id,
                dropoff_id=task.dropoff_id,
                top_state=MissionState.EXECUTING,
                config_checksum=self._world_checksum,
            )
        try:
            self._set_phase('VALIDATE_TASK', 'validating task')
            pickup, dropoff = self._station(task.pickup_id), self._station(task.dropoff_id)
            if pickup.type != 'pickup' or dropoff.type != 'dropoff':
                raise MissionFailure('invalid pickup/dropoff station types')
            home = str(self.get_parameter('home_node').value)
            door = self._door_model()
            west, east = door.west_node, door.east_node
            self._navigate_route(self._route(home, pickup.approach_node, False))
            self._move_fork(ForkCommand.DOWN, ForkState.AT_BOTTOM, 'LOWER_FORK')
            self._dock(pickup, 'pickup')
            self._move_fork(ForkCommand.UP, ForkState.AT_TOP, 'LIFT_LOAD')
            self.context.carrying_load = True
            self._navigate_route(self._route(pickup.approach_node, west, True))
            self._door(True)
            self._navigate_route(self._route(west, east, True))
            self._navigate_route(self._route(east, dropoff.approach_node, True))
            self._dock(dropoff, 'dropoff')
            self._move_fork(ForkCommand.DOWN, ForkState.AT_BOTTOM, 'LOWER_LOAD')
            self.context.carrying_load = False
            self._set_phase('REPORT_DELIVERED', 'load delivered')
            self._navigate_route(self._route(dropoff.approach_node, east, False))
            self._door(False)
            self._navigate_route(self._route(east, west, False))
            self._navigate_route(self._route(west, home, False))
            self._set_phase('REPORT_COMPLETE', 'mission completed', home)
            return True, 'mission completed'
        except Exception as error:
            self.context.top_state = MissionState.ERROR
            self.context.error_code = type(error).__name__
            self.context.message = str(error)
            self.get_logger().error(f'Mission {task.task_id} failed: {error}')
            return False, str(error)
        finally:
            stop = ForkCommand()
            stop.command = ForkCommand.STOP
            self.fork_pub.publish(stop)
            self._publish_state()
            time.sleep(0.1)
            with self._lock:
                self.context = None
                self._worker = None

    def _state_message(self):
        msg = MissionState()
        msg.stamp = self.get_clock().now().to_msg()
        context = self.context
        if context is None:
            msg.state, msg.phase, msg.message = MissionState.IDLE, 'IDLE', 'ready for task'
            msg.config_checksum = self._world_checksum
        else:
            msg.state = context.top_state
            fields = (
                'phase', 'task_id', 'pickup_id', 'dropoff_id', 'active_target',
                'expected_qr', 'verified_qr', 'pause_reason', 'error_code',
                'message', 'config_checksum',
            )
            for field in fields:
                setattr(msg, field, getattr(context, field))
            msg.carrying_load, msg.retry_count = context.carrying_load, context.retry_count
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
