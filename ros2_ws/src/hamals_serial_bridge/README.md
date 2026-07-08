# HAMALS Serial Bridge

> ROS 2 ile gömülü MCU firmware arasında checksum'lu seri haberleşme köprüsü.

`hamals_serial_bridge`, HAMALS AGV üzerinde ROS 2 graph'ı ile MCU firmware arasındaki seri haberleşme sınırını yönetir. Bu paket yalnızca veri köprüsüdür; encoder verisinden diferansiyel sürüş kinematiği veya odometri hesabı yapmaz.

Odometri hesabı ayrı paket olan `hamals_odometry` içindedir.

## Amaç

Bu paket aşağıdaki işleri üstlenir:

- Seri port bağlantısını açmak ve yönetmek
- MCU reset akışını isteğe bağlı olarak DTR üzerinden yapmak
- ROS `/cmd_vel` mesajlarını MCU protokolüne encode edip seri hatta yazmak
- MCU'dan gelen checksum'lu frame'leri parse etmek
- `$IMU,t_us,gz,ax,ay,az*CS` frame'lerini `/imu/data` mesajına çevirmek
- `$ENC,t_us,dl,dr*CS` frame'lerini ham `/wheel_ticks` mesajına çevirmek
- Dead-man timeout, cmd_vel deduplication ve rate-limit güvenliklerini uygulamak
- Debug modunda RX/TX sayaçlarını raporlamak

Bu paket şu işleri yapmaz:

- Encoder kinematiği hesaplamaz
- `/odom_raw` yayınlamaz
- Pose integration yapmaz
- TF yayınlamaz

## Mimari

```
[ ROS Graph Layer ]
        |
[ hamals_serial_bridge ]
        |
[ Framed Serial Protocol ]
        |
[ Embedded Firmware ]
```

## Veri Akışı

### ROS -> MCU

```
/cmd_vel
   |
Twist
   |
encode_cmd()
   |
$CMD,v,w*CS
   |
serial.write()
```

`/cmd_vel` mesajındaki `linear.x` ve `angular.z` değerleri MCU'nun beklediği `$CMD,v,w*CS` formatına çevrilir.

### MCU -> ROS: Encoder

```
$ENC,t_us,dl,dr*CS
   |
LineParser
   |
WheelTicks
   |
/wheel_ticks
```

`t_us`, `dl` ve `dr` alanları hiçbir kinematik hesap yapılmadan `hamals_interfaces/msg/WheelTicks` mesajına aktarılır.

`WheelTicks.header.stamp`, bridge'in publish anındaki ROS clock değeriyle doldurulur. Bu alan debug ve latency gözlemi içindir; odometri dt hesabı için kullanılmaz.

### MCU -> ROS: IMU

```
$IMU,t_us,gz,ax,ay,az*CS
   |
LineParser
   |
sensor_msgs/Imu
   |
/imu/data
```

IMU mesajında orientation bilinmediği için `orientation_covariance[0] = -1.0` olarak yayınlanır. Linear acceleration yayını `publish_linear_accel` parametresiyle açılıp kapatılabilir.

## Topic'ler

### Subscribe

| Topic | Tip | Açıklama |
| --- | --- | --- |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | MCU'ya gönderilecek hız komutu |

### Publish

| Topic | Tip | Açıklama |
| --- | --- | --- |
| `/wheel_ticks` | `hamals_interfaces/msg/WheelTicks` | MCU'dan gelen ham encoder delta verisi |
| `/imu/data` | `sensor_msgs/msg/Imu` | MCU'dan gelen IMU passthrough verisi |

## WheelTicks Mesajı

```text
std_msgs/Header header
uint32 t_us
int32 dl
int32 dr
```

Alanlar:

- `header.stamp`: Bridge'in publish anındaki ROS zamanı
- `t_us`: MCU `micros()` zaman damgası
- `dl`: Sol encoder delta tick
- `dr`: Sağ encoder delta tick

## Konfigürasyon

Varsayılan launch dosyası şu config dosyasını kullanır:

```text
config/serial_bridge.yaml
```

Örnek:

```yaml
/**:
  ros__parameters:
    port: /dev/ttyACM0
    baudrate: 230400
    timeout_ms: 50

    cmd_vel_topic: /cmd_vel
    wheel_ticks_topic: /wheel_ticks
    imu_topic: /imu/data
    imu_frame_id: imu_link

    publish_linear_accel: true
    imu_ang_vel_cov_diag: [9999.0, 9999.0, 0.005]
    imu_lin_acc_cov_diag: [0.01, 9999.0, 9999.0]

    reset_on_startup: true
    reset_pulse_ms: 100
    reset_boot_wait_ms: 1500

    cmd_vel_timeout_ms: 500
    cmd_vel_rate_limit_hz: 25
    cmd_dedup_enabled: true
    cmd_dedup_eps_v: 0.02
    cmd_dedup_eps_w: 0.05
    cmd_force_resend_ms: 300

    debug: false
```

## Güvenlik Mekanizmaları

### Dead-man Timeout

Belirli süre boyunca `/cmd_vel` alınmazsa bridge MCU'ya zorunlu stop komutu gönderir:

```text
$CMD,0.000,0.000*CS
```

Bu mekanizma teleop, Nav2 veya üst seviye kontrol node'ları durduğunda robotun hareket komutu almaya devam etmesini engeller.

### Rate-limit

`cmd_vel_rate_limit_hz`, seri hatta gönderilecek komut frekansını sınırlar. Stop ve hareket arasındaki geçişler kritik kabul edilir ve rate-limit'e takılmadan gönderilir.

### Deduplication

`cmd_dedup_enabled` açıksa önceki komuta göre anlamlı fark taşımayan hız komutları tekrar gönderilmez. `cmd_force_resend_ms` süresi dolduğunda aynı komut periyodik olarak yeniden gönderilebilir.

## Seri Protokol

### ROS -> MCU

```text
$CMD,v,w*CS
```

Örnek:

```text
$CMD,0.200,0.000*CS
```

### MCU -> ROS

Encoder:

```text
$ENC,t_us,dl,dr*CS
```

IMU:

```text
$IMU,t_us,gz,ax,ay,az*CS
```

Checksum algoritması `protocol.py` içinde XOR checksum olarak uygulanır. Invalid checksum taşıyan frame'ler parser tarafından discard edilir.

## Thread Modeli

- ROS callback'leri rclpy executor thread'inde çalışır
- Serial RX ayrı daemon thread içinde çalışır
- TX işlemleri lock ile korunur
- Parser byte/frame istatistiklerini tutar

## Debug Modu

`debug: true` ise 1 Hz hızında debug paneli loglanır:

- TX packet sayısı
- Dedup ve rate-limit nedeniyle atlanan komut sayısı
- RX byte sayısı
- Geçerli/geçersiz frame sayısı
- `/wheel_ticks` publish sayısı
- Dead-man durumu
- Son `/cmd_vel`
- Son `WheelTicks`

## Kullanım

Build:

```bash
colcon build --packages-select hamals_interfaces hamals_serial_bridge
source install/setup.bash
```

Launch:

```bash
ros2 launch hamals_serial_bridge serial_bridge.launch.py
```

Farklı config dosyasıyla launch:

```bash
ros2 launch hamals_serial_bridge serial_bridge.launch.py config:=/path/to/serial_bridge.yaml
```

## İlgili Paketler

- `hamals_interfaces`: `WheelTicks` mesaj tanımını içerir.
- `hamals_odometry`: `/wheel_ticks` dinler, MCU `t_us` farkından dt hesaplar ve `/odom_raw` yayınlar.
