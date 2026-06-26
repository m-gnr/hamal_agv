# HAMAL’S Firmware

> Diferansiyel sürüşlü mobil robot için gerçek zamanlı mikrodenetleyici kontrol katmanı
> 

hamals_firmware, HAMALS robotunun mikrodenetleyici tarafındaki düşük seviye kontrol yazılımıdır.
Encoder, IMU, kinematik, odometri, PID ve watchdog güvenlik mekanizmalarını içerir.

Bu katman:

- ROS 2’den bağımsızdır
- Deterministic kontrol döngüsü ile çalışır
- Framed + checksum’s seri protokol üzerinden haberleşir
- Güvenlik öncelikli tasarlanmıştır

## Sistem Rolü

Firmware aşağıdaki sorumluluklara sahiptir.

- Quadrature encoder ISR
- IMU polling (BNO085, SPI)
- Diferansiyel sürüş kinematiği
- IMU destekli 2D odometri
- Wheel speed PID kontrol
- Anti-windup + ramp limit
- Watchdog state machine
- Framed + checksum’lu seri haberleşme

## Mimari

```
                       ┌──────────────────────────────┐
                       │          ROS 2 Layer         │
                       │  Nav2 | EKF | Teleop | RViz  │
                       └───────────────┬──────────────┘
                                       │
                                       ▼
                       ┌──────────────────────────────┐
                       │     hamals_serial_bridge     │
                       │  Framed + Checksum Protocol  │
                       └───────────────┬──────────────┘
                                       │  Serial (UART)
                                       ▼
        ===============================================================
                                FIRMWARE
        ===============================================================

                       ┌──────────────────────────────┐
                       │        Serial RX (CMD)       │
                       └───────────────┬──────────────┘
                                       ▼
                       ┌──────────────────────────────┐
                       │          Watchdog            │
                       │     OK / GRACE / TIMEOUT    │
                       └───────────────┬──────────────┘
                                       ▼
                       ┌──────────────────────────────┐
                       │        VelocityCmd Filter    │
                       │  Clamp + Accel Limit + Slew  │
                       └───────────────┬──────────────┘
                                       ▼
                       ┌──────────────────────────────┐
                       │            Encoders          │
                       │     Quadrature ISR Delta     │
                       └───────────────┬──────────────┘
                                       ▼
                       ┌──────────────────────────────┐
                       │          Kinematics          │
                       │   Pulse → rad → v / w       │
                       └───────────────┬──────────────┘
                                       ▼
                       ┌──────────────────────────────┐
                       │              IMU             │
                       │      Absolute Yaw (rad)      │
                       └───────────────┬──────────────┘
                                       ▼
                       ┌──────────────────────────────┐
                       │           Odometry           │
                       │     IMU-assisted 2D pose     │
                       └───────────────┬──────────────┘
                                       ▼
                       ┌──────────────────────────────┐
                       │         Wheel PID (L/R)      │
                       │  Anti-windup + Ramp Limit    │
                       └───────────────┬──────────────┘
                                       ▼
                       ┌──────────────────────────────┐
                       │            Motor PWM         │
                       │        20 kHz Drive Output   │
                       └───────────────┬──────────────┘
                                       ▼
                       ┌──────────────────────────────┐
                       │         Serial TX (ODOM)     │
                       │   Framed + Checksum Packet   │
                       └──────────────────────────────┘
```

## Kontrol Döngüsü

Firmware sabit frekanslı scheduler ile çalışır.

constexpr float CONTROL_DT_S = 0.01f;   // 100 Hz

Delay kullanılmaz.

### Control Loop Timeline
```
|<------------- 10 ms (100 Hz) ------------->|

[Serial RX] 
      ↓
[Watchdog]
      ↓
[IMU Update]
      ↓
[Encoder Read]
      ↓
[Kinematics]
      ↓
[Odometry Integration]
      ↓
[Wheel PID (L/R)]
      ↓
[Motor PWM Update]
      ↓
[Serial TX (ODOM)]

## Watchdog (Fail-Safe)

Watchdog bir state machine olarak tasarlanmıştır.
```
```
OK      → Komut geliyor
GRACE   → Komut gecikti (soft stop)
TIMEOUT → Komut yok (hard stop)
```

TIMEOUT durumunda:

- VelocityCmd reset
- PID reset
- Motor stop
- PWM çıkışı sıfırlanır

Bu sayede:

- WiFi kopması
- ROS çökmesi
- Serial kopması

durumunda robot runaway olmaz.

## Dosya Yapısı

```
firmware/
├── hamals_firmware.ino   ← setup() + loop() (orkestrasyon)
│
├── config/
│   ├── config_pins.h
│   └── config_robot.h
│
├── encoder/
├── imu/
├── kinematics/
├── odometry/
├── control/
├── motor/
├── safety/
├── timing/
├── comm/
└── debug/
```

## Modül Sorumlulukları

### Encoder

- ISR tabanlı pulse sayımı
- readDelta() diferansiyel ölçüm
- Interrupt-safe erişim

### IMU (BNO085)

- SPI pooling
- GAME_ROTATION_VECTOR kullanımı
- Startup yaw zero
- Yaw rate hesaplama

Yaw wrap normalize edilir:

```
[-π , +π]
```

### Kinematics

- Pulse → wheel rad
- rad → rad/s
- Wheel linear speed
- Robot v ve w hesaplama

### Odometry (IMU Assisted)

```
x += v * cos(yaw) * dt
y += v * sin(yaw) * dt
yaw = IMU yaw
```

Wheel yaw kullanılmaz

Heading referansı IMU’dur

### VelocityCmd

- Robot-level clamp
- Wheel-level clamp
- Acceleration limit
- Config-driven motion limits

Bu katman ani hız sıçramalarını engeller

### WheelPID

- Derivative on measurement
- Anti-windup
- Output clamp
- Ramp limiter

Akış:

```
error → integral → derivative
↓
anti-windup
↓
clamp
↓
slew limit
```

PID çıkışı:

```
PWM ∈ [-255 , +255]
```

### Motor

- 20 kHz PWM
- Dual channel
- Direction + magnitude
- Saturation protection

### Serial Protocol

ROS → MCU

```
$CMD,0.200,0.000*5A
```

MCU → ROS

```
$ODOM,1.23,0.45,0.12,0.20,0.00*3F
```

- Framed ($)
- Checksum (*XX)
- Invalid frame discard
- Line realignment
- Parser istatistikleri

## Config Driven Tasarım

Tüm sistem compile-time config ile yönetilir.

### **config_pins.h**

- Encoder pinleri
- Motor pinleri
- IMU pinleri
- Serial baudrate

### **config_robot.h**

- Wheel radius
- Track width
- Encoder CPR
- Gear ratio
- PID gains
- Motion limits
- Control frequency
- Yaw correction parametreleri

Bu yapı:

- Tüm fiziksel parametreler merkezi konfigürasyondadır
- Robot değiştiğinde sadece config güncellenir

## Güvenlik Garantileri

Firmware aşağıdaki durumlarda güvenli davranır:

- Serial veri gelmez → watchdog
- PID saturation → anti-windup
- Hız sıçraması → acceleration limit
- PWM overflow → clamp
- ISR race → atomic read

## Ekosistem

Bu firmware, ROS 2 tarafında çalışan 
[**hamals_serial_bridge**](https://github.com/m-gnr/hamals_serial_bridge)
paketi ile entegre şekilde tasarlanmıştır.
