"""HAMAL gorev sunucusunu saha koordinatlariyla baslatir.

    ros2 launch hamals_mission mission.launch.py

BASLANGIC NOKTASI
-----------------
Artik launch'a sabit yazilmasi ZORUNLU DEGIL. RViz'de "2D Pose Estimate" ile
verdiginiz poz START kabul edilir; gorev bittiginde robot AYNI x/y ve AYNI
aciya doner. Asagidaki start_* degerleri sadece YEDEKTIR (poz hic verilmezse
ve TF de okunamazsa kullanilir).

QR VE CIZGI TAKIBI
------------------
Robot D1'e giderken yolda QR gorurse Nav2 hedefini birakir ve DOGRUDAN cizgi
takibine gecer (qr_watch_on_route). QR gorulmeden D1'e varilirsa robot orada
sabit durup QR bekler -- yedek davranis. Yuk alindiktan sonra D1'e UGRANMAZ,
dogrudan D2'ye gidilir.

DONUS
-----
B2'de yuk birakildiktan sonra robot DONMEDEN, geri geri D1'e kadar gelir
(dropoff_reverse_to_d1). Mesafe sureyle degil, TF'ten okunan gercek konumla
olculur; D1'e reverse_tolerance_m kadar yaklasinca durur.

Tek deger degistirmek icin dosyayi acmaya gerek yok:

    ros2 launch hamals_mission mission.launch.py d2_x:=2.40 reverse_max_m:=6.0
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

DEFAULTS = {
    # ================= SAHA KOORDINATLARI =================
    # Sirasi: START -> D1 -> D2 (kapi) -> B2
    # D1, D2'nin GERISINDEDIR (START'a daha yakin).

    # Baslangic noktasi -- YEDEK. Normalde RViz "2D Pose Estimate" pozu
    # kullanilir; bu degerler yalnizca poz hic gelmezse VE TF de okunamazsa
    # devreye girer. Asagidaki degerler ESKI olcumdur; guncel haritada dogru
    # yeri gostermez. Guvenmek istiyorsaniz sahada yeniden olcup yazin.
    'start_x': '0.50',
    'start_y': '-1.18',
    'start_yaw_deg': '89.9',

    # D1: QR'in okunacagi nokta. Robot burada SABIT DURUP QR bekler.
    # Donuste de bu noktaya kadar geri geri gelinir.
    'd1_x': '0.18',
    'd1_y': '0.28',
    'd1_yaw_deg': '84.6',

    # A1: paletin bulundugu nokta. YALNIZCA PANELDE GOSTERIM ICIN --
    # robot buraya Nav2 ile gitmez, cizgi takibiyle gider.
    'a1_x': '0.23',
    'a1_y': '1.39',
    'a1_yaw_deg': '85.6',

    # D2: kapinin onundeki bekleme noktasi.
    'd2_x': '1.95',
    'd2_y': '0.07',
    'd2_yaw_deg': '-3.1',

    # B2: yukun birakilacagi nokta.
    'b2_x': '3.83',
    'b2_y': '0.06',
    'b2_yaw_deg': '-5.8',

    # ================= BASLANGIC POZU =================
    # true : RViz "2D Pose Estimate" pozu START kabul edilir, gorev sonunda
    #        robot AYNI x/y ve AYNI aciya doner.
    #        Poz gelmemisse gorev basladigi andaki TF pozu alinir.
    # false: yukaridaki sabit start_* kullanilir.
    'start_from_initial_pose': 'true',
    # Node acilirken konumlanmaya sabit start_* pozunu KENDISI bildirsin mi?
    # RViz'den poz vereceginiz icin false kalmali.
    'auto_set_initial_pose': 'false',
    'initial_pose_delay_sec': '3.0',

    # ================= QR =================
    # true : START -> D1 bacaginda QR dinlenir; okundugu anda Nav2 hedefi
    #        iptal edilip DOGRUDAN cizgi takibine gecilir.
    # false: eski davranis -- D1'e varilir, orada sabit durup QR beklenir.
    # QR yolda gorulmeden D1'e varilirsa yine D1'de beklenir (yedek).
    'qr_watch_on_route': 'true',
    # QR ararken robot YAVAS gitmeli (hareket bulanikligi QR'i okunmaz yapar).
    # Bu bacak Nav2 ile suruldugu icin hizi mission_server degil Nav2 belirler;
    # asagidaki yuzde Nav2'ye /speed_limit ile bildirilir. 100 = sinir yok.
    # Bacak bitince otomatik %100'e donulur.
    # QR hala okunamiyorsa once bunu 25'e dusurun.
    'qr_speed_limit_pct': '25.0',

    # ================= CIZGI TAKIBI (palete giris) =================
    # Cizgi takibiyle gidilecek mesafe. TF ile olculur, sureyle DEGIL.
    # >>> BU DEGERI SAHADA OLCUP AYARLAYIN <<<
    # D1 (0.18, 0.28) -> A1 (0.23, 1.39) arasi 1.11 m; ancak QR yolda,
    # D1'e varmadan okunursa palete kalan mesafe DAHA UZUN olur.
    'line_distance_m': '1.67',
    # Palete giris hizi. 0.06 -> 0.10 yapildi (bacak ~19 sn yerine ~11 sn).
    # Yalpalama gorursen once 0.08'e dusur, sonra line_gain'i kucult.
    'line_speed': '0.25',        # m/s
    'line_gain': '0.0018',       # yalpaliyorsa KUCULT
    'line_deadband_px': '18.0',  # merkeze yakin kucuk hatalari yok say
    'line_smoothing': '0.25',    # 0-1, kucuk = daha yumusak
    'line_max_turn': '0.35',     # rad/s tavan
    'line_invert': 'false',      # cizgiden UZAKLASIYORSA true yapin
    'line_wait_s': '3.0',        # baslangicta cizgi arama suresi
    'line_lost_s': '1.5',        # bu kadar goremezse donmeyi birakip duz devam
    'line_fallback_straight': 'true',  # cizgi hic yoksa duz surusle devam

    # ================= MESAFELER VE SURELER =================
    # Cizgi bulunamazsa palete bu mesafe kadar DUZ surulerek girilir.
    'pickup_forward_m': '2.0',
    # Yuk alindiktan sonra paletten geri cikis. 0 = kapali, dogrudan D2'ye.
    # Nav2 palet alaninda donmekte zorlanirsa 0.80-1.20 arasi deneyin.
    'pickup_reverse_m': '0.0',
    'straight_speed': '0.30',    # m/s -- duz surus hizi

    # ---- B2'den D1'e GERI GERI DONUS ----
    # true : B2'den D1'e kadar geri geri gelinir. Nerede duracagini SURE degil,
    #        TF'ten okunan gercek konum belirler -- hiz kalibrasyonu yanlis olsa
    #        bile robot dogru noktada durur.
    'dropoff_reverse_to_d1': 'true',
    'reverse_tolerance_m': '0.20',   # D1'e bu kadar yaklasinca dur
    # GUVENLIK TAVANI: bu kadar geri gidip hedefe ulasilamazsa durur ve hata verir.
    # B2 -> D1 arasi mesafeden buyuk olmali (mevcut koordinatlarda 3.66 m).
    'reverse_max_m': '3.57',
    # Uzun geri suruste tekerlek farki sapma yapar; yonu sabit tutar.
    'reverse_yaw_hold': 'true',
    'reverse_yaw_gain': '1.0',       # yon hatasi kazanci -- yalpaliyorsa kucult
    'reverse_cross_gain': '1.2',     # yanal sapma kazanci -- yalpaliyorsa kucult
    'reverse_max_turn': '0.20',      # rad/s tavan
    # dropoff_reverse_to_d1 false ise kullanilir: sabit mesafe geri cikip Nav2.
    'dropoff_reverse_m': '2.0',

    'd1_stop_sec': '1.0',        # D1'e varinca duraklama
    'qr_wait_sec': '60.0',       # D1'de QR icin azami bekleme
    'qr_settle_sec': '0.5',      # QR okunduktan sonra duraklama
    'd2_wait_sec': '5.0',        # D2'de kapi beklemesi

    # ================= FORK =================
    'fork_enabled': 'true',
    'fork_rearm_sec': '6.5',     # firmware limitinin (8 sn) altinda kalmali
    'fork_max_rearm': '8',
    'fork_wait_sec': '60.0',
    'fork_settle_sec': '0.5',

    'nav_timeout_sec': '300.0',
}

_BOOL_KEYS = {
    'fork_enabled',
    'auto_set_initial_pose',
    'start_from_initial_pose',
    'dropoff_reverse_to_d1',
    'reverse_yaw_hold',
    'qr_watch_on_route',
    'line_invert',
    'line_fallback_straight',
}
# Node'da tamsayi olarak tanimli; float gecirilirse tip hatasi verir.
_INT_KEYS = {'fork_max_rearm'}


def generate_launch_description():
    arguments = [
        DeclareLaunchArgument(name, default_value=value)
        for name, value in DEFAULTS.items()
    ]

    parameters = {}
    for name in DEFAULTS:
        value = LaunchConfiguration(name)
        if name in _BOOL_KEYS:
            parameters[name] = ParameterValue(value, value_type=bool)
        elif name in _INT_KEYS:
            parameters[name] = ParameterValue(value, value_type=int)
        else:
            parameters[name] = ParameterValue(value, value_type=float)

    return LaunchDescription(arguments + [
        Node(
            package='hamals_mission',
            executable='mission_server',
            name='hamal_mission_server',
            output='screen',
            parameters=[parameters],
        ),
    ])