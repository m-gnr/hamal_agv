# HAMAL’S Localization

> Odometry → TF dönüşüm katmanı
> 

> Robotun konum bilgisini TF ağacında entegre eder
> 

## Paket Amacı

hamals_localization, robotun /odom topic’ini dinleyerek

```
odom → base_footprint
```

TF dönüşümünü üretir.

Bu paket:

- Odometry hesaplamaz
- Sensör verisi işlemez
- Filtreleme yapmaz
- SLAM içermez

Sadece:

> Odometry mesajını TF ağına taşır
> 

## Mimari

```
        hamals_serial_bridge
                │
              /odom
                │
                ▼
        hamals_localization
        (TF broadcaster)
                │
        odom → base_footprint
                │
                ▼
        hamals_robot_description
```

## Bağımlılıklar

Bu paket aşağıdaki pakete bağımlıdır

- [hamals_robot_description](https://github.com/m-gnr/hamals_robot_description)

- robot_state_publisher
- joint_state_publisher
- tf2_ros

Robot modelinin doğru çalışması için URDF paketi gereklidir

## Girdi / Çıktı

Subscribe

```
/odom   (nav_msgs/Odometry)
```

Publish

```
/tf     (odom → base_footprint)
```

## Parametreler

```yaml
odom_topic: /odom
parent_frame: odom
child_frame: base_footprint
```

## Çalıştırma

```yaml
ros2 launch hamals_localization odom_tf.launch.py
```

## Frame Zinciri

```yaml
/odom
   ↓
odom_tf_node
   ↓
odom → base_footprint
   ↓
robot_state_publisher
   ↓
base_link → wheels → lidar
```
