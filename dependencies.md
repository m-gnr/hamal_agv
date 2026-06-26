# Dependencies

## ROS2
- ROS2 Humble Hawksbill (Ubuntu 22.04)

Kurulum: https://docs.ros.org/en/humble/Installation.html

```bash
sudo rosdep init
rosdep update
rosdep install --from-paths ros2_ws/src --ignore-src -r -y
```

## Python
```bash
pip install -r requirements.txt
```

## Docker
- Docker Engine
- Docker Compose v2

Kurulum: https://docs.docker.com/engine/install/ubuntu/

## Donanım Sürücüleri
- Lidar: - Sonra doldurulacaktır ()
- Arduino IDE: https://www.arduino.cc/en/software

## İşletim Sistemi
- Ubuntu 22.04 (geliştirme)
- Raspberry Pi OS (Pi için)