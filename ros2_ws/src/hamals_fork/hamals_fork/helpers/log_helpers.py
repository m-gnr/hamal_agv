def log_fork_config(logger, config) -> None:
    logger.info(
        "\n".join(
            [
                "hamals_fork configuration:",
                f"  fork_cmd_topic: {config.fork_cmd_topic}",
                f"  fork_state_topic: {config.fork_state_topic}",
                f"  mcu_fork_cmd_topic: {config.mcu_fork_cmd_topic}",
                f"  mcu_fork_state_topic: {config.mcu_fork_state_topic}",
                f"  mcu_state_timeout_ms: {config.mcu_state_timeout_ms}",
                f"  state_publish_hz: {config.state_publish_hz}",
                f"  stop_on_shutdown: {config.stop_on_shutdown}",
                f"  debug: {config.debug}",
            ]
        )
    )
