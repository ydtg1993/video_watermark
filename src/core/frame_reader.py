# src/core/frame_reader.py
import cv2
from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition
from PySide6.QtGui import QImage


class FrameReader(QThread):
    frame_ready = Signal(QImage, int)  # QImage, frame_index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cap = None
        self.total_frames = 0
        self.fps = 25
        self._running = True
        self._paused = True
        self._seek_idx = -1
        self.mutex = QMutex()
        self.condition = QWaitCondition()

    def setup(self, cap, total_frames, fps):
        self.cap = cap
        self.total_frames = total_frames
        self.fps = max(fps, 1)

    def run(self):
        while self._running:
            self.mutex.lock()
            if self._paused and self._seek_idx < 0:
                self.condition.wait(self.mutex)
            self.mutex.unlock()
            if not self._running:
                break
            # 处理跳转请求
            if self._seek_idx >= 0:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, self._seek_idx)
                self._seek_idx = -1
            ret, frame = self.cap.read()
            if not ret:
                self._paused = True
                continue
            # 转换为 QImage
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
            idx = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            self.frame_ready.emit(img, idx)
            # 控制帧率
            self.msleep(int(1000 / self.fps))

    def seek(self, idx):
        self._seek_idx = idx
        self.resume()

    def resume(self):
        self.mutex.lock()
        self._paused = False
        self.condition.wakeOne()
        self.mutex.unlock()

    def pause(self):
        self.mutex.lock()
        self._paused = True
        self.mutex.unlock()

    def stop(self):
        self._running = False
        self.mutex.lock()
        self._paused = False
        self.condition.wakeAll()
        self.mutex.unlock()
        self.wait()