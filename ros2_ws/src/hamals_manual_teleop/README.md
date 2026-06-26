# hamals_manual_teleop

**hamals_manual_teleop**, ROS 2 için geliştirilmiş, klavye tabanlı ve**latched**
(tek tuş = sürekli hareket) mantığıyla çalışan bir teleop paketidir.
Paket,**cmd_vel** standardına uygun `geometry_msgs/Twist` mesajları yayınlar.

```text
hamals_manual_teleop/
├── hamals_manual_teleop/
│   └── teleop_node.py
├── config/
│   └── teleop.yaml
├── launch/
│   └── teleop.launch.py
├── package.xml
├── setup.py
└── README.md

```

## Kontrol Şeması

### Hareket (Latched)

Bir tuşa **bir kez basılması**, hareketin **sürekli devam etmesi** için yeterlidir.

Yeni bir hareket tuşu, önceki komutu geçersiz kılar.

| Tuş | Davranış |
| --- | --- |
| `w` | İleri hareket |
| `s` | Geri hareket |
| `a` | Sola dönüş |
| `d` | Sağa dönüş |
| `x` | Acil durdurma (`linear = 0`, `angular = 0`) |

---

### Hız Ayarı

Hız ayarları hareketten bağımsızdır.

Hız değiştiğinde mevcut hareket devam eder.

| Tuş | İşlev |
| --- | --- |
| `1` | Linear hız azalt |
| `2` | Linear hız artır |
| `3` | Angular hız azalt |
| `4` | Angular hız artır |

---

## cmd_vel Eksen Konvansiyonu

Bu paket, ROS standart eksen konvansiyonunu kullanır.

### Linear

- `linear.x > 0` : ileri
- `linear.x < 0` : geri

### Angular

- `angular.z > 0` : sola dönüş (counter-clockwise)
- `angular.z < 0` : sağa dönüş (clockwise)

`linear.y`, `linear.z`, `angular.x` ve `angular.y` değerleri kullanılmaz ve sıfırdır.

---

## Çalıştırma

### Doğrudan çalıştırma

```bash
ros2 run hamals_manual_teleop teleop_node

```

###
