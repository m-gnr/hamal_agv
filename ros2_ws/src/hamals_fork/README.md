# hamals_fork

## Kısa Açıklama

`hamals_fork`, AGV forklift çatal mekanizmasını ROS2 topic katmanında kontrol eden pakettir. Üst seviye fork komutlarını alır, serial bridge katmanına düşük seviye fork komutu gönderir ve MCU'dan gelen gerçek fork state bilgisini dış node'lar için temiz `/fork/state` olarak yayınlar.

Bu paket doğrudan seri port açmaz ve doğrudan MCU ile konuşmaz. Serial frame encode/decode, fiziksel haberleşme ve MCU protokol detayları `hamals_serial_bridge` tarafındadır.

Yeni mimari MCU feedback tabanlıdır. Eski timer tabanlı `UP_DONE` / `DOWN_DONE` mantığı kaldırılmıştır; fork konumu ROS tarafında süreyle tahmin edilmez, MCU'dan gelen limit switch state bilgisiyle izlenir.

## Mimari

```text
/fork/cmd
   ↓
hamals_fork_node
   ↓
/mcu/fork_cmd
   ↓
hamals_serial_bridge
   ↓
MCU

MCU
   ↓
hamals_serial_bridge
   ↓
/mcu/fork_state
   ↓
hamals_fork_node
   ↓
/fork/state
```

`hamals_fork` sorumlulukları:
- `/fork/cmd` üst seviye komutlarını dinler.
- Komutları `"UP"`, `"DOWN"`, `"STOP"` string komutlarına çevirip `/mcu/fork_cmd` topic'ine yayınlar.
- `/mcu/fork_state` topic'inden gelen MCU feedback bilgisini tutar.
- Dış node'lar için `/fork/state` topic'ini yayınlar.
- MCU state timeout ve ROS tarafı komut reddi gibi topic seviyesindeki güvenlik davranışlarını uygular.

`hamals_serial_bridge` sorumlulukları:
- ROS topic'leri ile seri protokol arasında köprü görevi yapar.
- `/mcu/fork_cmd` komutlarını MCU'ya taşır.
- MCU'dan gelen fork state bilgisini `/mcu/fork_state` olarak ROS'a yayınlar.

`MCU` sorumlulukları:
- Motor sürücüyü kontrol eder.
- Limit switch pinlerini okur.
- Motor güvenliğini sağlar.
- Gerçek donanım state ve hata bilgilerini üretir.

Önemli noktalar:
- Motor güvenliği MCU tarafındadır.
- Limit switch okuma MCU tarafındadır.
- ROS tarafı sadece komut gönderir ve state izler.
- `hamals_fork` serial porta bağlanmaz.
- `hamals_fork` motor pinlerini sürmez.
- `hamals_fork` sadece ROS topic katmanında çalışır.

## ROS Interfaces

### Subscribed

| Topic | Type | Açıklama |
| --- | --- | --- |
| `/fork/cmd` | `hamals_interfaces/msg/ForkCommand` | Üst seviye fork komutu. `STOP`, `UP`, `DOWN`. |
| `/mcu/fork_state` | `hamals_interfaces/msg/ForkState` | Serial bridge tarafından MCU'dan gelen ham/alt seviye fork state bilgisi. |

### Published

| Topic | Type | Açıklama |
| --- | --- | --- |
| `/mcu/fork_cmd` | `std_msgs/msg/String` | Serial bridge'e gönderilecek düşük seviye komut. `"UP"`, `"DOWN"`, `"STOP"`. |
| `/fork/state` | `hamals_interfaces/msg/ForkState` | Dış node'ların okuyacağı temiz fork state bilgisi. |

## Mesajlar

### ForkCommand.msg

```text
uint8 command

uint8 STOP=0
uint8 UP=1
uint8 DOWN=2
```

### ForkState.msg Alanları

| Alan | Açıklama |
| --- | --- |
| `stamp` | Mesajın üretildiği ROS zamanı. |
| `t_us` | MCU timestamp değeri. MCU tarafından mikro saniye cinsinden gönderilir. |
| `state` | Fork mekanizmasının mevcut state değeri. |
| `last_command` | Fork node'a gelen son geçerli ROS komutu. MCU'dan kopyalanmaz. |
| `error_code` | Fork hata kodu. |
| `is_moving` | Fork motorunun hareket edip etmediği. |
| `upper_limit` | Üst limit switch aktif mi? |
| `lower_limit` | Alt limit switch aktif mi? |

State enumları:

| Enum | Değer | Açıklama |
| --- | ---: | --- |
| `IDLE` | `0` | Motor çalışmıyor, aktif hareket yok. |
| `MOVING_UP` | `1` | Fork yukarı yönde hareket ediyor. |
| `MOVING_DOWN` | `2` | Fork aşağı yönde hareket ediyor. |
| `AT_TOP` | `3` | Üst limit switch aktif, fork üst konumda. |
| `AT_BOTTOM` | `4` | Alt limit switch aktif, fork alt konumda. |
| `ERROR` | `5` | Fork sistemi hata durumunda. |

Command enumları:

| Enum | Değer | Açıklama |
| --- | ---: | --- |
| `CMD_NONE` | `0` | Henüz komut alınmadı veya son komut bilinmiyor. |
| `CMD_STOP` | `1` | Son komut `STOP`. |
| `CMD_UP` | `2` | Son komut `UP`. |
| `CMD_DOWN` | `3` | Son komut `DOWN`. |

Error enumları:

| Enum | Değer | Açıklama |
| --- | ---: | --- |
| `ERROR_NONE` | `0` | Hata yok. |
| `ERROR_INVALID_COMMAND` | `1` | Geçersiz komut. |
| `ERROR_TOP_TIMEOUT` | `2` | Üst limite beklenen sürede ulaşılamadı. Genelde MCU tarafında üretilir. |
| `ERROR_BOTTOM_TIMEOUT` | `3` | Alt limite beklenen sürede ulaşılamadı. Genelde MCU tarafında üretilir. |
| `ERROR_LIMIT_CONFLICT` | `4` | Üst ve alt limit aynı anda aktif. |
| `ERROR_MCU_TIMEOUT` | `5` | MCU state mesajı beklenen sürede gelmedi. |

Önemli: `last_command` MCU'dan kopyalanmaz. Bu alan ROS tarafında, en son alınan `/fork/cmd` komutuna göre tutulur. Böylece `/fork/state`, MCU'nun gönderdiği `last_command` değerinden bağımsız olarak ROS tarafındaki son komutu gösterir.

## Config

Örnek `config/fork.yaml`:

```yaml
/**:
  ros__parameters:
    fork_cmd_topic: /fork/cmd
    fork_state_topic: /fork/state

    mcu_fork_cmd_topic: /mcu/fork_cmd
    mcu_fork_state_topic: /mcu/fork_state

    mcu_state_timeout_ms: 1000
    state_publish_hz: 10.0

    stop_on_shutdown: true
    debug: true
```

Parametreler:

| Parametre | Açıklama |
| --- | --- |
| `fork_cmd_topic` | Üst seviye fork komutlarının dinleneceği topic. |
| `fork_state_topic` | Dış node'lar için yayınlanan temiz fork state topic'i. |
| `mcu_fork_cmd_topic` | Serial bridge'e gönderilen düşük seviye fork komut topic'i. |
| `mcu_fork_state_topic` | Serial bridge'den gelen MCU fork state topic'i. |
| `mcu_state_timeout_ms` | İlk MCU state mesajından sonra yeni state gelmezse timeout üretilecek süre. |
| `state_publish_hz` | `/fork/state` yayın frekansı. |
| `stop_on_shutdown` | `true` ise node kapanırken `/mcu/fork_cmd` topic'ine `"STOP"` yayınlanır. |
| `debug` | `true` ise node başlangıç config ve debug logları yayınlanır. |

## Çalıştırma

Build:

```bash
cd ~/develop/hamal_agv/ros2_ws
colcon build --packages-select hamals_interfaces hamals_fork --symlink-install
source install/setup.bash
```

Launch:

```bash
ros2 launch hamals_fork fork.launch.py
```

Run:

```bash
ros2 run hamals_fork fork_node
```

## Manuel Testler

MCU komutunu izleme:

```bash
ros2 topic echo /mcu/fork_cmd
```

Fork state izleme:

```bash
ros2 topic echo /fork/state
```

UP komutu:

```bash
ros2 topic pub --once /fork/cmd hamals_interfaces/msg/ForkCommand "{command: 1}"
```

DOWN komutu:

```bash
ros2 topic pub --once /fork/cmd hamals_interfaces/msg/ForkCommand "{command: 2}"
```

STOP komutu:

```bash
ros2 topic pub --once /fork/cmd hamals_interfaces/msg/ForkCommand "{command: 0}"
```

Mock MCU `MOVING_UP`:

```bash
ros2 topic pub --once /mcu/fork_state hamals_interfaces/msg/ForkState "{t_us: 12345, state: 1, last_command: 0, error_code: 0, is_moving: true, upper_limit: false, lower_limit: false}"
```

Mock MCU `AT_TOP`:

```bash
ros2 topic pub --once /mcu/fork_state hamals_interfaces/msg/ForkState "{t_us: 12350, state: 3, last_command: 0, error_code: 0, is_moving: false, upper_limit: true, lower_limit: false}"
```

Mock conflict:

```bash
ros2 topic pub --once /mcu/fork_state hamals_interfaces/msg/ForkState "{t_us: 12355, state: 1, last_command: 0, error_code: 0, is_moving: true, upper_limit: true, lower_limit: true}"
```

Beklenen conflict sonucu:
- `/fork/state` içinde `state=ERROR`
- `error_code=ERROR_LIMIT_CONFLICT`
- `is_moving=false`

## Güvenlik Davranışı

- `ERROR` durumunda `UP` ve `DOWN` komutları reddedilir.
- `ERROR` durumunda sadece `STOP` kabul edilir.
- `stop_on_shutdown: true` ise node kapanırken `/mcu/fork_cmd` topic'ine `"STOP"` yayınlanır.
- İlk MCU state mesajı gelmeden MCU timeout hatası üretilmez.
- İlk MCU state mesajından sonra `mcu_state_timeout_ms` süresi boyunca yeni state gelmezse `ERROR_MCU_TIMEOUT` üretilir.
- `/mcu/fork_state` içinde `upper_limit=true` ve `lower_limit=true` aynı anda gelirse `ERROR_LIMIT_CONFLICT` üretilir ve `is_moving=false` yapılır.

## MCU Tarafında Olması Gereken Güvenlikler

Bu paket MCU kodunu içermez. Gerçek donanımda MCU tarafında aşağıdaki güvenliklerin uygulanması gerekir:

- Upper limit aktifken `UP` yasak.
- Lower limit aktifken `DOWN` yasak.
- İki limit aynı anda aktifse motor durdurulmalı ve `ERROR_LIMIT_CONFLICT` üretilmeli.
- Seri komut watchdog olmalı.
- Belirli süre yeni komut gelmezse motor durmalı.
- Üst limite ulaşılamazsa `ERROR_TOP_TIMEOUT` üretilmeli.
- Alt limite ulaşılamazsa `ERROR_BOTTOM_TIMEOUT` üretilmeli.
- ROS veya serial bağlantı kopsa bile MCU motoru güvenli şekilde durdurabilmeli.

## Donanım Mimarisi

MCU: Deneyap Kart 1A v2

Motor driver: BTS7960

Bağlantılar:

| Deneyap Kart 1A v2 | BTS7960 |
| --- | --- |
| A5 / PWM1 | RPWM |
| A4 / PWM0 | LPWM |
| D12 | R_EN |
| D13 | L_EN |
| 5V | VCC |
| GND | GND |

Limit switchler NC kullanılacak.

Üst limit switch:
- `COM -> GND`
- `NC -> D0`
- `NO -> boş`

Alt limit switch:
- `COM -> GND`
- `NC -> D1`
- `NO -> boş`

NC + `INPUT_PULLUP` mantığı:
- Switch basılı değilken pin `LOW`.
- Switch basılınca pin `HIGH`.
- MCU tarafında `upper_limit = digitalRead(D0) == HIGH`.
- MCU tarafında `lower_limit = digitalRead(D1) == HIGH`.

## Dosya Yapısı

```text
hamals_fork/
├── config/
│   └── fork.yaml
├── launch/
│   └── fork.launch.py
├── hamals_fork/
│   ├── __init__.py
│   ├── main.py
│   ├── fork_controller.py
│   ├── fork_commands.py
│   ├── fork_states.py
│   └── helpers/
│       ├── __init__.py
│       ├── config_loader.py
│       └── log_helpers.py
├── test/
│   └── test_fork_controller.py
├── package.xml
├── setup.py
└── setup.cfg
```

## Test

Unit testleri çalıştırma:

```bash
cd ~/develop/hamal_agv/ros2_ws
colcon test --packages-select hamals_fork
colcon test-result --verbose
```

## Kapsam Dışı

- Bu paket serial frame encode/decode yapmaz.
- Bu paket doğrudan MCU'ya serial yazmaz.
- Bu paket BTS7960 pinlerini sürmez.
- Bu paket limit switch pinlerini okumaz.
- Bu sorumluluklar `hamals_serial_bridge` ve MCU firmware tarafındadır.
