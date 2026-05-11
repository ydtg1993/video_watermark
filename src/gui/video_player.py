from PySide6.QtCore import Qt, QRect, QPoint, Signal, Slot
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QImage, QBrush, QFont
import cv2


class VideoPlayer(QWidget):
    area_selected = Signal(int, int, int, int)
    HANDLE_SIZE = 8
    MIN_SIZE = 10
    SNAP_DIST = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._frame = None
        self._pixmap = None
        self._video_rect = QRect()
        self._selection_video = QRect()
        self._dragging = False
        self._moving = False
        self._resizing = False
        self._resize_handle = None
        self._origin = QPoint()
        self._drag_offset = QPoint()
        self._preview_mode = 0
        self._video_size = (0, 0)

    def set_preview_mode(self, mode: int):
        self._preview_mode = mode
        self.update()

    def clear_selection(self):
        self._selection_video = QRect()
        self.update()

    def set_frame(self, frame):
        self._frame = frame
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self._pixmap = QPixmap.fromImage(image)
        self._video_size = (w, h)
        self.update()

    @Slot(QImage, int)
    def set_qimage(self, img: QImage, idx: int):
        self._frame = None
        self._pixmap = QPixmap.fromImage(img)
        self._video_size = (img.width(), img.height())
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            # 背景和边框使用与深色主题协调的颜色
            bg_color = QColor("#1e1e1e")
            border_color = QColor("#3a3a3a")
            painter.fillRect(self.rect(), bg_color)
            painter.setPen(QPen(border_color, 1))
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 14, 14)
            if self._pixmap is None:
                return
            scaled = self._pixmap.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            self._video_rect = QRect(x, y, scaled.width(), scaled.height())
            painter.drawPixmap(x, y, scaled)
            if not self._selection_video.isNull():
                rect = self._video_to_widget(self._selection_video)
                self._draw_selection(painter, rect)
            self._draw_guides(painter)
        finally:
            painter.end()

    def _draw_guides(self, painter):
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1, Qt.DashLine))
        cx = self._video_rect.center().x()
        cy = self._video_rect.center().y()
        painter.drawLine(cx, self._video_rect.top(), cx, self._video_rect.bottom())
        painter.drawLine(self._video_rect.left(), cy, self._video_rect.right(), cy)

    def _draw_selection(self, painter, rect):
        painter.setRenderHint(QPainter.Antialiasing)
        overlay = QColor(0, 0, 0, 120)
        painter.fillRect(QRect(self._video_rect.left(), self._video_rect.top(), self._video_rect.width(),
                               rect.top() - self._video_rect.top()), overlay)
        painter.fillRect(QRect(self._video_rect.left(), rect.bottom(), self._video_rect.width(),
                               self._video_rect.bottom() - rect.bottom()), overlay)
        painter.fillRect(
            QRect(self._video_rect.left(), rect.top(), rect.left() - self._video_rect.left(), rect.height()), overlay)
        painter.fillRect(QRect(rect.right(), rect.top(), self._video_rect.right() - rect.right(), rect.height()),
                         overlay)
        painter.setPen(Qt.NoPen)
        if self._preview_mode == 0:
            painter.setBrush(QColor(255, 50, 50, 60))
        elif self._preview_mode == 1:
            painter.setBrush(QColor(50, 150, 255, 60))
        else:
            painter.setBrush(QColor(50, 255, 50, 60))
        painter.drawRect(rect)
        painter.setPen(QColor(255, 255, 255, 200))
        painter.setFont(QFont("Microsoft YaHei", 12))
        text = "🚫 Remove" if self._preview_mode == 0 else "T Text" if self._preview_mode == 1 else "🖼 Image"
        painter.drawText(rect, Qt.AlignCenter, text)
        blue = QColor(59, 130, 246)
        painter.setPen(QPen(blue, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 4, 4)
        painter.setPen(QPen(QColor(255, 255, 255, 70), 1, Qt.DotLine))
        x1 = rect.left() + rect.width() // 3
        x2 = rect.left() + rect.width() * 2 // 3
        y1 = rect.top() + rect.height() // 3
        y2 = rect.top() + rect.height() * 2 // 3
        painter.drawLine(x1, rect.top(), x1, rect.bottom())
        painter.drawLine(x2, rect.top(), x2, rect.bottom())
        painter.drawLine(rect.left(), y1, rect.right(), y1)
        painter.drawLine(rect.left(), y2, rect.right(), y2)
        painter.setPen(QPen(blue, 4))
        corner = 20
        painter.drawLine(rect.left(), rect.top(), rect.left() + corner, rect.top())
        painter.drawLine(rect.left(), rect.top(), rect.left(), rect.top() + corner)
        painter.drawLine(rect.right() - corner, rect.top(), rect.right(), rect.top())
        painter.drawLine(rect.right(), rect.top(), rect.right(), rect.top() + corner)
        painter.drawLine(rect.left(), rect.bottom(), rect.left() + corner, rect.bottom())
        painter.drawLine(rect.left(), rect.bottom() - corner, rect.left(), rect.bottom())
        painter.drawLine(rect.right() - corner, rect.bottom(), rect.right(), rect.bottom())
        painter.drawLine(rect.right(), rect.bottom() - corner, rect.right(), rect.bottom())
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(QPen(blue, 2))
        for handle in self._handle_rects(rect).values():
            painter.drawEllipse(handle)

    def mousePressEvent(self, event):
        if self._pixmap is None:
            return
        pos = event.position().toPoint()
        widget_rect = self._video_to_widget(self._selection_video)
        handles = self._handle_rects(widget_rect)
        for name, h in handles.items():
            if h.contains(pos):
                self._resizing = True
                self._resize_handle = name
                self._origin = pos
                return
        if widget_rect.contains(pos):
            self._moving = True
            self._drag_offset = pos - widget_rect.topLeft()
            return
        if self._video_rect.contains(pos):
            self._dragging = True
            self._origin = pos
            self._selection_video = QRect()

    def mouseMoveEvent(self, event):
        if self._pixmap is None:
            return
        pos = event.position().toPoint()
        if self._dragging:
            rect = QRect(self._origin, pos).normalized()
            rect = rect.intersected(self._video_rect)
            self._selection_video = self._widget_to_video(rect)
            self.update()
            return
        if self._moving:
            rect = self._video_to_widget(self._selection_video)
            new_top_left = pos - self._drag_offset
            rect.moveTopLeft(self._snap(new_top_left))
            self._selection_video = self._widget_to_video(rect)
            self.update()
            return
        if self._resizing:
            rect = self._video_to_widget(self._selection_video)
            modifiers = QApplication.keyboardModifiers()
            center = modifiers & Qt.AltModifier
            aspect = modifiers & Qt.ShiftModifier
            rect = self._apply_resize(rect, pos, center, aspect)
            self._selection_video = self._widget_to_video(rect)
            self.update()
            return

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self._moving = False
        self._resizing = False
        self._resize_handle = None
        r = self._selection_video
        if r.width() > 0 and r.height() > 0:
            self.area_selected.emit(r.x(), r.y(), r.width(), r.height())

    def _apply_resize(self, rect, pos, center=False, aspect=False):
        left, top, right, bottom = rect.left(), rect.top(), rect.right(), rect.bottom()
        if self._resize_handle == "br":
            right, bottom = pos.x(), pos.y()
        elif self._resize_handle == "tr":
            right, top = pos.x(), pos.y()
        elif self._resize_handle == "bl":
            left, bottom = pos.x(), pos.y()
        elif self._resize_handle == "tl":
            left, top = pos.x(), pos.y()
        rect.setRect(left, top, right - left, bottom - top)
        rect = rect.normalized()
        if rect.width() < self.MIN_SIZE: rect.setWidth(self.MIN_SIZE)
        if rect.height() < self.MIN_SIZE: rect.setHeight(self.MIN_SIZE)
        if aspect:
            w = rect.width()
            ratio = self._selection_video.width() / max(self._selection_video.height(), 1)
            rect.setHeight(int(w / ratio))
        if center:
            c = rect.center()
            rect.moveCenter(c)
        return rect.intersected(self._video_rect)

    def _snap(self, p: QPoint):
        v = self._video_rect
        x, y = p.x(), p.y()
        if abs(x - v.left()) < self.SNAP_DIST: x = v.left()
        if abs(x - v.right()) < self.SNAP_DIST: x = v.right()
        if abs(y - v.top()) < self.SNAP_DIST: y = v.top()
        if abs(y - v.bottom()) < self.SNAP_DIST: y = v.bottom()
        return QPoint(x, y)

    def _handle_rects(self, rect):
        s = self.HANDLE_SIZE
        return {
            "tl": QRect(rect.left() - s // 2, rect.top() - s // 2, s, s),
            "tr": QRect(rect.right() - s // 2, rect.top() - s // 2, s, s),
            "bl": QRect(rect.left() - s // 2, rect.bottom() - s // 2, s, s),
            "br": QRect(rect.right() - s // 2, rect.bottom() - s // 2, s, s),
        }

    def _video_to_widget(self, rect):
        if self._pixmap is None or self._video_size == (0, 0):
            return QRect()
        w, h = self._video_size
        sx = self._video_rect.width() / w
        sy = self._video_rect.height() / h
        return QRect(
            int(rect.x() * sx + self._video_rect.x()),
            int(rect.y() * sy + self._video_rect.y()),
            int(rect.width() * sx),
            int(rect.height() * sy),
        )

    def _widget_to_video(self, rect):
        if self._pixmap is None or self._video_size == (0, 0):
            return QRect()
        w, h = self._video_size
        sx = w / self._video_rect.width()
        sy = h / self._video_rect.height()
        return QRect(
            int((rect.x() - self._video_rect.x()) * sx),
            int((rect.y() - self._video_rect.y()) * sy),
            int(rect.width() * sx),
            int(rect.height() * sy),
        )

    def set_selection_by_video_coords(self, x, y, w, h):
        self._selection_video = QRect(int(x), int(y), int(w), int(h))
        self.update()