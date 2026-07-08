# ============================================================
# ForkState.msg
#
# Bu mesaj, forklift çatal mekanizmasının anlık durumunu yayınlamak
# için kullanılır.
#
# Not:
# Bu sistemin ilk sürümünde çatal konumu encoder/switch ile ölçülmez.
# Hareketler açık çevrim, yani zaman tabanlı olarak yapılır.
#
# Bu yüzden:
#   UP_DONE   -> "Yukarı hareket süresi tamamlandı"
#   DOWN_DONE -> "Aşağı hareket süresi tamamlandı"
#
# anlamına gelir.
#
# UP_DONE kesin olarak "çatal en üstte" demek değildir.
# DOWN_DONE kesin olarak "çatal en altta" demek değildir.
# ============================================================


# Mesajın üretildiği ROS zamanı.
# Debug, loglama ve mission node senkronizasyonu için kullanılır.
builtin_interfaces/Time stamp


# ------------------------------------------------------------
# ANLIK DURUM BİLGİSİ
# ------------------------------------------------------------

# Fork mekanizmasının mevcut state değeridir.
#
# Kullanılabilecek değerler:
#   IDLE
#   MOVING_UP
#   MOVING_DOWN
#   UP_DONE
#   DOWN_DONE
#   ERROR
uint8 state


# Fork node'a gelen son geçerli komutu tutar.
#
# Örneğin:
#   CMD_UP   -> son komut yukarı hareket
#   CMD_DOWN -> son komut aşağı hareket
#   CMD_STOP -> son komut durdurma
#
# Hata durumunda hangi komuttan sonra hata olduğunu anlamak için kullanılır.
uint8 last_command


# Hata kodudur.
#
# Normal durumda ERROR_NONE olur.
# Geçersiz komut, timeout veya ileride eklenecek güvenlik hataları burada tutulur.
uint8 error_code


# Fork motoru şu anda hareket ediyor mu?
#
# true:
#   MOVING_UP veya MOVING_DOWN durumundadır.
#
# false:
#   IDLE, UP_DONE, DOWN_DONE veya ERROR durumundadır.
bool is_moving


# Timer tabanlı hareketlerde kalan süreyi milisaniye cinsinden gösterir.
#
# Örnek:
#   Yukarı hareket süresi 7000 ms ise,
#   hareket başında remaining_time_ms yaklaşık 7000 olur.
#   süre ilerledikçe azalır.
#   hareket tamamlanınca 0 olur.
#
# Debug ve mission node için faydalıdır.
uint32 remaining_time_ms


# ------------------------------------------------------------
# STATE ENUM DEĞERLERİ
# ------------------------------------------------------------

# Motor çalışmıyor, aktif hareket yok.
uint8 IDLE=0

# Fork yukarı yönde hareket ediyor.
uint8 MOVING_UP=1

# Fork aşağı yönde hareket ediyor.
uint8 MOVING_DOWN=2

# Yukarı hareket için belirlenen süre tamamlandı.
#
# Önemli:
# Bu değer gerçek üst limit algılandı anlamına gelmez.
# Sadece timer süresi doldu ve motor durduruldu anlamına gelir.
uint8 UP_DONE=3

# Aşağı hareket için belirlenen süre tamamlandı.
#
# Önemli:
# Bu değer gerçek alt limit algılandı anlamına gelmez.
# Sadece timer süresi doldu ve motor durduruldu anlamına gelir.
uint8 DOWN_DONE=4

# Fork sistemi hata durumunda.
# Detay için error_code alanına bakılır.
uint8 ERROR=5


# ------------------------------------------------------------
# COMMAND ENUM DEĞERLERİ
# ------------------------------------------------------------

# Henüz komut alınmadı veya son komut bilinmiyor.
uint8 CMD_NONE=0

# Son komut STOP.
uint8 CMD_STOP=1

# Son komut UP.
uint8 CMD_UP=2

# Son komut DOWN.
uint8 CMD_DOWN=3


# ------------------------------------------------------------
# ERROR ENUM DEĞERLERİ
# ------------------------------------------------------------

# Hata yok.
uint8 ERROR_NONE=0

# Timeout hatası.
#
# İlk timer-only sürümde normal hareket bitişi timeout sayılmaz.
# Bu değer daha çok ileride MCU cevabı beklenip alınamazsa veya
# beklenen süre içinde işlem tamamlanmazsa kullanılabilir.
uint8 ERROR_TIMEOUT=1

# Geçersiz komut hatası.
#
# Örneğin ForkCommand içinde tanımlı olmayan bir command değeri gelirse
# bu hata kodu kullanılabilir.
uint8 ERROR_INVALID_COMMAND=2