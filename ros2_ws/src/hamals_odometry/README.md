# HAMALS Odometry

> Ham encoder tick verisinden twist-only `/odom_raw` yayınlayan ROS 2 paketi.

`hamals_odometry`, `hamals_serial_bridge` tarafından yayınlanan `/wheel_ticks` topic'ini dinler ve diferansiyel sürüş kinematiği ile lineer/açısal hız hesaplar. Sonuç `nav_msgs/msg/Odometry` olarak `/odom_raw` topic'ine yayınlanır.

Bu paket pose dead-reckoning yapmaz. Odometry mesajındaki pose alanı her zaman identity kalır.

## Amaç

Bu paket aşağıdaki sorumluluklara sahiptir:

- `hamals_interfaces/msg/WheelTicks` mesajlarını dinlemek
- Ardışık iki `WheelTicks.t_us` değeri arasından dt hesaplamak
- Encoder delta tick değerlerinden teker açısal hızlarını hesaplamak
- Diferansiyel sürüş kinematiği ile `v` ve `w` üretmek
- `/odom_raw` topic'ine twist-only `nav_msgs/msg/Odometry` yayınlamak
- Debug modunda tick, dt ve odometri sayaçlarını raporlamak

Bu paket şu işleri yapmaz:

- x, y, yaw integration yapmaz
- TF yayınlamaz
- Seri portla konuşmaz
- MCU protokolünü parse etmez
- IMU verisi işlemez

## Mimari

```
/wheel_ticks
    |
hamals_odometry
    |
/odom_raw
```

Sistem içindeki yeri:

```
[ MCU Firmware ]
      |
      | $ENC,t_us,dl,dr*CS
      v
[ hamals_serial_bridge ]
      |
      | /wheel_ticks
      v
[ hamals_odometry ]
      |
      | /odom_raw
      v
[ robot_localization / EKF ]
```

## Topic'ler

### Subscribe

| Topic | Tip | Açıklama |
| --- | --- | --- |
| `/wheel_ticks` | `hamals_interfaces/msg/WheelTicks` | MCU'dan gelen ham encoder tick delta verisi |

### Publish

| Topic | Tip | Açıklama |
| --- | --- | --- |
| `/odom_raw` | `nav_msgs/msg/Odometry` | Twist-only ham odometri çıktısı |

## WheelTicks Mesajı

```text
std_msgs/Header header
uint32 t_us
int32 dl
int32 dr
```

Alanlar:

- `header.stamp`: Bridge'in publish anındaki ROS zamanı. Debug/latency gözlemi içindir.
- `t_us`: MCU `micros()` zaman damgası. dt hesabında kullanılan tek zaman kaynağıdır.
- `dl`: Sol encoder delta tick.
- `dr`: Sağ encoder delta tick.

## dt Hesabı

dt hesabı ROS receive-time veya DDS scheduling zamanından yapılmaz. Bunun yerine MCU firmware tarafından gönderilen `t_us` alanı kullanılır.

`t_us`, `uint32` mikrosaniye sayacıdır ve yaklaşık 71 dakikada bir taşabilir. Fark unsigned aritmetik ile alınır:

```python
dt_us = (t_us_new - t_us_prev) & 0xFFFFFFFF
dt = dt_us / 1e6
```

Bu yöntem wraparound durumunda ayrıca özel durum kodu gerektirmeden doğru farkı üretir.

İlk `WheelTicks` mesajında önceki `t_us` bulunmadığı için yalnızca referans kayıt edilir, odometri yayınlanmaz.

## dt Guard

Hesaplanan dt şu aralık dışında kalırsa odometri yayınlanmaz:

```python
if dt <= enc_dt_min_s or dt > enc_dt_max_s:
    return
```

Guard tetiklense bile son `t_us` kaydı güncellenir. Böylece bir sonraki mesaj eski, geçersiz timestamp'e göre hesaplanmaz.

Varsayılan değerler:

- `enc_dt_min_s`: `0.0`
- `enc_dt_max_s`: `0.5`

## Kinematik

Kullanılan formüller:

```text
dtheta_l = (2*pi*dl) / cpr_left
dtheta_r = (2*pi*dr) / cpr_right

omega_l = dtheta_l / dt
omega_r = dtheta_r / dt

v_l = omega_l * wheel_radius_m
v_r = omega_r * wheel_radius_m

v = 0.5 * (v_l + v_r)
w = (v_r - v_l) / track_width_m
```

`v`, `odom.twist.twist.linear.x` alanına; `w`, `odom.twist.twist.angular.z` alanına yazılır.

## Pose Politikası

Bu paket pose integration yapmaz. `/odom_raw` mesajındaki pose alanı her zaman aşağıdaki gibi yayınlanır:

```text
position.x = 0.0
position.y = 0.0
position.z = 0.0

orientation.x = 0.0
orientation.y = 0.0
orientation.z = 0.0
orientation.w = 1.0
```

Bu karar bilinçlidir. x/y/yaw dead-reckoning ve TF yayını bu paketin kapsamı dışındadır.

## Konfigürasyon

Varsayılan config dosyası:

```text
config/params.yaml
```

Örnek:

```yaml
/**:
  ros__parameters:
    wheel_ticks_topic: /wheel_ticks
    odom_topic: /odom_raw

    frame_id: odom
    child_frame_id: base_footprint

    wheel_radius_m: 0.03729
    track_width_m: 0.18
    cpr_left: 3959
    cpr_right: 3963

    enc_dt_min_s: 0.0
    enc_dt_max_s: 0.5

    pose_covariance: [ ... 36 elements ... ]
    twist_covariance: [ ... 36 elements ... ]

    debug: false
```

## Parametreler

| Parametre | Açıklama |
| --- | --- |
| `wheel_ticks_topic` | Dinlenecek `WheelTicks` topic'i |
| `odom_topic` | Yayınlanacak `Odometry` topic'i |
| `frame_id` | Odometry header frame adı |
| `child_frame_id` | Odometry child frame adı |
| `wheel_radius_m` | Teker yarıçapı |
| `track_width_m` | Sol/sağ teker arası iz genişliği |
| `cpr_left` | Sol encoder count-per-revolution değeri |
| `cpr_right` | Sağ encoder count-per-revolution değeri |
| `enc_dt_min_s` | Minimum kabul edilen dt |
| `enc_dt_max_s` | Maksimum kabul edilen dt |
| `pose_covariance` | Odometry pose covariance dizisi |
| `twist_covariance` | Odometry twist covariance dizisi |
| `debug` | 1 Hz debug panelini açar |

## Debug Modu

`debug: true` ise 1 Hz hızında debug paneli loglanır:

- Alınan `/wheel_ticks` sayısı
- Yayınlanan `/odom_raw` sayısı
- dt guard nedeniyle atlanan mesaj sayısı
- Son `WheelTicks`
- Son dt
- Son `v` ve `w`

## Kullanım

Build:

```bash
colcon build --packages-select hamals_interfaces hamals_odometry
source install/setup.bash
```

Node çalıştırma:

```bash
ros2 run hamals_odometry odometry_node --ros-args --params-file src/hamals_odometry/config/params.yaml
```

Bridge ile birlikte tipik akış:

```bash
ros2 launch hamals_serial_bridge serial_bridge.launch.py
ros2 run hamals_odometry odometry_node --ros-args --params-file src/hamals_odometry/config/params.yaml
```

## İlgili Paketler

- `hamals_serial_bridge`: Seri port yönetimi, protokol parse/encode, `/cmd_vel`, `/imu/data` ve `/wheel_ticks` köprüsü.
- `hamals_interfaces`: `WheelTicks` mesaj tanımı.
- `hamals_state_estimation`: `/odom_raw` çıktısını EKF tarafında kullanabilir.
