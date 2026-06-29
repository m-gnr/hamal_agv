"""
hamals_ui — ui.launch.py
Launches:
  1. rosbridge_server   (WebSocket ROS ↔ Web bridge)
  2. web_video_server   (MJPEG camera streams)
  3. ui_bridge_node     (topic aggregator / mock player)
  4. static web server  (serves web/dist/ built SPA on port 8080)

Usage:
  ros2 launch hamals_ui ui.launch.py
  ros2 launch hamals_ui ui.launch.py mode:=live
  ros2 launch hamals_ui ui.launch.py mode:=mock rosbridge_port:=9090
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    LogInfo,
)
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory("hamals_ui")
    web_dist = os.path.join(pkg_share, "web/dist")

    # web_video_server is optional (not available on macOS/robostack).
    # Detect at launch time; skip gracefully with a warning if missing.
    try:
        get_package_share_directory("web_video_server")
        vvs_available = True
    except Exception:
        vvs_available = False

    # ── Launch arguments ─────────────────────────────────────
    mode_arg = DeclareLaunchArgument(
        "mode",
        default_value="mock",
        description="Bridge mode: live | mock"
    )
    rosbridge_port_arg = DeclareLaunchArgument(
        "rosbridge_port",
        default_value="9090",
        description="rosbridge WebSocket port"
    )
    web_port_arg = DeclareLaunchArgument(
        "web_port",
        default_value="8080",
        description="Static web server port"
    )
    vvs_port_arg = DeclareLaunchArgument(
        "vvs_port",
        default_value="8081",
        description="web_video_server port"
    )
    serve_web_arg = DeclareLaunchArgument(
        "serve_web",
        default_value="true",
        description="Serve built web/dist/ with Python HTTP server"
    )

    mode = LaunchConfiguration("mode")
    rosbridge_port = LaunchConfiguration("rosbridge_port")
    web_port = LaunchConfiguration("web_port")
    vvs_port = LaunchConfiguration("vvs_port")
    serve_web = LaunchConfiguration("serve_web")

    # ── 1. rosbridge_server ──────────────────────────────────
    rosbridge_node = Node(
        package="rosbridge_server",
        executable="rosbridge_websocket",
        name="rosbridge_websocket",
        output="screen",
        parameters=[{
            "port": rosbridge_port,
            "address": "0.0.0.0",
            "retry_startup_delay": 5.0,
            "fragment_timeout": 600,
            "delay_between_messages": 0,
            "max_message_size": 10000000,
            "unregister_timeout": 10.0,
        }]
    )

    # ── 2. web_video_server ──────────────────────────────────
    vvs_node = Node(
        package="web_video_server",
        executable="web_video_server",
        name="web_video_server",
        output="screen",
        parameters=[{
            "port": vvs_port,
            "address": "0.0.0.0",
            "default_stream_type": "mjpeg",
            "ros_threads": 2,
        }]
    )

    # ── 3. ui_bridge_node ────────────────────────────────────
    bridge_node = Node(
        package="hamals_ui",
        executable="ui_bridge_node",
        name="ui_bridge_node",
        output="screen",
        parameters=[
            {"mode": mode}
        ]
    )

    # ── 4. Static web server (Python) ────────────────────────
    # Serves web/dist/ on web_port. Skipped if web/dist doesn't exist.
    static_server = ExecuteProcess(
        cmd=[
            "python3", "-m", "http.server", web_port,
            "--directory", web_dist,
            "--bind", "0.0.0.0"
        ],
        name="hamals_ui_web_server",
        output="screen",
        condition=IfCondition(serve_web)
    )

    log_start = LogInfo(
        msg=[
            "hamals_ui launching — mode=", mode,
            "  rosbridge=ws://0.0.0.0:", rosbridge_port,
            "  web=http://0.0.0.0:", web_port,
        ]
    )

    actions = [
        mode_arg,
        rosbridge_port_arg,
        web_port_arg,
        vvs_port_arg,
        serve_web_arg,
        log_start,
        rosbridge_node,
        bridge_node,
        static_server,
    ]

    # Add camera streaming only if web_video_server is installed.
    if vvs_available:
        actions.append(vvs_node)
    else:
        actions.append(LogInfo(
            msg="[hamals_ui] web_video_server not found — camera streams disabled "
                "(install ros-<distro>-web-video-server to enable)."
        ))

    return LaunchDescription(actions)
