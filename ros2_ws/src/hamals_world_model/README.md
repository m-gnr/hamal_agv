# hamals_world_model

`hamals_world_model`, robotun çalıştığı sahanın statik ve semantik bilgisinin tek kaynağıdır. İstasyon geometrileri, yaklaşma/hedef/çıkış pozları, QR eşleşmeleri, kapılar ve yüklü-yüksüz rota grafiği bu pakete aittir. Mission paketi koordinat saklamaz; ihtiyaç duyduğu saha bilgisini bu paketin tipli servislerinden alır.

## Sorumluluk sınırı

Bu paket:

- YAML saha profilini yükler ve başlangıçta doğrular.
- İstasyon ve kapı bilgilerini servislerle sunar.
- Yük durumuna uygun semantik rota hesaplar.
- Aktif profil ve config checksum bilgisini yayınlar.

Bu paket görev sırasına, PLC register'larına, Nav2 hareketine veya görüntü işlemeye karar vermez. Yüklenen model çalışma süresince değişmez; saha değişikliği için config güncellenip node yeniden başlatılır.

## Config yapısı

```text
config/
├── fields/
│   └── industrial_field.yaml
└── profiles/
    ├── competition.yaml
    └── simulation.yaml
```

`industrial_field.yaml` metre cinsinden `map` frame koordinatlarını, istasyon polygonlarını, pozları, QR kimliklerini, rota düğüm/kenarlarını ve kapı bekleme pozlarını içerir. Profil dosyaları kullanılacak saha dosyasını seçer.

Başlangıç doğrulaması şu hatalarda node'u fail-fast durdurur:

- Eksik veya geçersiz şema sürümü.
- Üçten az köşeli istasyon polygonu.
- Polygon dışında kalan hedef pozu.
- Tanımsız QR veya yaklaşma düğümü.
- Tanımsız düğüme bağlanan rota kenarı.
- Geçersiz yük modu.
- Pickup/dropoff istasyonları arasında bulunamayan rota.
- Eksik veya hatalı kapı düğümü/bekleme pozu.

Depodaki metrik değerler başlangıç modelidir. Fiziksel testten önce ölçülmüş saha ve harita koordinatlarıyla kalibre edilmelidir.

## ROS arayüzleri

| Tür | Ad | Arayüz | Açıklama |
|---|---|---|---|
| Topic | `/world_model/state` | `hamals_interfaces/msg/WorldModelState` | Latched profil, istasyon listesi ve checksum. |
| Service | `/world_model/get_station` | `hamals_interfaces/srv/GetStation` | İstasyon geometrisi ve docking bağlarını döndürür. |
| Service | `/world_model/get_door` | `hamals_interfaces/srv/GetDoor` | Kapı düğümleri ve bekleme pozlarını döndürür. |
| Service | `/world_model/plan_route` | `hamals_interfaces/srv/PlanSemanticRoute` | Yüklü/yüksüz semantik rota üretir. |

## Çalıştırma

Normal kullanımda node yalnızca `hamals_bringup` tarafından başlatılır. Tek başına geliştirme için:

```bash
source ros2_ws/install/setup.bash
ros2 run hamals_world_model world_model_node --ros-args \
  -p profile:=$(ros2 pkg prefix hamals_world_model)/share/hamals_world_model/config/profiles/competition.yaml
```

Servis örneği:

```bash
ros2 service call /world_model/get_station \
  hamals_interfaces/srv/GetStation "{station_id: A1}"
```

## Test

```bash
cd ros2_ws
colcon test --packages-select hamals_world_model
colcon test-result --verbose
```

Model testleri bütün pickup/dropoff kombinasyonlarının rota üretmesini ve hatalı saha verisinin reddedilmesini doğrular.
