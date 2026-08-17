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
