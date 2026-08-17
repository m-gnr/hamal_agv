# HAMAL ROS 2 Architecture

The production system is launched only through `hamals_bringup`. Packages own one
kind of decision:

- `hamals_world_model`: immutable field geometry, station/QR bindings and routes.
- `hamals_mission`: active task context and hierarchical mission sequencing.
- `hamals_navigation`: Nav2 configuration; it never launches mission code.
- `hamals_docking`: bounded QR/line precision motion.
- `hamals_plc_bridge`: external factory protocol adapter (mock until the official protocol).
- `hamals_safety`: E-stop, mode and obstacle aggregation into a fail-safe motion lock.
- `twist_mux`: the only path from navigation, docking and manual sources to `/cmd_vel`.

## Profiles

```bash
ros2 launch hamals_bringup mapping.launch.py
ros2 launch hamals_bringup competition.launch.py
ros2 launch hamals_bringup simulation.launch.py
```

Competition currently defaults to the mock PLC adapter. Submit a mock task with:

```bash
ros2 service call /plc/mock/submit_task std_srvs/srv/Trigger '{}'
```

Select a different mock pickup/dropoff through ROS parameters, or pass a future
official adapter config with `plc_config:=...`.

## Configuration ownership

Metric station polygons, target/approach/exit poses, QR bindings, doors and route
edges live under `hamals_world_model/config`. Mission timeouts and recovery policy
live under `hamals_mission/config`. Detection, safety and PLC parameters remain in
their owning packages. Pixel coordinates in `hamals_ui/config/topology.yaml` are
display-only and must never be used for control.

All control coordinates use meters in the `map` frame. The checked-in field values
are an initial coherent model and must be replaced by the surveyed official field
coordinates before physical competition testing.

The serial bridge accepts the physical safety frame
`$SAFETY,t_us,estop,manual*CS` and publishes `/estop` plus `/switch/mode`.
Firmware pin assignments are hardware-specific; the MCU must emit this frame from
the wired E-stop and auto/manual switch before field operation.
