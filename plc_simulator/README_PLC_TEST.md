# HAMAL terminal PLC simülatörü

Kullanıcının paylaştığı TEKNOFEST Ek Teknik Şartnamesi protokol özetini taklit
eder. Orijinal PDF bu çalışma kapsamında sağlanmadığından doğrulama paylaşılan
byte tablosuna göredir. Python 3.8+ standart kütüphanesi yeterlidir; ROS ve GUI yoktur.

## Çalıştırma

Proje kökünden, laboratuvarda:

```bash
python3 plc_simulator/plc_simulator.py --bind-ip 10.100.68.144 --port 1515
```

Yarışmada:

```bash
python3 plc_simulator/plc_simulator.py --bind-ip 192.168.100.100 --port 1515
```

Bind IP simülatör bilgisayarının bir ağ arayüzüne atanmış olmalıdır. Yarışma
robot IP'si `192.168.100.10`, gateway `192.168.100.1` olarak belirtilmiştir;
program ağ ayarlarını değiştirmez. UDP 1515 erişilebilir olmalıdır.
Varsayılan bind `0.0.0.0`, port `1515`; eski `--host` adı alias olarak korunur.
Bridge yalnız `plc_ip` ile aynı **kaynak IP** üzerinden gelen cevapları kabul
eder. Bu yüzden açık arayüz IP'sine bind etmek tercih edilir; `0.0.0.0` ile
kaynak IP yönlendirmeye bağlıdır. Verilen `competition.yaml` şu anda
`plc_ip: 10.100.68.144` kullanır: simülatör **10.100.68.144:1515** üzerinde
çalışmalıdır. Yarışma için bridge `plc_ip` değerini de `192.168.100.100` yapın.

Robot üzerinde, ROS çalışma alanı derlenip source edildikten sonra:

```bash
ros2 run hamals_plc_bridge plc_bridge_node --ros-args \
  -p transport:=udp -p plc_ip:=10.100.68.144 -p plc_port:=1515 \
  -p tx_rate_hz:=1.0 -p rx_timeout_sec:=1.0 \
  -p pose_topic:=/odom -p door_id:=MAIN_DOOR
```

## Terminal

Komutları harf + Enter ile verin. Başlangıç rastgele görev ve WAIT'tir.

| Komut | Etki |
|---|---|
| `x` | Rastgele A1–A3 → B1–B3 seçer; control WAIT (1) olur |
| `s` | START/CONTINUE (2) |
| `w` | WAIT (1) |
| `q` | Kapatır |

Yeni rastgele seçim öncekiyle aynı olabilir. Ctrl+C ve stdin EOF da kapatır.
Eski AUTO, `--manual`, `--pickup`, `--dropoff`, `--loop`, `--door-delay`
seçenekleri kaldırılmıştır; otomatik görev/kapı kontrolü yapılmaz.
Stdin ayrı daemon thread'dedir; görev/control kilit altında güncellenir.
UDP döngüsü cevap ve log için tek tutarlı görev snapshot'ı alır.

## Protokol ve watchdog

- Robot → PLC PAKET_TX **7 byte**: `<BBBhh`; durum, pickup, dropoff,
  signed little-endian X ve Y. Koordinatlar `int(metre * 100)`; decode `/100`.
- PLC → robot PAKET_RX **3 byte**: pickup, dropoff, control; kontrol **Byte2**.
  `[2, 3, 1]` = A2 → B3 WAIT, `[2, 3, 2]` = START.
- Tam 7 byte gelen her paket decode edilir ve geldiği IP/**source port**
  adresine aynı soketten cevaplanır. Robot için sabit port varsayılmaz.
  Görev kullanıcı değiştirene kadar her cevapta korunur.
- Farklı uzunluk loglanır; cevap verilmez ve watchdog yenilenmez. TX'teki
  bilinmeyen durum `UNKNOWN`, istasyon `0` ise `0` olarak gösterilir;
  uzunluk dışında TX değerleri reddedilmez. RX daima geçerli 1–3/1–2 üretir.
- İlk geçerli pakete kadar watchdog susar. `time.monotonic()` ile son geçerli
  paketten **> 1.0 s** sonra tek LOST logu; sonraki geçerli pakette RESTORED.
  UDP socket timeout'u 50 ms olduğundan tespit ilk uygun döngüde yapılır
  (normalde yaklaşık 50 ms ek gecikme; işletim sistemi/log yükü artırabilir).
  Ek tolerans eklenmez. Gelen paketten önce de süre kontrol edilir: 1 Hz
  jitter, LOST/RESTORED çiftine neden olabilir. Geçersiz trafik kontrolü engellemez.

## Mevcut bridge incelemesi

İncelenen paket: `ros2_ws/src/hamals_plc_bridge`; özellikle
`hamals_plc_bridge/plc_bridge_node.py`, config, README ve protokol testleri.

1. `transport=udp` `_start_udp()` çağırır; AF_INET/SOCK_DGRAM soketi,
   ayrı TX/RX daemon thread'leri açılır. Açık local bind yoktur; kaynak IP/portu
   işletim sistemi seçer. TX `plc_ip:plc_port` hedefine gider.
2. `_tx_loop()` ilk paketi hemen gönderir, sonra ayarlı periyodun kalanını
   uyur. `tx_rate_hz=1.0` hedefi 1 Hz'dir, gerçek zaman garantisi değildir.
3. `_build_tx()` tam `<BBBhh` / 7 byte üretir. `/odom` X/Y metre değerleri
   `int(value * 100)` ile sıfıra doğru kesilir, int16 sınırlarına kırpılır.
4. `_handle_rx()` önce kaynak IP'yi `plc_ip` ile karşılaştırır (kaynak portunu
   kontrol etmez), sonra tam 3 byte, pickup/dropoff 1–3 ve control 1/2 arar.
   Tek byte alanlarda endian farkı yoktur; control `data[2]`'dir.
5. Yalnız geçerli RX `_last_valid_rx` zamanını yeniler. Yaş `<= rx_timeout_sec`
   ise CONNECTED; ilk RX öncesi ve timeout'ta ERROR. `/plc/state` 0.5 s
   aralıklarla yayınlanır. Socket timeout ayrıca `last_rx` metnini günceller.
6. IDLE + WAIT görevi pending tutar. IDLE + START `plc-NNNN` kimliğiyle
   `/plc/mission_task` yayınlar; önceden WAIT zorunlu değildir. RX'teki
   istasyonlar pending'den farklıysa yeni RX değerleri kullanılır.
7. `active_task_id` yayın sonrası gecikmiş IDLE güncellemelerine karşı duplicate
   oluşumunu engeller. Çalışan görevde tekrar START yeni görev oluşturmaz.
   Ancak non-IDLE sonrası IDLE'a dönünce koruma temizlenir: sürekli START
   **aynı görevi tekrar başlatır**. `_last_plc_task` kalıcı dedup yapmaz.
8. Çalışma/manual pause/obstacle pause sırasında WAIT `/mission/plc_pause`,
   PAUSED_PLC veya pause isteği sonrası START `/mission/plc_resume` çağırır.
   İstek bayrakları tekrarı sınırlar; servis yoksa sonraki pakette yeniden denenir.
   Kapı bekleme önceliklidir: START kapı izni verir, WAIT izin vermez.

### Uyumluluk sınırları / mevcut riskler

Byte düzeni, signed little-endian koordinatlar, 7/3 byte boyları, kontrol Byte2,
1 Hz hedefi ve 1 s timeout verilen özetle uyumludur. Şu sınırlamalar vardır:

- Görev yokken bridge pickup/dropoff **0** gönderir; paylaşılan tablonun 1–3
  aralığı dışındadır. Simülatör bunu görünür biçimde decode eder.
- İnt16 dışındaki koordinatlar bridge'de kırpılır; bu davranış verilen özette
  tanımlanmamıştır. Laboratuvar YAML'i yarışma IP'sinden bilinçli olarak farklıdır.
- Gerçek `mission_server` entry point'i `hamals_mission.mission_node:main`.
  Bu dosyada `/mission/plc_pause` ve `/mission/plc_resume` servisleri **yok**;
  yalnız `yedek_mission.py` içinde var. Bridge çağrıları mevcut olsa da çalışan
  mission ile WAIT → pause / START → resume uçtan uca mevcut değildir.
  `w` komutunu fiziksel durdurma güvencesi olarak kullanmayın.
- Sürekli START görev bitiminden sonra tekrar görev üretir. Simülatör istek
  gereği duruma göre otomatik WAIT'e geçmez; operatör control değerini yönetir.
- Bridge 1 Hz TX ve 1 s RX timeout aynı sınırdadır. Scheduler/network jitter,
  socket RX ve state timer sıralaması geçici ERROR üretebilir. Timeout yalnız
  bağlantı durumunu bildirir; `_handle_rx()` kontrolünü otomatik WAIT yapmaz.
- Status 5 hem kapı hem PLC pause için kullanılır; her status 5 kapı demek
  değildir. Status 6 eşlemesi phase içindeki COMPLETE/REPORT metnine bağlıdır;
  byte uyumu gerçek rota/faz davranışının doğrulanması anlamına gelmez.

Bridge, mission, safety, LiDAR, docking ve fork kodları değiştirilmedi.

## Test

Proje kökünden, ROS ve ek Python paketi olmadan:

```bash
python3 -m unittest discover -s plc_simulator -v
```

8 test: örnek byte dizisi, negatif koordinatlar/int16 sınırı, durum açıklamaları,
6/8 byte ret, WAIT/START cevapları, rastgele görev/reset/komutlar,
localhost gerçek UDP cevap/tekrar/invalid cevap yok ve watchdog sınırı/restore.
Gerçek robot/ROS entegrasyonu bu testlerin kapsamında değildir.
