# PLC simülatörü hızlı çalıştırma

Proje kökünden laboratuvar config'i (`plc_ip: 10.100.68.144`) için:

```bash
python3 plc_simulator/plc_simulator.py --bind-ip 10.100.68.144 --port 1515
```

Yarışmada bridge `plc_ip` değerini de değiştirerek:

```bash
python3 plc_simulator/plc_simulator.py --bind-ip 192.168.100.100 --port 1515
```

Harf + Enter: `x` rastgele görev ve WAIT, `s` START/CONTINUE, `w` WAIT,
`q` çıkış. Başlangıç WAIT. Eski AUTO seçenekleri kaldırıldı.

ROS gerektirmeyen test:

```bash
python3 -m unittest discover -s plc_simulator -v
```

Ağ ayarları, bridge komutu ve mevcut pause/resume ile tekrar görev riskleri için
[PLC test rehberini](README_PLC_TEST.md) okuyun.
