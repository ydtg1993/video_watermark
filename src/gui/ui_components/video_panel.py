"""
视频预览区域 + 进度条覆盖层
包含：VideoPlayer 控件、处理进度条（默认隐藏）
"""
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QPushButton
)
from ..video_player import VideoPlayer
from .base import UIBaseMixin


class VideoPanel(QFrame, UIBaseMixin):
    cancel_clicked = None  # 信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        # 视频播放器
        self.player = VideoPlayer()
        layout.addWidget(self.player, 1)
        # 进度条层（默认隐藏，处理时显示）
        self.progress_frame = QFrame()
        self.progress_frame.setObjectName("progressFrame")
        self.progress_frame.setVisible(False)
        prog_layout = QHBoxLayout(self.progress_frame)
        prog_layout.setContentsMargins(8, 4, 8, 4)
        self.progress_label = QLabel("准备中...")
        self.progress_label.setObjectName("progressLabel")
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setTextVisible(True)
        self.cancel_btn = self.create_btn(
            text="取消", obj_name="cancelButton",
            fixed_size=(80, 28)
        )
        prog_layout.addWidget(self.progress_label)
        prog_layout.addWidget(self.progress_bar, 1)
        prog_layout.addWidget(self.cancel_btn)
        layout.addWidget(self.progress_frame)

    def show_progress(self, visible=True):
        """显示或隐藏进度条"""
        self.progress_frame.setVisible(visible)

    def update_progress(self, value, status_text=None):
        """更新进度（value 为 None 时跳过进度条更新）"""
        if value is not None:
            self.progress_bar.setValue(value)
        if status_text:
            self.progress_label.setText(status_text)

    def reset_progress(self):
        """重置进度条状态"""
        self.progress_bar.setValue(0)
        self.progress_label.setText("准备中...")
        self.show_progress(False)