# hamals_safety

`hamals_safety`, mission'dan bağımsız hareket izni üreten fail-safe güvenlik yöneticisidir. E-stop, fiziksel auto/manual anahtarı ve lidar engel durumunu tek bir tipli duruma toplar; hareket yasaklandığında `twist_mux` kilidini aktif eder.

## Sorumluluk sınırı

Bu paket:

- E-stop ve çalışma modu girişlerini izler.
- Lidar bölgesel engel durumunu izler.
- Engel kalkışında debounce uygular.
- Lidar heartbeat'i geciktiğinde fail-safe kilit üretir.
- UI ve mission için gerekçeli `SafetyState` yayınlar.
- Bütün hız kaynaklarını kesen `/safety/lock` çıkışını sürer.

Mission'ın hangi fazda olduğunu veya robotun nereye gideceğini bilmez. Fiziksel E-stop'un donanımsal enerji kesme zincirinin yerine geçmez; ROS kilidi ek bir yazılım güvenlik katmanıdır.

## ROS arayüzleri

| Yön | Ad | Arayüz | Kaynak/hedef |
|---|---|---|---|
| Giriş | `/estop` | `std_msgs/msg/Bool` | `hamals_serial_bridge` / MCU |
| Giriş | `/switch/mode` | `std_msgs/msg/String` | `hamals_serial_bridge` / MCU |
| Giriş | `/scan/obstacle_state` | `hamals_interfaces/msg/ObstacleState` | `hamals_lidar_toolbox` |
| Çıkış | `/safety/state` | `hamals_interfaces/msg/SafetyState` | mission ve UI |
| Çıkış | `/safety/lock` | `std_msgs/msg/Bool` | `twist_mux` lock |

Safety durumları `SAFE`, `OBSTACLE`, `MANUAL`, `ESTOP` ve `SENSOR_STALE` enumlarıyla taşınır. Yalnız `SAFE` durumunda `motion_allowed=true` olur.

## Config

[`config/safety.yaml`](config/safety.yaml) şu parametreleri içerir:

- `obstacle_clear_sec`: engel temizlendikten sonra beklenecek debounce süresi.
- `obstacle_stale_sec`: obstacle mesajının bayat sayılacağı süre.
- `require_obstacle_heartbeat`: lidar heartbeat'inin zorunlu olup olmadığı.
- `initial_mode`: başlangıç auto/manual varsayımı.

Competition profilinde obstacle heartbeat zorunludur. Processor başlamaz veya mesaj kesilirse sistem hareketi kilitler.

## Hız yetkilendirme zinciri

```text
/cmd_vel/nav ──────┐
/cmd_vel/docking ──┼──> twist_mux ──> /cmd_vel ──> serial bridge
/cmd_vel/manual ───┘        ▲
                            │
                     /safety/lock
```

Mux öncelikleri: manual `100`, docking `50`, navigation `10`; safety lock `255` önceliğindedir.

## Çalıştırma

Normal kullanımda `hamals_bringup` başlatır. Tek başına:

```bash
source ros2_ws/install/setup.bash
ros2 run hamals_safety safety_node --ros-args \
  --params-file ros2_ws/src/hamals_safety/config/safety.yaml
```

## Sahaya çıkmadan önce

- MCU'nun fiziksel E-stop ve auto/manual anahtarını güvenilir biçimde yayınladığını doğrulayın.
- E-stop'un ROS'tan bağımsız donanımsal enerji kesmesini doğrulayın.
- Lidar processor durduğunda `SENSOR_STALE` ve mux lock oluştuğunu test edin.
- Auto'ya dönüşte mission'ın operatör `resume` komutu beklediğini doğrulayın.
- Düşük hızda bütün engel bölgeleri ve debounce sürelerini kalibre edin.
