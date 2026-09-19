"""ROS-free protocol regression tests; exercise the production node methods."""

import ast
import itertools
import struct
from pathlib import Path
import threading
import time
from types import SimpleNamespace


class Message:
    def __init__(self, **kwargs):
        self.returning_home = False
        self.__dict__.update(kwargs)


class MissionState:
    IDLE, EXECUTING, WAITING_PLC, PAUSED_OBSTACLE = 1, 2, 3, 4
    PAUSED_MANUAL, ERROR, EMERGENCY_STOP, PAUSED_PLC = 5, 6, 7, 8


class DoorEvent(Message):
    ARRIVED, PERMISSION_GRANTED, PASSED = 0, 1, 2


class PlcState(Message):
    CONNECTED, ERROR = 2, 3
    CONTROL_UNKNOWN, CONTROL_WAIT, CONTROL_START_CONTINUE = 0, 1, 2


class Publisher:
    def __init__(self):
        self.messages = []

    def publish(self, msg):
        self.messages.append(msg)

    def get_subscription_count(self):
        return 1


def load_node():
    path = Path(__file__).resolve().parents[1] / 'hamals_plc_bridge/plc_bridge_node.py'
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'PlcBridgeNode')
    cls.bases = []
    mappings = [n for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id in (
                    'PICKUP_TO_BYTE', 'DROPOFF_TO_BYTE', 'BYTE_TO_PICKUP',
                    'BYTE_TO_DROPOFF') for t in n.targets)]
    module = ast.Module(body=mappings + [cls], type_ignores=[])
    ns = dict(threading=threading, time=time, itertools=itertools, struct=struct,
              MissionState=MissionState, MissionTask=Message, DoorEvent=DoorEvent,
              PlcState=PlcState, Trigger=SimpleNamespace(Request=Message),
              PICKUP_TO_BYTE={'A1': 1, 'A2': 2, 'A3': 3},
              DROPOFF_TO_BYTE={'B1': 1, 'B2': 2, 'B3': 3},
              BYTE_TO_PICKUP={1: 'A1', 2: 'A2', 3: 'A3'},
              BYTE_TO_DROPOFF={1: 'B1', 2: 'B2', 3: 'B3'})
    exec(compile(ast.fix_missing_locations(module), str(path), 'exec'), ns)
    return ns['PlcBridgeNode']


def bridge():
    node = object.__new__(load_node())
    node._lock = threading.RLock()
    node.counter = itertools.count(1)
    node._mission_state = MissionState.IDLE
    node._mission_seen = True
    node._pending_task = node._last_plc_task = None
    node._require_task_wait = node._hold_in_flight = False
    node._task_seen_running = node._pause_requested = node._resume_requested = False
    node._at_door = node._door_permission_active = False
    node._door_task_id = 'task-1'
    node._door_outbound = True
    node._last_valid_rx = None
    node._last_tx_at = None
    node._rx_pickup = node._rx_dropoff = 0
    node._rx_control = PlcState.CONTROL_UNKNOWN
    node.active_task_id = node.last_rx = node.last_tx = ''
    node._status_byte = 1
    node._cur_pickup = node._cur_dropoff = 0
    node._x = node._y = 0.0
    node.task_pub = Publisher()
    node.door_pub = Publisher()
    node.state_pub = Publisher()
    node.get_parameter = lambda name: Message(value={
        'plc_ip': '10.0.0.1', 'rx_timeout_sec': 1.0, 'door_id': 'MAIN_DOOR',
        'transport': 'udp'}[name])
    node.get_clock = lambda: Message(now=lambda: Message(to_msg=lambda: None))
    node.get_logger = lambda: Message(info=lambda *_: None, warning=lambda *_: None)
    node.calls = []
    node._request_plc_hold = lambda client, operation: node.calls.append(operation)
    node.plc_pause_client = 'pause'
    node.plc_resume_client = 'resume'
    return node


def rx(node, control, pickup=1, dropoff=2, sender='10.0.0.1'):
    node._handle_rx(bytes((pickup, dropoff, control)), (sender, 50000))


def test_pending_start_duplicate_and_repeat():
    n = bridge()
    rx(n, 1)
    assert n._pending_task == ('A1', 'B2') and not n.task_pub.messages
    rx(n, 2)
    rx(n, 2)  # stale IDLE state must not start twice
    assert len(n.task_pub.messages) == 1
    first = n.task_pub.messages[0].task_id
    n._mission_state_cb(Message(state=MissionState.EXECUTING, carrying_load=False,
                                phase='MOVE_EMPTY', pickup_id='A1', dropoff_id='B2'))
    rx(n, 2)
    assert len(n.task_pub.messages) == 1
    n._mission_state_cb(Message(state=MissionState.IDLE, carrying_load=False,
                                phase='IDLE', pickup_id='', dropoff_id=''))
    rx(n, 2)
    assert len(n.task_pub.messages) == 1
    rx(n, 1)  # A new WAIT/START handshake permits the same route again.
    rx(n, 2)
    assert len(n.task_pub.messages) == 2
    assert n.task_pub.messages[-1].task_id != first


def test_pause_resume_and_door_priority():
    n = bridge()
    n._mission_state = MissionState.EXECUTING
    rx(n, 1)
    rx(n, 1)
    assert n.calls == ['pause']
    n._mission_state = MissionState.PAUSED_PLC
    rx(n, 1)
    rx(n, 2)
    rx(n, 2)
    assert n.calls == ['pause', 'resume'] and not n.task_pub.messages
    n._at_door = True
    n._mission_state = MissionState.WAITING_PLC
    rx(n, 1)
    assert not n.door_pub.messages
    rx(n, 2)
    assert n.door_pub.messages[-1].event == DoorEvent.PERMISSION_GRANTED
    assert n.calls == ['pause', 'resume']


def test_plc_hold_is_independent_of_manual_hold():
    n = bridge()
    n._mission_state = MissionState.PAUSED_MANUAL
    rx(n, 1)
    rx(n, 2)
    assert n.calls == ['pause', 'resume']
    assert not n.task_pub.messages


def test_invalid_and_timeout():
    n = bridge()
    for data, sender in [(b'\x01\x02', '10.0.0.1'),
                         (b'\x01\x02\x01\x00', '10.0.0.1'),
                         (b'\x04\x02\x01', '10.0.0.1'),
                         (b'\x01\x04\x01', '10.0.0.1'),
                         (b'\x01\x02\x03', '10.0.0.1'),
                         (b'\x01\x02\x01', '10.0.0.2')]:
        n._handle_rx(data, (sender, 1515))
        assert n._pending_task is None and n._last_valid_rx is None
        assert n.last_rx.startswith('INVALID')
    rx(n, 1)
    assert n._is_connected()
    n._last_valid_rx = time.monotonic() - 2
    assert not n._is_connected()
    n._publish_state()
    assert n.state_pub.messages[-1].connection_state == PlcState.ERROR


def test_plc_pause_status_and_tx_format():
    import struct
    n = bridge()
    n._mission_state_cb(Message(state=MissionState.PAUSED_PLC, carrying_load=False,
                                phase='MOVE_EMPTY', pickup_id='A1', dropoff_id='B2'))
    assert n._status_byte == 5
    assert struct.unpack('<BBBhh', n._build_tx()) == (5, 1, 2, 0, 0)


def test_structured_telemetry_and_age():
    n = bridge()
    rx(n, 1)
    n._last_tx_at = time.monotonic() - 0.4
    n._mission_state_cb(Message(state=MissionState.PAUSED_PLC, carrying_load=False,
                                phase='MOVE_EMPTY', pickup_id='A1', dropoff_id='B2'))
    n._publish_state()
    msg = n.state_pub.messages[-1]
    assert (msg.rx_pickup, msg.rx_dropoff, msg.rx_control) == (1, 2, PlcState.CONTROL_WAIT)
    assert msg.tx_status == 5 and msg.transport == 'udp'
    assert 0 <= msg.rx_age_sec < 1 and 0.4 <= msg.tx_age_sec < 1
    n._last_valid_rx = time.monotonic() - 2
    n._publish_state()
    msg = n.state_pub.messages[-1]
    assert msg.connection_state == PlcState.ERROR and msg.rx_age_sec >= 2
