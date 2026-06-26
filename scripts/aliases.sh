#!/bin/bash
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f ~/.zshrc ]; then
    RC_FILE=~/.zshrc
else
    RC_FILE=~/.bashrc
fi

echo "alias cbuild='cd $REPO_DIR/ros2_ws && colcon build --symlink-install && source install/setup.bash'" >> $RC_FILE
echo "alias cdev='docker compose -f $REPO_DIR/docker/compose.yml up'" >> $RC_FILE
echo "alias crobot='docker compose -f $REPO_DIR/docker/compose.pi.yml up'" >> $RC_FILE

source $RC_FILE
echo "++ Alias'lar eklendi: cbuild, cdev, crobot"