import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from hamals_interfaces.msg import ForkCommand, ForkState
from hamals_fork.fork_controller import ForkController
from hamals_fork.fork_keepalive import ForkKeepalive
from hamals_fork.fork_states import error_name, state_name
from hamals_fork.helpers.config_loader import declare_fork_parameters, load_fork_config
from hamals_fork.helpers.log_helpers import log_fork_config


class ForkNode(Node):
    def __init__(self):
        super().__init__("fork_node")

        declare_fork_parameters(self)
        self.config = load_fork_config(self)
        self.controller = ForkController(self.config.mcu_state_timeout_ms)
        self.keepalive = ForkKeepalive()

        self.fork_state_pub = self.create_publisher(
            ForkState,
            self.config.fork_state_topic,
            10,
        )
        self.mcu_fork_cmd_pub = self.create_publisher(
            String,
            self.config.mcu_fork_cmd_topic,
            10,
        )

        self.fork_cmd_sub = self.create_subscription(
            ForkCommand,
            self.config.fork_cmd_topic,
            self.cmd_callback,
            10,
        )
        self.mcu_fork_state_sub = self.create_subscription(
            ForkState,
            self.config.mcu_fork_state_topic,
            self.mcu_state_callback,
            10,
        )

        timer_period_s = 1.0 / self.config.state_publish_hz
        self.timer = self.create_timer(timer_period_s, self.timer_callback)
        keepalive_period_s = self.config.keepalive_period_ms / 1000.0
        self.keepalive_timer = self.create_timer(
            keepalive_period_s,
            self.keepalive_timer_callback,
        )

        if self.config.debug:
            log_fork_config(self.get_logger(), self.config)

    def cmd_callback(self, msg: ForkCommand) -> None:
        was_error = self.controller.state == ForkState.ERROR
        mcu_cmd = self.controller.handle_command(msg.command)

        if mcu_cmd is None:
            if was_error and msg.command in (ForkCommand.UP, ForkCommand.DOWN):
                self.get_logger().warning(
                    "Fork is in ERROR; rejecting UP/DOWN command until STOP is received"
                )
            elif self.controller.error_code == ForkState.ERROR_INVALID_COMMAND:
                self.get_logger().warning(f"Invalid fork command: {msg.command}")
        else:
            self.publish_mcu_command(mcu_cmd)
            self.keepalive.record_published_command(mcu_cmd)

        self.publish_state()

    def mcu_state_callback(self, msg: ForkState) -> None:
        self.controller.update_from_mcu_state(msg)
        self.keepalive.update_from_mcu_state(self.controller.state)
        if self.config.debug:
            self.get_logger().debug(
                "MCU fork state: "
                f"state={state_name(self.controller.state)}, "
                f"error={error_name(self.controller.error_code)}, "
                f"moving={self.controller.is_moving}, "
                f"upper_limit={self.controller.upper_limit}, "
                f"lower_limit={self.controller.lower_limit}"
            )
        self.publish_state()

    def timer_callback(self) -> None:
        self.controller.update()
        if self.controller.state == ForkState.ERROR:
            self.keepalive.stop()
        self.publish_state()

    def keepalive_timer_callback(self) -> None:
        command = self.keepalive.command_to_publish()
        if command is not None:
            self.publish_mcu_command(command)

    def publish_mcu_command(self, command: str) -> None:
        msg = String()
        msg.data = command
        self.mcu_fork_cmd_pub.publish(msg)

    def publish_state(self) -> None:
        stamp = self.get_clock().now().to_msg()
        self.fork_state_pub.publish(self.controller.make_state_msg(stamp))

    def destroy_node(self) -> bool:
        if getattr(self, "config", None) and self.config.stop_on_shutdown:
            self.publish_mcu_command("STOP")
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ForkNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
