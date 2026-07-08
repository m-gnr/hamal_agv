from dataclasses import dataclass


@dataclass(frozen=True)
class ForkConfig:
    fork_cmd_topic: str
    fork_state_topic: str
    mcu_fork_cmd_topic: str
    mcu_fork_state_topic: str
    mcu_state_timeout_ms: int
    state_publish_hz: float
    stop_on_shutdown: bool
    debug: bool


def declare_fork_parameters(node) -> None:
    node.declare_parameter("fork_cmd_topic", "/fork/cmd")
    node.declare_parameter("fork_state_topic", "/fork/state")
    node.declare_parameter("mcu_fork_cmd_topic", "/mcu/fork_cmd")
    node.declare_parameter("mcu_fork_state_topic", "/mcu/fork_state")
    node.declare_parameter("mcu_state_timeout_ms", 1000)
    node.declare_parameter("state_publish_hz", 10.0)
    node.declare_parameter("stop_on_shutdown", True)
    node.declare_parameter("debug", True)


def load_fork_config(node) -> ForkConfig:
    config = ForkConfig(
        fork_cmd_topic=node.get_parameter("fork_cmd_topic").value,
        fork_state_topic=node.get_parameter("fork_state_topic").value,
        mcu_fork_cmd_topic=node.get_parameter("mcu_fork_cmd_topic").value,
        mcu_fork_state_topic=node.get_parameter("mcu_fork_state_topic").value,
        mcu_state_timeout_ms=node.get_parameter("mcu_state_timeout_ms").value,
        state_publish_hz=node.get_parameter("state_publish_hz").value,
        stop_on_shutdown=node.get_parameter("stop_on_shutdown").value,
        debug=node.get_parameter("debug").value,
    )
    validate_fork_config(config)
    return config


def validate_fork_config(config: ForkConfig) -> None:
    if config.mcu_state_timeout_ms <= 0:
        raise ValueError("mcu_state_timeout_ms must be greater than 0")
    if config.state_publish_hz <= 0:
        raise ValueError("state_publish_hz must be greater than 0")
