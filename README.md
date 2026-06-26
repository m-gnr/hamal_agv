# Hamal AGV

Otonom forklift robotu projesi. ROS2 Humble tabanlı, Raspberry Pi 5 üzerinde çalışır.

## Paketler

| Paket | Açıklama |
|---|---|
| hamals_bringup | Robot başlatma ve orkestrasyon |
| hamals_interfaces | Custom ROS2 mesaj tanımları |
| hamals_lidar_toolbox | RPLIDAR S2 sürücü ve araçları |
| hamals_localization | Robot lokalizasyonu |
| hamals_manual_teleop | Manuel kontrol |
| hamals_navigation | Nav2 navigasyon |
| hamals_robot_description | URDF/xacro tanımları |
| hamals_serial_bridge | Arduino serial haberleşme |
| hamals_slam | SLAM Toolbox entegrasyonu |

## Kurulum

### Linux
```bash
git clone https://github.com/...
cd hamal_agv
bash scripts/setup_ros2.sh
bash scripts/aliases.sh
```
Kurulum sonrası terminali yeniden başlat.

### macOS (Conda)
```bash
conda env create -f environment.yml
conda activate ros2
bash scripts/aliases.sh
```
Kurulum sonrası terminali yeniden başlat.

## Kullanım

| Komut | Açıklama |
|---|---|
| `cbuild` | Workspace'i derler ve source eder |
| `cclean` | Build, install ve log klasörlerini temizler |
| `cdev` | Geliştirme container'ını başlatır (Linux) |
| `crobot` | Robot container'ını başlatır (sadece Pi'de) |

> **macOS:** `cdev` yerine doğrudan Conda ortamında çalışın.

## Donanım

- Raspberry Pi 5
- RPLIDAR S2
- Arduino (motor sürücü, serial haberleşme)

## Dokümantasyon

`docs/` klasörüne bakınız.