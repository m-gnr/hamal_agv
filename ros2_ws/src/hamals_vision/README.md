# hamals_vision — birleşik görüş düğümü

Panelin `KAMERA_ARAYUZ.md` şartnamesine **birebir uyar**. Web tarafında
hiçbir değişiklik gerekmez.

---

## 1. Neden yavaştı

| Sorun | Ölçü |
|---|---|
| Kamera 1280x720 **ham** `Image` yayınlıyordu | kare başına 2,76 MB |
| Aynı kareye **3 node** abone (`line`, `qr`, `stream`) | 3× serileştirme, 3× decode |
| QoS `depth=5` | 5 karelik kuyruk → görüntü geç geliyor |
| `line_node` tam kareyi işleyip **tek satır** kullanıyordu | 921.600 pikselin 1280'i |
| `qr_node` pyzbar'a 720p verip **tüm barkod tiplerini** aratıyordu | — |
| `stream_node` çizimi tam çözünürlükte yapıp sonra küçültüyordu | ~10× fazla iş |
| `AfMode: 2` (sürekli otofokus) + otomatik pozlama | hareket halinde bulanık kare → QR okunmuyor |

Sonuç: ölçülen **3.8 Hz**.

## 2. Bu paket ne yapıyor

* **Tek process.** Kare bir kez alınır, DDS'ten hiç geçmez. Üç düğümün
  ağ/serileştirme maliyeti tamamen ortadan kalkar.
* **640x480**, panelin beklediği çözünürlük. Kare 2,76 MB → 0,92 MB.
* **`lores`/YUV420 akışı**: gri görüntü Y düzleminden bedava gelir,
  `cvtColor(BGR2GRAY)` tamamen kalkar.
* **QoS depth=1**, best effort → her zaman en son kare, kuyruk yok.
* **Çizgi**: sadece ROI bandı, 320 px'e indirilmiş. Tek satır yerine bandın
  sütun profili; en uzun geçerli blok + önceki merkeze yakınlık kriteri.
* **QR: ayrı iplik.** Çözme 80 ms sürse bile çizgi takibi beklemez.
  `pyzbar` sadece `QRCODE` arar.
* **Çizim küçük kare üzerinde**, JPEG **ayrı ve daha düşük hızda** yayınlanır —
  ağ yükü kontrol döngüsünü sınırlamaz.
* **Sabit kısa pozlama + manuel odak** → hareket bulanıklığı yok, QR okunur.

Ölçülen (aynı sentetik kare, aynı makine):

```
yeni yöntem (ROI + 320px):  0.39 ms/kare
eski yöntem (640x480):      1.02 ms/kare   (2.6x)
eski yöntem (1280x720):     2.23 ms/kare   (5.7x)

Kenarda gölge varken merkez:  eski = 210 px,  yeni = 400 px  (gerçek 400)
```

---

## 3. Kurulum (Pi tarafında)

```bash
# 1) paketi workspace'e koy
cp -r hamals_vision ~/ros2_ws/src/

# 2) bağımlılıklar
sudo apt install python3-pyzbar python3-opencv python3-numpy
#    picamera2 zaten sistemde olmalı (apt: python3-picamera2)

# 3) derle
cd ~/ros2_ws
colcon build --packages-select hamals_vision --symlink-install
source install/setup.bash

# 4) çalıştır
ros2 launch hamals_vision vision.launch.py
```

> **Eski düğümleri kapat.** `camera_node`, `line_node`, `qr_node`,
> `stream_node` artık çalışmamalı — aynı konuya iki yayıncı olursa panel
> karışır ve bant genişliği yine dolar.

Docker içinde çalışıyorsan `picamera2` container'da yoksa
`video_device: 0` yapıp V4L2 üzerinden de açabilirsin (biraz daha yavaş).

## 4. Doğrulama

```bash
ros2 topic hz /camera/image_raw/compressed    # ~12 Hz
ros2 topic hz /line/error                     # ~25-30 Hz  (kontrol hızı)
ros2 topic echo /line/overlay --once
ros2 topic echo /qr/text --once
ros2 topic info /line/overlay                 # TEK tip: std_msgs/msg/String
```

Düğüm 5 saniyede bir şunu basar:

```
kare 28.4 Hz | kare başı 4.1 ms | QR çözme 31.2 ms | cizgi=True qr=False
```

---

## 5. ÖNEMLİ — `line_gain` iki katına çıkmalı

`/line/error` artık **640x480** uzayında (şartnamenin istediği gibi).
Eskiden 1280x720 uzayındaydı, yani **aynı sapma yarı sayı** olarak geliyor.

`mission.launch.py` içinde:

```
line_gain:  0.0025  →  0.005
```

Yapmazsan robot çizgiye yarı güçle tepki verir, yalpalar ve virajı keser.

## 6. Sahada ayar sırası

1. **Odak.** `lens_position` değerini oynat, `/camera/image_raw/compressed`'i
   panelde izle. QR net görünene kadar. (1/metre: 4.5 ≈ 22 cm, 2.0 ≈ 50 cm)
2. **Pozlama.** Robot hareket ederken QR kenarları eriyorsa
   `exposure_time_us` düşür (6000 → 4000), karşılığında `analogue_gain`
   yükselt (6.0 → 9.0).
3. **Çizgi eşiği.** Zemin parlak/yansımalıysa `line_auto_threshold: true`
   (Otsu) kalsın. Çizgi ile zemin arasında kontrast düşükse
   `false` yapıp `line_threshold`'u elle bul.
4. **ROI.** Kamera arkada olduğu için robot ileri giderken çizgi geç
   görünür. `line_roi_top`/`line_roi_bottom` ile bandı kaydır.
5. **Genişlik filtresi.** Paletin ayağı çizgi sanılıyorsa
   `line_max_width_px` düşür.
6. **Hız.** QR artık okunuyorsa `mission.launch.py` içindeki
   `qr_search_speed` 0.04'ten 0.08-0.10'a çıkarılabilir.

## 7. Panel tarafında iki küçük ayar (isteğe bağlı)

`config/dashboard.yaml`:

```yaml
stream_fps: 8        # 5 idi — kamera penceresi daha akıcı görünür
```

`stream_fps` hem harita çizim hızını hem web akış hızını belirliyor;
Orin'i zorlarsa 5'te bırak.
