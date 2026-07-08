# ============================================================
# ForkState.msg
#
# Bu mesaj, forklift catal mekanizmasinin anlik durumunu yayinlamak
# icin kullanilir.
#
# Yeni mimaride fork konumu timer ile tahmin edilmez.
# Ust ve alt limit switch bilgileri MCU tarafindan okunur.
#
# Bu yuzden:
#   AT_TOP    -> ust limit switch aktif
#   AT_BOTTOM -> alt limit switch aktif
#
# anlamina gelir.
#
# Motor guvenligi ve limit kontrolu MCU tarafinda yapilmalidir.
# ROS tarafi sadece komut gonderir ve state bilgisini izler.
# ============================================================

# Mesajin uretildigi ROS zamani.
builtin_interfaces/Time stamp

# MCU timestamp degeri.
# MCU tarafindan mikro saniye cinsinden gonderilir.
# Eger MCU state bilgisi henuz alinmadiysa 0 olabilir.
uint32 t_us

# Fork mekanizmasinin mevcut state degeridir.
uint8 state

# Fork node'a gelen son gecerli komutu tutar.
uint8 last_command

# Hata kodudur.
uint8 error_code

# Fork motoru su anda hareket ediyor mu?
bool is_moving

# Ust limit switch aktif mi?
#
# NC + INPUT_PULLUP baglantisinda MCU tarafinda:
#   digitalRead(UPPER_PIN) == HIGH -> upper_limit = true
bool upper_limit

# Alt limit switch aktif mi?
#
# NC + INPUT_PULLUP baglantisinda MCU tarafinda:
#   digitalRead(LOWER_PIN) == HIGH -> lower_limit = true
bool lower_limit


# ------------------------------------------------------------
# STATE ENUM DEGERLERI
# ------------------------------------------------------------

# Motor calismiyor, aktif hareket yok.
uint8 IDLE=0

# Fork yukari yonde hareket ediyor.
uint8 MOVING_UP=1

# Fork asagi yonde hareket ediyor.
uint8 MOVING_DOWN=2

# Ust limit switch aktif, fork ust konumda.
uint8 AT_TOP=3

# Alt limit switch aktif, fork alt konumda.
uint8 AT_BOTTOM=4

# Fork sistemi hata durumunda.
# Detay icin error_code alanina bakilir.
uint8 ERROR=5


# ------------------------------------------------------------
# COMMAND ENUM DEGERLERI
# ------------------------------------------------------------

# Henuz komut alinmadi veya son komut bilinmiyor.
uint8 CMD_NONE=0

# Son komut STOP.
uint8 CMD_STOP=1

# Son komut UP.
uint8 CMD_UP=2

# Son komut DOWN.
uint8 CMD_DOWN=3


# ------------------------------------------------------------
# ERROR ENUM DEGERLERI
# ------------------------------------------------------------

# Hata yok.
uint8 ERROR_NONE=0

# Gecersiz komut hatasi.
uint8 ERROR_INVALID_COMMAND=1

# Ust limite beklenen sekilde ulasilamadi.
# Bu hata daha cok MCU tarafinda uretilebilir.
uint8 ERROR_TOP_TIMEOUT=2

# Alt limite beklenen sekilde ulasilamadi.
# Bu hata daha cok MCU tarafinda uretilebilir.
uint8 ERROR_BOTTOM_TIMEOUT=3

# Ust ve alt limit ayni anda aktif gibi tutarsiz bir durum var.
uint8 ERROR_LIMIT_CONFLICT=4

# MCU state mesaji beklenen surede gelmedi.
uint8 ERROR_MCU_TIMEOUT=5
