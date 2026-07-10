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
git clone https://github.com/m-gnr/hamal_agv.git
cd hamal_agv
bash scripts/aliases.sh
source ~/.bashrc
h cdev      # development container'ına gir
h cbuild    # workspace'i derle ve source et
```

### macOS (Conda)

```bash
git clone https://github.com/m-gnr/hamal_agv.git
cd hamal_agv
conda env create -f environment.yml
conda activate ros2
bash scripts/aliases.sh
source ~/.zshrc
h cbuild    # workspace'i derle ve source et
```

Kurulum scripti Bash veya Zsh yapılandırmasına tek bir `source` satırı
ekler. Tekrar çalıştırılabilir; eski, repo tarafından oluşturulmuş alias
satırlarını yeni CLI kaydına dönüştürür.

## Docker

Proje, geliştirme ve robot ortamı için Docker kullanır.

- **`h cdev`** — Linux'ta geliştirme container'ını başlatır ve shell'e bağlanır. ROS 2 ve tüm bağımlılıklar container içinde gelir.
- **`h crobot`** — Pi'de robot container'ını başlatır. Serial portlara (`/dev`) erişimi vardır, robot yeniden başlasa bile container otomatik ayağa kalkar (`restart: unless-stopped`).

> **macOS:** Docker yerine Conda ortamı kullanılır.

## HAMALS CLI

Bütün geliştirme komutları tek bir `h` shell function'ı altındadır. Kategorili
komut listesini `h`, bir komutun ayrıntılarını `h help <komut>` ile görün.

### Örnekler

```bash
h
h cbuild
h cbuild hamals_odometry
h crun
h crun --debug
h claunch hamals_bringup
h claunch --debug
h ctopic
h cstatus
h cdoctor
```

Paket seçimli build/test, ROS 2 run/launch, topic/node/TF araçları, sistem
tanılama ve Docker komutlarının tüm kullanım örnekleri CLI yardımında yer alır.

## Donanım

- Raspberry Pi 5
- RPLIDAR S2
- Arduino (motor sürücü, serial haberleşme)

## Dokümantasyon

`docs/` klasörüne bakınız.
