# HAMAL — PLC UDP Testi (kurulum + calistirma)

Bu klasor gercek PLC yerine gecen `plc_simulator.py` icerir. Robot ile
Raspberry Pi (veya baska PC) arasinda UDP protokolunu bastan sona test eder.

## 0) Mimari
```
Robot (192.168.100.10)                 Pi = PLC sim (192.168.100.100:1515)
  hamals_plc_bridge  --PAKET_TX(7B)-->   plc_simulator.py
  (transport=udp)    <--PAKET_RX(3B)--
        |  /plc/mission_task -> mission_node
        |  /mission/door_event <-> /plc/door_event (kapi mesafesi)
```

## 1) Ag ayari (ROS'tan ONCE)
Pi (PLC):    IP 192.168.100.100 / 255.255.255.0 / gw 192.168.100.1
Robot:       IP 192.168.100.10  / 255.255.255.0 / gw 192.168.100.1

Kontrol:
```bash
# Pi'de
ip addr | grep 192.168.100
ping 192.168.100.10      # robotu gormeli
# Robot'ta
ping 192.168.100.100     # Pi'yi gormeli
```
Ping calismadan ROS'a GECME.

## 2) Pi'de PLC simulatorunu baslat
```bash
python3 plc_simulator.py                       # AUTO, rastgele gorev
python3 plc_simulator.py --pickup A1 --dropoff B1   # sabit gorev
python3 plc_simulator.py --manual              # elle: t A1 B1 / w / s / q
python3 plc_simulator.py --loop --door-delay 3 # surekli + kapida 3sn bekletme
```
Beklenen: robot baglaninca her saniye `RX <- durum=...` satiri.

## 3) Robot'ta koseyi kur ve calistir
```bash
cd ~/ros2_ws
colcon build
source install/setup.bash
```
Sadece PLC koprusu (baglanti testi):
```bash
ros2 run hamals_plc_bridge plc_bridge_node --ros-args \
  --params-file src/hamals_plc_bridge/config/competition.yaml
```
Tam yarisma (her sey, PLC UDP dahil — launch artik competition.yaml kullanir):
```bash
ros2 launch hamals_bringup competition.launch.py
```

## 4) Dogrulama
- Pi ekraninda saniyede bir `RX <- durum=1(idle)` -> TX 1 Hz CALISIYOR.
- AUTO modda robot hazir olunca `>> GOREV VERILDI: A1 -> B1` -> gorev girdi.
- Robot kapida: `RX durum=5` -> `>> ROBOT KAPIDA -> BEKLE` -> door_delay sonra
  `>> KAPI IZNI: BASLA` -> robotta `DOOR GRANTED` -> gecer. (2 kez: gidis+donus)
- Gorev bitince `>> GOREV TAMAMLANDI`.

## 5) Faydali izleme (ayri terminaller, robot tarafi)
```bash
ros2 topic echo /plc/state          # connection_state, door_permission, last_tx/rx
ros2 topic echo /mission/state      # FSM durumu, faz
ros2 topic echo /plc/mission_task   # gelen gorev
```

## 6) Sorun giderme
- RX timeout: ping/IP/port(1515)/firewall kontrol. Pi'de `sudo ufw allow 1515/udp`.
- Gorev girmiyor: AUTO'da robot durumu 1(idle) olmali; MANUAL'de `t A1 B1` sonra `s`.
- Kapi acilmiyor: mission durumu 5 gorunuyor mu? (`ros2 topic echo /mission/state`).
  Gorunmuyorsa robot henuz kapiya varmadi.
- durum baytlari yanlissa: bridge `_mission_state_cb` eslemesini sahaya gore ayarla.
