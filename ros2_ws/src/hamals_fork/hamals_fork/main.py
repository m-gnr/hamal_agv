#!/usr/bin/env python3

# hamals_fork/main.py

import rclpy
from rclpy.node import Node

from std_msgs.msg import String
from hamals_interfaces.msg import ForkCommand, ForkState

from .fork_controller import ForkController
from .fork_commands import command_to_text
from .fork_states import state_to_text

from .helpers.config_loader import (
    declare_fork_parameters,
    load_fork_config,
    validate_fork_config,
)
from .helpers.log_helpers import log_startup_config


class ForkNode(Node):
    """
    HAMALS Fork ROS2 node.

    Görevleri:
    - /fork/cmd üzerinden ForkCommand alır.
    - ForkController ile timer tabanlı açık çevrim kontrol yapar.
    - /mcu/fork_cmd üzerinden serial_bridge'e UP / DOWN / STOP gönderir.
    - /fork/state üzerinden ForkState yayınlar.
    """

    def __init__(self):
        super().__init__('hamals_fork_node')

        # ------------------------------------------------------------
        # CONFIG
        # ------------------------------------------------------------
        declare_fork_parameters(self)
        self.config = load_fork_config(self)
        validate_fork_config(self.config)

        # ------------------------------------------------------------
        # CONTROLLER
        # ------------------------------------------------------------
        self.controller = ForkController(
            up_duration_ms=self.config.up_duration_ms,
            down_duration_ms=self.config.down_duration_ms,
        )

        # ------------------------------------------------------------
        # ROS INTERFACES
        # ------------------------------------------------------------
        self.cmd_sub = self.create_subscription(
            ForkCommand,
            self.config.fork_cmd_topic,
            self.cmd_callback,
            10,
        )

        self.state_pub = self.create_publisher(
            ForkState,
            self.config.fork_state_topic,
            10,
        )

        self.mcu_cmd_pub = self.create_publisher(
            String,
            self.config.mcu_fork_cmd_topic,
            10,
        )

        timer_period_s = 1.0 / self.config.state_publish_hz
        self.timer = self.create_timer(timer_period_s, self.timer_callback)

        log_startup_config(self, self.config)
        self.get_logger().info("hamals_fork_node started")

    # ------------------------------------------------------------
    # CALLBACKS
    # ------------------------------------------------------------

    def cmd_callback(self, msg: ForkCommand) -> None:
        """
        /fork/cmd callback.

        Gelen yüksek seviye fork komutunu controller'a verir.
        Controller gerekirse MCU'ya gönderilecek string komutu döndürür.
        """

        command = int(msg.command)

        if self.config.debug:
            self.get_logger().info(
                f"Fork command received: {command_to_text(command)} ({command})"
            )

        mcu_cmd = self.controller.handle_command(command)

        if mcu_cmd is not None:
            self.publish_mcu_cmd(mcu_cmd)

        self.publish_state()

    def timer_callback(self) -> None:
        """
        Periyodik update callback.

        Bu callback iki iş yapar:
        1. Controller timer süresi doldu mu diye kontrol eder.
        2. ForkState mesajını düzenli yayınlar.
        """

        mcu_cmd = self.controller.update()

        if mcu_cmd is not None:
            self.publish_mcu_cmd(mcu_cmd)

            if self.config.debug:
                self.get_logger().info(
                    f"Fork motion finished. State={state_to_text(self.controller.state)}"
                )

        self.publish_state()

    # ------------------------------------------------------------
    # PUBLISH HELPERS
    # ------------------------------------------------------------

    def publish_mcu_cmd(self, cmd: str) -> None:
        """
        Serial bridge'e gönderilecek düşük seviye fork komutunu yayınlar.

        Topic:
          /mcu/fork_cmd

        Mesaj:
          std_msgs/String

        Örnek:
          UP
          DOWN
          STOP
        """

        msg = String()
        msg.data = cmd
        self.mcu_cmd_pub.publish(msg)

        if self.config.debug:
            self.get_logger().info(f"MCU fork cmd published: {cmd}")

    def publish_state(self) -> None:
        """
        Güncel ForkState mesajını yayınlar.
        """

        stamp = self.get_clock().now().to_msg()
        msg = self.controller.make_state_msg(stamp)
        self.state_pub.publish(msg)

    # ------------------------------------------------------------
    # SHUTDOWN
    # ------------------------------------------------------------

    def destroy_node(self) -> None:
        """
        Node kapanırken istenirse MCU'ya STOP gönderir.

        Bu sayede node Ctrl+C ile kapatılsa bile fork motoruna dur komutu gider.
        """

        if self.config.stop_on_shutdown:
            self.publish_mcu_cmd('STOP')

        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ForkNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()