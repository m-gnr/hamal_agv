# hamals_plc_bridge

`hamals_plc_bridge`, dış PLC protokolü ile ROS 2 görev sistemi arasındaki tek adaptör sınırıdır. Mission paketi register, soket veya üretici protokolü bilmez; yalnızca tipli görev ve kapı olaylarını kullanır.

UDP yarışma profili `config/competition.yaml` ile çalışır. Mock transport ayrı bir test seçeneğidir.

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
| Çıkış | Service çağrısı | `/mission/plc_pause` | `std_srvs/srv/Trigger` |
| Çıkış | Service çağrısı | `/mission/plc_resume` | `std_srvs/srv/Trigger` |

UDP RX tam üç byte olmalıdır: pickup (1–3), dropoff (1–3), control (1 WAIT, 2 START/CONTINUE). Yalnız `plc_ip` adresinden gelen geçerli paketler bağlantı zamanını yeniler; kaynak portu doğrulanmaz. IDLE durumunda WAIT görevi pending tutar; START görevi bir kez yayınlar. Aktif görevde WAIT PLC pause servisini, CONTINUE PLC resume servisini çağırır. Kapı beklemesinde CONTINUE yalnız kapı izni verir. Tekrarlanan paketler yeni görev veya tekrarlanan pause isteği üretmez. TX `<BBBhh` formatında, yarışma profilinde 1 Hz devam eder; `PAUSED_PLC` ve kapı `WAITING_PLC` durumu status 5'tir.

## Config profilleri

```text
config/
└── competition.yaml
```

`competition.yaml` UDP transportu, PLC adresini ve 1 Hz TX hızını tanımlar. Mock transport parametreleri test ortamında ayrıca verilebilir.

## Mock kullanım

Sistem başlatıldıktan sonra:

```bash
ros2 service call /plc/mock/submit_task std_srvs/srv/Trigger '{}'
```

Varsayılan görev `A1 → B1`'dir. Farklı bir kombinasyon için `mock_pickup` ve `mock_dropoff` node parametreleri verilir.

Tek başına çalıştırma:

```bash
source ros2_ws/install/setup.bash
ros2 run hamals_plc_bridge plc_bridge_node --ros-args \
  -p transport:=mock -p mock_pickup:=A1 -p mock_dropoff:=B1
```

## Adaptör sınırı

PLC transportuna özgü değişiklikler yalnız bu paketin içinde kalmalıdır. Adaptör şu olayları tipli ROS verisine çevirir:

- Bağlantı/heartbeat durumu.
- Görev kimliği ile pickup/dropoff istasyonları.
- Görev alındısı ve tamamlanma bildirimi.
- Kapıya varış, izin ve geçiş olayları.
- Teslim bildirimi ve protokol hata kodları.

PLC adresleri ve register eşlemeleri bu paketin config'i dışında hiçbir pakete yayılmamalıdır.
