# ============================================================
# ForkCommand.msg
#
# Bu mesaj, forklift çatal mekanizmasına komut göndermek için kullanılır.
#
# İlk sürümde sistem zaman tabanlı açık çevrim çalışır.
# Yani UP veya DOWN komutu geldiğinde fork node, motoru belirlenen
# süre boyunca ilgili yönde çalıştırır ve süre bitince STOP gönderir.
#
# Bu mesaj doğrudan MCU'ya gitmez.
# Genel akış:
#
#   /fork/cmd
#       ↓
#   hamals_fork_node
#       ↓
#   /mcu/fork_cmd
#       ↓
#   hamals_serial_bridge
#       ↓
#   MCU
#
# Mission node ileride bu mesaja command değeri basarak çatalı
# yukarı/aşağı hareket ettirebilir veya durdurabilir.
# ============================================================


# ------------------------------------------------------------
# KOMUT ALANI
# ------------------------------------------------------------

# Fork mekanizmasına gönderilecek komut değeridir.
#
# Kullanılabilecek değerler:
#
#   STOP -> motoru hemen durdur
#   UP   -> fork motorunu yukarı yönde çalıştır
#   DOWN -> fork motorunu aşağı yönde çalıştır
#
# Örnek:
#   command = UP
#   anlamı: çatalı yukarı hareket ettir.
#
# Örnek:
#   command = DOWN
#   anlamı: çatalı aşağı hareket ettir.
#
# Örnek:
#   command = STOP
#   anlamı: motoru hemen durdur.
uint8 command


# ------------------------------------------------------------
# COMMAND ENUM DEĞERLERİ
# ------------------------------------------------------------

# Motoru durdurur.
#
# STOP komutu geldiğinde:
#   - aktif hareket timer'ı iptal edilir
#   - MCU'ya STOP komutu gönderilir
#   - fork state IDLE yapılır
uint8 STOP=0


# Fork motorunu yukarı yönde çalıştırır.
#
# UP komutu geldiğinde:
#   - MCU'ya UP komutu gönderilir
#   - state MOVING_UP yapılır
#   - up_duration_ms timer'ı başlatılır
#   - süre dolunca MCU'ya STOP gönderilir
#   - state UP_DONE yapılır
#
# Not:
#   UP_DONE gerçek üst limit algılandı demek değildir.
#   Sadece yukarı hareket süresi tamamlandı demektir.
uint8 UP=1


# Fork motorunu aşağı yönde çalıştırır.
#
# DOWN komutu geldiğinde:
#   - MCU'ya DOWN komutu gönderilir
#   - state MOVING_DOWN yapılır
#   - down_duration_ms timer'ı başlatılır
#   - süre dolunca MCU'ya STOP gönderilir
#   - state DOWN_DONE yapılır
#
# Not:
#   DOWN_DONE gerçek alt limit algılandı demek değildir.
#   Sadece aşağı hareket süresi tamamlandı demektir.
uint8 DOWN=2