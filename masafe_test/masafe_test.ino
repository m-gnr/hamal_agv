// MZ80 / Mesafe sensoru testi - ROS YOK, sadece Serial.
// Deneyap Kart (ESP32-S3). OUT pinini kendi baglantina gore ayarla.

#define MESAFE_PIN  D0    // <<< SENSOR OUT pinini buraya yaz (Mesafe konnektoru)

// Cogu MZ80 modulu: engel VAR -> LOW, engel YOK -> HIGH (active-low).
// Modulun tersse asagidaki ACTIVE_LOW'u false yap.
#define ACTIVE_LOW  true

void setup() {
  Serial.begin(230400);
  delay(300);
  pinMode(MESAFE_PIN, INPUT_PULLUP);   // dahili pull-up
  Serial.println("MZ80 test basladi. Elini sensorun onune koy/cek.");
}

void loop() {
  int raw = digitalRead(MESAFE_PIN);           // HIGH / LOW
  bool engel = ACTIVE_LOW ? (raw == LOW)       // active-low: LOW = engel
                          : (raw == HIGH);      // active-high: HIGH = engel

  Serial.print("raw=");
  Serial.print(raw == HIGH ? "HIGH" : "LOW");
  Serial.print("  ENGEL=");
  Serial.println(engel ? "VAR (algilandi)" : "yok");

  delay(200);   // 5 Hz
}
