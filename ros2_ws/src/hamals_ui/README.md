# hamals_ui

Vue 3 SPA ↔ rosbridge `/ui/state` + `/ui/cmd` ↔ `ui_bridge_node` ↔ mevcut ROS 2 arayüzleri.
Kamera ayrı `web_video_server` MJPEG bağlantısı kullanır.

## Canlı çalıştırma

Frontend değişkenleri **build zamanında** uygulanır. Varsayılan veri kaynağı `rosbridge`;
varsayılan WebSocket adresi sayfanın host'u üzerinde `ws://<host>:9090`.

```bash
cd ros2_ws/src/hamals_ui/web
npm install
VITE_DATA_SOURCE=rosbridge npm run build
cd ../../..
colcon build --packages-select hamals_ui --symlink-install
source install/setup.bash
ros2 launch hamals_ui ui.launch.py mode:=live
```

Ekran: `http://<robot>:8080`. Robot node'ları ayrıca başlatılmalıdır.
Farklı host için build sırasında `VITE_ROSBRIDGE_URL` ve isteğe bağlı
`VITE_VIDEO_BASE_URL=http://<video-host>:8081` verilebilir.

Kamera: `http://<host>:8081/stream?type=mjpeg&topic=/camera/image_raw`.
Topic/host `config/params.yaml` içinden gelir. Launch `vvs_port` argümanı hem
web_video_server'a hem UI köprüsüne uygulanır. `web_video_server` yoksa görüntü unavailable kalır.
Kamera sekmesindeki “Kamera Değiştir” butonu canlı modda rosbridge üzerinden
doğrudan `/fork/is_up` (`std_msgs/Bool`) yayınlar; terminaldeki topic komutuyla
aynı yolu kullanır. `false` ön, `true` arka kamerayı seçer. Tarayıcı aynı topic'i
dinleyerek seçimi güncel tutar; mock modunda seçim yalnızca yerel state'i değiştirir.

## Mock / live ayrımı

```bash
cd ros2_ws/src/hamals_ui/web
VITE_DATA_SOURCE=mock npm run dev
```

Frontend demo: `useMockData.js` (port 5174), ROS bağlantısı ve robot komutu yok.
Backend demo ayrıca `ros2 launch hamals_ui ui.launch.py mode:=mock` ile
`config/scenario.yaml` oynatır. Canlı frontend, `meta.mode != live` olan backend
snapshots'larını reddeder. Backend demo canlı frontend için fallback değildir.

## Canlı state sözleşmesi

Mapping: `config/bridge.yaml`. Ortak frontend semantiği: `liveState.js`.
Canlı ekran: `LivePanel.vue`; eski demo panelleri yalnız frontend mock modunda açılır.

- `null` / eksik alan = unknown; pil = unavailable / N/A.
- `meta.ts`: köprünün snapshot zamanı (Unix saniye).
- `meta.sources[topic].age_s`: son gerçek mesajın monotonik alım yaşı; hiç mesaj yoksa null.
- Tarayıcı kendi snapshot alım yaşını ekler. Global timeout 2 s, mode timeout 1 s,
  diğer kaynaklar 3 s. Yeni aggregate mesajı, eski ROS kaynağını tazelemez.
- Disconnect ve stale durumunda eski telemetri aktif değer olarak gösterilmez.
  Yeniden bağlantı yeni subscription açar ve yeni state bekler.
- `safety.obstacle_active` boolean; `obstacle.regions` gerçek bölge/boolean/mesafe.
  Her panel aynı safety özetini kullanır. Eksik/stale veri sağlıklı kabul edilmez.
- `mission.state`, ham `phase`, `phase_normalized`, lowercase `fsm` ve `elapsed_s`
  korunur. `nav.status` mission phase bilgisidir; Nav2 action feedback olduğu iddia edilmez.
- `plc.connection_state`: 0 disconnected, 1 connecting, 2 connected, 3 error;
  bilinmeyen enum null bağlantıdır. Runtime transport/IP/port, config'teki
  `network.parameter_node` üzerinden ROS GetParameters ile okunur; unavailable ise tahmin edilmez.
  Repo competition config'i UDP `10.100.68.144:1515`; runtime mock seçilmişse ekranda mock yazar.
- Fork yüzde yüksekliği yoktur; state, limitler, moving, last_command, error_code gösterilir.
- QR `/qr/detection` kaybolunca eski payload temizlenir. Çizgi `/line/detected`
  ve `/line/error` (Int32, piksel) kullanır. Desteklenmeyen offset üretilmez.
- Topoloji YAML'i şematik piksel düzenidir; world model `map` koordinatlarıyla aynı değildir.
  `/odom` frame bilgisi ve sayısal pose gösterilir; grafiğe robot marker/aktif yol çizilmez.
  Kullanılmayan `useLiveTopics.js` TF/map kodu bu nedenle etkinleştirilmedi.

## Komutlar ve güvenlik sınırı

- Manual: `/ui/cmd` teleop → `/cmd_vel/manual_teleop` (`geometry_msgs/Twist`).
  Tarayıcı ve köprü yalnız taze fiziksel `manual` modunda kabul eder; AUTO/unknown/stale
  modda **sıfır Twist dahil** yayın yapılmaz. Komut, son köprü snapshot timestamp'ini taşır;
  750 ms'den eski komut reddedilir. Hız sınırları: 0.5 m/s, 1 rad/s.
- D-pad basılı tutunca 10 Hz gönderir; bırakma, pointerup/cancel/leave, blur, hidden,
  sekmeden çıkma ve unmount stream'i keser ve geçerli MANUAL modunda zero dener.
  Disconnect sonrası otomatik hareket devam etmez. Kapalı sokette stop teslimi garanti değildir;
  mevcut serial/MCU deadman ve mode routing değiştirilmedi.
- Fork: `/fork/cmd`, `ForkCommand` STOP=0 / UP=1 / DOWN=2. Mevcut fork/MCU
  kontrolleri korunur; feedback `/fork/state`. Komut kabulü hareket tamamlandı anlamına gelmez.
- Mission start: `/mission/execute`, `ExecuteMission`, `task_id/pickup_id/dropoff_id` gerekli.
  Pause: `/mission/pause`, `PauseMission.reason`; resume: `/mission/resume`,
  `ResumeMission.operator_id`. Cancel yalnız bu bridge'in sahip olduğu action goal handle'ı ile.
  Servis/action yanıtları `command_result` alanına yazılır; mission telemetry yerel değiştirilmez.
- Web E-STOP **kontrol değildir**. `/estop` ve `/safety/state` sadece status kaynaklarıdır.
  Kritik mevcut sorun: `arduino/arduino.ino` E-STOP feedback'ini sabit `false` gönderiyor.
  UI fiziksel E-STOP yerine geçmez; firmware bu değişiklikte düzenlenmedi.

## Doğrulama

```bash
npm test
npm run build
python3 -m pytest ../test/test_live_bridge.py -q
```

Frontend testleri state, transport/reconnect, hold-to-run ve gerçek Vue render'larını;
Python testleri gerçek köprü metotlarını stub ROS transport ile sınar. Robot üzerinde ROS
integration / fiziksel hareket testi bunların yerine geçmez. Paket ament testleri ROS ortamı gerektirir.
MJPEG hata ve ROS kamera kaynağı timeout'u gösterilir; tarayıcının `<img>` arayüzü HTTP
akışındaki her frame için timestamp sağlamaz, ayrı HTTP akış donması donanımla doğrulanmalıdır.
