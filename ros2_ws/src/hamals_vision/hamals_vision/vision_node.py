#!/usr/bin/env python3

import json
import threading
import time

import cv2
import numpy as np

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data

from libcamera import controls
from picamera2 import Picamera2

from sensor_msgs.msg import Image, CompressedImage
from std_msgs.msg import Bool, Int32, String
from cv_bridge import CvBridge

from pyzbar.pyzbar import decode as qr_decode


# =====================================================================
#  QR isci ipligi: pyzbar agir; ana donguyu bloklamamasi icin
#  ayri thread'te calisir. Ana dongu kare gonderir, beklemez.
# =====================================================================
class QrWorker:

    def __init__(self, on_result):
        self._on_result = on_result
        self._lock = threading.Lock()
        self._frame = None
        self._running = True
        self._new = threading.Event()
        self.last_ms = 0.0
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="qr-worker"
        )

    def start(self):
        self._thread.start()

    def submit(self, gray):
        # Sadece en yeni kareyi tut (bayat kareleri atla)
        with self._lock:
            self._frame = gray
        self._new.set()

    def _loop(self):
        while self._running:
            if not self._new.wait(timeout=0.5):
                continue
            self._new.clear()

            with self._lock:
                gray = self._frame
                self._frame = None

            if gray is None:
                continue

            t0 = time.monotonic()
            text, points = self._decode(gray)
            self.last_ms = (time.monotonic() - t0) * 1000.0

            self._on_result(text, points)

    def _decode(self, gray):
        decoded = qr_decode(gray)
        if not decoded:
            return "", None
        obj = decoded[0]
        try:
            data = obj.data.decode("utf-8")
        except UnicodeDecodeError:
            data = obj.data.decode("utf-8", errors="ignore")
        points = np.array(
            [(p.x, p.y) for p in obj.polygon],
            dtype=np.float32
        )
        return data, points

    def stop(self):
        self._running = False
        self._new.set()


# =====================================================================
#  Birlesik gorus nodu: tek kamera dongusu -> line + qr + yayin
#  Cift kamera (on/arka) /fork/is_up ile yonetilir.
# =====================================================================
class VisionNode(Node):

    # --- cizgi parametreleri (eski line_node ile ayni) ---
    ROW_RATIO = 0.90
    BLUR_SIZE = (7, 7)
    KERNEL_SIZE = (7, 7)

    # --- cizim renkleri ---
    COLOR_LINE = (0, 255, 0)
    COLOR_LINE_REF = (255, 255, 0)
    COLOR_LINE_EDGE = (0, 165, 255)
    COLOR_QR = (0, 255, 0)
    COLOR_TEXT = (0, 255, 0)

    # --- yous: cizgi renk tespiti (HSV) - RENK + MOMENT ---
    BAND_TOP_RATIO = 0.0      # yous: alt %40'lik serit uzerinde calis
    MIN_AREA       = 3000      # yous: cizgi ~10cm genis -> bu kadar pikselden azsa yok say
    BLUE_LO   = (95, 60, 30)    # yous: mavi alt sinir  (H,S,V)
    BLUE_HI   = (130, 255, 255) # yous: mavi ust sinir
    ORANGE_LO = (0, 110, 90)    # yous: turuncu alt sinir
    ORANGE_HI = (22, 255, 255)  # yous: turuncu ust sinir

    def __init__(self):
        super().__init__("vision_node")
        self.get_logger().info("===== HAMALS Vision Node (birlesik) =====")

        # =========================
        # Kamera ayarlari
        # =========================
        self.WIDTH = 640
        self.HEIGHT = 480
        self.FPS = 30                 # yukseltildi (QR ayri thread'te)

        self.FRONT_CAMERA = 0
        self.REAR_CAMERA = 1

        self.FRONT_LENS = 1.25
        self.REAR_LENS = 1.25

        self.FRONT_FLIP = True
        self.REAR_FLIP = True

        self.EXPOSURE = 5000
        self.GAIN = 4.0

        # --- yayin / isleme hizlari ---
        self.PUBLISH_FPS = 30         # JPEG yayin hizi (izleme icin yeterli)
        self.QR_EVERY_N = 3           # her 3 karede bir QR dene
        self.JPEG_QUALITY = 75

        # --- kararlilik esikleri (eski nodlarla ayni) ---
        self.LINE_STABLE = 5
        self.QR_STABLE = 1

        self.bridge = CvBridge()

        # =========================
        # Yayincilar
        # =========================
        self.pub_jpeg = self.create_publisher(
            CompressedImage, "/camera/image_raw/compressed",
            qos_profile_sensor_data
        )
        self.pub_raw = self.create_publisher(
            Image, "/camera/image_raw", qos_profile_sensor_data
        )

        self.pub_line_detected = self.create_publisher(
            Bool, "/line/detected", 10)
        self.pub_line_error = self.create_publisher(
            Int32, "/line/error", 10)
        self.pub_line_overlay = self.create_publisher(
            String, "/line/overlay", 10)

        self.pub_qr_detected = self.create_publisher(
            Bool, "/qr/detected", 10)
        self.pub_qr_text = self.create_publisher(
            String, "/qr/text", 10)
        self.pub_qr_overlay = self.create_publisher(
            String, "/qr/overlay", 10)

        # =========================
        # Durum degiskenleri
        # =========================
        self._line_hit = 0
        self._line_miss = 0
        self._line_stable = False
        self._line_error = 0
        self._line_last_overlay = None

        self._qr_lock = threading.Lock()
        self._qr_text = ""
        self._qr_points = None
        self._qr_stamp = 0.0
        self._qr_hold_sec = 0.5
        self._qr_last_text = ""
        self._qr_last_overlay = None
        self._qr_hit = 0
        self._qr_miss = 0
        self._qr_stable = False

        self._frame_no = 0
        self._last_publish = 0.0
        self._publish_period = 1.0 / self.PUBLISH_FPS
        self._proc_ms = 0.0
        self._fps_window = []

        # =========================
        # Kameralar (cift, tek aktif)
        # =========================
        self.front = Picamera2(camera_num=self.FRONT_CAMERA)
        self.rear = Picamera2(camera_num=self.REAR_CAMERA)

        self._configure(self.front, self.FRONT_LENS)
        self._configure(self.rear, self.REAR_LENS)

        self.active_camera = self.front
        self.active_flip = self.FRONT_FLIP
        self.rear_active = False
        self._cam_lock = threading.Lock()

        self.front.start()
        self.get_logger().info(
            f"Kamera: ON aktif | {self.WIDTH}x{self.HEIGHT} @ {self.FPS} FPS"
        )

        # =========================
        # QR isci ipligi
        # =========================
        self.qr_worker = QrWorker(self._on_qr_result)
        self.qr_worker.start()

        # =========================
        # Fork aboneligi
        # =========================
        self.fork_sub = self.create_subscription(
            Bool, "/fork/is_up", self.fork_callback, 10
        )

        # =========================
        # Yakalama ipligi (ana is burada)
        # =========================
        self._running = True
        self.capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True, name="hamal-capture"
        )
        self.capture_thread.start()

        # Son durumlari 30 Hz hizinda tekrar yayinla
        self.state_timer = self.create_timer(
            1.0 / 30.0,
            self._publish_state
        )

        # Istatistik

    # ==========================================================
    # Kamera yapilandirmasi
    # ==========================================================
    def _configure(self, camera, lens):
        frame_us = int(1_000_000 / self.FPS)

        cam_controls = {
            "FrameDurationLimits": (frame_us, frame_us),
            "AeEnable": False,
            "ExposureTime": self.EXPOSURE,
            "AnalogueGain": self.GAIN,
            "AwbEnable": True,
            "AwbMode": controls.AwbModeEnum.Fluorescent,
            "AfMode": controls.AfModeEnum.Manual,
            "LensPosition": lens,
        }

        # Her iki kamerada sensorun tamamini kullan
        sensor_w, sensor_h = camera.camera_properties["PixelArraySize"]
        cam_controls["ScalerCrop"] = (
            0, 0, sensor_w, sensor_h
        )

        # main (BGR) + lores (YUV420 -> Y kanali bedava gri)
        config = camera.create_video_configuration(
            main={"size": (self.WIDTH, self.HEIGHT), "format": "RGB888"},
            lores={"size": (self.WIDTH, self.HEIGHT), "format": "YUV420"},
            controls=cam_controls,
            buffer_count=4,
            queue=False,          # bayat kare dondurme -> dusuk gecikme
        )
        camera.configure(config)

    # ==========================================================
    # Kamera degistirme (/fork/is_up)
    # ==========================================================
    def fork_callback(self, msg):
        # yous: /fork/is_up Bool - True=yuklu/arka, False=yuksuz/on
        use_rear = bool(msg.data)
        if use_rear == self.rear_active:
            return
        self.rear_active = use_rear

        if use_rear:
            self._switch_camera(self.front, self.rear, self.REAR_FLIP, "ARKA")
        else:
            self._switch_camera(self.rear, self.front, self.FRONT_FLIP, "ON")

    def _switch_camera(self, old_cam, new_cam, flip, name):
        with self._cam_lock:
            try:
                old_cam.stop()
            except Exception:
                pass
            try:
                new_cam.start()
                self.active_camera = new_cam
                self.active_flip = flip
            except Exception as e:
                self.get_logger().error(f"Kamera degistirme hatasi: {e}")

    # ==========================================================
    # Kare yakalama: main (bgr) + lores (gri bedava)
    # ==========================================================
    def _grab(self):
        with self._cam_lock:
            cam = self.active_camera
            flip = self.active_flip
            request = cam.capture_request()

        try:
            bgr = request.make_array("main")     # RGB888 -> numpy'de BGR
            yuv = request.make_array("lores")
            gray = np.ascontiguousarray(yuv[:self.HEIGHT, :self.WIDTH])
        finally:
            request.release()

        # Ters monteli kamera -> 180 dondur (hem renk hem gri)
        if flip:
            bgr = cv2.rotate(bgr, cv2.ROTATE_180)
            gray = cv2.rotate(gray, cv2.ROTATE_180)

        return bgr, gray

    # ==========================================================
    # Ana dongu
    # ==========================================================
    def _capture_loop(self):
        while self._running and rclpy.ok():
            try:
                bgr, gray = self._grab()
            except Exception as exc:
                self.get_logger().warn(f"Kare alinamadi (gecis olabilir): {exc}")
                time.sleep(0.02)
                continue

            started = time.monotonic()
            self._frame_no += 1

            # ---- cizgi: her karede (kontrol dongusu bunu bekliyor) ----
            line = self._process_line(bgr)   # yous: renk tespiti -> bgr (eski: gray)
            self._publish_line(line)

            # ---- QR: isci iplige devret (dongu beklemez) ----
            if self._frame_no % self.QR_EVERY_N == 0:
                self.qr_worker.submit(gray)

            self._expire_qr()

            # ---- JPEG + raw yayini (dusuk hizda) ----
            now = time.monotonic()
            if now - self._last_publish >= self._publish_period:
                self._last_publish = now
                self._publish_image(bgr, line)

            self._proc_ms = (time.monotonic() - started) * 1000.0
            self._fps_window.append(now)

    # ==========================================================
    # yous: ESKI cizgi isleme (gri + satir tarama) - saklandi
    # ==========================================================
    # def _process_line(self, gray):
    #     h, w = gray.shape[:2]
    #     image_center = w // 2
    #
    #     blur = cv2.GaussianBlur(gray, self.BLUR_SIZE, 0)
    #     _, binary = cv2.threshold(blur, 100, 255, cv2.THRESH_BINARY_INV)
    #
    #     kernel = cv2.getStructuringElement(cv2.MORPH_RECT, self.KERNEL_SIZE)
    #     binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    #     binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    #
    #     MIN_PX    = 20
    #     MAX_PX    = 200
    #     NUM_ROWS  = 5
    #     MIN_VOTES = 3
    #     base_row  = int(h * self.ROW_RATIO)
    #     centers   = []
    #     best      = None
    #     for i in range(NUM_ROWS):
    #         r = max(0, base_row - i * 3)
    #         line_row = binary[r]
    #         whites = np.where(line_row == 255)[0]
    #         if len(whites) == 0:
    #             continue
    #         splits = np.where(np.diff(whites) > 1)[0]
    #         groups = np.split(whites, splits + 1)
    #         grp    = max(groups, key=len)
    #         lft    = int(grp[0])
    #         rgt    = int(grp[-1])
    #         wdt    = rgt - lft + 1
    #         if wdt < MIN_PX or wdt > MAX_PX:
    #             continue
    #         centers.append((lft + rgt) // 2)
    #         if best is None:
    #             best = {"row": r, "left": lft, "right": rgt}
    #     if len(centers) < MIN_VOTES or best is None:
    #         return None
    #     center = int(sum(centers) / len(centers))
    #     error  = center - image_center
    #     return {
    #         "row": best["row"], "left": best["left"], "right": best["right"],
    #         "center": center, "image_center": image_center,
    #         "error": error,
    #     }

    # ==========================================================
    # yous: YENI cizgi isleme (RENK HSV + MOMENT, alt serit)
    #   Cizgi = 2 mavi kenar + ortada turuncu. BGR kare uzerinde calisir.
    #   Ayni sozlugu dondurur: row/left/right/center/image_center/error
    # ==========================================================
    def _process_line(self, bgr):
        h, w = bgr.shape[:2]
        image_center = w // 2

        # yous: sadece alt serit (robota en yakin bolge) -> moment
        band_top = int(h * self.BAND_TOP_RATIO)
        band = bgr[band_top:h, :]

        hsv = cv2.cvtColor(band, cv2.COLOR_BGR2HSV)

        # yous: mavi + turuncu maskeleri, sonra birlestir
        mask_blue = cv2.inRange(hsv, self.BLUE_LO, self.BLUE_HI)
        mask_orange = cv2.inRange(hsv, self.ORANGE_LO, self.ORANGE_HI)
        mask = cv2.bitwise_or(mask_blue, mask_orange)

        # yous: gurultu temizligi (eski KERNEL_SIZE yeniden kullanildi)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, self.KERNEL_SIZE)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # yous: cizgi genis (~10cm) -> yeterli alan yoksa cizgi yok say
        area = int(cv2.countNonZero(mask))
        if area < self.MIN_AREA:
            return None

        M = cv2.moments(mask, binaryImage=True)
        if M["m00"] <= 0:
            return None

        cx = int(M["m10"] / M["m00"])
        cy_band = int(M["m01"] / M["m00"])
        cy = cy_band + band_top          # yous: tam kare koordinatina esle

        # yous: cizim icin merkez satirdaki sol/sag kenar
        row_local = max(0, min(cy_band, mask.shape[0] - 1))
        xs = np.where(mask[row_local] == 255)[0]
        if xs.size:
            left = int(xs.min())
            right = int(xs.max())
        else:
            left = right = cx

        error = cx - image_center
        return {
            "row": cy, "left": left, "right": right,
            "center": cx, "image_center": image_center,
            "error": error,
        }

    def _publish_state(self):
        # Line durumunu 30 Hz hizinda yayinla
        line_detected = Bool()
        line_detected.data = self._line_stable
        self.pub_line_detected.publish(line_detected)

        line_error = Int32()
        line_error.data = self._line_error
        self.pub_line_error.publish(line_error)

        # QR durumunu 30 Hz hizinda yayinla
        qr_detected = Bool()
        qr_detected.data = self._qr_stable
        self.pub_qr_detected.publish(qr_detected)

        qr_text = String()
        qr_text.data = self._qr_text
        self.pub_qr_text.publish(qr_text)

    def _publish_line(self, line):
        detected = line is not None

        if detected:
            self._line_hit += 1
            self._line_miss = 0
        else:
            self._line_miss += 1
            self._line_hit = 0

        if self._line_hit >= self.LINE_STABLE and not self._line_stable:
            self._line_stable = True
        elif self._line_miss >= self.LINE_STABLE and self._line_stable:
            self._line_stable = False

        if detected:
            self._line_error = int(line["error"])
            payload = {
                "detected": True,
                "row": line["row"], "left": line["left"],
                "right": line["right"], "center": line["center"],
                "image_center": line["image_center"],
            }
        else:
            payload = {"detected": False}

        if payload != self._line_last_overlay:
            self._line_last_overlay = payload
            out = String()
            out.data = json.dumps(payload)
            self.pub_line_overlay.publish(out)

    # ==========================================================
    # QR sonucu (isci iplikten cagrilir)
    # ==========================================================
    def _on_qr_result(self, text, points):
        found = bool(text)

        if found:
            self._qr_hit += 1
            self._qr_miss = 0
        else:
            self._qr_miss += 1
            self._qr_hit = 0

        with self._qr_lock:
            if found:
                self._qr_text = text
                self._qr_points = points
                self._qr_stamp = time.monotonic()

        if self._qr_hit >= self.QR_STABLE and not self._qr_stable:
            self._qr_stable = True
        elif self._qr_miss >= self.QR_STABLE and self._qr_stable:
            self._qr_stable = False
            self._qr_last_text = ""

        if found:
            self._qr_last_text = text

        if found and points is not None:
            payload = {
                "detected": True, "text": text,
                "points": np.asarray(points).reshape(-1, 2).astype(int).tolist(),
            }
        else:
            payload = {"detected": False}

        if payload != self._qr_last_overlay:
            self._qr_last_overlay = payload
            out = String()
            out.data = json.dumps(payload)
            self.pub_qr_overlay.publish(out)

    def _expire_qr(self):
        with self._qr_lock:
            if self._qr_points is None:
                return
            if time.monotonic() - self._qr_stamp > self._qr_hold_sec:
                self._qr_points = None
                self._qr_text = ""

    # ==========================================================
    # Goruntu yayini (JPEG + raw), cizim kucuk kare uzerinde
    # ==========================================================
    def _publish_image(self, bgr, line):
        frame = bgr.copy()
        self._draw_line(frame, line)
        self._draw_qr(frame)

        stamp = self.get_clock().now().to_msg()

        ok, buf = cv2.imencode(
            ".jpg", frame,
            [cv2.IMWRITE_JPEG_QUALITY, self.JPEG_QUALITY]
        )
        if ok:
            jm = CompressedImage()
            jm.header.stamp = stamp
            jm.header.frame_id = "camera_link"
            jm.format = "jpeg"
            jm.data = buf.tobytes()
            self.pub_jpeg.publish(jm)

        raw = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
        raw.header.stamp = stamp
        raw.header.frame_id = "camera_link"
        self.pub_raw.publish(raw)

    # ==========================================================
    # Cizim
    # ==========================================================
    def _draw_line(self, frame, line):
        h, w = frame.shape[:2]
        cx = w // 2
        if line is None:
            return
        row = int(line["row"])
        left = int(line["left"])
        right = int(line["right"])
        center = int(line["center"])
        cv2.line(frame, (0, row), (w, row), self.COLOR_LINE_REF, 1)
        cv2.circle(frame, (left, row), 4, self.COLOR_LINE_EDGE, -1)
        cv2.circle(frame, (right, row), 4, self.COLOR_LINE_EDGE, -1)
        cv2.line(frame, (left, row), (right, row), self.COLOR_LINE, 2)
        cv2.circle(frame, (center, row), 7, self.COLOR_LINE, 2)
        cv2.putText(
            frame, f"Line Error: {line['error']:+d}", (8, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.COLOR_LINE, 2, cv2.LINE_AA,
        )

    def _draw_qr(self, frame):
        with self._qr_lock:
            points = self._qr_points
            text = self._qr_text
        if points is None:
            return
        pts = np.asarray(points).reshape(-1, 1, 2).astype(np.int32)
        cv2.polylines(frame, [pts], True, self.COLOR_QR, 2, cv2.LINE_AA)
        x = int(pts[:, 0, 0].min())
        y = int(pts[:, 0, 1].min())
        cv2.putText(
            frame, text[:24], (x, max(20, y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.COLOR_TEXT, 2, cv2.LINE_AA,
        )

    # ==========================================================
    def _log_stats(self):
        now = time.monotonic()
        self._fps_window = [t for t in self._fps_window if now - t <= 5.0]
        hz = len(self._fps_window) / 5.0
        qr_ms = self.qr_worker.last_ms
        cam = "ARKA" if self.rear_active else "ON"
        self.get_logger().info(
            f"[{cam}] kare {hz:.1f} Hz | kare basi {self._proc_ms:.1f} ms | "
            f"QR {qr_ms:.1f} ms | cizgi={self._line_stable} qr={self._qr_stable}"
        )

    def destroy_node(self):
        self._running = False
        self.qr_worker.stop()
        time.sleep(0.15)
        try:
            self.front.stop()
        except Exception:
            pass
        try:
            self.rear.stop()
        except Exception:
            pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = VisionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
