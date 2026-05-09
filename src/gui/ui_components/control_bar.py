from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, Signal
from .base import UIBaseMixin
from .timeline_widget import TimelineWidget


class ControlBar(QFrame, UIBaseMixin):
    seek_requested = Signal(float)

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._icon_map = []
        self._playing_state = False
        self.setObjectName("controlBar")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        # 时间轴
        self.timeline = TimelineWidget()
        self.timeline.positionChanged.connect(self._on_timeline_seek)
        layout.addWidget(self.timeline)
        # 控制按钮行
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)
        btn_size = 32
        # 参考 SideBar 风格：边创建边加入布局
        self.prev_btn = self._add_icon("prev", tooltip="上一帧", fixed_size=btn_size)
        ctrl_row.addWidget(self.prev_btn)
        self.play_btn = self._add_icon("play", tooltip="播放/暂停", fixed_size=btn_size)
        ctrl_row.addWidget(self.play_btn)
        self.stop_btn = self._add_icon("stop", tooltip="停止", fixed_size=btn_size)
        ctrl_row.addWidget(self.stop_btn)
        self.next_btn = self._add_icon("next", tooltip="下一帧", fixed_size=btn_size)
        ctrl_row.addWidget(self.next_btn)
        ctrl_row.addStretch()
        # 时间显示
        self.time_label = QLabel("00:00:00")
        self.time_label.setObjectName("timeLabel")
        ctrl_row.addWidget(self.time_label)
        self.total_label = QLabel("/ 00:00:00")
        self.total_label.setObjectName("totalLabel")
        ctrl_row.addWidget(self.total_label)
        # 波形切换按钮 (保留原有 emoji 样式)
        self.waveform_toggle = self.create_btn(
            icon_text="🔊", obj_name="toolbarButton",
            fixed_size=28, tooltip="显示/隐藏音频波形",
            checkable=True, checked=True
        )
        self.waveform_toggle.toggled.connect(self._toggle_waveform)
        ctrl_row.addWidget(self.waveform_toggle)
        layout.addLayout(ctrl_row)

    def _add_icon(self, icon_name, **kwargs):
        """统一图标按钮创建方法，与 SideBar 保持一致"""
        btn = self.create_icon_btn(icon_name, **kwargs)
        self._icon_map.append((btn, icon_name))
        return btn

    def _on_timeline_seek(self, pos):
        self.seek_requested.emit(pos)

    def _toggle_waveform(self, checked):
        self.timeline.setMinimumHeight(100 if checked else 40)
        self.timeline.update()

    def update_time(self, current_sec, total_sec):
        self.time_label.setText(self._sec_to_hms(current_sec))
        self.total_label.setText(f"/ {self._sec_to_hms(total_sec)}")

    def update_slider(self, value, max_value):
        if max_value > 0:
            self.timeline.set_position(value / max_value)

    def set_play_icon(self, is_playing):
        """根据播放状态动态切换图标"""
        self._playing_state = is_playing
        icon_name = "pause" if is_playing else "play"
        self._set_icon_on_button(self.play_btn, icon_name)

    def refresh_all_icons(self):
        """刷新所有图标，但跳过播放按钮的初始图标，由状态决定"""
        for btn, name in self._icon_map:
            if btn != self.play_btn:
                self._set_icon_on_button(btn, name)
        # 单独处理播放按钮的刷新
        self.set_play_icon(self._playing_state)

    def enable_controls(self, enabled):
        self.play_btn.setEnabled(enabled)
        self.timeline.setEnabled(enabled)

    def clear_timeline_data(self):
        self.timeline.clear_waveform()
        self.timeline.update()

    @staticmethod
    def _sec_to_hms(seconds):
        seconds = int(seconds)
        h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
        return f"{h:02}:{m:02}:{s:02}"

    def set_processing_progress(self, percent: int):
        if 0 <= percent <= 100:
            self.timeline.set_processing_progress(percent / 100.0)
        else:
            self.timeline.set_processing_progress(-1.0)