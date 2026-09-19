# PLC YARIŞMA HAZIRLIK RAPORU

## Düzeltme sonrası durum — 19 Eylül 2026

Aşağıdaki ilk denetim tarihsel kayıttır; bu bölüm düzeltme sonrası durumu özetler.

- **WAIT/RESUME düzeltildi:** aktif mission, bridge ile aynı `std_srvs/srv/Trigger`
  tipinde `/mission/plc_pause` ve `/mission/plc_resume` server'ları sunuyor.
  PLC hold ayrı tutuluyor; PLC START manuel/engel/estop nedenlerini kaldırmıyor.
  Mevcut operatör servislerinin isim ve tipleri korunuyor. Servis çağrıları
  bridge'de sıralanıyor; resume sonrası bayraklar manuel hold sürse de temizleniyor.
- **Hareketin durması:** Nav2 goal iptali ve terminal sonuç bekleniyor; devamda
  aynı mutlak hedef yeniden gönderiliyor, retry harcanmıyor. Mission'ın doğrudan
  hız ve fork döngüleri PLC hold'u izliyor. Fork'un komut sonrası yeni/taze
  geri bildirim şartı korunuyor. Docking, `/mission/state` hold durumunu izleyip
  aynı action içinde duruyor; mesafe/açı baştan başlatılmıyor. İlerleme sürelerinden
  bekleme çıkarılıyor; mesafe/açı integrasyonuna beklenen süre eklenmiyor.
- **Duplicate düzeltildi:** ilk görevde doğrudan START desteği korunuyor. Kabul
  edilen görevden sonra IDLE'da yeni, aynı istasyon çiftine ait WAIT→START
  görülmeden başka görev kabul edilmiyor. Çalışma sırasında gelen WAIT, sonraki
  görevi hazırlamıyor. Aynı A/B yeni handshake ile yeniden kabul ediliyor.
- **Status düzeltildi:** VALIDATE_TASK ve fork işleme fazları=2, normal hareket=3/4,
  WAITING_PLC/PAUSED_PLC=5, dönüş=6, ERROR=7, ESTOP=8. MissionContext ve
  MissionState içindeki `returning_home` bayrağı teslimattan IDLE'a kadar taşınıyor;
  dönüş faz adları veya alt dizeleri tahmin edilmiyor. Dönüşte PLC bekleme, hata
  ve estop önceliği korunuyor. Mission exception yolu ESTOP'u ERROR ile ezmiyor.
- **İlk START teslim riski azaltıldı:** mission state görülüp task subscriber
  keşfedilmeden START tüketilmiyor; sonraki PLC START yanıtıyla tekrar deneniyor.
  Bu, mission tarafından alınma/başarılı icra için ayrıca bir ACK protokolü değildir.
- Yarışma YAML'ı bu düzeltmede değiştirilmedi; önceki kullanıcı değişikliği aynen
  korundu. NaN/Inf TX koruması korundu; simulator değiştirilmedi.

**Test:** ilgili bridge/mission/docking ROS'suz testleri **99 PASS**;
ROS Trigger servis smoke testi **1 SKIP** (`rclpy` bu bilgisayarda yok).
Simulator **8 PASS**. Python syntax ve `git diff --check` **PASS**.
Gerçek robot veya organizasyon PLC'siyle fiziksel durma/devam doğrulanmadı.
Eski duplicate testi hatalı tekrarı bekliyordu; yeni handshake beklentisine
çevrildi. Docking'in eski iptal/yeniden başlatma beklentisi, ilerleme koruma
beklentisine çevrildi; Nav2 iptal onayı ayrıca test ediliyor. Fork fixture'ı
üretimdeki taze geri bildirim sözleşmesine uyarlandı; freshness testleri korunuyor.

**Dağıtım:** `MissionState.msg` değişti. Robot ve bu mesajı kullanan diğer ROS
makinelerinde aynı kaynak sürümünden workspace'i yeniden derleyip bütün ilgili
node'ları yeniden başlatın. Eski/yeni message tanımlarını aynı graph'ta karıştırmayın.
Önceki checklist'in yalnız bridge build adımı bu düzeltme için yeterli değildir:

```bash
# Robotun ros2_ws dizininde, kurulu ROS environment source edildikten sonra:
colcon build --symlink-install
source install/setup.bash
```

**Kalan yarışma riskleri:** resmi PLC'nin IDLE istasyon `0,0` kabulü ve yeni görev
WAIT→START döngüsü sahada doğrulanmalı. 1 Hz/1 s jitter ve timeout'ta otomatik
mission hold olmaması değişmedi. Dedup bellektedir; bridge yeniden başlatılırsa
kilit sıfırlanır. Fiziksel ESTOP'un IDLE'da daima TX=8 olması ve çok kısa
ERROR/COMPLETE durumlarının 1 Hz TX tarafından görülmesi garanti edilmez.
Gerçek UDP/DDS/action gecikmeleri ve fiziksel durma mesafesi robotta test edilmeli.

## İlk denetim — düzeltme öncesi tarihsel bulgular

Tarih: 19 Eylül 2026. Kapsam: mevcut çalışma ağacındaki kaynak kod, launch/YAML,
ROS gerektirmeyen üretim-metodu testleri ve yerel UDP socket testleri.
Referans: kullanıcının aktardığı TEKNOFEST ek teknik şartname protokolü.
Orijinal şartname dosyası depoda bulunmadı; aktarılmayan alanlar varsayılmadı.
Robot Ubuntu'su ve organizasyon PLC Simulator'ü bu denetimde erişilebilir değildi.

**Karar: Yarışmaya tam hazır onayı verilemez. Paket biçimleri doğru; çalışan
görevde PLC WAIT/RESUME yolu aktif mission uygulamasında eksik.**

| Alan | Sonuç | Gerekçe |
|---|---|---|
| NETWORK | WARNING | Kaynak YAML doğru; robot IP/route, kurulu overlay ve organizasyon PLC'si doğrulanamadı. |
| TX PROTOCOL | PASS | 7 byte `<BBBhh`, cm dönüşümü, little-endian ve negatif değerler doğrulandı; IDLE istasyonları ayrı risk. |
| RX PROTOCOL | PASS | Tam 3 byte, istasyon/control aralığı ve kaynak IP doğrulaması var. |
| STATUS MAPPING | FAIL | İşleme fazı 2 yerine 3; dönüş boyunca 6 korunmuyor. |
| MISSION START | WARNING | Topic/type ve callback yolu doğru; gerçek ROS teslimi test edilemedi, başlangıç teslim garantisi yok. |
| WAIT/RESUME | FAIL | Aktif mission server'da PLC servisleri ve hold mekanizması yok. |
| DUPLICATE TASK PROTECTION | FAIL | Görev sürerken koruma var; IDLE'a dönünce aynı START yeni görev başlatıyor. |
| TIMEOUT | WARNING | 1 Hz ve 1 s eşik uygulanıyor; jitter payı yok, otomatik mission hold yok. |
| LOCAL SIMULATOR | WARNING | 8/8 test geçti; TX alanlarını doğrulamadığından resmi PLC kabulünü kanıtlamaz. |

## CRITICAL ISSUES

1. **CRITICAL — PLC WAIT çalışan robotu durdurmuyor.** Bridge
   `std_srvs/srv/Trigger` ile `/mission/plc_pause` ve `/mission/plc_resume`
   client'larını oluşturuyor. Aktif `mission_node.py` yalnız
   `/mission/pause` (`hamals_interfaces/srv/PauseMission`) ve
   `/mission/resume` (`hamals_interfaces/srv/ResumeMission`) server'larını
   oluşturuyor. İsimler ve tipler farklı; basit remap çözüm değildir.
   `setup.py` içindeki `mission_server = hamals_mission.mission_node:main`
   nedeniyle PLC servislerini içeren `yedek_mission.py` çalıştırılmıyor.
   WAIT'te bridge servis yok uyarısı verip pause bayrağını sıfırlıyor; sonraki
   WAIT yine dener. Gerçek durdurma ve START ile devam bu yoldan gerçekleşmez.
   Kapıdaki WAIT/START izni ayrı akıştır ve genel pause desteği anlamına gelmez.
   Mission/navigation/docking/fork refactor'ı veya yedek dosya değişimi yapılmadı.

2. **HIGH PRIORITY — Görev bitince aynı START tekrar görev oluşturuyor.**
   Çalışma sırasında `active_task_id` ve mission state korur. İlk non-IDLE
   sonrası IDLE callback'i kimliği temizler; sonraki aynı START yeni
   `plc-0002` üretir. `_last_plc_task` atanıyor fakat tekrar engellemede
   kullanılmıyor. Mevcut `test_pending_start_duplicate_and_repeat` testi
   tam olarak ikinci görevin oluşturulmasını bekliyor ve geçiyor.
   Hata sonrası IDLE'a dönüşte de tekrar mümkün. Gerçek PLC tamamlanınca
   WAIT'e dönüyorsa risk azalır; aynı START'ı tutuyorsa tekrar kesindir.
   Yeni görev için açık bir WAIT→START çevrimiyle yeniden izin verme önerisi,
   organizasyonun yaşam döngüsü doğrulandıktan sonra uygulanmalı. Sürekli
   istasyon çifti engeli aynı rotadaki meşru sonraki görevleri de engeller.

3. **HIGH PRIORITY — İlk görev yayınında teslim riski.** Bridge başlangıçta
   kendisini IDLE kabul ediyor. Mission subscriber keşfedilmeden gelen START
   tek sefer yayınlanıp `active_task_id` doldurulur. Publisher varsayılan
   volatile durability kullanıyor; geç katılan subscriber'a geçmiş mesaj
   garantisi yok. Mission hiç non-IDLE olmazsa kimlik temizlenmez, tekrarlanan
   START da yayınlanmaz. Koddan görülen risk; gerçek ROS ile yeniden üretilmedi.
   Sahada mission subscriber ve ilk `/mission/state` görülmeden START verilmemeli.

4. **HIGH PRIORITY — Bağlantıyı kesen NaN/Inf TX hatası düzeltildi.**
   `int(x * 100)` NaN'da ValueError, Inf'te OverflowError üretiyordu;
   yalnız OSError yakalayan TX thread kalıcı ölüyordu. Minimal değişiklikle
   iki exception yakalanıyor, uyarı yazılıyor ve o çevrim atlanıyor. Sonraki
   geçerli koordinatta TX kendiliğinden devam ediyor. Sürekli bozuk odometri
   hâlâ paket gönderimini ve bağlantıyı engeller; sahte koordinat üretilmiyor.
   NaN, ±Inf ve çarpımda taşan çok büyük finite değer için toparlanma testleri geçti.

## Network ve config

Yarışmada kullanılacak kaynak dosya:
`ros2_ws/src/hamals_plc_bridge/config/competition.yaml`.

```yaml
hamals_plc_bridge:
  ros__parameters:
    transport: udp
    plc_ip: 192.168.100.100
    plc_port: 1515
    tx_rate_hz: 1.0
    rx_timeout_sec: 1.0
    pose_topic: /odom
    door_id: MAIN_DOOR
```

- `competition.launch.py` varsayılan `plc_config` için paketin **install/share**
  dizinindeki `config/competition.yaml` dosyasını seçiyor. Node adı ve YAML
  kökü aynı: `hamals_plc_bridge`; namespace yok, bridge için ikinci parametre
  dosyası yok. `setup.py` YAML'ı install ediyor.
- `plc_config:=...` launch argümanı dosyayı değiştirebilir. Depoda ek otomatik
  override bulunmadı; robotta farklı overlay/önceden kurulmuş dosya olabilir.
- `172.20.10.4` çalışma ağacında yalnız config yorumu ve test girdisi; aktif
  PLC değeri değil. **HEAD sürümünde eski IP hâlâ aktif**, doğru IP kullanıcının
  önceden mevcut yerel değişikliği. Bu değişiklik korunmuştur; sadece eski
  commit'i robotta çekmek doğru config'i taşımaz.
- `10.100.68.144` eski README, simülatör talimatları ve UI testlerinde geçiyor;
  aktif PLC YAML/launch override'ı değil. Bu dokümanlardaki laboratuvar
  komutları yarışma için kullanılmamalı.
- Node doğrudan config'siz çalıştırılırsa transport varsayılanı `mock`.

### UDP socket

AF_INET/SOCK_DGRAM; local IP'ye veya porta bind yok. İlk `sendto` işletim
sisteminin route'a göre IP ve geçici kaynak port seçmesini sağlar. Hedef
YAML ile `192.168.100.100:1515`. RX aynı socket üzerinde `recvfrom(64)`
kullanır; PLC cevabı kaynak porta gönderirse okunur. Gerçek loopback
socket testi bunu ve ardışık TX'lerde aynı kaynak portu doğruladı.

Aktarılan şartname robot için sabit UDP portu belirtmiyor. Sabit port
gerektiği varsayılmadı; organizasyonun cevabı source porta gönderdiği
sahada doğrulanmalı. Kaynak IP string olarak tam karşılaştırılıyor;
`192.168.100.100` kabul edilir. Kaynak port denetlenmiyor; yalnız 1515
kaynak portunu zorunlu kılmak için ek şartname kanıtı yok.

Socket timeout/OSError yakalanıyor. Geçersiz datagramlar güvenli biçimde
reddediliyor. Ancak `_handle_rx` içindeki ROS publish veya `call_async`
senkron exception'ları genel olarak RX loop'ta yakalanmıyor; thread ölümü
mümkün, ROS ortamında tetiklendiği gösterilmedi. Future sonucundaki
exception'lar ayrıca yakalanıyor. RX timeout hareketi durdurmuyor; yalnız
telemetri üretiyor.

## Paketler, koordinatlar ve durumlar

TX örneği: `(4, A2, B3, 1.23 m, -0.45 m)` →
`04 02 03 7b 00 d3 ff`. Tam 7 byte; signed int16 little-endian.
`int(x * 100)` sıfıra doğru keser; yuvarlama değildir. Normal taşmalarda
[-32768, 32767] clamp var. Çok büyük finite değer çarpımda Inf olursa yeni
koruma çevrimi atlar. `/odom` → `nav_msgs/msg/Odometry.pose.pose.position.x/y`.
Hardware launch EKF'nin `/odometry/filtered` çıkışını `/odom` olarak remap eder.
İlk odom öncesi `0,0`, odom durursa son koordinat gönderilir; freshness/frame
kontrolü yok. Odom başlangıcı ile yarışma koordinat başlangıcının aynı olduğu
bu denetimde doğrulanamadı.

| Robot/mission durumu | Gönderilen byte | Değerlendirme |
|---|---|---|
| IDLE | 1 | Doğru. |
| TASK RECEIVED / VALIDATE_TASK | 3 | EXECUTING ve yüksüz olduğu için; beklenen işleme=2 değil. |
| MOVING UNLOADED | 3 | Doğru. |
| MOVING LOADED | 4 | Doğru. |
| WAITING_PLC / PAUSED_PLC | 5 | Bridge eşlemesi doğru; aktif mission PAUSED_PLC üretmiyor. |
| REPORT_DELIVERED / REPORT_COMPLETE | 6 | Faz adında REPORT/COMPLETE varsa. |
| Dönüş hareketi MOVE_EMPTY | 3 | Dönüş boyunca beklenen 6 korunmuyor. Kapıda 5 oluyor. |
| ERROR | 7 | Bu MissionState bridge'e ulaştığında. |
| EMERGENCY_STOP | 8 | Bu MissionState bridge'e ulaştığında. |
| PAUSED_MANUAL / PAUSED_OBSTACLE / BOOTING / bilinmeyen | 2 | REPORT/COMPLETE olmayan fazlarda varsayılan. |

Bridge doğrudan safety/estop dinlemiyor. Aktif mission estop'ta exception
atıp genel hata yolunda ERROR'a geçebiliyor; IDLE'da ise mission her zaman
IDLE yayınlıyor. Bu yüzden fiziksel estop'un daima TX=8 olarak görünmesi
garanti değil. Kısa REPORT_COMPLETE ve ERROR fazları 1 Hz TX arasında
kaçabilir; gönderim olay kuyruğu değil son durum örneklemesidir.

İstasyonlar çift yönlü doğru: A1/A2/A3 ↔ 1/2/3; B1/B2/B3 ↔ 1/2/3.
9 kombinasyonun WAIT→START→TX dönüşü üretim mapping'leriyle test edildi.
Başlangıç ve IDLE'da boş station kimlikleri TX `0,0` olur. İlk WAIT'teki
pending task TX istasyonlarını güncellemez; mission state gelene kadar
sıfır kalabilir. Resmi tabloda sıfır tanımlı değil. Görev bilinmiyorken
bir istasyon uydurmamak mantıklı; fakat 0,0 protokolün tek olası tasarımı
veya organizasyonca kabul edilmiş değeri olarak sunulamaz. **HIGH PRIORITY
uyumluluk riski:** resmi PLC sıfırı reddederse ilk görev cevabı hiç gelmez.
Kesin kanıt olmadan istasyon değeri değiştirilmedi.

## A2 / B3 WAIT → START akışı

1. UDP `02 03 01`: IP, tam uzunluk, istasyonlar ve control doğrulanır.
2. Geçerli RX zamanı ve telemetri yenilenir; IDLE'da pending=(A2,B3).
   MissionTask yayınlanmaz.
3. UDP `02 03 02`: aynı kontroller; pending temizlenir; task_id=`plc-0001`,
   pickup_id=`A2`, dropoff_id=`B3`, source=`plc_udp` oluşturulur.
4. `hamals_interfaces/msg/MissionTask`, `/plc/mission_task` üzerinde yayınlanır.
5. Aktif mission aynı topic/type'a abonedir; `_task_received`, busy değilse
   `_run_task` worker'ını başlatır; task kimlikleri MissionContext'e alınır,
   VALIDATE_TASK ve dünya modeli istasyon doğrulaması çalışır.
6. Mission state henüz IDLE görünürken active_task_id ikinci START'ı engeller;
   EXECUTING'de de START yeni görev üretmez. Task tamamlanınca koruma sıfırlanır.

START için önceden WAIT zorunlu değil. START farklı çift içerirse o çift
kullanılır. ROS topic teslimi, Nav2 ve fiziksel görev icrası burada test edilmedi.

## Connection state / timeout / GUI

TX ayrı thread'de `period=1/1.0`; işlem süresi çıkarılıp kalan süre uyunuyor.
Gerçek zaman garantisi yok. Son **geçerli** RX yaşı <=1 s ise CONNECTED=2;
ilk RX öncesi veya eşik aşılınca ERROR=3. DISCONNECTED=0 tanımlı fakat bu
kodun timeout çıkışı değil. `/plc/state` 0.5 s timer ile yayınlanıyor, bu
yüzden gösterge gecikmesi nominal olarak ek 0.5 s olabilir. Geçersiz paket
timeout süresini yenilemez. Yeni geçerli RX otomatik toparlar.

1 Hz/1 s sınırında scheduler/ağ jitter'ı CONNECTED/ERROR dalgalanması
oluşturabilir. `_is_connected` gerçek zamana bakar; recv socket timeout'unun
henüz oluşmaması bunu engellemez. Eşik/rate değiştirilmedi.

GUI hem UI bridge üzerinden boolean bağlantıyı hem web'de doğrudan
`/plc/state` (`hamals_interfaces/msg/PlcState`) aboneliğini kullanır.
`PlcStatusPanel.vue` 2'yi “Bağlı”, 0/3'ü “Bağlantı yok” gösterir;
ekranda literal CONNECTED/RX TIMEOUT yazması gerekmiyor. Bridge node tümüyle
ölürken rosbridge açık kalırsa doğrudan PLC panelinde bağımsız mesaj yaşına
göre geçersizleştirme yok; son bağlı bilgisi kalabilir.

## Local simulator

7 byte `<BBBhh` çözüyor, 3 byte cevap üretiyor; cevabı TX sender IP/port'una
gönderiyor. `x`: random task + WAIT, `s`: START, `w`: WAIT, `q`: quit doğru.
Random yeni çift öncekiyle aynı olabilir. START, `w/x` verilene kadar sürekli
tekrarlanır; görev sonunda otomatik WAIT'e geçmez ve tekrar-görev riskini tetikler.

**Test sınırlaması:** `decode_tx` sadece uzunluğu denetler; status ve istasyon
aralığı denetlenmez. `00 00 00 00 00 00 00` dahi kabul edilir. Dolayısıyla
simülatör PASS sonucu IDLE 0,0'ın resmi PLC'de kabul edileceğini göstermez.
1 s watchdog jitter nedeniyle LOST/RESTORED üretebilir. Yarışmada çalıştırılmayacak.

## Test sonuçları

| Test | Sonuç |
|---|---|
| Bridge mevcut 6 test + ek 26 kontrol | PASS — 32/32 |
| TX exact pack/endian/negatif/clamp/truncation | PASS |
| 9 station kombinasyonu, RX→task→TX | PASS |
| Geçersiz uzunluk/control/station/sender | PASS |
| Yarışma IP kabulü ve eski IP reddi | PASS |
| WAIT pending, START ve çalışma sırasında duplicate | PASS |
| Tamamlanma sonrası aynı START'ın tekrarını önleme | FAIL — mevcut test tekrar üretildiğini doğruluyor |
| Timeout ve geçerli RX sonrası toparlanma | PASS; jitter riski sürüyor |
| NaN/±Inf/aşırı büyük koordinat sonrası TX thread toparlanması | PASS |
| Gerçek loopback UDP, aynı bağlanmamış socket, 3 TX / yaklaşık 1 Hz | PASS |
| Yerel simulator unittest + UDP smoke | PASS — 8/8 |
| Mission PLC pause regression | FAIL — 0/6 |
| ROS graph/service/action ve organizasyon PLC testi | ÇALIŞTIRILAMADI — bu ortamda ros2 ve /opt/ros yok |

Mission testlerinden resume, navigation cancel/restart, line-follow ve odom
hold beklentileri sağlanmadı. Dock testinin Future stub'ı ve fork testinin
eksik DOWN sabiti de aktif uygulamayla uyumsuz; altı hatanın tümü bağımsız
donanım arızası gibi yorumlanmamalı. Servislerin yokluğu ayrıca kaynak koddan
kesin doğrulandı. Testleri yeşile boyamak için beklentiler değiştirilmedi.

Tekrar çalıştırma (repo kökünden):

```bash
python3 -m pytest ros2_ws/src/hamals_plc_bridge/test -q
python3 -m unittest discover -s plc_simulator -v
python3 -m pytest ros2_ws/src/hamals_mission/test/test_plc_pause.py -q
```

Yapılan değişiklikler: TX loop'a yalnız ValueError/OverflowError koruması;
test loader'ın gerçek mapping sabitlerini okuması; ek PLC regresyon testleri;
bu rapor. Kullanıcının competition.yaml değişikliği korundu. PLC dışı üretim
kodu değiştirilmedi. `git diff --check` geçti.

## YARIŞMA GÜNÜ UBUNTU NETWORK

Robot IP: **192.168.100.10**

Gateway: **192.168.100.1**

PLC: **192.168.100.100:1515 UDP**

SSID, subnet prefix ve Ubuntu arayüz adı verilmedi; ağ profili uydurulmadı.
Organizasyonun verdiği prefix ile robotun NetworkManager profilini hazırlayın.
IP/route çıktısında PLC'ye giden kaynak IP 192.168.100.10 olmalı. Aynı ağdaki
PLC için doğrudan on-link route normaldir; gateway diğer ağlara erişim içindir.
Ping başarısı UDP kanıtı değil, ping başarısızlığı da tek başına UDP arızası değil.

### En fazla 10 adımlık komut checklist'i

Bash terminalinde çalıştırın. 5. adım gerçek ROS setup ve repo yollarını sorar;
dağıtım veya Ubuntu home yolu varsayılmaz. Güncel kaynak/config önceden robota
aktarılmış olmalı. 7. adım gerçek hardware bringup başlatır; ilk denemede PLC
WAIT'te tutulmalı ve aktif hareket verilmemeli. Mevcut WAIT arızası giderilmeden
çalışan robotta PLC'nin durduracağına güvenilmemeli. Aynı bringup zaten çalışıyorsa
ikinci kez başlatmayın. Gerekli ROS bağımlılıkları ve tcpdump kurulu kabul edilir.

```bash
# 1 — Arayüz / bağlı Wi-Fi
nmcli device status

# 2 — IPv4: robot arayüzünde 192.168.100.10 olmalı
ip -br -4 address

# 3 — Route ve PLC'ye giderken seçilen source IP
ip -4 route show && ip -4 route get 192.168.100.100

# 4 — ICMP ön kontrolü; asıl UDP kanıtı 10. adım
ping -c 3 -W 1 192.168.100.100

# 5 — Kurulu ROS ve workspace
read -e -p 'ROS setup.bash tam yolu: ' HAMAL_ROS_SETUP; read -e -p 'hamal_agv repo tam yolu: ' HAMAL_REPO; source "$HAMAL_ROS_SETUP" && cd "$HAMAL_REPO/ros2_ws" && source install/setup.bash

# 6 — Güncel bridge/config'i kur ve overlay'i yenile
colcon build --symlink-install --packages-select hamals_plc_bridge && source install/setup.bash

# 7 — Açıkça kaynak yarışma config'iyle başlat; log /tmp/hamal-competition.log
ros2 launch hamals_bringup competition.launch.py plc_config:="$HAMAL_REPO/ros2_ws/src/hamals_plc_bridge/config/competition.yaml" > /tmp/hamal-competition.log 2>&1 &

# 8 — Runtime parametreleri, mission subscriber ve servis ad/tiplerini incele
ros2 param dump /hamals_plc_bridge && ros2 topic info /plc/mission_task --verbose && ros2 service list -t

# 9 — CONNECTED=2, RX/TX age ve hata; timeout komutunun 124 çıkışı normal
timeout 8s ros2 topic echo /plc/state

# 10 — Robot→PLC UDP length 7; PLC→aynı source port UDP length 3; yaklaşık 1 Hz
sudo timeout 12s tcpdump -ni any -tttt -vv -X 'udp and host 192.168.100.100'
```

8. adımda transport=udp, doğru hedef ve 1.0/1.0 görülmeli; mission subscriber
hamals_mission olmalı. `/mission/plc_pause` ve `/mission/plc_resume` Trigger
server'ları mevcut kodda görünmeyecek: bu FAIL bulgusudur. 10. adımda yalnız
TX varsa resmi PLC kabulü, source IP/cevap portu ve ağ/firewall kontrol edilir;
hiç TX yoksa `/tmp/hamal-competition.log` ve bridge süreci incelenir.
