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
bash scripts/aliases.sh # Yalnızca bir kez çalıştırın
# Terminali yeniden başlat
cdev        # container'a gir
cbuild      # workspace'i derle
```

### macOS (Conda)
```bash
git clone https://github.com/...
cd hamal_agv
conda env create -f environment.yml
conda activate ros2
bash scripts/aliases.sh # Yalnızca bir kez çalıştırın
# Terminali yeniden başlat
cbuild      # workspace'i derle
```

## Docker

Proje, geliştirme ve robot ortamı için Docker kullanır.

- **`cdev`** — Linux'ta geliştirme container'ını başlatır. ROS2 ve tüm bağımlılıklar container içinde gelir, host makineye kurulum gerekmez.
- **`crobot`** — Pi'de robot container'ını başlatır. Serial portlara (`/dev`) erişimi vardır, robot yeniden başlasa bile container otomatik ayağa kalkar (`restart: unless-stopped`).

> **macOS:** Docker yerine Conda ortamı kullanılır.

## Kullanım

| Komut | Açıklama |
|---|---|
| `cbuild` | Workspace'i derler ve source eder |
| `cclean` | Build, install ve log klasörlerini temizler |
| `cdev` | Geliştirme container'ını başlatır (Linux) |
| `crobot` | Robot container'ını başlatır (sadece Pi'de) |

### Örnekler

```bash
# Temiz build
cclean && cbuild

# Pi'de robotu başlat
crobot
```

## Donanım

- Raspberry Pi 5
- RPLIDAR S2
- Arduino (motor sürücü, serial haberleşme)

## Dokümantasyon

`docs/` klasörüne bakınız.