from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from qfluentwidgets import FluentIcon as FIF, NavigationToolButton
from PySide6.QtGui import QFont

class SideBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sideBar")
        self.setFixedWidth(60)
        self.setStyleSheet("background-color: #11151d;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 12, 4, 12)
        layout.setSpacing(10)

        self.app_logo = QLabel("WT")
        self.app_logo.setAlignment(Qt.AlignCenter)
        self.app_logo.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        layout.addWidget(self.app_logo)
        layout.addSpacing(20)

        self.process_btn = NavigationToolButton(FIF.PLAY)
        self.process_btn.setSelected(True)
        self.process_btn.setToolTip("处理")
        layout.addWidget(self.process_btn)

        self.history_btn = NavigationToolButton(FIF.HISTORY)
        self.history_btn.setToolTip("历史记录")
        layout.addWidget(self.history_btn)

        self.settings_btn = NavigationToolButton(FIF.SETTING)
        self.settings_btn.setToolTip("设置")
        layout.addWidget(self.settings_btn)

        layout.addStretch()

        self.version_label = QLabel("v1.0")
        self.version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.version_label)