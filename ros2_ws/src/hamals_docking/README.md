# hamals_docking

`hamals_docking`, Nav2'nin istasyon yaklaşma pozunda bıraktığı robotu QR ve çizgi algısıyla hassas alma/bırakma konumuna taşır. Paket, sınırları belirli bir `Dock` action sunar ve yalnızca kendi mux girişine hız komutu gönderir.

## Sorumluluk sınırı

Bu paket:

- Beklenen QR kimliğini doğrular.
- Çizgi hatasını açısal hıza dönüştürür.
- Odometriyle kat edilen docking mesafesini izler.
- QR doğrulama, çizgi kaybı, timeout ve iptal durumlarında güvenli şekilde durur.
- Sonucu tipli `Dock.action` ile mission'a bildirir.

İstasyon koordinatlarının, görev sırasının, fork hareketinin ve genel güvenlik kararının sahibi değildir. Nihai `/cmd_vel` yetkisi `twist_mux` ve `hamals_safety` zincirindedir.

## ROS arayüzleri

| Yön | Tür | Ad | Arayüz |
|---|---|---|---|
| Giriş | Topic | `/qr/detection` | `hamals_interfaces/msg/QrDetection` |
| Giriş | Topic | `/line/detected` | `std_msgs/msg/Bool` |
| Giriş | Topic | `/line/error` | `std_msgs/msg/Int32` |
| Giriş | Topic | `/odom` | `nav_msgs/msg/Odometry` |
| Giriş/çıkış | Action | `/dock` | `hamals_interfaces/action/Dock` |
| Çıkış | Topic | `/cmd_vel/docking` | `geometry_msgs/msg/Twist` |

Dock goal; istasyon kimliği, `pickup`/`dropoff` işlemi, beklenen QR ve docking profilini taşır. Action feedback, QR doğrulamasını, çizgi görünürlüğünü ve ilerlenen mesafeyi verir.

## Config

[`config/docking_profiles.yaml`](config/docking_profiles.yaml) şu çalışma parametrelerini içerir:

- İleri hız ve çizgi kontrol kazancı.
- Maksimum dönüş hızı.
- Pickup/dropoff ilerleme mesafesi.
- Genel timeout ve çizgi kaybı toleransı.
- Desteklenen profil adları.

Bu değerler düşük hızlı saha testiyle kalibre edilmelidir. Profil adları world model içindeki istasyonların `docking_profile` alanıyla eşleşmelidir.

## Çalıştırma

Normal kullanımda `hamals_bringup` başlatır. Tek başına:

```bash
source ros2_ws/install/setup.bash
ros2 run hamals_docking docking_node --ros-args \
  --params-file ros2_ws/src/hamals_docking/config/docking_profiles.yaml
```

Mission dışından örnek goal:

```bash
ros2 action send_goal /dock hamals_interfaces/action/Dock \
  "{station_id: A1, operation: pickup, expected_qr: q2, profile: pickup_default}" \
  --feedback
```

## Güvenli davranış

- Beklenen QR görülmeden hareket başlamaz.
- Odometri yoksa goal abort edilir.
- Çizgi izin verilen süreden uzun kaybolursa sıfır hız yayınlanır ve goal abort edilir.
- İptal ve timeout sonunda sıfır hız yayınlanır.
- Safety lock aktifken `twist_mux`, bu paketin hızını `/cmd_vel` çıkışına geçirmez.

## Dropoff sonrası düz geri çıkış

Mevcut mission sırası korunur: `dropoff` action (geri çizgi takibi ve
180° dönüş) → `LOWER_LOAD` (`ForkState.AT_BOTTOM` doğrulanır) →
`dropoff_escape` action → kamera/kapı/navigation adımları.
Dönüş mevcut sistemde yük indirilmeden öncedir; yeni escape bu dönüşün arasına
veya yük indirmeden önce eklenmez. `Dock.action` şeması değişmez;
`operation=dropoff_escape` yalnız yükün bırakılması doğrulandıktan sonra çağrılır.

`dropoff_escape.enabled`, `distance_m`, `speed_mps`, `timeout_sec` parametreleri
varsayılan olarak `true`, `0.50`, `0.08`, `8.0` değerlerini alır. Devre dışıyken
yeni action hareket veya maske etkinleştirmeden başarılı döner.
Mesafe başlangıç odom x/y konumundan Öklid uzaklığıdır. Komut yalnız
`linear.x=-abs(speed_mps)`, `angular.z=0` içerir; çizgi takibi kullanılmaz.

`/docking/dropoff_escape_active` (`std_msgs/Bool`) başlangıçta false yayınlanır;
escape döngüsü çalışırken yaklaşık 20 Hz true yenilenir. Her çıkışta önce sıfır
hız, ardından false yayınlanır. İptal, odom yokluğu/bayatlığı, timeout, exception
ve shutdown başarısızlıkla sonlanır. Mission beklemesi iptal/hata alırsa aktif
Dock goal iptal edilir. İşlem çökerse veya true mesajları kesilirse scan processor
steady-clock ile `fork_mask.dropoff_escape_timeout` (1 saniye) sonra override'ı
kaldırır; yeni scan normal switch davranışıyla değerlendirilir. ROS iletişimi
kapanmışsa son false teslimi garanti edilemez; bu durumda da süre sınırı geçerlidir.

Bu depodaki normal fork mask, `/mcu/fork_state` üzerinden front bölgesinin
**tamamını** dışlar; bu mevcut davranış değiştirilmedi. Escape ek maskesi ise
`fork_mask.min=2.941592653589793`, `max=-2.941592653589793` ile yalnız fork yönünde
±π çevresindeki ±0.20 rad aralığını dışlar. `min > max` açı sarmalamasını ifade
eder. Maske dışındaki front beam'leri ve diğer bölgelerin danger-distance
hesapları korunur. `fork_mask.enabled=false` her iki maskeyi de kapatır.

Bırakılan yük mission readiness'i OBSTACLE durumunda tutabilir. Yalnız escape
maskesini kuracak action'ın gönderilmesine bu durumda izin verilir; estop,
sensor-stale ve manuel beklemeler korunur. Safety node ve twist-mux kilitleri
her hız komutunu denetlemeye devam eder. Maskenin dışındaki engeller hareketi
engellerse escape zaman aşımıyla durur; navigation'a geçilmez.
