# hamals_plc_bridge

`hamals_plc_bridge`, dış PLC protokolü ile ROS 2 görev sistemi arasındaki tek adaptör sınırıdır. Mission paketi register, soket veya üretici protokolü bilmez; yalnızca tipli görev ve kapı olaylarını kullanır.

Mevcut sürüm mock-first çalışır. Resmî saha protokolü netleşene kadar görev üretimi ve kapı izni testlerini deterministik biçimde simüle eder.

## Sorumluluk sınırı

Bu paket:

- PLC'den gelen alma/bırakma isteğini `MissionTask` mesajına çevirir.
- Mission'ın kapıya varış olayını PLC tarafına aktarır.
- Kapı geçiş iznini `DoorEvent` olarak yayınlar.
- Bağlantı ve son haberleşme özetini `PlcState` ile yayınlar.
- Mock modda elle görev başlatma servisi sunar.

Görev akışını, rota hesabını, navigasyonu ve safety kararını yönetmez.

## ROS arayüzleri

| Yön | Tür | Ad | Arayüz |
|---|---|---|---|
| Çıkış | Topic | `/plc/mission_task` | `hamals_interfaces/msg/MissionTask` |
| Çıkış | Topic | `/plc/state` | `hamals_interfaces/msg/PlcState` |
| Çıkış | Topic | `/plc/door_event` | `hamals_interfaces/msg/DoorEvent` |
| Giriş | Topic | `/mission/door_event` | `hamals_interfaces/msg/DoorEvent` |
| Giriş/çıkış | Service | `/plc/mock/submit_task` | `std_srvs/srv/Trigger` |

## Config profilleri

```text
config/
├── mock.yaml
└── competition.yaml
```

`mock.yaml`; pickup/dropoff kimliklerini ve otomatik kapı iznini belirler. `competition.yaml` gerçek transport sınırını temsil eder fakat protokol adaptörü henüz uygulanmadığı için node bunu açıkça `ERROR` durumuyla raporlar; sessizce mock'a düşmez.

## Mock kullanım

Sistem başlatıldıktan sonra:

```bash
ros2 service call /plc/mock/submit_task std_srvs/srv/Trigger '{}'
```

Varsayılan görev `A1 → B1`'dir. Farklı bir kombinasyon için node parametreleri veya `mock.yaml` değiştirilir.

Tek başına çalıştırma:

```bash
source ros2_ws/install/setup.bash
ros2 run hamals_plc_bridge plc_bridge_node --ros-args \
  --params-file ros2_ws/src/hamals_plc_bridge/config/mock.yaml
```

## Gerçek PLC adaptörü için sözleşme

Gerçek transport eklendiğinde yalnız bu paketin içi değişmelidir. Adaptör en az şu olayları tipli ROS verisine çevirmelidir:

- Bağlantı/heartbeat durumu.
- Görev kimliği ile pickup/dropoff istasyonları.
- Görev alındısı ve tamamlanma bildirimi.
- Kapıya varış, izin ve geçiş olayları.
- Teslim bildirimi ve protokol hata kodları.

PLC adresleri ve register eşlemeleri bu paketin config'i dışında hiçbir pakete yayılmamalıdır.
