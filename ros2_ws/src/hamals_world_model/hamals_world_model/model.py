"""Config loading, validation and semantic route planning."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import heapq
import json
from pathlib import Path
from typing import Any

import yaml


class WorldModelError(ValueError):
    """Raised when a field profile is incomplete or inconsistent."""


@dataclass(frozen=True)
class Route:
    node_ids: list[str]
    poses: list[dict[str, float]]
    total_cost: float


def _point_in_polygon(x: float, y: float, vertices: list[dict[str, float]]) -> bool:
    inside = False
    previous = len(vertices) - 1
    for current, vertex in enumerate(vertices):
        xi, yi = float(vertex['x']), float(vertex['y'])
        xj, yj = float(vertices[previous]['x']), float(vertices[previous]['y'])
        if (yi > y) != (yj > y):
            crossing = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x <= crossing:
                inside = not inside
        previous = current
    return inside


class WorldModel:
    """Immutable, validated snapshot of one competition field."""

    def __init__(self, profile_path: str | Path):
        self.profile_path = Path(profile_path).resolve()
        profile = self._read_yaml(self.profile_path)
        if int(profile.get('schema_version', 0)) != 1:
            raise WorldModelError('profile schema_version must be 1')
        field_path = (self.profile_path.parent / str(profile['field'])).resolve()
        self.profile = str(profile.get('profile', self.profile_path.stem))
        self.data = self._read_yaml(field_path)
        self.frame_id = str(self.data.get('frame_id', 'map'))
        self.stations = dict(self.data.get('stations', {}))
        self.qr_markers = dict(self.data.get('qr_markers', {}))
        routes = self.data.get('routes', {})
        self.nodes = dict(routes.get('nodes', {}))
        self.edges = list(routes.get('edges', []))
        self.doors = dict(self.data.get('doors', {}))
        canonical = json.dumps({'profile': profile, 'field': self.data}, sort_keys=True)
        self.checksum = hashlib.sha256(canonical.encode()).hexdigest()[:16]
        self._validate()

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise WorldModelError(f'config file not found: {path}')
        with path.open(encoding='utf-8') as stream:
            result = yaml.safe_load(stream) or {}
        if not isinstance(result, dict):
            raise WorldModelError(f'config root must be a mapping: {path}')
        return result

    @staticmethod
    def _validate_pose(pose: Any, label: str) -> None:
        if not isinstance(pose, dict) or not {'x', 'y', 'yaw_deg'} <= set(pose):
            raise WorldModelError(f'{label} must contain x, y and yaw_deg')

    def _validate(self) -> None:
        if int(self.data.get('schema_version', 0)) != 1:
            raise WorldModelError('field schema_version must be 1')
        if not self.stations:
            raise WorldModelError('at least one station is required')
        for station_id, station in self.stations.items():
            vertices = station.get('zone', {}).get('vertices', [])
            if len(vertices) < 3:
                raise WorldModelError(f'{station_id}: zone needs at least three vertices')
            for key in ('target_pose', 'approach_pose', 'exit_pose'):
                self._validate_pose(station.get(key), f'{station_id}.{key}')
            target = station['target_pose']
            if not _point_in_polygon(float(target['x']), float(target['y']), vertices):
                raise WorldModelError(f'{station_id}: target_pose is outside station polygon')
            expected_qr = station.get('expected_qr')
            if expected_qr and expected_qr not in self.qr_markers:
                raise WorldModelError(f'{station_id}: unknown QR {expected_qr}')
            approach_node = station.get('approach_node')
            if approach_node not in self.nodes:
                raise WorldModelError(f'{station_id}: unknown approach_node {approach_node}')
        for node_id, node in self.nodes.items():
            self._validate_pose(node.get('pose'), f'routes.nodes.{node_id}.pose')
        for edge in self.edges:
            if edge.get('from') not in self.nodes or edge.get('to') not in self.nodes:
                raise WorldModelError(f'edge references unknown node: {edge}')
            modes = edge.get('allowed_load_states', ['empty', 'loaded'])
            if not set(modes) <= {'empty', 'loaded'}:
                raise WorldModelError(f'edge has invalid load state: {edge}')
        pickups = [key for key, value in self.stations.items() if value.get('type') == 'pickup']
        dropoffs = [key for key, value in self.stations.items() if value.get('type') == 'dropoff']
        for pickup in pickups:
            self.plan_route('START', self.stations[pickup]['approach_node'], False)
            for dropoff in dropoffs:
                self.plan_route(
                    self.stations[pickup]['approach_node'],
                    self.stations[dropoff]['approach_node'],
                    True,
                )
        for door_id, door in self.doors.items():
            for node_key in ('west_node', 'east_node'):
                if door.get(node_key) not in self.nodes:
                    raise WorldModelError(f'{door_id}: unknown {node_key} {door.get(node_key)}')
            for direction in ('outbound', 'return'):
                self._validate_pose(door.get('request_pose', {}).get(direction), f'{door_id}.{direction}')

    def station(self, station_id: str) -> dict[str, Any]:
        try:
            return self.stations[station_id]
        except KeyError as error:
            raise WorldModelError(f'unknown station: {station_id}') from error

    def plan_route(self, start_id: str, goal_id: str, carrying_load: bool) -> Route:
        if start_id not in self.nodes or goal_id not in self.nodes:
            raise WorldModelError(f'unknown route endpoint: {start_id} -> {goal_id}')
        mode = 'loaded' if carrying_load else 'empty'
        graph: dict[str, list[tuple[str, float]]] = {node: [] for node in self.nodes}
        for edge in self.edges:
            if mode not in edge.get('allowed_load_states', ['empty', 'loaded']):
                continue
            cost = float(edge.get('cost', 1.0))
            graph[edge['from']].append((edge['to'], cost))
            if edge.get('bidirectional', False):
                graph[edge['to']].append((edge['from'], cost))
        queue = [(0.0, start_id, [])]
        best: dict[str, float] = {}
        while queue:
            cost, node, prefix = heapq.heappop(queue)
            if node in best and best[node] <= cost:
                continue
            best[node] = cost
            path = prefix + [node]
            if node == goal_id:
                return Route(path, [self.nodes[item]['pose'] for item in path], cost)
            for next_node, edge_cost in graph[node]:
                heapq.heappush(queue, (cost + edge_cost, next_node, path))
        raise WorldModelError(f'no {mode} route: {start_id} -> {goal_id}')
