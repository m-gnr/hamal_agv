#!/bin/bash
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if [ -f ~/.zshrc ]; then
    RC_FILE=~/.zshrc
    SETUP_FILE="install/setup.zsh"
else
    RC_FILE=~/.bashrc
    SETUP_FILE="install/setup.bash"
fi

echo "alias cbuild='cd $REPO_DIR/ros2_ws && colcon build --cmake-args -DPython_EXECUTABLE=\$(which python) && source $SETUP_FILE && echo \"+++ Build başarılı\" || echo \"!!! Build başarısız !!!\"'" >> $RC_FILE
echo "alias cclean='rm -rf $REPO_DIR/ros2_ws/build $REPO_DIR/ros2_ws/install $REPO_DIR/ros2_ws/log && echo \"+++ Temizlendi\"'" >> $RC_FILE
echo "alias cdev='docker compose -f $REPO_DIR/docker/compose.yml up'" >> $RC_FILE
echo "alias crobot='docker compose -f $REPO_DIR/docker/compose.pi.yml up'" >> $RC_FILE

source $RC_FILE
echo "+++ Alias'lar eklendi: cbuild, cclean, cdev, crobot"
echo "Tekrar execute etmeden önce .zshrc veya .bashrc dosyasından sildiğinize emin olun."