#!/usr/bin/env python3
"""
HAMAL - PLC Simulatoru  (Raspberry Pi / herhangi bir PC'de calisir)
===================================================================
Gercek yarisma PLC'sini taklit eder (TEKNOFEST ek sartname protokolu).

  UDP server : 192.168.100.100 : 1515   (varsayilan)
  Robot -> PLC : PAKET_TX (7 byte) 1 Hz
  PLC -> Robot : PAKET_RX (3 byte)   (her TX'e cevap)

PAKET_TX (<BBBhh): durum, alim(1-3), birak(1-3), X=int16(x*100), Y=int16(y*100)
PAKET_RX (<BBB)  : alim(1-3), birak(1-3), kontrol(1 BEKLE / 2 BASLA-DEVAM)

MODLAR
------
  --auto  (varsayilan): gercek PLC gibi davranir
      1) robot hazir (durum=1) gorunce rastgele (ya da sabit) gorev gonderir
      2) robot kapida (durum=5) gorunce door_delay kadar BEKLE der, sonra BASLA (izin)
      3) iki kapi gecisini de yonetir, gorev bitince (loop ise) yeni gorev
  --manual : operator klavyeden yonetir
      t A1 B1  -> gorev ayarla     w -> BEKLE gonder     s -> BASLA gonder
      q -> cikis

KULLANIM
--------
  python3 plc_simulator.py
  python3 plc_simulator.py --pickup A2 --dropoff B3 --door-delay 3
  python3 plc_simulator.py --manual
  python3 plc_simulator.py --host 0.0.0.0 --port 1515 --loop
"""

import argparse
import random
import socket
import struct
import threading
import time

PICKUP = {1: 'A1', 2: 'A2', 3: 'A3'}
DROPOFF = {1: 'B1', 2: 'B2', 3: 'B3'}
STATUS = {1: 'idle/hazir', 2: 'islniyor', 3: 'yuksuz-hareket',
          4: 'yuklu-hareket', 5: 'PLC-BEKLENIYOR(kapi)', 6: 'bitti/donuyor',
          7: 'HATA', 8: 'ACIL-STOP'}
PICK_B = {'A1': 1, 'A2': 2, 'A3': 3}
DROP_B = {'B1': 1, 'B2': 2, 'B3': 3}


class PlcSim:
    def __init__(self, args):
        self.args = args
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((args.host, args.port))
        self.robot_addr = None
        self.lock = threading.Lock()

        # cevap paketi (her TX'e gonderilir)
        self.resp_pu = 0
        self.resp_do = 0
        self.resp_ctrl = 1        # 1 BEKLE

        # auto durum makinesi
        self.assigned = False
        self.moved = False
        self.last_status = 0
        self.door_enter = None
        self.done = False

        print('=' * 60)
        print(f'PLC SIMULATORU dinliyor  {args.host}:{args.port}')
        print(f'mod: {"AUTO (gercek PLC gibi)" if args.auto else "MANUAL"}')
        if args.auto:
            tgt = (f'{args.pickup}->{args.dropoff}' if args.pickup
                   else 'RASTGELE')
            print(f'gorev: {tgt} | kapi bekleme: {args.door_delay}s | '
                  f'loop: {args.loop}')
        print('=' * 60)

    # -------- yardimci --------
    def _pick_task(self):
        if self.args.pickup and self.args.dropoff:
            return PICK_B[self.args.pickup], DROP_B[self.args.dropoff]
        return random.randint(1, 3), random.randint(1, 3)

    def _auto_logic(self, st):
        """Alinan duruma gore cevap paketini (resp) gunceller (gercek PLC gibi)."""
        now = time.monotonic()
        if not self.assigned:
            if st == 1:            # robot hazir -> gorev ver + BASLA
                pu, do = self._pick_task()
                self.resp_pu, self.resp_do, self.resp_ctrl = pu, do, 2
                self.assigned = True
                self.moved = False
                print(f'>> GOREV VERILDI: {PICKUP[pu]} -> {DROPOFF[do]} (BASLA)')
            else:
                self.resp_pu, self.resp_do, self.resp_ctrl = 0, 0, 1
            self.last_status = st
            return

        if st in (3, 4, 5, 6):
            self.moved = True

        # kapiya giris tespiti
        if st == 5 and self.last_status != 5:
            self.door_enter = now
            print('>> ROBOT KAPIDA (durum=5) -> BEKLE')

        if st == 5:
            if self.door_enter and (now - self.door_enter) >= self.args.door_delay:
                self.resp_ctrl = 2          # izin ver
                if self.last_status == 5 and self.resp_ctrl == 2:
                    pass
                print('>> KAPI IZNI: BASLA/GEC')
            else:
                self.resp_ctrl = 1          # bekle
        elif st == 1 and self.moved:
            # gorev tamamlandi (hareket etti, idle'a dondu)
            print('>> GOREV TAMAMLANDI.')
            if self.args.loop:
                self.assigned = False
                self.resp_pu, self.resp_do, self.resp_ctrl = 0, 0, 1
            else:
                self.done = True
                self.resp_ctrl = 1
        else:
            self.resp_ctrl = 2              # devam et

        self.last_status = st

    # -------- RX (robottan TX) --------
    def rx_loop(self):
        while True:
            data, addr = self.sock.recvfrom(64)
            self.robot_addr = addr
            if len(data) != 7:
                print(f'! beklenmeyen paket {len(data)}B: {data.hex()}')
                continue
            st, pu, do, xi, yi = struct.unpack('<BBBhh', data)
            print(f'RX <- durum={st}({STATUS.get(st,"?")}) '
                  f'alim={PICKUP.get(pu,"-")} birak={DROPOFF.get(do,"-")} '
                  f'X={xi/100.0:.2f} Y={yi/100.0:.2f}')
            with self.lock:
                if self.args.auto:
                    self._auto_logic(st)
                pkt = struct.pack('<BBB', self.resp_pu, self.resp_do, self.resp_ctrl)
            self.sock.sendto(pkt, addr)
            print(f'TX -> alim={self.resp_pu} birak={self.resp_do} '
                  f'kontrol={self.resp_ctrl}'
                  f'({"BEKLE" if self.resp_ctrl==1 else "BASLA"})')

    # -------- manuel komutlar --------
    def manual_loop(self):
        print('komutlar: t A1 B1 | w (bekle) | s (basla) | q')
        while True:
            try:
                line = input('> ').strip().split()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            c = line[0].lower()
            with self.lock:
                if c == 'q':
                    break
                elif c == 't' and len(line) == 3:
                    p, d = PICK_B.get(line[1].upper()), DROP_B.get(line[2].upper())
                    if p and d:
                        self.resp_pu, self.resp_do = p, d
                        print(f'gorev: {line[1]}->{line[2]} (s ile gonder)')
                    else:
                        print('! ornek: t A1 B1')
                elif c == 'w':
                    self.resp_ctrl = 1
                    print('kontrol=1 BEKLE')
                elif c == 's':
                    self.resp_ctrl = 2
                    print('kontrol=2 BASLA')
                else:
                    print('! komut: t A1 B1 | w | s | q')
        self.sock.close()

    def run(self):
        threading.Thread(target=self.rx_loop, daemon=True).start()
        if self.args.auto:
            print('AUTO calisiyor. Robot baglaninca gorev otomatik gonderilir.')
            try:
                while not self.done:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                pass
            print('cikis.')
        else:
            self.manual_loop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='0.0.0.0')
    ap.add_argument('--port', type=int, default=1515)
    ap.add_argument('--pickup', default=None, help='A1/A2/A3 (bos=rastgele)')
    ap.add_argument('--dropoff', default=None, help='B1/B2/B3 (bos=rastgele)')
    ap.add_argument('--door-delay', type=float, default=3.0, dest='door_delay')
    ap.add_argument('--loop', action='store_true')
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument('--auto', dest='auto', action='store_true')
    grp.add_argument('--manual', dest='auto', action='store_false')
    ap.set_defaults(auto=True)
    args = ap.parse_args()
    if bool(args.pickup) ^ bool(args.dropoff):
        ap.error('--pickup ve --dropoff birlikte verilmeli')
    PlcSim(args).run()


if __name__ == '__main__':
    main()
