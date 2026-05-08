from PySide6.QtCore import (
    Qt,
    QRect,
    QPoint,
    Signal
)

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPen,
    QPixmap,
    QImage,
    QBrush
)

import cv2


class VideoPlayer(QWidget):
    area_selected = Signal(int, int, int, int)

    HANDLE_SIZE = 8
    MIN_SIZE = 10

    SNAP_DIST = 12   # ✔ 吸附距离

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setMouseTracking(True)

        self._frame = None
        self._pixmap = None

        self._video_rect = QRect()

        self._selection_video = QRect()

        # 状态
        self._dragging = False
        self._moving = False
        self._resizing = False
        self._resize_handle = None

        self._origin = QPoint()
        self._drag_offset = QPoint()

        # ✔ 多选框（预留）
        self._selections = []

    # =========================
    # Frame
    # =========================

    def set_frame(self, frame):
        self._frame = frame

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        h, w, ch = rgb.shape
        bytes_per_line = ch * w

        image = QImage(
            rgb.data,
            w,
            h,
            bytes_per_line,
            QImage.Format_RGB888
        )

        self._pixmap = QPixmap.fromImage(image)
        self.update()

    # =========================
    # Paint
    # =========================

    def paintEvent(self, event):
        painter = QPainter(self)

        try:
            painter.fillRect(self.rect(), QColor(20, 20, 20))

            if self._pixmap is None:
                return

            scaled = self._pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

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
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1))

        cx = self._video_rect.center().x()
        cy = self._video_rect.center().y()

        # 中心线
        painter.drawLine(cx, self._video_rect.top(), cx, self._video_rect.bottom())
        painter.drawLine(self._video_rect.left(), cy, self._video_rect.right(), cy)

    # =========================
    # Mouse
    # =========================

    def mousePressEvent(self, event):
        if self._frame is None:
            return

        pos = event.position().toPoint()
        widget_rect = self._video_to_widget(self._selection_video)

        handles = self._handle_rects(widget_rect)

        # resize
        for name, h in handles.items():
            if h.contains(pos):
                self._resizing = True
                self._resize_handle = name
                self._origin = pos
                return

        # move
        if widget_rect.contains(pos):
            self._moving = True
            self._drag_offset = pos - widget_rect.topLeft()
            return

        # create
        if self._video_rect.contains(pos):
            self._dragging = True
            self._origin = pos
            self._selection_video = QRect()

    def mouseMoveEvent(self, event):
        if self._frame is None:
            return

        pos = event.position().toPoint()

        # =========================
        # create
        # =========================
        if self._dragging:
            rect = QRect(self._origin, pos).normalized()
            rect = rect.intersected(self._video_rect)
            self._selection_video = self._widget_to_video(rect)
            self.update()
            return

        # =========================
        # move + snap
        # =========================
        if self._moving:
            rect = self._video_to_widget(self._selection_video)

            new_top_left = pos - self._drag_offset
            rect.moveTopLeft(self._snap(new_top_left))

            self._selection_video = self._widget_to_video(rect)
            self.update()
            return

        # =========================
        # resize（Shift / Alt 支持）
        # =========================
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

    # =========================
    # Resize (Shift / Alt)
    # =========================

    def _apply_resize(self, rect, pos, center=False, aspect=False):
        left = rect.left()
        right = rect.right()
        top = rect.top()
        bottom = rect.bottom()

        if self._resize_handle == "br":
            right = pos.x()
            bottom = pos.y()
        elif self._resize_handle == "tr":
            right = pos.x()
            top = pos.y()
        elif self._resize_handle == "bl":
            left = pos.x()
            bottom = pos.y()
        elif self._resize_handle == "tl":
            left = pos.x()
            top = pos.y()

        # 先设置为可能负的矩形
        rect.setRect(left, top, right - left, bottom - top)

        # 归一化，确保宽高为正
        rect = rect.normalized()

        if rect.width() < self.MIN_SIZE:
            rect.setWidth(self.MIN_SIZE)
        if rect.height() < self.MIN_SIZE:
            rect.setHeight(self.MIN_SIZE)

        # Shift 等比
        if aspect:
            w = rect.width()
            h = rect.height()
            if h > 0:
                ratio = w / max(h, 1)
                rect.setHeight(int(w / ratio))

        # Alt 中心缩放
        if center:
            c = rect.center()
            rect.moveCenter(c)

        # 限制在视频区域内
        rect = rect.intersected(self._video_rect)

        return rect

    # =========================
    # Snap（吸附）
    # =========================

    def _snap(self, p: QPoint):
        v = self._video_rect

        x = p.x()
        y = p.y()

        if abs(x - v.left()) < self.SNAP_DIST:
            x = v.left()
        if abs(x - v.right()) < self.SNAP_DIST:
            x = v.right()

        if abs(y - v.top()) < self.SNAP_DIST:
            y = v.top()
        if abs(y - v.bottom()) < self.SNAP_DIST:
            y = v.bottom()

        return QPoint(x, y)

    def _snap_rect(self, rect: QRect):
        rect.moveTopLeft(self._snap(rect.topLeft()))
        rect.moveBottomRight(self._snap(rect.bottomRight()))
        return rect

    # =========================
    # Helpers（保持你原逻辑）
    # =========================

    def _handle_rects(self, rect):
        s = self.HANDLE_SIZE

        return {
            "tl": QRect(rect.left()-s//2, rect.top()-s//2, s, s),
            "tr": QRect(rect.right()-s//2, rect.top()-s//2, s, s),
            "bl": QRect(rect.left()-s//2, rect.bottom()-s//2, s, s),
            "br": QRect(rect.right()-s//2, rect.bottom()-s//2, s, s),
        }

    def _video_to_widget(self, rect):
        if self._frame is None:
            return QRect()

        h, w = self._frame.shape[:2]

        sx = self._video_rect.width() / w
        sy = self._video_rect.height() / h

        return QRect(
            int(rect.x()*sx + self._video_rect.x()),
            int(rect.y()*sy + self._video_rect.y()),
            int(rect.width()*sx),
            int(rect.height()*sy),
        )

    def set_selection_by_video_coords(self, x, y, w, h):
        self._selection_video = QRect(int(x), int(y), int(w), int(h))
        self.update()

    def _widget_to_video(self, rect):
        if self._frame is None:
            return QRect()

        h, w = self._frame.shape[:2]

        sx = w / self._video_rect.width()
        sy = h / self._video_rect.height()

        return QRect(
            int((rect.x()-self._video_rect.x())*sx),
            int((rect.y()-self._video_rect.y())*sy),
            int(rect.width()*sx),
            int(rect.height()*sy),
        )

    def _draw_selection(self, painter, rect):
        painter.setRenderHint(QPainter.Antialiasing)

        # 半透明遮罩
        painter.fillRect(rect, QColor(0, 255, 0, 40))

        # 边框
        painter.setPen(QPen(QColor(0, 255, 0), 2))
        painter.drawRect(rect)

        # handles
        painter.setBrush(QBrush(QColor(255, 255, 255)))

        for handle in self._handle_rects(rect).values():
            painter.drawRect(handle)