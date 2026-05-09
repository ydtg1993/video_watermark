import subprocess
import threading
import time
from PySide6.QtCore import QObject, Signal


class GPUMonitor(QObject):
    """
    NVENC / GPU 实时监控（nvidia-smi）
    """
    data_updated = Signal(dict)

    def __init__(self, interval=1.0):
        super().__init__()
        self.interval = interval
        self._running = False

    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False

    def _query(self):
        try:
            cmd = [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,utilization.encoder,utilization.decoder,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits"
            ]
            result = subprocess.check_output(cmd, encoding="utf-8").strip()
            g, enc, dec, mem_u, mem_t, temp = result.split(", ")

            return {
                "gpu": int(g),
                "encoder": int(enc),
                "decoder": int(dec),
                "mem_used": int(mem_u),
                "mem_total": int(mem_t),
                "temp": int(temp)
            }
        except Exception:
            return None

    def _loop(self):
        while self._running:
            data = self._query()
            if data:
                self.data_updated.emit(data)
            time.sleep(self.interval)