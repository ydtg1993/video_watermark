import os
import time
import threading

from PySide6.QtCore import QObject, Signal

from .ffmpeg import run_ffmpeg_command, terminate_process
from .logger import logger


class FFmpegRunner(QObject):
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self.process = None
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        terminate_process(self.process)

    def run(self, cmd: list[str], duration: float, output_path: str):
        try:
            self.status.emit("FFmpeg处理中...")
            self.process = run_ffmpeg_command(cmd)

            last_progress = 0

            while True:
                if self._cancelled:
                    terminate_process(self.process)
                    self.finished.emit(False, "任务已取消")
                    return

                line = self.process.stdout.readline()
                if not line:
                    if self.process.poll() is not None:
                        break
                    continue

                line = line.strip()
                if "=" not in line:
                    continue

                k, v = line.split("=", 1)
                if k == "out_time_ms" and duration > 0:
                    try:
                        sec = int(v) / 1_000_000
                        percent = int((sec / duration) * 100)
                        percent = max(0, min(100, percent))

                        # 限频 + 防抖
                        if abs(percent - last_progress) >= 1:
                            last_progress = percent
                            self.progress.emit(percent)
                    except:
                        pass

            code = self.process.wait()

            if self._cancelled:
                self.finished.emit(False, "已取消")
                return

            if code != 0:
                self.finished.emit(False, f"FFmpeg失败 code={code}")
                return

            if not os.path.exists(output_path):
                self.finished.emit(False, "输出文件不存在")
                return

            self.progress.emit(100)
            self.finished.emit(True, output_path)

        except Exception as e:
            self.finished.emit(False, str(e))