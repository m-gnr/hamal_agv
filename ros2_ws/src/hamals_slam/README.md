# HAMAL’S SLAM

ROS 2 Humble uyumlu SLAM ve Localization paketi.

Online SLAM ve localization sağlar

## Paket Yapısı

```
hamals_slam/
├── config/
│   ├── slam.yaml
│   └── localization.yaml
│
├── launch/
│   ├── slam.launch.py
│   └── localization.launch.py
```

## Mimari

```
map
↓
odom
↓
base_footprint
↓
base_link
↓
sensörler
```

# Çalışma Modları

## 1) slam.launch

```
ros2 launch hamals_slam slam.launch.py
```

- async_slam_toolbox_node çalıştırır
- Online SLAM yapar
- Harita oluşturur
- Loop closure yapar
- map → odom TF yayınlar

**Kullanılan config:**

```
config/slam.yaml
```

Bu mod yalnızca harita çıkartılırken kullanılmaldırı

## 2) localization.launch

```
ros2 launch hamals_slam localization.launch.py
```

- localization_slam_toolbox_node çalıştırır
- Yeni harita üretmez
- Var olan haritayı kullanır
- map → odom TF yayınlar

**Kullanılan config:**

```
config/localization.yaml
```

Daha önce çıkarılmış bir harita ile çalışırken  veya Nav2 ile görev planlaması yapılırken kullanılmalıdır.

# Uyarı

- **SLAM** ve **Localization** aynı anda çalıştırılamaz
- Localization modu için **map_file_name paramteresi** zorunludur **(yaml/map_file_name:)**
- Odometry TF zinciri düzgün çalışmalıdır
