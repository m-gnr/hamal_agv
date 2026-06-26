#!/bin/bash
cd "$(dirname "$0")/../ros2_ws"
colcon build --symlink-install
source install/setup.bash
echo "** Build tamamlandı **"