"""ROS-free competition checks using production bridge methods and UDP sockets."""
import socket
import struct
import threading
import time
from types import SimpleNamespace as NS

import pytest

from test_plc_protocol import bridge, Message, MissionState, PlcState


def test_exact_endian_negative_and_clamp():
    n = bridge()
    n._status_byte, n._cur_pickup, n._cur_dropoff = 4, 2, 3
    n._pose_cb(NS(pose=NS(pose=NS(position=NS(x=1.23, y=-0.45)))))
    assert n._build_tx() == bytes.fromhex('04 02 03 7b 00 d3 ff')
    n._x, n._y = -1000., 1000.
    assert struct.unpack('<BBBhh', n._build_tx()) == (4, 2, 3, -32768, 32767)
    n._x, n._y = -.019, .019
    assert struct.unpack('<BBBhh', n._build_tx())[3:] == (-1, 1)


@pytest.mark.parametrize('pickup', (1, 2, 3))
@pytest.mark.parametrize('dropoff', (1, 2, 3))
def test_station_roundtrip(pickup, dropoff):
    n = bridge()
    n._handle_rx(bytes((pickup, dropoff, 1)), ('10.0.0.1', 1515))
    assert not n.task_pub.messages
    n._handle_rx(bytes((pickup, dropoff, 2)), ('10.0.0.1', 1515))
    task = n.task_pub.messages[0]
    assert (task.pickup_id, task.dropoff_id, task.source) == (
        f'A{pickup}', f'B{dropoff}', 'plc_udp')
    n._mission_state_cb(Message(state=MissionState.EXECUTING, carrying_load=False,
                                phase='MOVE', pickup_id=task.pickup_id,
                                dropoff_id=task.dropoff_id))
    assert n._build_tx()[1:3] == bytes((pickup, dropoff))


@pytest.mark.parametrize('state,phase,loaded,expected', [
    (MissionState.IDLE, 'IDLE', False, 1),
    (MissionState.EXECUTING, 'VALIDATE_TASK', False, 2),
    (MissionState.EXECUTING, 'MOVE', False, 3),
    (MissionState.EXECUTING, 'MOVE', True, 4),
    (MissionState.WAITING_PLC, 'REQUEST_DOOR_RETURN', False, 5),
    (MissionState.PAUSED_PLC, 'MOVE', False, 5),
    (MissionState.EXECUTING, 'REPORT_COMPLETE', False, 6),
    (MissionState.ERROR, 'REPORT_COMPLETE', False, 7),
    (MissionState.EMERGENCY_STOP, '', False, 8),
    (99, '', False, 2),
])
def test_observed_status_mapping(state, phase, loaded, expected):
    n = bridge()
    n._mission_state_cb(Message(state=state, phase=phase, carrying_load=loaded,
                                pickup_id='', dropoff_id='', returning_home=phase == 'REPORT_COMPLETE'))
    assert n._build_tx()[0] == expected


@pytest.mark.parametrize('invalid', [float('nan'), float('inf'), -float('inf'), 1e308])
def test_tx_thread_recovers_after_invalid_coordinate(invalid):
    n = bridge()
    n._stop = False
    n._x = invalid
    n.get_parameter = lambda key: NS(value={
        'plc_ip': '192.168.100.100', 'plc_port': 1515, 'tx_rate_hz': 1.0}[key])
    packets, warnings = [], []
    n._sock = NS(sendto=lambda data, endpoint: packets.append((data, endpoint)))
    n.get_logger = lambda: NS(warning=warnings.append)
    cycles = iter((True, True, False))
    ns = n._tx_loop.__func__.__globals__
    ns['rclpy'] = NS(ok=lambda: next(cycles))
    ns['time'] = NS(monotonic=lambda: 10., sleep=lambda _: setattr(n, '_x', 1.23))
    n._tx_loop()
    assert len(warnings) == 1 and len(packets) == 1
    assert packets[0][1] == ('192.168.100.100', 1515)
    assert struct.unpack('<BBBhh', packets[0][0])[3] == 123


def test_competition_sender_timeout_and_recovery():
    n = bridge()
    n.get_parameter = lambda key: NS(value={
        'plc_ip': '192.168.100.100', 'rx_timeout_sec': 1., 'transport': 'udp'}[key])
    for sender in ('172.20.10.4', '10.100.68.144'):
        n._handle_rx(b'\x02\x03\x01', (sender, 1515))
        assert n._last_valid_rx is None
    n._handle_rx(b'\x02\x03\x01', ('192.168.100.100', 50000))
    n._publish_state()
    assert n.state_pub.messages[-1].connection_state == PlcState.CONNECTED
    n._last_valid_rx = time.monotonic() - 1.01
    n._publish_state()
    assert n.state_pub.messages[-1].connection_state == PlcState.ERROR
    n._handle_rx(b'\x02\x03\x01', ('192.168.100.100', 1515))
    n._publish_state()
    assert n.state_pub.messages[-1].connection_state == PlcState.CONNECTED


def test_real_udp_same_unbound_socket_and_one_hz():
    n = bridge()
    n._stop = False
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind(('127.0.0.1', 0))
        server.settimeout(2.)
        endpoint = server.getsockname()
        n.get_parameter = lambda key: NS(value={
            'plc_ip': endpoint[0], 'plc_port': endpoint[1], 'tx_rate_hz': 1.,
            'rx_timeout_sec': 1., 'door_id': 'MAIN_DOOR'}[key])
        n.get_logger = lambda: NS(warning=lambda *_: None, error=lambda *_: None,
                                  info=lambda *_: None)
        ns = n._tx_loop.__func__.__globals__
        ns.update(socket=socket, rclpy=NS(ok=lambda: True))
        n._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        n._sock.settimeout(.1)
        threads = [threading.Thread(target=fn, daemon=True)
                   for fn in (n._tx_loop, n._rx_loop)]
        times, sources = [], []
        try:
            for thread in threads:
                thread.start()
            for _ in range(3):
                packet, source = server.recvfrom(64)
                assert len(packet) == 7
                times.append(time.monotonic())
                sources.append(source)
                server.sendto(b'\x02\x03\x01', source)
            deadline = time.monotonic() + .5
            while n._pending_task is None and time.monotonic() < deadline:
                time.sleep(.01)
            assert n._pending_task == ('A2', 'B3')
            assert len(set(sources)) == 1
            assert all(.8 < b - a < 1.3 for a, b in zip(times, times[1:]))
        finally:
            n._stop = True
            for thread in threads:
                thread.join(2.)
            n._sock.close()
        assert all(not thread.is_alive() for thread in threads)


def test_return_status_is_explicit_and_survives_every_return_phase():
    n = bridge()
    for phase in ('REPORT_DELIVERED', 'CONFIRM_DOOR_QR', 'QR_SEARCH',
                  'MOVE_EMPTY', 'REPORT_COMPLETE'):
        n._mission_state_cb(Message(state=MissionState.EXECUTING, phase=phase,
                                    carrying_load=False, pickup_id='A1', dropoff_id='B2',
                                    returning_home=True))
        assert n._build_tx()[0] == 6
    # Identical phase name on the outbound journey is ordinary unloaded motion.
    n._mission_state_cb(Message(state=MissionState.EXECUTING, phase='MOVE_EMPTY',
                                carrying_load=False, pickup_id='A1', dropoff_id='B2'))
    assert n._build_tx()[0] == 3
    for state, expected in ((MissionState.WAITING_PLC, 5), (MissionState.PAUSED_PLC, 5),
                            (MissionState.ERROR, 7), (MissionState.EMERGENCY_STOP, 8)):
        n._mission_state_cb(Message(state=state, phase='MOVE_EMPTY', carrying_load=False,
                                    pickup_id='A1', dropoff_id='B2', returning_home=True))
        assert n._build_tx()[0] == expected


def test_running_wait_cannot_arm_next_task_and_pending_must_match():
    n = bridge()
    send = lambda control, pu=1, do=2: n._handle_rx(bytes((pu, do, control)), ('10.0.0.1', 1515))
    send(2)  # Preserve initial direct START support.
    n._mission_state_cb(Message(state=MissionState.EXECUTING, phase='MOVE_EMPTY',
                                carrying_load=False, pickup_id='A1', dropoff_id='B2'))
    send(1)
    send(2)
    n._mission_state_cb(Message(state=MissionState.IDLE, phase='IDLE',
                                carrying_load=False, pickup_id='', dropoff_id=''))
    for _ in range(10):
        send(2)
    send(2, 3, 3)  # A changed pair alone is not a new handshake either.
    assert len(n.task_pub.messages) == 1
    send(1)
    send(2, 3, 3)
    assert len(n.task_pub.messages) == 1
    send(2)
    send(2)
    assert len(n.task_pub.messages) == 2


def test_bridge_wait_start_calls_real_mission_handlers_and_preserves_manual_hold():
    import runpy
    from pathlib import Path
    fixture = Path(__file__).resolve().parents[2] / 'hamals_mission/test/test_plc_pause.py'
    mission = runpy.run_path(str(fixture))['mission']()
    n = bridge()
    n._mission_state = MissionState.EXECUTING
    n._request_plc_hold = n.__class__._request_plc_hold.__get__(n)
    operations = []

    def client(callback, operation):
        def call(_):
            operations.append(operation)
            response = callback(None, NS(success=False, message=''))
            return NS(add_done_callback=lambda cb: cb(NS(result=lambda: response)))
        return NS(service_is_ready=lambda: True, call_async=call)

    n.plc_pause_client = client(mission._plc_pause, 'pause')
    n.plc_resume_client = client(mission._plc_resume, 'resume')
    send = lambda c: n._handle_rx(bytes((1, 2, c)), ('10.0.0.1', 1515))
    send(1)
    assert mission._plc_pause_required
    assert mission._mctx.top_state == MissionState.PAUSED_PLC
    assert mission.cmd_pub.messages[-1].linear.x == 0
    assert mission.fork_pub.messages[-1].command == 0
    send(1)
    assert operations == ['pause']
    mission._manual_resume_required = True
    send(2)
    assert not mission._plc_pause_required
    assert mission._mctx.top_state == MissionState.PAUSED_MANUAL
    assert not n._pause_requested and not n._resume_requested
    # Another PLC WAIT must still be accepted while the manual hold remains.
    n._mission_state = MissionState.PAUSED_MANUAL
    send(1)
    assert mission._plc_pause_required
    send(2)
    assert mission._manual_resume_required and not mission._plc_pause_required
    assert operations == ['pause', 'resume', 'pause', 'resume']


def test_service_calls_are_serialized_across_wait_start():
    n = bridge()
    n._request_plc_hold = n.__class__._request_plc_hold.__get__(n)
    n._mission_state = MissionState.EXECUTING
    callbacks, calls = [], []
    def client(name):
        def call(_):
            calls.append(name)
            return NS(add_done_callback=callbacks.append)
        return NS(service_is_ready=lambda: True, call_async=call)
    n.plc_pause_client, n.plc_resume_client = client('pause'), client('resume')
    send = lambda c: n._handle_rx(bytes((1, 2, c)), ('10.0.0.1', 1515))
    send(1)
    send(2)
    assert calls == ['pause']
    callbacks.pop(0)(NS(result=lambda: NS(success=True)))
    send(2)
    assert calls == ['pause', 'resume']
    callbacks.pop(0)(NS(result=lambda: NS(success=True)))
    assert not n._hold_in_flight and not n._pause_requested


def test_start_is_not_consumed_before_mission_is_ready():
    n = bridge()
    n._mission_seen = False
    n.task_pub.get_subscription_count = lambda: 0
    send = lambda: n._handle_rx(b'\x01\x02\x02', ('10.0.0.1', 1515))
    send()
    assert not n.active_task_id and not n._require_task_wait
    n._mission_state_cb(Message(state=MissionState.IDLE, phase='IDLE',
                                carrying_load=False, pickup_id='', dropoff_id=''))
    send()
    assert not n.active_task_id
    n.task_pub.get_subscription_count = lambda: 1
    send()
    send()
    assert len(n.task_pub.messages) == 1
