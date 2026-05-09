"""模态进度对话框 - 用于独立窗口展示进度"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton
)
from PySide6.QtCore import Qt


class ProgressDialog(QDialog):
    """处理进度弹窗（非模态，允许后台运行）"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("正在处理...")
        self.setWindowFlags(
            Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint
        )
        self.setFixedSize(480, 140)
        self.setWindowModality(Qt.ApplicationModal)  # 改为应用级模态防止误操作
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        self.label = QLabel("准备中...")
        self.label.setObjectName("progressDialogTitle")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(True)
        self.bar.setMinimumHeight(24)
        self.cancel_btn = QPushButton("取消任务")
        self.cancel_btn.setObjectName("dangerButton")
        self.cancel_btn.setMinimumHeight(36)
        self.cancel_btn.setFixedWidth(120)
        layout.addWidget(self.label)
        layout.addWidget(self.bar)
        layout.addStretch()
        layout.addWidget(self.cancel_btn, alignment=Qt.AlignRight)

    def update_progress(self, value: int, status: str = None):
        """更新进度值和状态文本"""
        self.bar.setValue(value)
        if status:
            self.label.setText(status)

    def reset(self):
        """重置为初始状态"""
        self.bar.setValue(0)
        self.label.setText("准备中...")