# Ham teker encoder tick delta mesajı.
#
# Bu mesaj MCU'dan gelen $ENC,t_us,dl,dr*CS frame'inin
# ROS tarafındaki karşılığıdır.
#
# Not:
# - Bu mesajda hiçbir kinematik hesap yapılmaz.
# - dl/dr değerleri ardışık encoder ölçümleri arasındaki tick farkıdır.
# - t_us MCU tarafındaki micros() zamanıdır.
# - Odometry dt hesabı header.stamp ile değil, t_us üzerinden yapılmalıdır.

# ROS publish zamanı.
# Debug, latency ölçümü ve mesaj izleme amacıyla kullanılır.
# Odometry dt hesabında kullanılmaz.
std_msgs/Header header

# MCU zaman damgası, mikrosaniye cinsinden.
# Kaynak: MCU micros() / donanım timer.
# uint32 olduğu için yaklaşık 71 dakikada bir wraparound olur.
# Ardışık iki mesaj arasındaki dt hesabı unsigned fark ile yapılmalıdır:
# dt_us = (t_us_new - t_us_prev) & 0xFFFFFFFF
uint32 t_us

# Sol teker encoder delta tick değeri.
# Son gönderilen ENC frame'inden bu frame'e kadar olan tick farkıdır.
# İleri yönde pozitif, geri yönde negatif olacak şekilde yorumlanır.
int32 dl

# Sağ teker encoder delta tick değeri.
# Son gönderilen ENC frame'inden bu frame'e kadar olan tick farkıdır.
# İleri yönde pozitif, geri yönde negatif olacak şekilde yorumlanır.
int32 dr