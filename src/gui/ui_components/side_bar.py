"""
左侧导航栏组件 (60px 宽)
包含：Logo、导航按钮、主题切换、版本号
"""
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtGui import QFont
from .base import UIBaseMixin
from PySide6.QtCore import Qt

class SideBar(QFrame, UIBaseMixin):
    nav_process_clicked = None  # 信号将在主窗口连接
    nav_history_clicked = None
    nav_settings_clicked = None
    theme_clicked = None

    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._icon_map = []
        self.setObjectName("sideBar")
        self.setFixedWidth(60)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 12, 4, 12)
        layout.setSpacing(10)
        # Logo
        self.app_logo = QLabel("WT")
        self.app_logo.setObjectName("appLogo")
        self.app_logo.setAlignment(Qt.AlignCenter)
        self.app_logo.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        layout.addWidget(self.app_logo)
        layout.addSpacing(20)
        # 导航按钮
        self.nav_process_btn = self._add_icon("lightning", checkable=True, checked=True)
        layout.addWidget(self.nav_process_btn)
        self.nav_history_btn = self._add_icon("history", checkable=True)
        layout.addWidget(self.nav_history_btn)
        self.nav_settings_btn = self._add_icon("gear", checkable=True)
        layout.addWidget(self.nav_settings_btn)
        layout.addStretch()
        # 底部工具
        self.theme_btn = self.create_btn(
            icon_text="🌙", tooltip="切换主题",
            obj_name="themeButton"
        )
        layout.addWidget(self.theme_btn)
        self.version_label = QLabel("v1.0")
        self.version_label.setObjectName("versionLabel")
        self.version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.version_label)

    def _add_icon(self, icon_name, **kwargs):
        btn = self.create_icon_btn(icon_name, **kwargs)
        self._icon_map.append((btn, icon_name))
        return btn

    def refresh_all_icons(self):
        for btn, name in self._icon_map:
            self._set_icon_on_button(btn, name)
        # 主题按钮需要单独切换 moon/sun
        theme_icon = "moon" if self.theme_manager.current_theme == "dark" else "sun"
        self._set_icon_on_button(self.theme_btn, theme_icon)