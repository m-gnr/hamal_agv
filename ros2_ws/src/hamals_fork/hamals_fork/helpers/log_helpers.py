# hamals_fork/helpers/log_helpers.py

from .config_loader import ForkConfig


def log_startup_config(node, config: ForkConfig) -> None:
    """
    Node başlangıcında temel config bilgisini sade şekilde loglar.
    """

    node.get_logger().info("HAMALS Fork node config:")
    node.get_logger().info(f"  fork_cmd_topic       : {config.fork_cmd_topic}")
    node.get_logger().info(f"  fork_state_topic     : {config.fork_state_topic}")
    node.get_logger().info(f"  mcu_fork_cmd_topic   : {config.mcu_fork_cmd_topic}")
    node.get_logger().info(f"  mcu_fork_state_topic : {config.mcu_fork_state_topic}")
    node.get_logger().info(f"  up_duration_ms       : {config.up_duration_ms}")
    node.get_logger().info(f"  down_duration_ms     : {config.down_duration_ms}")
    node.get_logger().info(f"  state_publish_hz     : {config.state_publish_hz}")
    node.get_logger().info(f"  stop_on_shutdown     : {config.stop_on_shutdown}")
    node.get_logger().info(
        f"  retrigger_same_cmd   : {config.allow_retrigger_same_command}"
    )
    node.get_logger().info(f"  debug                : {config.debug}")