"""Mock-first PLC bridge; real transport can replace only this adapter."""

import itertools

import rclpy
from rclpy.node import Node
from std_srvs.srv import Trigger

from hamals_interfaces.msg import DoorEvent, MissionTask, PlcState


class PlcBridgeNode(Node):
    def __init__(self):
        super().__init__('hamals_plc_bridge')
        self.declare_parameter('transport', 'mock')
        self.declare_parameter('mock_pickup', 'A1')
        self.declare_parameter('mock_dropoff', 'B1')
        self.declare_parameter('auto_grant_door', True)
        self.counter = itertools.count(1)
        self.active_task_id = ''
        self.last_rx = ''
        self.last_tx = ''
        self.task_pub = self.create_publisher(MissionTask, '/plc/mission_task', 10)
        self.state_pub = self.create_publisher(PlcState, '/plc/state', 10)
        self.door_pub = self.create_publisher(DoorEvent, '/plc/door_event', 10)
        self.create_subscription(DoorEvent, '/mission/door_event', self._door_request, 10)
        self.create_service(Trigger, '/plc/mock/submit_task', self._submit_task)
        self.create_timer(0.5, self._publish_state)

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

    def _door_request(self, msg):
        self.last_tx = f'DOOR {msg.door_id} event={msg.event}'
        if msg.event != DoorEvent.ARRIVED or not bool(self.get_parameter('auto_grant_door').value):
            return
        granted = DoorEvent()
        granted.stamp = self.get_clock().now().to_msg()
        granted.task_id = msg.task_id
        granted.door_id = msg.door_id
        granted.event = DoorEvent.PERMISSION_GRANTED
        granted.outbound = msg.outbound
        self.last_rx = f'DOOR {msg.door_id} GRANTED'
        self.door_pub.publish(granted)

    def _publish_state(self):
        msg = PlcState()
        msg.stamp = self.get_clock().now().to_msg()
        transport = str(self.get_parameter('transport').value)
        msg.connection_state = PlcState.CONNECTED if transport == 'mock' else PlcState.ERROR
        if transport != 'mock':
            msg.error_message = f'PLC transport adapter not implemented: {transport}'
        msg.active_task_id = self.active_task_id
        msg.last_rx = self.last_rx
        msg.last_tx = self.last_tx
        self.state_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = PlcBridgeNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
