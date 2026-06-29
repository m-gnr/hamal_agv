#!/usr/bin/env python3
"""
hamals_ui — ui_bridge_node
Aggregates ROS topics into a single /ui/state JSON and listens to /ui/cmd.
Supports two modes (params.yaml → mode):
  live : subscribe real ROS topics via bridge.yaml mapping
  mock : replay scenario.yaml, never subscribe to any topic
"""

import copy
import json
import math
import os
import time
from typing import Any, Dict

import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import String


# ─────────────────────────────────────────────────────────────
# Default state skeleton — always published, filled by live/mock
# ─────────────────────────────────────────────────────────────
def _default_state() -> Dict[str, Any]:
    return {
        "meta": {
            "mode": "live",
            "ts": 0.0,
            "bridge_ok": True,
            "scenarios": [],
            "scenario": "",
            "playback_status": "paused",
        },
        "connection": {"robot": False, "plc": False, "rosbridge": True},
        "switch": {"mode": "auto"},
        "estop": {"active": False, "source": "hw"},
        "battery": {
            "percent": 100.0, "voltage": 24.0, "current": 0.0,
            "eta_min": 0, "status": "normal"
        },
        "mission": {
            "id": "", "fsm": "idle",
            "pickup": "", "dropoff": "", "step": "Başlatılıyor…",
            "elapsed_s": 0,
            "timer": {"elapsed_s": 0, "target_s": 1800, "limit_s": 2700}
        },
        "pose": {
            "x": 0.0, "y": 0.0, "theta_deg": 0.0,
            "speed": 0.0, "path_deviation_cm": 0.0, "omega": 0.0
        },
        "nav": {
            "mode": "nav2", "current_goal": "",
            "total_distance_m": 0.0, "remaining_m": 0.0
        },
        "qr": {
            "id": "", "x": 0.0, "y": 0.0, "angle_deg": 0.0,
            "distance_m": 0.0, "status": "none"
        },
        "line": {
            "detected": False, "center_px": 0, "deviation_cm": 0.0,
            "status": "tracking", "history": []
        },
        "plc": {
            "connected": False, "ip": "", "port": 502,
            "protocol": "tcp_modbus", "signal": 0,
            "last_msg": "", "door_permission": "none", "expected_cmd": ""
        },
        "sensors": {
            "lidar": False, "cam_front": False,
            "cam_back": False, "imu": False, "encoder": False
        },
        "safety": {
            "estop": False, "obstacle": "safe", "obstacle_distance_m": 99.0,
            "zones": {"front": "safe", "left": "safe", "right": "safe", "back": "safe"},
            "system_health": "normal"
        },
        "cameras": {
            "active": "front",
            "front_url": "",
            "back_url": ""
        },
        "lift": {"height_pct": 0, "moving": False},
        "nodes": [],
        "messages": [],
        "errors": [],
        "logs": []
    }


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge overlay into base (modifies base in-place, returns it)."""
    for k, v in overlay.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _set_nested(d: dict, dotkey: str, value: Any):
    """Set d[a][b][c] from 'a.b.c' dotkey."""
    parts = dotkey.split(".")
    for p in parts[:-1]:
        d = d.setdefault(p, {})
    d[parts[-1]] = value


def _get_nested(obj, dotkey: str, default=None):
    """Get nested attribute from object or dict using dot-notation."""
    parts = dotkey.split(".")
    cur = obj
    for p in parts:
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            cur = getattr(cur, p, None)
        if cur is None:
            return default
    return cur


def _load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}


# ─────────────────────────────────────────────────────────────
# QoS helpers
# ─────────────────────────────────────────────────────────────
def _make_qos(qos_name: str) -> QoSProfile:
    if qos_name == "reliable":
        return QoSProfile(
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
            depth=10
        )
    return QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
        depth=10
    )


# ─────────────────────────────────────────────────────────────
# Dynamic ROS message import
# ─────────────────────────────────────────────────────────────
def _import_msg_class(type_str: str):
    """'nav_msgs/Odometry' → nav_msgs.msg.Odometry"""
    try:
        pkg, name = type_str.split("/")
        mod = __import__(f"{pkg}.msg", fromlist=[name])
        return getattr(mod, name)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# Node
# ─────────────────────────────────────────────────────────────
class UIBridgeNode(Node):

    def __init__(self):
        super().__init__("ui_bridge_node")

        pkg_share = get_package_share_directory("hamals_ui")
        cfg_dir = os.path.join(pkg_share, "config")

        self._params = _load_yaml(os.path.join(cfg_dir, "params.yaml"))
        self._bridge_cfg = _load_yaml(os.path.join(cfg_dir, "bridge.yaml"))
        self._scenario_cfg = _load_yaml(os.path.join(cfg_dir, "scenario.yaml"))

        # ROS param 'mode' (launch'tan) verilmişse params.yaml'ı geçersiz kılar
        self.declare_parameter("mode", "")
        _mode_param = self.get_parameter("mode").get_parameter_value().string_value
        self._mode = _mode_param if _mode_param else self._params.get("mode", "mock")
        ui_cfg = self._params.get("ui_bridge", {})
        self._publish_hz = float(ui_cfg.get("publish_hz", 10.0))
        self._log_buf = int(ui_cfg.get("log_buffer", 50))
        self._msg_buf = int(ui_cfg.get("msg_buffer", 20))

        cam_cfg = self._params.get("camera", {})
        vvs_host = cam_cfg.get("web_video_server_host", "robot")
        vvs_port = cam_cfg.get("web_video_server_port", 8081)
        self._cam_front_url = (
            f"http://{vvs_host}:{vvs_port}/stream"
            f"?topic={cam_cfg.get('front_topic', '/camera_front/image_raw')}"
        )
        self._cam_back_url = (
            f"http://{vvs_host}:{vvs_port}/stream"
            f"?topic={cam_cfg.get('back_topic', '/camera_back/image_raw')}"
        )

        # Live state (always sent)
        self._state = _default_state()
        self._state["meta"]["mode"] = self._mode
        self._state["cameras"]["front_url"] = self._cam_front_url
        self._state["cameras"]["back_url"] = self._cam_back_url

        # Node list from config
        self._build_nodes_list()

        # ROS publishers / subscribers
        self._state_pub = self.create_publisher(String, "/ui/state", 10)
        self._cmd_sub = self.create_subscription(
            String, "/ui/cmd", self._cmd_callback, 10
        )

        if self._mode == "live":
            self._setup_live_subscriptions()
            self._state["connection"]["robot"] = True
        else:
            self._setup_mock()

        self.create_timer(1.0 / self._publish_hz, self._publish_state)

        self.get_logger().info(
            f"ui_bridge_node started — mode={self._mode} "
            f"@ {self._publish_hz:.0f} Hz"
        )

    # ─────────────────────────────────────────────────────────
    # Node list
    # ─────────────────────────────────────────────────────────
    def _build_nodes_list(self):
        """Build initial nodes list from params.yaml."""
        expected = self._params.get("expected_nodes", [])
        planned = set(self._params.get("planned_nodes", []))
        self._state["nodes"] = [
            {"name": n, "active": n not in planned}
            for n in (expected + list(planned))
        ]

    def _update_nodes_live(self):
        """Refresh node active status by querying ROS graph (live mode only)."""
        try:
            live_nodes = set(self.get_node_names_and_namespaces())
            # get_node_names_and_namespaces returns list of (name, namespace) tuples
            live_full = {
                (ns.rstrip("/") + "/" + n) if ns != "/" else "/" + n
                for n, ns in live_nodes
            }
        except Exception:
            return
        for node in self._state["nodes"]:
            node["active"] = node["name"] in live_full

    # ─────────────────────────────────────────────────────────
    # LIVE MODE
    # ─────────────────────────────────────────────────────────
    def _setup_live_subscriptions(self):
        self._topic_last_seen: Dict[str, float] = {}
        self._topic_offline_key: Dict[str, str] = {}

        for src in self._bridge_cfg.get("sources", []):
            topic = src.get("topic", "")
            type_str = src.get("type", "")
            qos_name = src.get("qos", "best_effort")
            fields = src.get("fields", [])
            offline_key = src.get("offline_key", "")

            msg_cls = _import_msg_class(type_str)
            if msg_cls is None:
                self.get_logger().warn(
                    f"Cannot import msg type '{type_str}' for {topic} — skipping"
                )
                continue

            if offline_key:
                self._topic_offline_key[topic] = offline_key
                _set_nested(self._state, offline_key, False)

            def make_cb(t=topic, f=fields, ok=offline_key):
                def cb(msg):
                    self._on_topic(t, msg, f, ok)
                return cb

            self.create_subscription(
                msg_cls, topic, make_cb(), _make_qos(qos_name)
            )

        # Heartbeat check: mark sensors offline if not heard recently
        self.create_timer(2.0, self._check_topic_health)
        # Node status refresh (every 5 s is enough)
        self.create_timer(5.0, self._update_nodes_live)

    def _on_topic(self, topic: str, msg, fields: list, offline_key: str):
        self._topic_last_seen[topic] = time.time()
        if offline_key:
            _set_nested(self._state, offline_key, True)

        for fmap in fields:
            msg_field = fmap.get("msg_field", "")
            state_key = fmap.get("state_key", "")
            if not msg_field or not state_key:
                continue

            if state_key.startswith("_") and state_key.endswith("_json"):
                raw = getattr(msg, "data", "")
                if raw:
                    try:
                        parsed = json.loads(raw)
                        self._apply_json_topic(state_key, parsed)
                    except json.JSONDecodeError:
                        pass
                continue

            val = _get_nested(msg, msg_field, fmap.get("default"))
            if val is not None:
                _set_nested(self._state, state_key, val)

        if topic == "/odom":
            try:
                q = msg.pose.pose.orientation
                siny = 2.0 * (q.w * q.z + q.x * q.y)
                cosy = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
                theta = math.degrees(math.atan2(siny, cosy))
                self._state["pose"]["theta_deg"] = round(theta, 2)
            except Exception:
                pass

        self._state["connection"]["robot"] = True

    def _apply_json_topic(self, key: str, data: dict):
        if key == "_mission_json":
            _deep_merge(self._state["mission"], data)
        elif key == "_nav_json":
            _deep_merge(self._state["nav"], data)
        elif key == "_qr_json":
            _deep_merge(self._state["qr"], data)
        elif key == "_line_json":
            _deep_merge(self._state["line"], data)
        elif key == "_plc_json":
            _deep_merge(self._state["plc"], data)
        elif key == "_safety_json":
            _deep_merge(self._state["safety"], data)

    def _check_topic_health(self):
        now = time.time()
        for topic, ok_key in self._topic_offline_key.items():
            last = self._topic_last_seen.get(topic, 0.0)
            alive = (now - last) < 3.0
            _set_nested(self._state, ok_key, alive)
        any_alive = any(
            (now - t) < 3.0 for t in self._topic_last_seen.values()
        )
        self._state["connection"]["robot"] = any_alive

    # ─────────────────────────────────────────────────────────
    # MOCK MODE
    # ─────────────────────────────────────────────────────────
    def _setup_mock(self):
        self._state["meta"]["mode"] = "mock"

        # Read multi-scenario YAML
        scenarios_cfg = self._scenario_cfg.get("scenarios", {})
        default_name = self._scenario_cfg.get("default", next(iter(scenarios_cfg), "senaryo1"))

        self._mock_scenarios = scenarios_cfg
        self._mock_scenario_names = list(scenarios_cfg.keys())
        self._mock_active = default_name
        self._mock_paused = False
        self._mock_idx = 0
        self._mock_step_start = time.time()

        active_scen = self._mock_scenarios.get(self._mock_active, {})
        self._mock_steps = active_scen.get("steps", [])
        self._mock_loop = active_scen.get("loop", True)
        self._mock_speed = float(active_scen.get("speed", 1.0))

        # Populate nodes: expected=active, planned=inactive
        expected = self._params.get("expected_nodes", [])
        planned = set(self._params.get("planned_nodes", []))
        self._state["nodes"] = [
            {"name": n, "active": True} for n in expected
        ] + [
            {"name": n, "active": False} for n in planned
        ]

        # Meta
        self._state["meta"]["scenarios"] = self._mock_scenario_names
        self._state["meta"]["scenario"] = self._mock_active
        self._state["meta"]["playback_status"] = "playing"

        if self._mock_steps:
            self._apply_mock_step(self._mock_steps[0])

        self.create_timer(0.1, self._tick_mock)

    def _tick_mock(self):
        if self._mock_paused or not self._mock_steps:
            return
        now = time.time()
        step = self._mock_steps[self._mock_idx]
        dt = step.get("dt_s", 3) / self._mock_speed
        if (now - self._mock_step_start) >= dt:
            self._mock_idx += 1
            if self._mock_idx >= len(self._mock_steps):
                if self._mock_loop:
                    self._mock_idx = 0
                else:
                    self._mock_idx = len(self._mock_steps) - 1
                    return
            self._mock_step_start = now
            self._apply_mock_step(self._mock_steps[self._mock_idx])

    def _apply_mock_step(self, step: dict):
        # Full or partial state merge
        overlay = step.get("state", {})
        if overlay:
            _deep_merge(self._state, overlay)

        # Dot-notation patch (e.g. patch: {'mission.fsm': 'idle'})
        for dotkey, val in step.get("patch", {}).items():
            _set_nested(self._state, dotkey, val)

        # List prepend (e.g. push: {messages: {ts: ..., text: ...}})
        for listname, item in step.get("push", {}).items():
            if isinstance(self._state.get(listname), list):
                self._state[listname].insert(0, item)

        # Node partial updates (e.g. nodesPatch: {'/plc_bridge': True})
        for node_name, active in step.get("nodesPatch", {}).items():
            for n in self._state["nodes"]:
                if n["name"] == node_name:
                    n["active"] = active
                    break

        # Keep connection alive
        self._state["connection"]["robot"] = True
        self._state["connection"]["rosbridge"] = True

        # Sync mission timer
        elapsed = self._state["mission"].get("elapsed_s", 0)
        self._state["mission"]["timer"] = {
            "elapsed_s": elapsed,
            "target_s": self._params.get("mission", {}).get("target_min", 30) * 60,
            "limit_s": self._params.get("mission", {}).get("limit_min", 45) * 60,
        }

        # Truncate buffers
        self._state["messages"] = self._state["messages"][-self._msg_buf:]
        self._state["logs"] = self._state["logs"][-self._log_buf:]

        # Keep camera URLs
        self._state["cameras"]["front_url"] = self._cam_front_url
        self._state["cameras"]["back_url"] = self._cam_back_url

    def _switch_scenario(self, name: str):
        """Select a scenario and reset to step 0 (paused)."""
        if name not in self._mock_scenarios:
            self.get_logger().warn(f"Unknown scenario: {name}")
            return
        self._mock_active = name
        self._mock_idx = 0
        self._mock_step_start = time.time()
        self._mock_paused = True

        active_scen = self._mock_scenarios[name]
        self._mock_steps = active_scen.get("steps", [])
        self._mock_loop = active_scen.get("loop", True)
        self._mock_speed = float(active_scen.get("speed", 1.0))

        self._state["meta"]["scenario"] = name
        self._state["meta"]["playback_status"] = "paused"

        if self._mock_steps:
            self._apply_mock_step(self._mock_steps[0])

        self.get_logger().info(f"Scenario selected (paused): {name}")

    # ─────────────────────────────────────────────────────────
    # /ui/cmd handler
    # ─────────────────────────────────────────────────────────
    def _cmd_callback(self, msg: String):
        try:
            cmd = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warn("Received malformed /ui/cmd JSON")
            return

        cmd_type = cmd.get("type", "")
        payload = cmd.get("payload", {})

        if cmd_type == "teleop":
            self._handle_teleop(payload)
        elif cmd_type == "lift":
            self._handle_lift(payload)
        elif cmd_type == "estop":
            self._handle_estop()
        elif cmd_type == "estop_ack":
            self._state["estop"]["active"] = False
            self._state["mission"]["fsm"] = "idle"
            self._state["mission"]["step"] = "Acil durum temizlendi — hazır"
            if self._mode == "mock":
                self._mock_paused = False
                self._state["meta"]["playback_status"] = "playing"
            self.get_logger().warn("E-STOP acknowledged via UI")
        elif cmd_type == "scenario":
            if self._mode == "mock":
                self._switch_scenario(cmd.get("name", ""))
            else:
                self.get_logger().info(f"CMD: scenario (live no-op) name={cmd.get('name')}")
        elif cmd_type == "start_scenario":
            if self._mode == "mock":
                self._mock_paused = False
                self._mock_step_start = time.time()
                self._state["meta"]["playback_status"] = "playing"
                self.get_logger().info("Scenario playback started")
            else:
                self.get_logger().info("CMD: start_scenario (live no-op)")
        elif cmd_type == "stop_scenario":
            if self._mode == "mock":
                self._mock_paused = True
                self._state["meta"]["playback_status"] = "paused"
                self.get_logger().info("Scenario playback stopped")
        elif cmd_type == "switch_mode":
            mode_val = payload if isinstance(payload, str) else payload.get("mode", "")
            if not mode_val:
                mode_val = cmd.get("payload", "")
            if mode_val in ("manual", "auto"):
                self._state["switch"]["mode"] = mode_val
                self.get_logger().info(f"Switch mode → {mode_val}")
            else:
                self.get_logger().warn(f"CMD: switch_mode unknown value: {mode_val!r}")
        elif cmd_type == "connect_plc":
            self.get_logger().info("CMD: connect_plc (no-op: plc package not yet present)")
        elif cmd_type == "set_ready":
            self.get_logger().info("CMD: set_ready (no-op: mission_manager not yet present)")
        elif cmd_type == "mapping":
            self.get_logger().info(f"CMD: mapping action={payload.get('action') if isinstance(payload, dict) else payload}")
        elif cmd_type == "define_route":
            self.get_logger().info("CMD: define_route (no-op)")
        else:
            self.get_logger().warn(f"Unknown /ui/cmd type: {cmd_type}")

    def _handle_estop(self):
        self._state["estop"]["active"] = True
        self._state["mission"]["fsm"] = "emergency_stop"
        self._state["pose"]["speed"] = 0.0
        self._state["mission"]["step"] = "ACİL DURDURMA — yazılımsal"
        if self._mode == "mock":
            self._mock_paused = True
            self._state["meta"]["playback_status"] = "paused"
        self.get_logger().error("E-STOP activated via UI")

    def _handle_teleop(self, payload: dict):
        if not isinstance(payload, dict):
            return
        linear = float(payload.get("linear", 0.0))
        angular = float(payload.get("angular", 0.0))
        if self._state["switch"]["mode"] != "manual":
            self.get_logger().warn("Teleop rejected: switch is not in MANUAL mode")
            return
        if self._mode == "live":
            from geometry_msgs.msg import Twist
            tw = Twist()
            tw.linear.x = linear
            tw.angular.z = angular
            if not hasattr(self, "_cmd_vel_pub"):
                self._cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel", 10)
            self._cmd_vel_pub.publish(tw)
        else:
            self._state["pose"]["speed"] = abs(linear)

    def _handle_lift(self, payload: dict):
        action = payload.get("action", "") if isinstance(payload, dict) else payload
        lift = self._state.setdefault("lift", {"height_pct": 0, "moving": False})
        step = 10
        if action == "up":
            lift["height_pct"] = min(100, lift["height_pct"] + step)
            lift["moving"] = True
        elif action == "down":
            lift["height_pct"] = max(0, lift["height_pct"] - step)
            lift["moving"] = True
        else:
            lift["moving"] = False
        self.get_logger().info(
            f"CMD: lift action={action} height_pct={lift['height_pct']}"
        )

    # ─────────────────────────────────────────────────────────
    # Publish
    # ─────────────────────────────────────────────────────────
    def _publish_state(self):
        self._state["meta"]["ts"] = time.time()
        batt = self._state["battery"]
        if batt["current"] > 0.1:
            cap_wh = batt["voltage"] * 10.0
            power_w = batt["voltage"] * batt["current"]
            batt["eta_min"] = int(cap_wh * (batt["percent"] / 100.0) * 60.0 / power_w)
        batt["status"] = "critical" if batt["percent"] < 10 else (
            "low" if batt["percent"] < 20 else "normal"
        )
        msg = String()
        msg.data = json.dumps(self._state, ensure_ascii=False)
        self._state_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = UIBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
