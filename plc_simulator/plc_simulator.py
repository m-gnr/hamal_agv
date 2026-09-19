#!/usr/bin/env python3
"""Terminal PLC simulator for the supplied TEKNOFEST UDP protocol (no ROS)."""

import argparse
from dataclasses import dataclass
import random
import socket
import struct
import threading
import time

TX_FORMAT = struct.Struct('<BBBhh')
STATUS = {
    1: 'READY', 2: 'PROCESSING', 3: 'MOVING_UNLOADED',
    4: 'MOVING_LOADED', 5: 'WAITING_AUTOMATION', 6: 'RETURNING_HOME',
    7: 'ERROR', 8: 'EMERGENCY_STOP',
}


@dataclass(frozen=True)
class RobotPacket:
    status: int
    pickup: int
    dropoff: int
    x: float
    y: float

    @property
    def description(self):
        return STATUS.get(self.status, 'UNKNOWN')


def decode_tx(data):
    if len(data) != TX_FORMAT.size:
        raise ValueError(f'expected 7 bytes, got {len(data)}')
    status, pickup, dropoff, x, y = TX_FORMAT.unpack(data)
    return RobotPacket(status, pickup, dropoff, x / 100.0, y / 100.0)


def encode_rx(pickup, dropoff, control):
    if pickup not in (1, 2, 3) or dropoff not in (1, 2, 3) or control not in (1, 2):
        raise ValueError('pickup/dropoff must be 1..3; control must be 1 or 2')
    return bytes((pickup, dropoff, control))


def task_text(task):
    pickup, dropoff, control = task
    return f'A{pickup} -> B{dropoff} | {"WAIT" if control == 1 else "START"}'


def station(prefix, value):
    return f'{prefix}{value}' if value in (1, 2, 3) else str(value)


class PlcSim:
    def __init__(self, bind_ip='0.0.0.0', port=1515, log=print):
        self.log = log
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.task = (random.randint(1, 3), random.randint(1, 3), 1)
        self.last_valid_tx = None
        self.connection_lost = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind((bind_ip, port))
            self.sock.settimeout(0.05)
        except OSError:
            self.sock.close()
            raise

    def snapshot(self):
        with self.lock:
            return self.task

    def command(self, command):
        command = command.strip().lower()
        if command == 'q':
            self.stop.set()
            return
        with self.lock:
            if command == 'x':
                self.task = (random.randint(1, 3), random.randint(1, 3), 1)
                self.log(f'[PLC] New task: {task_text(self.task)}')
            elif command in ('s', 'w'):
                self.task = (*self.task[:2], 2 if command == 's' else 1)
                self.log(f'[PLC] Control: {task_text(self.task)}')
            elif command:
                self.log('[PLC] Commands: x=random task, s=start, w=wait, q=quit')

    def check_watchdog(self, now):
        # Strict > 1.0 s; polling affects detection latency, not the threshold.
        if (self.last_valid_tx is not None and
                now - self.last_valid_tx > 1.0 and not self.connection_lost):
            self.connection_lost = True
            self.log('[PLC] ROBOT CONNECTION LOST - no valid PAKET_TX for > 1.0 s')

    def receive_once(self):
        try:
            data, sender = self.sock.recvfrom(65535)
        except socket.timeout:
            self.check_watchdog(time.monotonic())
            return
        now = time.monotonic()
        self.check_watchdog(now)
        try:
            packet = decode_tx(data)
        except ValueError as exc:
            self.log(f'[RX] INVALID packet from {sender}: {exc}')
            return
        if self.connection_lost:
            self.log('[PLC] ROBOT CONNECTION RESTORED')
        self.connection_lost = False
        self.last_valid_tx = now
        self.log(f'[RX] status={packet.status} {packet.description} | '
                 f'pickup={station("A", packet.pickup)} | '
                 f'dropoff={station("B", packet.dropoff)} | '
                 f'x={packet.x:.2f} | y={packet.y:.2f}')
        task = self.snapshot()
        self.sock.sendto(encode_rx(*task), sender)
        self.log(f'[TX] {task_text(task)}')

    def read_commands(self):
        while not self.stop.is_set():
            try:
                command = input()
            except EOFError:
                self.stop.set()
                return
            self.command(command)

    def run(self):
        ip, port = self.sock.getsockname()
        self.log(f'[PLC] Listening on {ip}:{port}')
        self.log(f'[PLC] Task: {task_text(self.snapshot())}')
        self.log('Commands (letter + Enter): x=random task, s=start, w=wait, q=quit')
        threading.Thread(target=self.read_commands, daemon=True).start()
        try:
            while not self.stop.is_set():
                self.receive_once()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop.set()
            self.sock.close()
            self.log('[PLC] Stopped')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind-ip', '--host', default='0.0.0.0',
                        help='local interface IP (default: all IPv4 interfaces)')
    parser.add_argument('--port', type=int, default=1515)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be in 1..65535')
    try:
        PlcSim(args.bind_ip, args.port).run()
    except OSError as exc:
        parser.exit(1, f'[PLC] UDP error: {exc}\n')


if __name__ == '__main__':
    main()
