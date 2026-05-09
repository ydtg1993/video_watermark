"""
底部控制栏 - 嵌入增强型时间轴
"""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QWidget
from PySide6.QtCore import Qt, Signal
from .base import UIBaseMixin
from .timeline_widget import TimelineWidget  # 修复：添加相对导入


class ControlBar(QFrame, UIBaseMixin):
    seek_requested = Signal(float)
    _playing_state  = False

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._icon_map = []
        self.setObjectName("controlBar")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        # 增强型时间轴
        self.timeline = TimelineWidget()
        self.timeline.positionChanged.connect(self._on_timeline_seek)
        layout.addWidget(self.timeline)
        # 控制按钮行
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)
        btn_size = 32
        self.play_btn = self.create_btn(icon_text="▶", fixed_size=btn_size)
        self.prev_btn = self.create_btn(icon_text="⏮", fixed_size=btn_size)
        self.next_btn = self.create_btn(icon_text="⏭", fixed_size=btn_size)
        self.stop_btn = self.create_btn(icon_text="⏹", fixed_size=btn_size)  # 新增停止按钮
        ctrl_row.addWidget(self.play_btn)
        ctrl_row.addWidget(self.prev_btn)
        ctrl_row.addWidget(self.next_btn)
        ctrl_row.addWidget(self.stop_btn)
        ctrl_row.addStretch()
        # 时间显示
        self.time_label = QLabel("00:00:00")
        self.time_label.setObjectName("timeLabel")
        self.total_label = QLabel("/ 00:00:00")
        self.total_label.setObjectName("totalLabel")
        # 波形切换按钮
        self.waveform_toggle = self.create_btn(
            icon_text="🔊", obj_name="toolbarButton",
            fixed_size=28, tooltip="显示/隐藏音频波形",
            checkable=True, checked=True
        )
        self.waveform_toggle.toggled.connect(self._toggle_waveform)
        ctrl_row.addWidget(self.time_label)
        ctrl_row.addWidget(self.total_label)
        ctrl_row.addWidget(self.waveform_toggle)
        layout.addLayout(ctrl_row)

    def _on_timeline_seek(self, pos):
        self.seek_requested.emit(pos)

    def _toggle_waveform(self, checked):
        if checked:
            self.timeline.setMinimumHeight(100)
        else:
            self.timeline.setMinimumHeight(40)
        self.timeline.update()

    def update_time(self, current_sec, total_sec):
        self.time_label.setText(self._sec_to_hms(current_sec))
        self.total_label.setText(f"/ {self._sec_to_hms(total_sec)}")

    def update_slider(self, value, max_value):
        if max_value > 0:
            pos = value / max_value
            self.timeline.set_position(pos)

    def set_play_icon(self, is_playing):
        self._playing_state = is_playing
        icon = "pause" if is_playing else "play"
        self._set_icon_on_button(self.play_btn, icon)

    def refresh_all_icons(self):
        for btn, name in self._icon_map:
            self._set_icon_on_button(btn, name)
        # 播放按钮保持当前状态
        self.set_play_icon(self._playing_state)

    def enable_controls(self, enabled):
        self.play_btn.setEnabled(enabled)
        self.timeline.setEnabled(enabled)

    def clear_timeline_data(self):
        self.timeline.clear_waveform()
        self.timeline.thumbnails = []
        self.timeline.update()

    @staticmethod
    def _sec_to_hms(seconds):
        seconds = int(seconds)
        h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
        return f"{h:02}:{m:02}:{s:02}"
