# hamals_fork/helpers/config_loader.py

from dataclasses import dataclass
from rclpy.node import Node


@dataclass
class ForkConfig:
    """
    Fork node runtime configuration.

    Bu sınıf ROS parametrelerinden okunan değerleri tek yerde tutar.
    Böylece main.py içinde sürekli get_parameter kullanmamıza gerek kalmaz.
    """

    fork_cmd_topic: str
    fork_state_topic: str

    mcu_fork_cmd_topic: str
    mcu_fork_state_topic: str

    up_duration_ms: int
    down_duration_ms: int

    state_publish_hz: float

    stop_on_shutdown: bool
    allow_retrigger_same_command: bool

    debug: bool


def declare_fork_parameters(node: Node) -> None:
    """
    Fork node için gerekli ROS parametrelerini declare eder.

    Bu değerler config/fork.yaml içinden override edilebilir.
    """

    node.declare_parameter('fork_cmd_topic', '/fork/cmd')
    node.declare_parameter('fork_state_topic', '/fork/state')

    node.declare_parameter('mcu_fork_cmd_topic', '/mcu/fork_cmd')
    node.declare_parameter('mcu_fork_state_topic', '/mcu/fork_state')

    node.declare_parameter('up_duration_ms', 7000)
    node.declare_parameter('down_duration_ms', 7000)

    node.declare_parameter('state_publish_hz', 10.0)

    node.declare_parameter('stop_on_shutdown', True)
    node.declare_parameter('allow_retrigger_same_command', True)

    node.declare_parameter('debug', True)


def load_fork_config(node: Node) -> ForkConfig:
    """
    Declare edilmiş ROS parametrelerini okuyup ForkConfig objesine çevirir.
    """

    return ForkConfig(
        fork_cmd_topic=str(node.get_parameter('fork_cmd_topic').value),
        fork_state_topic=str(node.get_parameter('fork_state_topic').value),

        mcu_fork_cmd_topic=str(node.get_parameter('mcu_fork_cmd_topic').value),
        mcu_fork_state_topic=str(node.get_parameter('mcu_fork_state_topic').value),

        up_duration_ms=int(node.get_parameter('up_duration_ms').value),
        down_duration_ms=int(node.get_parameter('down_duration_ms').value),

        state_publish_hz=float(node.get_parameter('state_publish_hz').value),

        stop_on_shutdown=bool(node.get_parameter('stop_on_shutdown').value),
        allow_retrigger_same_command=bool(
            node.get_parameter('allow_retrigger_same_command').value
        ),

        debug=bool(node.get_parameter('debug').value),
    )


def validate_fork_config(config: ForkConfig) -> None:
    """
    Config değerlerini basit güvenlik kontrollerinden geçirir.

    Hatalı parametre varsa node başlarken exception fırlatır.
    """

    if config.up_duration_ms <= 0:
        raise ValueError("up_duration_ms must be greater than 0")

    if config.down_duration_ms <= 0:
        raise ValueError("down_duration_ms must be greater than 0")

    if config.state_publish_hz <= 0.0:
        raise ValueError("state_publish_hz must be greater than 0")