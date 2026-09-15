# HAMAL AGV — Calistirma, Test ve Hata Izleme Komutlari
=========================================================
(TEKNOFEST Sanayide Robotik — PLC UDP testi dahil)

Terminoloji: her komut blogu AYRI bir terminaldedir. Robot tarafinda her
yeni terminalde once:  `cd ~/ros2_ws && source install/setup.bash`

===============================================================
BOLUM 0 — AG HAZIRLIGI (ROS'tan ONCE, cok onemli)
===============================================================
Raspberry Pi (PLC):  IP 192.168.100.100 / mask 255.255.255.0 / gw 192.168.100.1
Robot        :       IP 192.168.100.10  / mask 255.255.255.0 / gw 192.168.100.1
Uzak monitor :       IP 192.168.100.20  (istege bagli)

# Robot / Pi'de statik IP (ornek, netplan ya da NetworkManager'a gore degisir):
#   nmcli con mod <baglanti> ipv4.addresses 192.168.100.10/24 ipv4.gateway 192.168.100.1 ipv4.method manual
#   nmcli con up <baglanti>

# Kontrol:
ip addr | grep 192.168.100          # dogru IP atanmis mi
# Pi'de:
ping -c 3 192.168.100.10            # robotu gormeli
# Robot'ta:
ping -c 3 192.168.100.100           # Pi'yi gormeli

# Pi'de UDP portu firewall'a takiliyorsa:
sudo ufw allow 1515/udp

# >>> PING CALISMADAN ROS'A GECME <<<

===============================================================
BOLUM 1 — PI TARAFI: PLC SIMULATORU
===============================================================
# (plc_simulator.zip'i Pi'ye kopyala, ac, icine gir)
unzip plc_simulator.zip && cd plc_simulator

# AUTO (gercek PLC gibi, rastgele gorev):
python3 plc_simulator.py

# AUTO sabit gorev + surekli + kapida 3sn bekletme:
python3 plc_simulator.py --pickup A1 --dropoff B1 --loop --door-delay 3

# MANUAL (elle yonet):  komutlar ->  t A1 B1  |  w=BEKLE  |  s=BASLA  |  q=cikis
python3 plc_simulator.py --manual

# Beklenen: robot baglaninca saniyede bir "RX <- durum=..." satiri.

===============================================================
BOLUM 2 — ROBOT TARAFI: DERLEME
===============================================================
cd ~/ros2_ws
colcon build
source install/setup.bash
# tek paket derlemek istersen:
# colcon build --packages-select hamals_plc_bridge hamals_mission hamals_docking

===============================================================
BOLUM 3 — ADIM ADIM TEST (kolaydan zora)
===============================================================

# --- 3A) SADECE PLC KOPRUSU (baglanti + TX/RX testi) ---
ros2 run hamals_plc_bridge plc_bridge_node --ros-args \
  --params-file src/hamals_plc_bridge/config/competition.yaml
# Pi ekraninda 1 Hz RX gorunmeli. AUTO'da gorev otomatik gelir.

# --- 3B) TAM YARISMA (her dugum + PLC UDP) ---
ros2 launch hamals_bringup competition.launch.py
# launch artik competition.yaml (udp) kullanir.

# --- 3C) HARITALAMA (yarisma oncesi, ayri) ---
ros2 launch hamals_bringup mapping.launch.py

===============================================================
BOLUM 4 — IZLEME / HATA AYIKLAMA (ayri terminaller)
===============================================================
# PLC baglantisi, kapi izni, son TX/RX:
ros2 topic echo /plc/state

# Gorev FSM durumu ve faz (kapida durum=5, donuste 6 gormek icin):
ros2 topic echo /mission/state

# PLC'den gelen gorev:
ros2 topic echo /plc/mission_task

# QR:
ros2 topic echo /qr/detected
ros2 topic echo /qr/text
ros2 topic echo /qr/detection      # x,y,z,yaw_deg,confidence (visual servo)

# Hat:
ros2 topic echo /line/detected
ros2 topic echo /line/error

# Guvenlik / engel:
ros2 topic echo /safety/state
ros2 topic echo /proximity/detected

# Hiz komutlari (twist_mux ciktisi + kaynaklar):
ros2 topic echo /cmd_vel
ros2 topic echo /cmd_vel/docking   # dock + mission QR arama/ortalama
ros2 topic echo /cmd_vel/nav

# Fork:
ros2 topic echo /fork/state
ros2 topic echo /fork/is_up        # true=arka kamera (yuklu)

# Genel tani:
ros2 node list
ros2 topic list
ros2 topic hz /odom                # odom akiyor mu
ros2 topic hz /scan                # lidar akiyor mu
ros2 run tf2_tools view_frames     # TF agaci (map->odom->base)

# Node loglari (hangi node hata veriyor):
ros2 run <paket> <exe> --ros-args --log-level debug

===============================================================
BOLUM 5 — MANUEL GOREV (PLC olmadan hizli test)
===============================================================
# mock modda (competition.yaml yerine mock.yaml ile) gorev tetikle:
ros2 run hamals_plc_bridge plc_bridge_node --ros-args \
  --params-file src/hamals_plc_bridge/config/mock.yaml
# baska terminalde:
ros2 service call /plc/mock/submit_task std_srvs/srv/Trigger {}

===============================================================
BOLUM 6 — BEKLENEN AKIS (dogru calisiyorsa)
===============================================================
PLC: RX durum=1  ->  >> GOREV VERILDI A1->B1 (BASLA)
Robot: MOVE -> QR(ALIM1) bul+ortala -> hat takibi -> yuk al -> fork up
       -> /fork/is_up true (arka kamera)
Kapi(gidis): durum=5 -> PLC BEKLE -> (door_delay) -> KAPI IZNI BASLA -> gecer
Robot: B1'e git -> QR(BIRAK1) -> hat -> yuk birak -> /fork/is_up false
Kapi(donus): durum=5 -> BEKLE -> BASLA -> gecer
Robot: START'a don -> durum=1 ->  >> GOREV TAMAMLANDI

===============================================================
BOLUM 7 — SIK HATALAR VE COZUM
===============================================================
[RX timeout / baglanti yok]
  -> ping calisiyor mu? IP 192.168.100.10/.100 dogru mu? port 1515?
  -> Pi firewall: sudo ufw allow 1515/udp

[Gorev robota girmiyor]
  -> AUTO'da robot durumu 1(idle) olmali (ros2 topic echo /mission/state)
  -> MANUAL'de: t A1 B1  sonra  s

[Kapi acilmiyor]
  -> /mission/state te durum 5 gorunuyor mu? Gorunmuyorsa robot kapiya varmadi.
  -> Simde >> ROBOT KAPIDA gorunuyor mu?

[QR ortalama ters yone donuyor]
  -> docking_profiles.yaml / mission: qr_vs_invert: true yap

[Robot cok agresif / seri]
  -> ilgili yaml'da hiz ve gain dusur (speed_mps, line_gain, search_angular_speed)

[durum baytlari PLC'nin bekledigiyle uyusmuyor]
  -> plc_bridge_node.py _mission_state_cb esleme tablosunu sahaya gore ayarla

[Hat bulunamadi (LINE LOST) hemen]
  -> QR'dan hat baslangicina bosluk varsa docking line_lost_sec artir
