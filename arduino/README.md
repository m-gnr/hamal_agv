# HAMALS Firmware

## 1. Kısa Açıklama

Bu firmware Deneyap Kart 1A v2 üzerinde çalışan HAMALS AGV mikrodenetleyici yazılımıdır. ROS2 tarafındaki `hamals_serial_bridge` paketiyle checksum'lu framed serial protokol üzerinden haberleşir.

Firmware base motor kontrolü, teker encoder okuma, BNO085 IMU okuma, periyodik telemetry gönderimi ve fork/lift motor kontrolünü yürütür. ROS tarafı komut verir; MCU motor sürme, limit switch okuma ve kritik fork güvenlik kararlarını yerelde uygular.

Fork entegrasyonu MCU seviyesinde fail-safe olacak şekilde tasarlanmıştır. Checksum doğrulanmadan fork komutu uygulanmaz, limit conflict durumunda motor durur, hareket sırasında command watchdog ve max motion timeout çalışır.

## 2. Genel Mimari

```text
ROS2
  ↓
hamals_serial_bridge
  ↓
Serial Protocol: $PAYLOAD*CS\n
  ↓
Deneyap Kart 1A v2 Firmware
  ├── Base motor control
  ├── Encoder read
  ├── IMU read
  ├── Fork motor control
  └── Safety checks
```

Modül sorumlulukları:

| Klasör | Sorumluluk |
| --- | --- |
| `comm/` | Serial frame parse, checksum doğrulama, payload dispatch, frame üretimi, fork protocol köprüsü. |
| `config/` | Pin tanımları, robot sabitleri ve fork konfigürasyonu. |
| `control/` | `VelocityCmd`, wheel PID ve fork state machine. |
| `encoder/` | Sol/sağ teker quadrature encoder okuma ve delta tick üretimi. |
| `imu/` | BNO085 IMU SPI okuma. |
| `kinematics/` | Encoder delta ve robot geometrisinden wheel/robot hız yardımcıları. |
| `motor/` | Base motor PWM sürücüleri ve BTS7960 fork motor sürücüsü. |
| `odometry/` | IMU destekli 2D odometry helper sınıfı. Mevcut ana loop raw `ENC` yayınlar; odom frame yayınlamaz. |
| `safety/` | Watchdog helper ve fork limit switch safety okuma. |
| `timing/` | Periyodik görev zamanlama yardımcıları. |

## 3. Donanım

| Parça | Açıklama |
| --- | --- |
| MCU | Deneyap Kart 1A v2 |
| Base motor sürücü | Mevcut çift yönlü PWM sürücü yapısı; pinler `MOTOR_L_IN1/IN2`, `MOTOR_R_IN1/IN2`. |
| Fork/lift motor sürücü | BTS7960 |
| IMU | BNO085, SPI bağlantı |
| Encoder | Sol/sağ teker quadrature encoder |
| Limit switch | Fork üst/alt NC limit switch, `INPUT_PULLUP` ile okunur |

## 4. Pin Layout

Pinler `arduino/src/config/config_pins.h` dosyasından alınmıştır.

| Pin | GPIO | Kullanım | Açıklama |
| --- | --- | --- | --- |
| `D12` | `GPIO10` | `ENC_L_A` | Sol encoder channel A |
| `D0` | `GPIO1` | `ENC_L_B` | Sol encoder channel B |
| `D13` | `GPIO3` | `ENC_R_A` | Sağ encoder channel A |
| `D14` | `GPIO8` | `ENC_R_B` | Sağ encoder channel B |
| `A3` | Kart pinout'a göre | `MOTOR_L_IN1` | Sol base motor PWM hattı |
| `A2` | Kart pinout'a göre | `MOTOR_L_IN2` | Sol base motor PWM hattı |
| `A0` | Kart pinout'a göre | `MOTOR_R_IN1` | Sağ base motor PWM hattı |
| `A1` | Kart pinout'a göre | `MOTOR_R_IN2` | Sağ base motor PWM hattı |
| `D4` | `GPIO42` | `IMU_CS` | BNO085 SPI chip select |
| `D1` | `GPIO2` | `IMU_INT` | BNO085 data ready interrupt |
| `D8` | `GPIO38` | `IMU_RST` | BNO085 reset |
| `A5` | `GPIO16` | `FORK_RPWM` | BTS7960 RPWM |
| `A4` | `GPIO15` | `FORK_LPWM` | BTS7960 LPWM |
| `D10` | `GPIO47` | `FORK_R_EN` | BTS7960 R_EN |
| `D11` | `GPIO21` | `FORK_L_EN` | BTS7960 L_EN |
| `A6` | `GPIO17` | `FORK_LIMIT_TOP` | Üst NC limit switch |
| `A7` | `GPIO18` | `FORK_LIMIT_BOT` | Alt NC limit switch |

Önemli notlar:

- `D0`, `D1`, `D12`, `D13` encoder/IMU tarafından kullanıldığı için fork için kullanılmaz.
- Fork pinleri çakışmayı önlemek için `A4/A5`, `D10/D11`, `A6/A7` olarak seçilmiştir.
- `D10/D11` normalde SDA/SCL olarak da kullanılabilir; ileride I2C kullanılacaksa pin planı tekrar kontrol edilmelidir.
- Fork limit switchler NC + `INPUT_PULLUP` mantığıyla okunur.
- NC switchte basılı değilken `LOW`, basılınca `HIGH` okunur.
- Serial baudrate: `230400`.

## 5. Fork / Lift Donanım Bağlantısı

### BTS7960

| Deneyap Kart 1A v2 | BTS7960 | Açıklama |
| --- | --- | --- |
| `A5 / GPIO16` | `RPWM` | Fork motor PWM hattı |
| `A4 / GPIO15` | `LPWM` | Fork motor PWM hattı |
| `D10 / GPIO47` | `R_EN` | Enable |
| `D11 / GPIO21` | `L_EN` | Enable |
| `5V` | `VCC` | Logic besleme |
| `GND` | `GND` | Ortak ground |

Gerçek donanımda fork yönü ters çıkarsa sadece [fork_motor.cpp](/Users/murat/develop/hamal_agv/arduino/src/motor/fork_motor.cpp) içinde `RPWM/LPWM` kullanımı terslenmelidir.

### Limit Switch

Üst limit switch:

- `COM -> GND`
- `NC -> A6 / GPIO17`
- `NO -> boş`

Alt limit switch:

- `COM -> GND`
- `NC -> A7 / GPIO18`
- `NO -> boş`

NC + `INPUT_PULLUP` okuma:

```cpp
upper_limit = digitalRead(FORK_LIMIT_TOP) == HIGH;
lower_limit = digitalRead(FORK_LIMIT_BOT) == HIGH;
```

Switch basılı değilken NC kapalı olduğu için pin GND'ye çekilir ve `LOW` okunur. Switch basılınca NC açılır, internal pull-up nedeniyle `HIGH` okunur. Kablo koparsa `HIGH` okunması fail-safe kabul edilir.

## 6. Serial Protocol

Frame formatı:

```text
$PAYLOAD*CS\n
```

Checksum:

- Payload üzerinde XOR checksum hesaplanır.
- `$`, `*` ve `\n` checksum'a dahil edilmez.
- Checksum 2 haneli uppercase HEX formatındadır.

Örnek:

```text
$FORK,UP*CS
```

ROS -> MCU:

| Frame | Açıklama |
| --- | --- |
| `$CMD,v,w*CS` | Base hız komutu. `v` linear hız, `w` angular hız. |
| `$FORK,UP*CS` | Fork yukarı komutu. |
| `$FORK,DOWN*CS` | Fork aşağı komutu. |
| `$FORK,STOP*CS` | Fork motor stop komutu. |

MCU -> ROS:

| Frame | Açıklama |
| --- | --- |
| `$ENC,t_us,dl,dr*CS` | Encoder delta tick telemetry. |
| `$IMU,t_us,gz,ax,ay,az*CS` | IMU telemetry. |
| `$FORK_STATE,t_us,state,upper,lower,error*CS` | Fork state telemetry. |

Mevcut firmware ana loop'u `$ODOM,...` frame'i yayınlamaz. `odometry/` altında helper sınıf vardır; ROS tarafında odometry üretimi ayrı paket sorumluluğudur.

## 7. Fork State Machine

State enumları:

| State | Değer |
| --- | ---: |
| `IDLE` | `0` |
| `MOVING_UP` | `1` |
| `MOVING_DOWN` | `2` |
| `AT_TOP` | `3` |
| `AT_BOTTOM` | `4` |
| `ERROR` | `5` |

Error enumları:

| Error | Değer |
| --- | ---: |
| `ERROR_NONE` | `0` |
| `ERROR_INVALID_COMMAND` | `1` |
| `ERROR_TOP_TIMEOUT` | `2` |
| `ERROR_BOTTOM_TIMEOUT` | `3` |
| `ERROR_LIMIT_CONFLICT` | `4` |
| `ERROR_MCU_TIMEOUT` | `5` |

`FORK,UP` davranışı:

- Sistem `ERROR` durumundaysa `UP` reddedilir.
- Üst ve alt limit aynı anda aktifse motor durur, `ERROR_LIMIT_CONFLICT` üretilir.
- Üst limit aktifse motor sürülmez, `AT_TOP` state'i gönderilir.
- Aksi halde motor yukarı sürülür, `MOVING_UP` state'i gönderilir.

`FORK,DOWN` davranışı:

- Sistem `ERROR` durumundaysa `DOWN` reddedilir.
- Üst ve alt limit aynı anda aktifse motor durur, `ERROR_LIMIT_CONFLICT` üretilir.
- Alt limit aktifse motor sürülmez, `AT_BOTTOM` state'i gönderilir.
- Aksi halde motor aşağı sürülür, `MOVING_DOWN` state'i gönderilir.

`FORK,STOP` davranışı:

- `STOP` her zaman kabul edilir.
- Motor durur.
- State `IDLE` olur.
- Error `ERROR_NONE` olur.

Loop içi güvenlik:

- `MOVING_UP` sırasında üst limit gelirse motor durur, state `AT_TOP` olur.
- `MOVING_DOWN` sırasında alt limit gelirse motor durur, state `AT_BOTTOM` olur.
- İki limit aynı anda aktifse motor durur, error `ERROR_LIMIT_CONFLICT` olur.
- Max hareket süresi aşılırsa motor durur, `ERROR_TOP_TIMEOUT` veya `ERROR_BOTTOM_TIMEOUT` üretilir.
- Hareket sırasında komut watchdog süresi aşılırsa motor durur, `ERROR_MCU_TIMEOUT` üretilir.

## 8. Güvenlik Kuralları

- Checksum doğrulanmadan hiçbir `FORK` komutu uygulanmaz.
- `ERROR` durumunda sadece `STOP` kabul edilir.
- `ERROR` durumunda `UP/DOWN` reddedilir.
- Upper limit aktifken `UP` uygulanmaz.
- Lower limit aktifken `DOWN` uygulanmaz.
- Limit conflict durumunda motor her zaman durur.
- Komut watchdog hareket sırasında motoru güvenli durdurur.
- Max motion timeout switch arızasına karşı ikinci güvenlik katmanıdır.
- Firmware loop içinde blocking `delay()` kullanmamalıdır.
- Fork safety MCU tarafında uygulanır; ROS tarafına güvenilmez.

## 9. Fork Config

Fork konfigürasyonu [fork_config.h](/Users/murat/develop/hamal_agv/arduino/src/config/fork_config.h) içindedir. Pinler [config_pins.h](/Users/murat/develop/hamal_agv/arduino/src/config/config_pins.h) makrolarından alınır.

| Parametre | Değer | Açıklama |
| --- | ---: | --- |
| `FORK_PWM` | `180` | BTS7960 PWM komut değeri. |
| `FORK_STATE_PERIOD_MS` | `100` | `FORK_STATE` publish periyodu, 10 Hz. |
| `FORK_CMD_TIMEOUT_MS` | `1000` | Hareket sırasında yeni fork komutu gelmezse fail-safe timeout. |
| `FORK_MAX_UP_TIME_MS` | `8000` | Yukarı hareket için max süre. |
| `FORK_MAX_DOWN_TIME_MS` | `8000` | Aşağı hareket için max süre. |
| `LIMIT_DEBOUNCE_COUNT` | `3` | Limit switch için ardışık doğrulama sayısı. |

`FORK_MAX_UP_TIME_MS` ve `FORK_MAX_DOWN_TIME_MS` gerçek donanımda ölçülerek kalibre edilmelidir. Çok düşük değer yanlış timeout'a, çok yüksek değer geç fail-safe'e neden olur.

## 10. Firmware Çalıştırma / Derleme

Deneyap Kart 1A v2 board package kurulu olmalıdır.

Genel Arduino CLI formatı:

```bash
arduino-cli compile --fqbn <DENEYAP_KART_1A_V2_FQBN> <sketch_path>
```

Bu projede kullanılan FQBN:

```text
deneyap:esp32:dydk1a_mpv20
```

Repo klasörü `arduino/`, ana sketch dosyası `hamals_firmware.ino` olduğu için Arduino CLI doğrudan `arduino/` klasörünü hedeflediğinde `arduino.ino` arayabilir. Bu durumda geçici sketch klasörüyle compile yapılabilir:

```bash
mkdir -p /tmp/hamals_firmware
cp arduino/hamals_firmware.ino /tmp/hamals_firmware/hamals_firmware.ino
cp -R arduino/src /tmp/hamals_firmware/src
arduino-cli compile --fqbn deneyap:esp32:dydk1a_mpv20 /tmp/hamals_firmware
```

Gerekirse BNO085 kütüphanesi için yerel Arduino libraries path'i `--libraries` ile verilebilir.

## 11. Test Senaryoları

Serial frame testleri checksum'lu tam frame olarak gönderilmelidir. Aşağıdaki örneklerde `CS`, payload XOR checksum değeridir.

### STOP

```text
$FORK,STOP*CS
```

Beklenen:

- Motor durur.
- State `IDLE`.
- Error `ERROR_NONE`.

### UP

```text
$FORK,UP*CS
```

Beklenen:

- Üst limit aktif değilse motor yukarı döner.
- State `MOVING_UP`.
- Üst limit aktif olunca motor durur ve `AT_TOP` gönderilir.

### DOWN

```text
$FORK,DOWN*CS
```

Beklenen:

- Alt limit aktif değilse motor aşağı döner.
- State `MOVING_DOWN`.
- Alt limit aktif olunca motor durur ve `AT_BOTTOM` gönderilir.

### Invalid Command

```text
$FORK,LEFT*CS
```

Beklenen:

- Motor durur.
- State `ERROR`.
- Error `ERROR_INVALID_COMMAND`.

### Checksum Hatalı Frame

- Komut uygulanmaz.
- Motor hareket etmez.
- Mevcut state bozulmaz.

### Limit Conflict

Üst ve alt limit aynı anda aktifse:

- Motor durur.
- State `ERROR`.
- Error `ERROR_LIMIT_CONFLICT`.

### Watchdog

`MOVING_UP` veya `MOVING_DOWN` sırasında yeni komut gelmezse:

- Motor durur.
- Error `ERROR_MCU_TIMEOUT`.

### Max Motion Timeout

Switch tetiklenmezse:

- Motor durur.
- `ERROR_TOP_TIMEOUT` veya `ERROR_BOTTOM_TIMEOUT` üretilir.

### ERROR Durumunda UP/DOWN

`ERROR` durumundayken `UP/DOWN` gönderilirse:

- Motor çalışmaz.
- State `ERROR` kalır.
- Mevcut error korunur.

### ERROR Durumunda STOP

`ERROR` durumundayken `STOP` gönderilirse:

- Motor durur.
- State `IDLE`.
- Error `ERROR_NONE`.

## 12. ROS ile Entegrasyon

ROS tarafındaki paketler:

- `hamals_serial_bridge`: `$FORK,...` frame gönderir, `$FORK_STATE,...` frame parse eder.
- `hamals_fork`: `/fork/cmd` alır, `/mcu/fork_cmd` gönderir, `/mcu/fork_state` dinler, `/fork/state` yayınlar.

Akış:

```text
/fork/cmd
  ↓
hamals_fork
  ↓
/mcu/fork_cmd
  ↓
hamals_serial_bridge
  ↓
$FORK,UP*CS
  ↓
MCU firmware
  ↓
$FORK_STATE,...
  ↓
hamals_serial_bridge
  ↓
/mcu/fork_state
  ↓
hamals_fork
  ↓
/fork/state
```

## 13. Kapsam Dışı

- Firmware ROS node çalıştırmaz.
- Firmware `/fork/cmd` topic'ini doğrudan bilmez.
- Firmware sadece serial frame alır/gönderir.
- Fork görev planlaması firmware'de yapılmaz.
- Palet alma/bırakma gibi görevler ROS mission layer sorumluluğudur.

## 14. Bilinen Notlar / Dikkat Edilecekler

- `D10/D11` I2C pinleri fork enable için kullanılıyor; ileride I2C cihaz eklenecekse pin planı tekrar yapılmalı.
- Fork motor yönü ters çıkarsa [fork_motor.cpp](/Users/murat/develop/hamal_agv/arduino/src/motor/fork_motor.cpp) içinde `RPWM/LPWM` yönleri terslenmelidir.
- Limit switch mekanik montajı gerçek testte doğrulanmalıdır.
- Limit switch debounce değeri gerçek donanımda gerekirse artırılmalıdır.
- `FORK_PWM` gerçek motor/güç durumuna göre kalibre edilmelidir.
- Max motion timeout değerleri gerçek hareket süresine göre ölçülmelidir.
