import cv2
from PySide6.QtCore import QObject, Slot, Signal
from PySide6.QtGui import QImage
from ...core.frame_reader import FrameReader
from ...core.logger import logger


class PlaybackController(QObject):
    """管理视频加载、播放、跳转逻辑"""
    video_loaded = Signal(str, int, int, float, int)  # path, w, h, fps, total_frames
    frame_changed = Signal(QImage, int)  # img, idx
    play_state_changed = Signal(bool)  # is_playing
    time_updated = Signal(float, float)  # cur_sec, total_sec

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cap = None
        self.video_path = None
        self.total_frames = 0
        self.current_frame_idx = 0
        self.is_playing = False
        self.frame_reader = FrameReader()
        self.frame_reader.frame_ready.connect(self._on_frame_decoded)

    @Slot(str)
    def load_video(self, path: str):
        if self.cap:
            self.cap.release()
            self.frame_reader.stop()
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise RuntimeError("无法打开视频文件")
        self.video_path = path
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = self.cap.get(cv2.CAP_PROP_FPS) or 25
        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.frame_reader.setup(self.cap, self.total_frames, fps)
        self.frame_reader.start()
        self.seek(0)
        self.frame_reader.pause()
        self.video_loaded.emit(path, w, h, fps, self.total_frames)
        logger.info("视频打开成功: %s (%dx%d@%.2ffps)", path, w, h, fps)

    @Slot(QImage, int)
    def _on_frame_decoded(self, img: QImage, idx: int):
        self.current_frame_idx = idx
        self.frame_changed.emit(img, idx)
        fps = self.cap.get(cv2.CAP_PROP_FPS) or 25
        cur_sec = idx / fps
        total_sec = self.total_frames / fps
        self.time_updated.emit(cur_sec, total_sec)

    @Slot()
    def toggle_play(self):
        if not self.cap: return
        if self.is_playing:
            self.frame_reader.pause()
        else:
            self.frame_reader.resume()
        self.is_playing = not self.is_playing
        self.play_state_changed.emit(self.is_playing)

    @Slot(int)
    def seek(self, idx: int):
        if not self.cap:
            return
        new_idx = max(0, min(self.total_frames - 1, idx))
        self.frame_reader.seek(new_idx)
        # 如果当前正在播放，则保持播放；否则暂停
        if not self.is_playing:
            self.frame_reader.pause()
        # 如果之前是播放状态，seek 后 continue 播放（无需操作）

    @Slot(float)
    def seek_percent(self, pos: float):
        if self.total_frames > 0:
            self.seek(int(pos * (self.total_frames - 1)))

    def release(self):
        self.frame_reader.stop()
        if self.cap:
            self.cap.release()
            self.cap = None