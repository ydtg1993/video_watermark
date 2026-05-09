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

    def _add_icon(self, icon_name, **kwargs):
        btn = self.create_icon_btn(icon_name, **kwargs)
        self._icon_map.append((btn, icon_name))
        return btn

    def refresh_all_icons(self):
        """刷新所有图标"""
        for btn, name in self._icon_map:
            self._set_icon_on_button(btn, name)

    def update_video_info(self, filename, width, height, fps):
        """更新视频信息显示"""
        self.video_info_label.setText(
            f"{filename} | {width}x{height} | {fps:.2f} FPS"
        )

    def set_processing_enabled(self, enabled):
        """启用/禁用开始按钮"""
        self.start_btn.setEnabled(enabled)