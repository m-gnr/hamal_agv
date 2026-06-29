# hamals_ui

TEKNOFEST 2026 Sanayide Robotik Uygulamalar — HAMALS AGV jüri web arayüzü.

**Mimari:**  
`Vue 3 SPA` ↔ `ws://robot:9090` (rosbridge) ↔ `ui_bridge_node` ↔ ROS 2 topic'leri  
Kamera: `<img>` ← `web_video_server` MJPEG (ayrı HTTP)

## Build (ROS paketi)

```bash
# Workspace root'undan:
cbuild   # alias → colcon build --symlink-install
# veya:
cd ~/ros2_ws && colcon build --packages-select hamals_ui --symlink-install
```

## Mock ile çalıştırma (robot gerekmez)

```bash
cd ros2_ws/src/hamals_ui/web
npm install
npm run dev        # → http://localhost:5173
```

`web/.env` dosyasında `VITE_DATA_SOURCE=mock` olduğunda rosbridge'e gerek yoktur.  
Mock senaryosu (scenario.yaml) FSM adımlarını otomatik oynatır.

## Canlı robot ile çalıştırma

```bash
# 1. Web'i build et
cd ros2_ws/src/hamals_ui/web
npm install && npm run build   # → web/dist/

# 2. ROS paketini build et
cd ~/ros2_ws && colcon build --packages-select hamals_ui

# 3. Launch
source install/setup.bash
ros2 launch hamals_ui ui.launch.py mode:=live

# Tarayıcıda: http://robot:8080
```

Live mod için `web/.env` dosyasında:
```
VITE_DATA_SOURCE=rosbridge
VITE_ROSBRIDGE_URL=ws://robot:9090
```

## Config nasıl düzenlenir

| Dosya | Açıklama |
|---|---|
| `config/params.yaml` | Mod (live/mock), portlar, toleranslar |
| `config/bridge.yaml` | ROS topic → `/ui/state` alan eşlemesi |
| `config/panels.yaml` | Sekme ve panel tanımları |
| `config/topology.yaml` | Yarışma alanı topoloji grafiği |
| `config/scenario.yaml` | Mock senaryo adımları |

### Yeni ROS topic eklemek (live mod)

`config/bridge.yaml`'a yeni bir `sources:` girdisi ekleyin:

```yaml
- topic: /my/topic
  type: std_msgs/Float32
  qos: best_effort
  fields:
    - { msg_field: "data", state_key: "my.value", default: 0.0 }
```

Python'a dokunmadan `/ui/state`'e yansır.

### Sekme eklemek / çıkarmak

`config/panels.yaml` → `tabs:` listesine ekle / sil.  
Yeni `type:` için `web/src/components/` altına bileşen eklenmelidir.

## Sekme özeti

| # | Sekme | İçerik |
|---|---|---|
| 1 | Genel Durum | FSM rozeti, konum, mini harita, QR, PLC, sensörler, güvenlik, batarya |
| 2 | Harita & Rota | Büyük topoloji haritası, rota bilgisi, harita kontrolleri |
| 3 | Görev & PLC | FSM adım şeridi, PLC detayı, mesaj geçmişi |
| 4 | Manuel Kontrol | D-pad + hız, kaldır/indir, kamera — **anahtar AUTO'yken kilitli** |
| 5 | Kamera & Çizgi | MJPEG kamera akışı, çizgi takip, QR bilgisi |
| 6 | Hata & Güvenlik | LiDAR bölge radarı, hata listesi, kayıtlar + dışa aktar |
| 7 | Ayarlar | Toleranslar (RO), ağ, sensör durumu, mod bilgisi |
