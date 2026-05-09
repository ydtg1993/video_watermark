"""
增强版时间轴 - 支持音频波形可视化
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QRect, Signal, QThread, QPoint, Slot  # 修复：添加 Slot
from PySide6.QtGui import QPainter, QColor, QPixmap, QImage, QBrush, QPen, QPolygon


class WaveformGenerator(QThread):
    """后台生成波形图"""
    waveform_ready = Signal(object)

    def __init__(self, video_path, width=1200, height=80):
        super().__init__()
        self.video_path = video_path
        self.width = width
        self.height = height
        self._cancelled = False

    def run(self):
        try:
            import subprocess
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
                temp_path = f.name
            cmd = [
                "ffmpeg", "-i", self.video_path,
                "-filter_complex",
                f"showwavespic=s={self.width}x{self.height}:colors=white@0.5",
                "-frames:v", "1",
                "-y", temp_path
            ]
            proc = subprocess.run(cmd, capture_output=True, timeout=10)
            if proc.returncode == 0 and os.path.exists(temp_path):
                pixmap = QPixmap(temp_path)
                if not pixmap.isNull():
                    self.waveform_ready.emit(pixmap)
            try:
                os.unlink(temp_path)
            except:
                pass
        except Exception as e:
            print(f"Waveform generation failed: {e}")
        finally:
            self.deleteLater()


class TimelineWidget(QWidget):
    positionChanged = Signal(float)

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(100)
        self.setMaximumHeight(140)
        self.duration = 1.0
        self.position = 0.0
        self.thumbnails = []
        self.waveform_pixmap = None
        self._waveform_thread = None
        self.setStyleSheet("background-color: transparent;")  # 修复：透明背景
        self.processing_progress = -1.0

    def set_duration(self, d):
        self.duration = max(d, 0.001)
        self.update()

    def set_position(self, p):
        self.position = max(0, min(1, p))
        self.update()

    def set_thumbnails(self, thumbs):
        self.thumbnails = thumbs
        self.update()

    def generate_waveform(self, video_path):
        if self._waveform_thread and self._waveform_thread.isRunning():
            return
        self._waveform_thread = WaveformGenerator(
            video_path, width=self.width() or 800, height=60
        )
        self._waveform_thread.waveform_ready.connect(self._on_waveform_ready)
        self._waveform_thread.start()

    @Slot(object)  # 修复：使用 pyqtSignal 对应的 Slot 装饰器
    def _on_waveform_ready(self, pixmap):
        self.waveform_pixmap = pixmap
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._update_pos(e.position().x())

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self._update_pos(e.position().x())

    def _update_pos(self, x):
        self.position = max(0, min(1, x / self.width()))
        self.positionChanged.emit(self.position)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        # 背景轨道
        track_rect = QRect(4, 20, rect.width() - 8, rect.height() - 36)
        p.fillRect(track_rect, QColor("#161b22"))
        p.setPen(QPen(QColor("#30363d"), 1))
        p.drawRoundedRect(track_rect, 4, 4)

        # 波形绘制
        if self.waveform_pixmap and not self.waveform_pixmap.isNull():
            wave_y = rect.height() // 2
            scaled = self.waveform_pixmap.scaled(
                track_rect.width(), track_rect.height(),
                Qt.IgnoreAspectRatio, Qt.SmoothTransformation
            )
            p.drawPixmap(track_rect.x(), wave_y, scaled)

        # 播放头
        head_x = int(self.position * rect.width())
        p.setPen(QPen(QColor("#5ea2ff"), 2))
        p.drawLine(head_x, 0, head_x, rect.height())
        triangle = QPolygon([QPoint(head_x - 6, 0), QPoint(head_x + 6, 0), QPoint(head_x, 12)])
        p.setBrush(QBrush(QColor("#5ea2ff")))
        p.drawPolygon(triangle)

        # 时间刻度
        p.setPen(QColor("#484f58"))
        for i in range(11):
            x = int(rect.width() * i / 10)
            p.drawLine(x, rect.height() - 12, x, rect.height() - 8)
            if i % 2 == 0:
                sec = int(self.duration * i / 10)
                p.drawText(x - 15, rect.height() - 2, f"{sec}s")

        # ========== 处理进度拨片（深红色，必须在 p.end() 之前） ==========
        if self.processing_progress >= 0:
            proc_x = int(self.processing_progress * rect.width())
            # 深红色竖线
            p.setPen(QPen(QColor(180, 0, 0, 200), 3))
            p.drawLine(proc_x, 0, proc_x, rect.height())
            # 三角箭头
            arrow_tri = QPolygon([
                QPoint(proc_x - 5, 0),
                QPoint(proc_x + 5, 0),
                QPoint(proc_x, 8)
            ])
            p.setBrush(QBrush(QColor(180, 0, 0, 220)))
            p.setPen(Qt.NoPen)
            p.drawPolygon(arrow_tri)

        p.end()  # 所有绘制在此结束

    def clear_waveform(self):
        self.waveform_pixmap = None
        self.update()

    def set_processing_progress(self, value: float):
        """设置处理进度（0~1），-1 表示隐藏"""
        self.processing_progress = max(0.0, min(1.0, value)) if value >= 0 else -1.0
        self.update()

