#!/usr/bin/env bash
set -e

PACKAGE_NAME="hamals_robot_description"

PACKAGE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
WS_DIR="$(cd "$PACKAGE_DIR/.." && pwd)"
PKG_SHARE="$WS_DIR/install/$PACKAGE_NAME/share/$PACKAGE_NAME"

usage() {
  echo ""
  echo "HAMALS Gazebo workflow"
  echo ""
  echo "Usage:"
  echo "  ./scripts/hamals_gazebo.sh update   # YAML -> model.sdf üret + build"
  echo "  ./scripts/hamals_gazebo.sh server   # update + build + Gazebo server başlat"
  echo "  ./scripts/hamals_gazebo.sh gui      # Gazebo GUI aç"
  echo "  ./scripts/hamals_gazebo.sh check    # Gazebo world içinde robot var mı kontrol et"
  echo "  ./scripts/hamals_gazebo.sh clean    # gz sim süreçlerini kapat"
  echo ""
}

clean_gazebo() {
  echo "[clean] Stopping Gazebo processes..."
  pkill -f "gz sim" || true
}

update_model_and_build() {
  echo "[1/3] Generating Gazebo model.sdf from config/robot_dimensions.yaml..."
  cd "$PACKAGE_DIR"
  python3 scripts/generate_gazebo_model.py

  echo "[2/3] Rebuilding workspace..."
  cd "$WS_DIR"
  rm -rf build install log
  colcon build --packages-select "$PACKAGE_NAME"

  echo "[3/3] Done."
}

run_server() {
  update_model_and_build

  echo ""
  echo "[server] Starting Gazebo server..."
  cd "$WS_DIR"
  source install/setup.zsh

  clean_gazebo

  ros2 launch "$PACKAGE_NAME" gazebo.launch.py
}

run_gui() {
  echo "[gui] Starting Gazebo GUI..."

  if [ ! -d "$PKG_SHARE" ]; then
    echo "Package install folder not found:"
    echo "$PKG_SHARE"
    echo ""
    echo "Run first:"
    echo "  ./scripts/hamals_gazebo.sh update"
    exit 1
  fi

  export GZ_SIM_RESOURCE_PATH="$PKG_SHARE/models"

  gz sim -g "$PKG_SHARE/worlds/hamals_empty.world.sdf"
}

check_model() {
  echo "[check] Checking hamals_robot in /world/hamals_empty/pose/info..."
  gz topic -e -t /world/hamals_empty/pose/info | grep -A 5 -B 5 hamals_robot
}

case "$1" in
  update)
    update_model_and_build
    ;;
  server)
    run_server
    ;;
  gui)
    run_gui
    ;;
  check)
    check_model
    ;;
  clean)
    clean_gazebo
    ;;
  *)
    usage
    exit 1
    ;;
esac