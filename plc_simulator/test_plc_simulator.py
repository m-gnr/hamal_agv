"""Run with python3 -m unittest discover -s plc_simulator -v; ROS not needed."""
import socket
import unittest
from unittest.mock import patch

from plc_simulator import PlcSim, STATUS, decode_tx, encode_rx


class ProtocolTests(unittest.TestCase):
    def test_decode_example(self):
        packet = decode_tx(bytes.fromhex('04 02 03 7b 00 d3 ff'))
        self.assertEqual((packet.status, packet.pickup, packet.dropoff), (4, 2, 3))
        self.assertEqual((packet.x, packet.y), (1.23, -0.45))
        self.assertEqual(packet.description, 'MOVING_LOADED')

    def test_negative_coordinates_and_limits(self):
        packet = decode_tx(bytes.fromhex('03 01 02 00 80 ff ff'))
        self.assertEqual((packet.x, packet.y), (-327.68, -0.01))

    def test_status_descriptions(self):
        expected = ['READY', 'PROCESSING', 'MOVING_UNLOADED', 'MOVING_LOADED',
                    'WAITING_AUTOMATION', 'RETURNING_HOME', 'ERROR', 'EMERGENCY_STOP']
        self.assertEqual(list(STATUS.values()), expected)
        for status, description in enumerate(expected, 1):
            self.assertEqual(decode_tx(bytes([status]) + bytes(6)).description, description)
        self.assertEqual(decode_tx(bytes(7)).description, 'UNKNOWN')

    def test_invalid_lengths(self):
        for size in (6, 8):
            with self.assertRaises(ValueError):
                decode_tx(bytes(size))

    def test_responses(self):
        self.assertEqual(encode_rx(2, 3, 1), bytes([2, 3, 1]))
        self.assertEqual(encode_rx(2, 3, 2), bytes([2, 3, 2]))
        for task in ((0, 3, 1), (2, 4, 1), (2, 3, 0)):
            with self.assertRaises(ValueError):
                encode_rx(*task)


class SimulatorTests(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.sim = PlcSim('127.0.0.1', 0, self.logs.append)
        self.addCleanup(self.sim.sock.close)

    def test_commands_and_random_reset(self):
        self.assertEqual(self.sim.snapshot()[2], 1)
        for _ in range(100):
            self.sim.command('s')
            self.assertEqual(self.sim.snapshot()[2], 2)
            self.sim.command('x')
            pickup, dropoff, control = self.sim.snapshot()
            self.assertIn(pickup, (1, 2, 3))
            self.assertIn(dropoff, (1, 2, 3))
            self.assertEqual(control, 1)
        self.sim.command('s')
        self.sim.command('w')
        self.assertEqual(self.sim.snapshot()[2], 1)
        self.sim.command('q')
        self.assertTrue(self.sim.stop.is_set())

    def test_udp_response_repeat_and_invalid_no_reply(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.bind(('127.0.0.1', 0))
            client.settimeout(0.1)
            endpoint = self.sim.sock.getsockname()
            for command in ('w', 's', 's'):
                self.sim.command(command)
                client.sendto(bytes.fromhex('04 02 03 7b 00 d3 ff'), endpoint)
                self.sim.receive_once()
                data, sender = client.recvfrom(64)
                self.assertEqual(data, encode_rx(*self.sim.snapshot()))
                self.assertEqual(sender, endpoint)
            last_valid = self.sim.last_valid_tx
            for size in (6, 8):
                client.sendto(bytes(size), endpoint)
                self.sim.receive_once()
                with self.assertRaises(socket.timeout):
                    client.recvfrom(64)
                self.assertEqual(self.sim.last_valid_tx, last_valid)

    def test_watchdog_strict_threshold_once_and_restore(self):
        self.sim.check_watchdog(100)
        self.assertFalse(self.logs)
        self.sim.last_valid_tx = 10
        self.sim.check_watchdog(11)
        self.assertFalse(self.logs)
        self.sim.check_watchdog(11.001)
        self.sim.check_watchdog(12)
        self.assertEqual(len(self.logs), 1)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
            client.sendto(bytes(7), self.sim.sock.getsockname())
            with patch('plc_simulator.time.monotonic', return_value=12):
                self.sim.receive_once()
        self.assertEqual(sum('RESTORED' in line for line in self.logs), 1)
        self.assertEqual(self.sim.last_valid_tx, 12)
        self.sim.check_watchdog(13.001)
        self.assertEqual(sum('LOST' in line for line in self.logs), 2)


if __name__ == '__main__':
    unittest.main()
