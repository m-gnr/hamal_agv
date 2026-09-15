# Velocity routing

Mode source: existing `std_msgs/msg/String` topic `/switch/mode`. The bridge
already publishes MCU SAFETY frames here; its new subscriber uses only the
received exact `manual` / `auto` strings. Startup and other strings deny both
velocity inputs. Valid mode -> invalid mode also forces a stop.

- `manual_teleop` -> `/cmd_vel/manual_teleop` -> bridge MANUAL input.
- Nav2 / autonomous scripts -> `/cmd_vel` -> twist_mux.
- Docking / mission -> `/cmd_vel/docking` -> twist_mux.
- twist_mux -> `/cmd_vel/selected` -> bridge AUTO input (`cmd_vel_topic`).
- UI's `/cmd_vel/manual` is no longer connected to either bridge input or mux.

Only the selected input reaches `_maybe_send_cmd()`. Rejected messages do not
refresh the deadman. Each actual valid-mode change sends a forced zero command;
repeated mode messages do not. Previous commands are not buffered or replayed.
Existing autonomous mux priorities and safety lock remain in place.
The manual input goes directly to the bridge: the existing mux safety lock also
locks on MANUAL mode, so it cannot be used for manual routing.

This is topic-based routing, not publisher authentication. Keep
`/cmd_vel/manual_teleop` exclusive to the teleop node in deployment. Arbitrary ROS
publishers/remaps onto that topic require separate access control if untrusted
nodes must be supported. The bridge refuses startup if its two resolved input
topic names are identical.

## Build and inspect

From the workspace, rebuild all changed packages and restart the running nodes
(including twist_mux); an old running mux still has the old source list:

```bash
cd ~/develop/hamal_agv/ros2_ws
colcon build --packages-select hamals_serial_bridge hamals_manual_teleop hamals_bringup
source install/setup.bash
ros2 topic echo /switch/mode
ros2 node info /hamals_serial_bridge
ros2 topic info /cmd_vel/manual_teleop --verbose
ros2 topic info /cmd_vel/selected --verbose
```

The manual publisher should be only the teleop node; the auto publisher should
be twist_mux. The bridge must subscribe to both inputs and `/switch/mode`.

## Physical-switch test

Test with the wheels raised / robot restrained. Keep the real switch publisher
as the only mode authority; do not publish a competing mode on the hardware.
Run the normal bringup and Nav2, and in a separate terminal:

```bash
ros2 run hamals_manual_teleop teleop_node
```

Use the teleop's displayed keys. With the switch MANUAL, teleop should control
the robot even while Nav2 publishes. Switch AUTO: there must be an immediate
zero command, then only autonomous commands can move the robot. Switch back:
there must again be a zero before subsequent manual motion. Repeated messages
of the same mode must not repeatedly stop the robot.

For a deterministic substitute for Nav2, stop Nav2 and publish:

```bash
ros2 topic pub --rate 10 /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.05}, angular: {z: 0.0}}'
```

AUTO still requires the existing mux safety lock to be clear. In MANUAL this
stream must never drive the robot. To test the bridge independently of mux
locking, stop twist_mux and publish to `/cmd_vel/selected` instead. This must
also be rejected in MANUAL. Stop the accepted command publisher: after 500 ms
(default), deadman must send zero even if the rejected source keeps publishing.

## Isolated mode injection (no hardware mode publisher)

Use a mock serial port that emits no SAFETY frames, not a live MCU publishing
mode. On this isolated bridge instance, send test velocities on both inputs:

```bash
ros2 topic pub --rate 10 /cmd_vel/manual_teleop geometry_msgs/msg/Twist '{linear: {x: 0.05}}'
ros2 topic pub --rate 10 /cmd_vel/selected geometry_msgs/msg/Twist '{linear: {x: 0.10}}'
```

Run the two publishers in separate terminals. Before any mode arrives neither
velocity may appear in captured serial output. Then, one at a time:

```bash
ros2 topic pub --once /switch/mode std_msgs/msg/String '{data: manual}'
ros2 topic pub --once /switch/mode std_msgs/msg/String '{data: auto}'
ros2 topic pub --once /switch/mode std_msgs/msg/String '{data: invalid}'
```

Expected serial CMD linear speeds: manual only 0.05, auto only 0.10, invalid
neither. Transitions from a valid mode include `CMD,0.000,0.000` in the existing
checksummed protocol. Topic echo alone cannot prove what was written to serial;
inspect the mock serial capture or hardware response.

## Local regression tests (no ROS installation required)

```bash
PYTHONPATH=ros2_ws/src/hamals_serial_bridge python3 -m pytest -q \
  ros2_ws/src/hamals_serial_bridge/test/test_velocity_routing.py \
  ros2_ws/src/hamals_serial_bridge/test/test_parser.py
```
