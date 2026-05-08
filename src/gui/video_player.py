# src/gui/video_player.py
import cv2
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from PySide6.QtWidgets import QLabel, QRubberBand

class VideoPlayer(QLabel):
    area_selected = Signal(int, int, int, int)  # x, y, w, h

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignCenter)
        self.setMouseTracking(True)
        self.setStyleSheet("background-color: black;")
        self._source_frame = None
        self._selection = QRect()          # 当前选择矩形（屏幕坐标）
        self._selecting = False            # 是否正在框选新区域
        self._moving = False               # 是否正在移动现有矩形
        self._origin = QPoint()
        self._drag_offset = QPoint()

        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        self.rubber_band.hide()

    def set_frame(self, frame_bgr):
        self._source_frame = frame_bgr.copy()
        self._display_frame()

    def _display_frame(self):
        if self._source_frame is None:
            return
        rgb = cv2.cvtColor(self._source_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qt_img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.setPixmap(QPixmap.fromImage(qt_img).scaled(
            self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or self.pixmap() is None:
            return
        pos = event.position().toPoint()

        # 1. 如果点击在已有矩形内部 → 开始移动模式
        if self._selection.isValid() and self._selection.contains(pos):
            self._moving = True
            self._drag_offset = pos - self._selection.topLeft()
            self.setCursor(Qt.ClosedHandCursor)
            return

        # 2. 否则开始新框选
        self._origin = pos
        self._selecting = True
        self.rubber_band.setGeometry(QRect(self._origin, self._origin))
        self.rubber_band.show()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()

        if self._selecting:
            self.rubber_band.setGeometry(
                QRect(self._origin, pos).normalized()
            )
        elif self._moving:
            # 计算新位置并限制在 label 范围内
            new_top_left = pos - self._drag_offset
            new_rect = QRect(new_top_left, self._selection.size())
            # 限制边界
            max_x = self.width() - new_rect.width()
            max_y = self.height() - new_rect.height()
            if new_rect.left() < 0:
                new_rect.moveLeft(0)
            elif new_rect.left() > max_x:
                new_rect.moveLeft(max_x)
            if new_rect.top() < 0:
                new_rect.moveTop(0)
            elif new_rect.top() > max_y:
                new_rect.moveTop(max_y)
            self._selection = new_rect
            self.update()  # 重绘绿色矩形

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return

        if self._selecting:
            self._selecting = False
            self.rubber_band.hide()
            rect = QRect(self._origin, event.position().toPoint()).normalized()
            if rect.width() > 5 and rect.height() > 5:
                self._selection = rect
                self._emit_area_from_rect(rect)
            self.update()

        elif self._moving:
            self._moving = False
            self.setCursor(Qt.ArrowCursor)
            # 移动结束，发送新坐标
            self._emit_area_from_rect(self._selection)
            self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._source_frame is not None:
            self._display_frame()
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._selection.isNull() and self._source_frame is not None:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(0, 255, 0), 2))
            # 当正在框选时，rubber_band 已经显示了，这里再画一个可能会重复，但没关系
            # 正常模式画实线矩形
            painter.drawRect(self._selection)

    def _emit_area_from_rect(self, rect: QRect):
        """将屏幕坐标的矩形映射回视频坐标并发射信号"""
        if self._source_frame is None:
            return
        img_h, img_w = self._source_frame.shape[:2]
        label_w = self.width()
        label_h = self.height()
        scale = min(label_w / img_w, label_h / img_h)
        offset_x = (label_w - img_w * scale) / 2
        offset_y = (label_h - img_h * scale) / 2

        video_x = int((rect.x() - offset_x) / scale)
        video_y = int((rect.y() - offset_y) / scale)
        video_w = int(rect.width() / scale)
        video_h = int(rect.height() / scale)

        # 限制不超出视频边界
        video_x = max(0, min(video_x, img_w - 1))
        video_y = max(0, min(video_y, img_h - 1))
        video_w = max(1, min(video_w, img_w - video_x))
        video_h = max(1, min(video_h, img_h - video_y))

        self.area_selected.emit(video_x, video_y, video_w, video_h)