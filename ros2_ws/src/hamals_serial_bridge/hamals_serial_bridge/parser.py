# hamals_serial_bridge/parser.py

from typing import List, Dict
from .protocol import decode_line


class LineParser:
    """
    Seri çerçeve protokolü ayrıştırıcısı.

    Seri porttan parça parça gelen veriyi tamponlar; '$' ile yeniden
    hizalanır ve yalnızca tamamlanmış satırları protokole gönderir.
    Geçerli/geçersiz çerçeve sayaçları tanılama amaçlı tutulur.
    """

    def __init__(self):
        self._buffer = ""

        # Statistics
        self.valid_frames = 0
        self.invalid_frames = 0
        self.bytes_received = 0

    def push(self, data: str) -> List[Dict]:
        messages: List[Dict] = []

        if not data:
            return messages

        self.bytes_received += len(data)
        self._buffer += data

        # Gürültü veya eksik veri sonrası ilk çerçeve başlangıcına hizalan.
        start_idx = self._buffer.find('$')
        if start_idx > 0:
            self._buffer = self._buffer[start_idx:]

        # Sonraki çağrıda tamamlanabilecek yarım çerçeveyi tamponda bırak.
        while '\n' in self._buffer:
            line, self._buffer = self._buffer.split('\n', 1)
            line = line.strip()

            if not line:
                continue

            decoded = decode_line(line)

            if decoded is not None:
                self.valid_frames += 1
                messages.append(decoded)
            else:
                # Satır tamamlandı ancak checksum ya da biçim geçersiz.
                self.invalid_frames += 1

        return messages

    def reset(self):
        self._buffer = ""
        self.valid_frames = 0
        self.invalid_frames = 0
        self.bytes_received = 0
