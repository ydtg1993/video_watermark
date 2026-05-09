from PySide6.QtWidgets import QLabel, QHBoxLayout, QFrame

from src.gui.ui_components import UIBaseMixin


class TopToolbar(QFrame, UIBaseMixin):
    def __init__(self, theme_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self._icon_map = []
        self.setObjectName("topToolbar")
        self.setFixedHeight(48)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)

        # 打开视频按钮（文字 + 图标）
        self.open_btn = self.create_btn(text=" 打开视频", obj_name="toolbarButton")
        self._set_icon_on_button(self.open_btn, "folder")
        self._icon_map.append((self.open_btn, "folder"))
        layout.addWidget(self.open_btn)

        self.video_info_label = QLabel("暂无视频")
        self.video_info_label.setObjectName("videoInfoLabel")
        layout.addWidget(self.video_info_label)

        layout.addStretch()

        # 开始处理按钮
        self.start_btn = self.create_btn(text=" 开始处理", obj_name="startButton",
                                         fixed_size=(140, 36), enabled=False)
        self._set_icon_on_button(self.start_btn, "lightning")
        self._icon_map.append((self.start_btn, "lightning"))
        layout.addWidget(self.start_btn)

        # 主题切换按钮 (使用 _add_icon 统一管理)
        theme_icon = "moon" if self.theme_manager.current_theme == "dark" else "sun"
        self.theme_toggle = self._add_icon(theme_icon, obj_name="themeToggle", fixed_size=36)
        layout.addWidget(self.theme_toggle)

    def _add_icon(self, icon_name, **kwargs):
        btn = self.create_icon_btn(icon_name, **kwargs)
        self._icon_map.append((btn, icon_name))
        return btn

    def refresh_all_icons(self):
        for btn, name in self._icon_map:
            self._set_icon_on_button(btn, name)
        # 主题图标可能需要动态更换，这里再根据当前主题设置一次
        theme_icon = "moon" if self.theme_manager.current_theme == "dark" else "sun"
        self._set_icon_on_button(self.theme_toggle, theme_icon)

    def update_video_info(self, filename, width, height, fps):
        """更新视频信息显示"""
        self.video_info_label.setText(
            f"{filename} | {width}x{height} | {fps:.2f} FPS"
        )

    def set_processing_enabled(self, enabled):
        """启用/禁用开始按钮"""
        self.start_btn.setEnabled(enabled)