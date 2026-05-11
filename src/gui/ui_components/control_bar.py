from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal
from qfluentwidgets import ToolButton, FluentIcon as FIF, TogglePushButton
from .timeline_widget import TimelineWidget

class ControlBar(QFrame):
    seek_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("controlBar")
        self._playing = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        self.timeline = TimelineWidget()
        self.timeline.positionChanged.connect(lambda pos: self.seek_requested.emit(pos))
        layout.addWidget(self.timeline)

        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(4)

        self.prev_btn = ToolButton(FIF.LEFT_ARROW)
        ctrl_row.addWidget(self.prev_btn)
        self.play_btn = ToolButton(FIF.PLAY)
        ctrl_row.addWidget(self.play_btn)
        self.stop_btn = ToolButton(FIF.CANCEL)
        ctrl_row.addWidget(self.stop_btn)
        self.next_btn = ToolButton(FIF.RIGHT_ARROW)
        ctrl_row.addWidget(self.next_btn)

        ctrl_row.addStretch()
        self.time_label = QLabel("00:00:00")
        self.total_label = QLabel("/ 00:00:00")
        ctrl_row.addWidget(self.time_label)
        ctrl_row.addWidget(self.total_label)

        self.waveform_toggle = TogglePushButton(FIF.MUSIC, '', self)
        self.waveform_toggle.setChecked(True)
        self.waveform_toggle.toggled.connect(
            lambda checked: self.timeline.setMinimumHeight(100 if checked else 40)
        )
        ctrl_row.addWidget(self.waveform_toggle)
        layout.addLayout(ctrl_row)

    def set_play_icon(self, is_playing):
        self._playing = is_playing
        self.play_btn.setIcon(FIF.PAUSE if is_playing else FIF.PLAY)

    def update_time(self, cur, total):
        self.time_label.setText(self._sec_to_hms(cur))
        self.total_label.setText(f"/ {self._sec_to_hms(total)}")

    def update_slider(self, value, max_val):
        if max_val > 0:
            self.timeline.set_position(value / max_val)

    def enable_controls(self, enabled):
        self.play_btn.setEnabled(enabled)
        self.timeline.setEnabled(enabled)

    def set_processing_progress(self, percent):
        self.timeline.set_processing_progress(percent / 100.0 if 0 <= percent <= 100 else -1.0)

    @staticmethod
    def _sec_to_hms(seconds):
        seconds = int(seconds)
        h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
        return f"{h:02}:{m:02}:{s:02}"