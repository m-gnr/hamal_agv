"""ROS services exposing the immutable semantic world model."""

import math
import os

from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import Point32, Pose2D
import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy

from hamals_interfaces.msg import Door, Station, WorldModelState
from hamals_interfaces.srv import GetDoor, GetStation, PlanSemanticRoute
from .model import WorldModel, WorldModelError


def _pose(data):
    result = Pose2D()
    result.x = float(data['x'])
    result.y = float(data['y'])
    result.theta = math.radians(float(data['yaw_deg']))
    return result


class WorldModelNode(Node):
    def __init__(self):
        super().__init__('hamals_world_model')
        default = os.path.join(
            get_package_share_directory('hamals_world_model'), 'config', 'profiles', 'competition.yaml'
        )
        self.declare_parameter('profile', default)
        profile = str(self.get_parameter('profile').value)
        self.model = WorldModel(profile)
        qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.state_pub = self.create_publisher(WorldModelState, '/world_model/state', qos)
        self.create_service(GetStation, '/world_model/get_station', self._get_station)
        self.create_service(GetDoor, '/world_model/get_door', self._get_door)
        self.create_service(PlanSemanticRoute, '/world_model/plan_route', self._plan_route)
        self.timer = self.create_timer(1.0, self._publish_state)
        self._publish_state()
        self.get_logger().info(
            f'World model ready: profile={self.model.profile} checksum={self.model.checksum}'
        )

    def _publish_state(self):
        msg = WorldModelState()
        msg.stamp = self.get_clock().now().to_msg()
        msg.valid = True
        msg.profile = self.model.profile
        msg.frame_id = self.model.frame_id
        msg.config_checksum = self.model.checksum
        msg.station_ids = sorted(self.model.stations)
        msg.qr_ids = sorted(self.model.qr_markers)
        msg.stations = [self._station_message(station_id, self.model.stations[station_id])
                        for station_id in sorted(self.model.stations)]
        self.state_pub.publish(msg)

    def _station_message(self, station_id, data):
        station = Station()
        station.id = station_id
        station.type = str(data['type'])
        station.frame_id = str(data.get('zone', {}).get('frame_id', self.model.frame_id))
        station.zone = [Point32(x=float(point['x']), y=float(point['y']))
                        for point in data['zone']['vertices']]
        station.target_pose = _pose(data['target_pose'])
        station.approach_pose = _pose(data['approach_pose'])
        station.exit_pose = _pose(data['exit_pose'])
        station.expected_qr = str(data.get('expected_qr', ''))
        station.docking_profile = str(data.get('docking_profile', 'default'))
        station.approach_node = str(data['approach_node'])
        return station

    def _get_station(self, request, response):
        try:
            data = self.model.station(request.station_id)
        except WorldModelError as error:
            response.message = str(error)
            return response
        response.found = True
        response.station = self._station_message(request.station_id, data)
        response.message = 'ok'
        return response

    def _get_door(self, request, response):
        data = self.model.doors.get(request.door_id)
        if data is None:
            response.message = f'unknown door: {request.door_id}'
            return response
        door = Door()
        door.id = request.door_id
        door.plc_id = str(data.get('plc_id', request.door_id))
        door.west_node = str(data['west_node'])
        door.east_node = str(data['east_node'])
        door.outbound_wait_pose = _pose(data['request_pose']['outbound'])
        door.return_wait_pose = _pose(data['request_pose']['return'])
        response.found = True
        response.door = door
        response.message = 'ok'
        return response

    def _plan_route(self, request, response):
        try:
            route = self.model.plan_route(request.start_id, request.goal_id, request.carrying_load)
        except WorldModelError as error:
            response.message = str(error)
            return response
        response.success = True
        response.node_ids = route.node_ids
        response.poses = [_pose(item) for item in route.poses]
        response.total_cost = route.total_cost
        response.message = 'ok'
        return response


def main(args=None):
    rclpy.init(args=args)
    try:
        node = WorldModelNode()
    except Exception as error:
        rclpy.logging.get_logger('hamals_world_model').fatal(str(error))
        rclpy.shutdown()
        raise
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
