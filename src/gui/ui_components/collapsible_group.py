"""可折叠分组框 - 用于未来可能的设置项折叠需求"""
from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QPushButton, QFrame
from PySide6.QtCore import QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont


class CollapsibleGroup(QGroupBox):
    """带折叠功能的 GroupBox"""

    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self._collapsed = False
        self._content = QFrame()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(8)
        # 折叠按钮
        self._toggle_btn = QPushButton("▼")
        self._toggle_btn.setFixedSize(24, 24)
        self._toggle_btn.setFlat(True)
        self._toggle_btn.setFont(QFont("Microsoft YaHei", 9))
        self._toggle_btn.clicked.connect(self.toggle)
        # 布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        title_container = QFrame()
        title_container.setObjectName("collapsibleHeader")
        title_layout = QVBoxLayout(title_container)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.addWidget(self._toggle_btn)
        main_layout.addWidget(title_container)
        main_layout.addWidget(self._content)
        # 动画
        self._animation = QPropertyAnimation(self._content, b"maximumHeight")
        self._animation.setDuration(250)
        self._animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.set_collapsed(False)

    @property
    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def toggle(self):
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, state: bool):
        self._collapsed = state
        if state:
            self._animation.setEndValue(0)
            self._toggle_btn.setText("▶")
        else:
            self._content.adjustSize()
            self._animation.setEndValue(self._content.sizeHint().height())
            self._toggle_btn.setText("▼")
        self._animation.start()
        self._content.setEnabled(not state)