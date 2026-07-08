# hamals_serial_bridge

## Kısa Açıklama

`hamals_serial_bridge`, ROS2 sistemi ile MCU arasında seri haberleşme köprüsü kuran pakettir. Serial portu açar, ROS topic'lerinden gelen komutları mevcut framed serial protokole çevirir, MCU'dan gelen framed serial mesajları parse eder ve parse edilen verileri ROS topic'leri olarak yayınlar.

Bu paket kontrol kararı vermez. Fork state machine, odometri hesabı, görev planlama veya motor güvenlik kararı burada yapılmaz. `hamals_serial_bridge` sadece ROS topic ↔ serial protocol bridge katmanıdır.

Fork protokolü bu bridge'e eklenmiştir. `/mcu/fork_cmd` topic'inden gelen `UP`, `DOWN`, `STOP` komutları `$FORK,<CMD>*CS` frame'lerine çevrilir; MCU'dan gelen `$FORK_STATE,...*CS` frame'leri `/mcu/fork_state` topic'ine aktarılır.

## Mimari

```text
ROS2
 ├── /cmd_vel
 ├── /mcu/fork_cmd
 │
 ↓
hamals_serial_bridge
 │
 ↓
Serial protocol
 │
 ↓
MCU

MCU
 │
 ↓
Serial protocol
 │
 ↓
hamals_serial_bridge
 ├── /wheel_ticks
 ├── /imu/data
 └── /mcu/fork_state
```

Sorumluluk ayrımı:

- `hamals_serial_bridge`: Serial port yönetimi, protocol encode/decode, ROS topic ↔ serial frame dönüşümü.
- `hamals_fork`: Fork state machine ve komut politikası. Son ROS fork komutunu local olarak tutar.
- MCU: Motor sürme, limit switch okuma, donanım güvenliği ve gerçek fork state üretimi.
- `hamals_odometry`: Varsa `/wheel_ticks` raw encoder verisinden odometry üretimi.

Önemli:

- `hamals_serial_bridge` serial porta sahip olan tek pakettir.
- Başka ROS node'ları doğrudan `/dev/ttyACM0` açmamalıdır.
- Fork limit switch güvenliği MCU tarafındadır.
- `last_command` bilgisi `hamals_fork` tarafında tutulur; serial bridge bunu hesaplamaz.

## Serial Protocol

Frame formatı:

```text
$PAYLOAD*CS\n
```

Checksum kuralları:

- Checksum payload üzerinden XOR ile hesaplanır.
- `$`, `*` ve `\n` checksum'a dahil edilmez.
- Checksum iki haneli uppercase hex formatındadır.
- Örnek checksum gösterimi: `*2A`

## ROS → MCU Frame'leri

| Frame | Açıklama | Kaynak Topic |
| --- | --- | --- |
| `$CMD,v,w*CS` | Base hareket komutu. `v=linear.x`, `w=angular.z`. | `/cmd_vel` |
| `$FORK,UP*CS` | Fork yukarı komutu. | `/mcu/fork_cmd` |
| `$FORK,DOWN*CS` | Fork aşağı komutu. | `/mcu/fork_cmd` |
| `$FORK,STOP*CS` | Fork motorunu durdurma komutu. | `/mcu/fork_cmd` |

`/cmd_vel` için `encode_cmd(v, w)` mevcut formatı kullanır:

```text
$CMD,0.100,-0.200*CS
```

Fork komutları için `encode_fork_cmd(cmd)` aynı frame ve checksum stilini kullanır:

```text
$FORK,UP*CS
```

## MCU → ROS Frame'leri

| Frame | Açıklama |
| --- | --- |
| `$ENC,t_us,dl,dr*CS` | Encoder delta tick verisi. |
| `$IMU,t_us,gz,ax,ay,az*CS` | IMU verisi. |
| `$FORK_STATE,t_us,state,upper,lower,error*CS` | Fork state bilgisi. |
| `$ODOM,t_us,x,y,yaw,v,w*CS` | Legacy odom frame parse desteği. |

`ENC` alanları:

- `t_us`: MCU timestamp.
- `dl`: Left wheel delta tick.
- `dr`: Right wheel delta tick.

`IMU` alanları:

- `t_us`: MCU timestamp.
- `gz`: Angular velocity z.
- `ax`, `ay`, `az`: Linear acceleration.

`FORK_STATE` alanları:

- `t_us`: MCU timestamp.
- `state`: `ForkState` enum değeri.
- `upper`: Üst limit switch durumu (`0` veya `1`).
- `lower`: Alt limit switch durumu (`0` veya `1`).
- `error`: `ForkState` error enum değeri.

Legacy `ODOM` frame'i `decode_line()` içinde parse edilir. Yeni mimaride odometri hesabı bridge içinde yapılmaz; encoder raw verisi `/wheel_ticks` olarak yayınlanır ve odometry üretimi ayrı paket sorumluluğundadır.

## ROS Interfaces

### Subscribed Topics

| Topic | Type | Açıklama |
| --- | --- | --- |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | Base hareket komutu. `$CMD,v,w*CS` olarak MCU'ya gönderilir. |
| `/mcu/fork_cmd` | `std_msgs/msg/String` | Fork düşük seviye komutu. Kabul edilen değerler: `UP`, `DOWN`, `STOP`. |

### Published Topics

| Topic | Type | Açıklama |
| --- | --- | --- |
| `/wheel_ticks` | `hamals_interfaces/msg/WheelTicks` | MCU'dan gelen `$ENC,t_us,dl,dr*CS` frame'lerinden yayınlanan encoder delta tick verisi. |
| `/imu/data` | `sensor_msgs/msg/Imu` | MCU'dan gelen `$IMU,t_us,gz,ax,ay,az*CS` frame'lerinden yayınlanır. |
| `/mcu/fork_state` | `hamals_interfaces/msg/ForkState` | MCU'dan gelen `$FORK_STATE,t_us,state,upper,lower,error*CS` frame'lerinden yayınlanır. |

## Fork Entegrasyonu

Fork entegrasyonu taşıyıcı katman olarak çalışır:

1. `hamals_fork` paketi `/mcu/fork_cmd` topic'ine `UP`, `DOWN` veya `STOP` yayınlar.
2. `hamals_serial_bridge` bu string'i `$FORK,<CMD>*CS\n` formatına çevirir.
3. MCU fork motorunu sürer, limit switchleri okur ve donanım güvenliğini uygular.
4. MCU `$FORK_STATE,t_us,state,upper,lower,error*CS` frame'i gönderir.
5. `hamals_serial_bridge` bu frame'i parse edip `/mcu/fork_state` topic'ine `ForkState` olarak yayınlar.

`ForkState.last_command` serial bridge tarafından hesaplanmaz. Bu alan `/mcu/fork_state` yayınında `ForkState.CMD_NONE` bırakılır. Son ROS komutu `hamals_fork` tarafından local olarak tutulur ve dış dünyaya `/fork/state` üzerinden aktarılır.

## Config

Varsayılan config dosyası:

```text
config/serial_bridge.yaml
```

Mevcut config örneği:

```yaml
/**:
  ros__parameters:
    port: /dev/ttyACM0
    baudrate: 230400
    timeout_ms: 50

    imu_frame_id: imu_link

    cmd_vel_topic: /cmd_vel
    wheel_ticks_topic: /wheel_ticks
    imu_topic: /imu/data
    mcu_fork_cmd_topic: /mcu/fork_cmd
    mcu_fork_state_topic: /mcu/fork_state

    publish_linear_accel: true

    imu_ang_vel_cov_diag: [9999.0, 9999.0, 0.005]
    imu_lin_acc_cov_diag: [0.01, 9999.0, 9999.0]

    reset_on_startup: true
    reset_pulse_ms: 100
    reset_boot_wait_ms: 1500

    debug: false

    cmd_vel_timeout_ms: 500
    cmd_vel_rate_limit_hz: 25

    cmd_dedup_enabled: true
    cmd_dedup_eps_v: 0.02
    cmd_dedup_eps_w: 0.05
    cmd_force_resend_ms: 300
```

Parametreler:

| Parametre | Açıklama |
| --- | --- |
| `port` | Açılacak serial port. Varsayılan `/dev/ttyACM0`. |
| `baudrate` | Serial haberleşme baudrate değeri. |
| `timeout_ms` | Serial read timeout süresi. |
| `cmd_vel_topic` | Base hareket komutu topic'i. |
| `wheel_ticks_topic` | Encoder delta tick publish topic'i. |
| `imu_topic` | IMU publish topic'i. |
| `mcu_fork_cmd_topic` | Fork komutlarının dinleneceği topic. |
| `mcu_fork_state_topic` | MCU fork state bilgisinin yayınlanacağı topic. |
| `imu_frame_id` | Yayınlanan `sensor_msgs/msg/Imu` mesajının frame id değeri. |
| `publish_linear_accel` | `true` ise IMU linear acceleration alanları yayınlanır. |
| `imu_ang_vel_cov_diag` | IMU angular velocity covariance diagonal değerleri. |
| `imu_lin_acc_cov_diag` | IMU linear acceleration covariance diagonal değerleri. |
| `reset_on_startup` | `true` ise başlangıçta MCU DTR üzerinden resetlenir. |
| `reset_pulse_ms` | DTR reset pulse süresi. |
| `reset_boot_wait_ms` | Reset sonrası MCU boot bekleme süresi. |
| `cmd_vel_timeout_ms` | `/cmd_vel` kesilirse stop komutu göndermek için kullanılan dead-man timeout. |
| `cmd_vel_rate_limit_hz` | Serial hatta gönderilecek `/cmd_vel` frame frekans limiti. |
| `cmd_dedup_enabled` | Aynı veya çok yakın hız komutlarını tekrar göndermeyi azaltır. |
| `cmd_dedup_eps_v` | Linear velocity dedup eşiği. |
| `cmd_dedup_eps_w` | Angular velocity dedup eşiği. |
| `cmd_force_resend_ms` | Dedup açıkken aynı komutun zorunlu yeniden gönderim aralığı. |
| `debug` | `true` ise debug paneli loglanır. |

## Çalıştırma

Build:

```bash
cd ~/develop/hamal_agv/ros2_ws
colcon build --packages-select hamals_interfaces hamals_serial_bridge --symlink-install
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

Run:

```bash
ros2 run hamals_serial_bridge serial_node
```

## Manuel Testler

Fork komut testi:

Terminal 1:

```bash
ros2 topic echo /mcu/fork_cmd
```

Terminal 2:

```bash
ros2 topic pub --once /mcu/fork_cmd std_msgs/msg/String "{data: 'UP'}"
```

Beklenen:

- Node çalışırken serial porta `$FORK,UP*CS\n` frame'i yazılır.
- Gerçek serial port yoksa node başlatma hata verebilir.

Invalid fork komutu:

```bash
ros2 topic pub --once /mcu/fork_cmd std_msgs/msg/String "{data: 'LEFT'}"
```

Beklenen:

- Warning log görülür.
- Serial'e frame yazılmaz.

`FORK_STATE` parser testi:

Geçerli frame payload'ı:

```text
FORK_STATE,12345678,1,0,0,0
```

Checksum `compute_checksum("FORK_STATE,12345678,1,0,0,0")` ile hesaplanır ve frame `decode_line()` üzerinden test edilir.

Beklenen parse sonucu:

```python
{
    "type": "fork_state",
    "t_us": 12345678,
    "state": 1,
    "upper_limit": False,
    "lower_limit": False,
    "error_code": 0,
}
```

## Test

Unit test komutları:

```bash
cd ~/develop/hamal_agv/ros2_ws
colcon test --packages-select hamals_serial_bridge
colcon test-result --verbose
```

Test kapsamı:

- `encode_fork_cmd`
- `decode_line` ile `FORK_STATE`
- Checksum hatalı frame'in reddedilmesi
- Mevcut `CMD` encode regression testi
- Mevcut `ENC` decode regression testi
- Mevcut `IMU` decode regression testi
- Mevcut legacy `ODOM` decode regression testi

## Güvenlik Notları

- Serial bridge güvenlik kararı vermez.
- Upper limit aktifken `UP` yasaklama MCU tarafında yapılmalıdır.
- Lower limit aktifken `DOWN` yasaklama MCU tarafında yapılmalıdır.
- İki limit aynı anda aktifse MCU motoru durdurup `ERROR_LIMIT_CONFLICT` üretmelidir.
- Komut watchdog MCU tarafında olmalıdır.
- ROS veya serial bağlantı kopsa bile MCU motoru güvenli şekilde durdurabilmelidir.
- `hamals_serial_bridge` sadece gelen state bilgisini ROS'a taşır.
- Base hareket için bridge tarafında `/cmd_vel` dead-man timeout ve rate-limit uygulanır; bu motor donanım güvenliğinin yerine geçmez.

## Dosya Yapısı

```text
hamals_serial_bridge/
├── config/
│   └── serial_bridge.yaml
├── launch/
│   └── serial_bridge.launch.py
├── hamals_serial_bridge/
│   ├── __init__.py
│   ├── main.py
│   ├── parser.py
│   ├── protocol.py
│   └── helpers/
│       ├── __init__.py
│       ├── config_loader.py
│       └── debug_panels.py
├── test/
│   ├── test_copyright.py
│   ├── test_flake8.py
│   ├── test_parser.py
│   └── test_pep257.py
├── package.xml
├── setup.py
└── setup.cfg
```

## Kapsam Dışı

- Bu paket fork state machine çalıştırmaz.
- Bu paket limit switch pinlerini okumaz.
- Bu paket BTS7960 pinlerini sürmez.
- Bu paket motor PWM üretmez.
- Bu paket görev planlama yapmaz.
- Bu paket odometry fusion yapmaz.
- Fork kararları `hamals_fork` tarafındadır.
- Donanım güvenliği ve motor sürme MCU firmware tarafındadır.
- Encoder raw verisinden odometry üretimi `hamals_odometry` gibi ayrı paketlerin sorumluluğudur.
- Navigation ve mission kararları navigation/mission paketlerinin sorumluluğudur.
