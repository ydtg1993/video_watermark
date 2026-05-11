from PySide6.QtWidgets import QLabel, QHBoxLayout, QFrame
from qfluentwidgets import PrimaryPushButton, PushButton, FluentIcon as FIF

class TopToolbar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("topToolbar")
        self.setFixedHeight(48)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)

        self.open_btn = PushButton(FIF.FOLDER, ' 打开视频')
        layout.addWidget(self.open_btn)

        self.video_info_label = QLabel("暂无视频")
        self.video_info_label.setObjectName("videoInfoLabel")
        layout.addWidget(self.video_info_label)
        layout.addStretch()

        self.start_btn = PrimaryPushButton(FIF.PLAY, ' 开始处理')
        self.start_btn.setFixedSize(140, 36)
        self.start_btn.setEnabled(False)
        layout.addWidget(self.start_btn)

    def update_video_info(self, filename, width, height, fps):
        self.video_info_label.setText(f"{filename} | {width}x{height} | {fps:.2f} FPS")

    def set_processing_enabled(self, enabled):
        self.start_btn.setEnabled(enabled)