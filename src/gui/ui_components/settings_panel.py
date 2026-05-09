"""
右侧属性面板 (380px 宽)
包含：模式选择、ROI 区域、文字水印、图片水印、输出设置
支持：数据绑定、设置持久化、状态管理
"""
import os
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QGroupBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QFontComboBox, QPushButton, QMessageBox,
    QLabel, QLineEdit
)
from PySide6.QtCore import Qt
from ...core.utils import get_best_encoder
from .base import UIBaseMixin

OUTPUT_FORMATS = ["mp4", "avi", "mov", "mkv", "flv"]


class SettingsPanel(QFrame, UIBaseMixin):
    """右侧完整设置面板 - 自包含的数据管理器"""
    # 定义信号供外部连接
    mode_changed = None  # 将由外部赋值或使用 pyqtSignal

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPanel")
        self.setFixedWidth(380)
        self._setup_ui()
        self._apply_initial_state()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        # 1. 模式选择区
        layout.addLayout(self._create_mode_section())
        # 2. ROI 区域（坐标输入）
        layout.addWidget(self._create_roi_section())
        # 3. 文字水印设置
        self.text_group = self._create_text_watermark_section()
        layout.addWidget(self.text_group)
        self.text_group.setVisible(False)  # 默认隐藏
        # 4. 图片水印设置
        self.image_group = self._create_image_watermark_section()
        layout.addWidget(self.image_group)
        self.image_group.setVisible(False)  # 默认隐藏
        # 5. 输出设置
        layout.addWidget(self._create_output_section())
        # 6. 全局选项
        self.remove_before_add_check = self.create_checkbox(
            "先去原水印再添加（仅加水印模式生效）"
        )
        layout.addWidget(self.remove_before_add_check)
        layout.addStretch()

    # ==================== 区域构建器 ====================
    def _create_mode_section(self):
        """模式选择下拉框"""
        row = QHBoxLayout()
        row.addWidget(QLabel("模式"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["智能去水印", "文字水印", "图片水印"])
        self.mode_combo.setMinimumHeight(36)
        row.addWidget(self.mode_combo)
        return row

    def _create_roi_section(self):
        """ROI 区域精确输入面板"""
        panel = QFrame()
        panel.setObjectName("regionPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 8, 0, 8)
        # 标题行 + 锁定按钮
        header = QHBoxLayout()
        header.addWidget(QLabel("水印区域"))
        self.lock_ratio_btn = self.create_btn(
            icon_text="🔒", obj_name="lockButton",
            checkable=True, fixed_size=28,
            tooltip="锁定宽高比例"
        )
        header.addWidget(self.lock_ratio_btn)
        layout.addLayout(header)
        # 坐标输入网格（使用工厂方法）
        coord_layout = QHBoxLayout()
        self.spin_x, self.spin_y, self.spin_w, self.spin_h = \
            self.create_coord_spins(prefix_list=["X ", "Y ", "W ", "H "])
        for spin in [self.spin_x, self.spin_y, self.spin_w, self.spin_h]:
            coord_layout.addWidget(spin)
        layout.addLayout(coord_layout)
        # 操作按钮行
        btn_row = QHBoxLayout()
        self.clear_rect_btn = self.create_btn(
            text="清除区域", icon_text="🗑",
            obj_name="clearButton"
        )
        self.apply_rect_btn = self.create_btn(
            text="应用区域", icon_text="✓",
            obj_name="applyButton"
        )
        btn_row.addWidget(self.clear_rect_btn)
        btn_row.addWidget(self.apply_rect_btn)
        layout.addLayout(btn_row)
        return panel

    def _create_text_watermark_section(self):
        """文字水印设置 GroupBox"""
        group = QGroupBox("文字水印")
        layout = QVBoxLayout(group)
        # 文字输入
        self.text_input = QLineEdit()
        self.text_input.setPlaceholderText("输入水印文字...")
        layout.addLayout(self.create_label_row("文字内容", self.text_input))
        # 字体选择
        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("字体"))
        self.font_combo = QFontComboBox()
        font_row.addWidget(self.font_combo)
        layout.addLayout(font_row)
        # 颜色 + 透明度（两列布局）
        props_grid = QHBoxLayout()
        self.color_combo, color_row = self.create_combo_row(
            "颜色", ["white", "black", "red", "green", "blue", "yellow", "cyan"]
        )
        self.text_alpha, alpha_row = self.create_double_spin_row(
            "透明度", default=0.8
        )
        props_grid.addLayout(color_row)
        props_grid.addLayout(alpha_row)
        layout.addLayout(props_grid)
        # 字体文件路径
        self.fontfile_edit, self.fontfile_btn, fontfile_row = \
            self.create_input_row("字体文件", read_only=True, browse_text="浏览...",
                                  browse_handler=lambda: None)
        layout.addLayout(fontfile_row)
        return group

    def _create_image_watermark_section(self):
        """图片水印设置 GroupBox"""
        group = QGroupBox("图片水印")
        layout = QVBoxLayout(group)
        # 图片路径
        self.img_path_edit, self.img_browse_btn, img_row = \
            self.create_input_row("图片路径", read_only=True, browse_text="浏览",
                                  browse_handler=lambda: None)
        layout.addLayout(img_row)
        # 缩放模式 + 透明度
        props_grid = QHBoxLayout()
        self.scale_combo, scale_row = self.create_combo_row(
            "缩放", ["适应区域", "原始大小"]
        )
        self.img_alpha, img_alpha_row = self.create_double_spin_row(
            "透明度", default=0.9
        )
        props_grid.addLayout(scale_row)
        props_grid.addLayout(img_alpha_row)
        layout.addLayout(props_grid)
        return group

    def _create_output_section(self):
        """输出设置 GroupBox"""
        group = QGroupBox("输出设置")
        layout = QVBoxLayout(group)
        # 路径
        default_path = os.path.join(os.path.expanduser("~"), "Videos")
        self.output_path_edit, self.output_browse_btn, path_row = \
            self.create_input_row("保存路径", placeholder=default_path,
                                  browse_text="...", fixed_btn_size=(36, 36),
                                  browse_handler=lambda: None)
        layout.addLayout(path_row)
        # 格式
        self.format_combo, fmt_row = self.create_combo_row(
            "格式", OUTPUT_FORMATS, current_index=0
        )
        layout.addLayout(fmt_row)
        # 编码器（自动检测最佳）
        best_enc = get_best_encoder()
        self.encoder_combo, enc_row = self.create_combo_row(
            "编码器", ["nvenc (NVIDIA)", "qsv (Intel)", "amf (AMD)", "libx264 (CPU)"],
            current_index=["nvenc", "qsv", "amf", "libx264"].index(best_enc) if best_enc in ["nvenc", "qsv",
                                                                                             "amf"] else 3
        )
        layout.addLayout(enc_row)
        # 质量
        self.quality_combo, qual_row = self.create_combo_row(
            "质量", ["标准", "高质量", "无损"]
        )
        layout.addLayout(qual_row)
        return group

    def _apply_initial_state(self):
        """应用初始状态（默认隐藏非活动面板）"""
        self.update_mode_visibility(0)

    # ==================== 公共接口（供 MainWindow 调用）====================
    @property
    def current_mode(self) -> int:
        """获取当前模式索引：0=去水印, 1=文字, 2=图片"""
        return self.mode_combo.currentIndex()

    def get_roi_values(self) -> tuple:
        """获取 ROI 坐标元组 (x, y, w, h)"""
        return (
            self.spin_x.value(), self.spin_y.value(),
            self.spin_w.value(), self.spin_h.value()
        )

    def set_roi_values(self, x: int, y: int, w: int, h: int):
        """设置 ROI 坐标（阻塞信号避免循环触发）"""
        for spin in [self.spin_x, self.spin_y, self.spin_w, self.spin_h]:
            spin.blockSignals(True)
        try:
            self.spin_x.setValue(x)
            self.spin_y.setValue(y)
            self.spin_w.setValue(w)
            self.spin_h.setValue(h)
        finally:
            for spin in [self.spin_x, self.spin_y, self.spin_w, self.spin_h]:
                spin.blockSignals(False)

    def clear_roi(self):
        """清空 ROI 选择为 0"""
        self.set_roi_values(0, 0, 0, 0)

    def update_mode_visibility(self, mode_idx: int):
        """根据模式索引显示/隐藏对应的面板"""
        self.text_group.setVisible(mode_idx == 1)
        self.image_group.setVisible(mode_idx == 2)
        # 调整"先去后加"选项可见性（仅在添加模式下显示）
        self.remove_before_add_check.setVisible(mode_idx > 0)

    def get_output_config(self) -> dict:
        """获取输出配置字典（便于传递给处理器）"""
        enc_text = self.encoder_combo.currentText()
        enc_key = enc_text.split()[0].lower()  # 提取 nvenc/qsv/amf/libx264
        return {
            'path': self.output_path_edit.text().strip(),
            'format': self.format_combo.currentText(),
            'encoder': enc_key,
            'quality': self.quality_combo.currentText(),
            'remove_first': self.remove_before_add_check.isChecked() if self.remove_before_add_check.isVisible() else False
        }

    def get_text_watermark_config(self) -> dict:
        """获取文字水印配置"""
        return {
            'text': self.text_input.text(),
            'font': self.font_combo.currentText(),
            'color': self.color_combo.currentText(),
            'alpha': self.text_alpha.value(),
            'fontfile': self.fontfile_edit.text().strip()
        }

    def get_image_watermark_config(self) -> dict:
        """获取图片水印配置"""
        return {
            'path': self.img_path_edit.text().strip(),
            'scale_mode': self.scale_combo.currentIndex(),  # 0=适应, 1=原始
            'alpha': self.img_alpha.value()
        }

    def validate_for_processing(self, mode: int) -> tuple[bool, str]:
        """验证当前配置是否满足处理条件
        Returns:
            (is_valid, error_message)
        """
        # 检查输出路径
        out_cfg = self.get_output_config()
        if not out_cfg['path']:
            return False, "请设置输出路径"
        # 检查 ROI
        x, y, w, h = self.get_roi_values()
        if w == 0 or h == 0:
            return False, "请在视频上框选水印区域"
        # 模式特定验证
        if mode == 1:  # 文字水印
            txt_cfg = self.get_text_watermark_config()
            if not txt_cfg['text']:
                return False, "请输入水印文字内容"
        elif mode == 2:  # 图片水印
            img_cfg = self.get_image_watermark_config()
            if not img_cfg['path']:
                return False, "请选择水印图片文件"
            if not os.path.exists(img_cfg['path']):
                return False, f"图片文件不存在: {img_cfg['path']}"
        return True, ""

    def load_settings(self, qsettings):
        """从 QSettings 加载配置"""
        self.mode_combo.setCurrentIndex(qsettings.value("mode", 0, type=int))
        # 文字水印
        self.text_input.setText(qsettings.value("text", ""))
        font = qsettings.value("font", "")
        if font:
            idx = self.font_combo.findText(font)
            if idx >= 0: self.font_combo.setCurrentIndex(idx)
        color = qsettings.value("color", "white")
        idx = self.color_combo.findText(color)
        if idx >= 0: self.color_combo.setCurrentIndex(idx)
        self.text_alpha.setValue(qsettings.value("text_alpha", 0.8, type=float))
        self.fontfile_edit.setText(qsettings.value("fontfile", ""))
        # 图片水印
        self.img_path_edit.setText(qsettings.value("image_path", ""))
        self.scale_combo.setCurrentIndex(qsettings.value("scale_mode", 0, type=int))
        self.img_alpha.setValue(qsettings.value("img_alpha", 0.9, type=float))
        # 输出
        enc = qsettings.value("encoder", "libx264")
        idx = self.encoder_combo.findText(enc, Qt.MatchContains)
        if idx >= 0: self.encoder_combo.setCurrentIndex(idx)
        qual = qsettings.value("quality", "标准")
        idx = self.quality_combo.findText(qual)
        if idx >= 0: self.quality_combo.setCurrentIndex(idx)
        self.remove_before_add_check.setChecked(
            qsettings.value("remove_before_add", False, type=bool)
        )
        self.output_path_edit.setText(
            qsettings.value("output_dir", os.path.join(os.path.expanduser("~"), "Videos"))
        )
        self.format_combo.setCurrentText(qsettings.value("output_format", "mp4"))
        # ROI
        rect_list = qsettings.value("watermark_rect")
        if rect_list and len(rect_list) == 4:
            self.set_roi_values(*[int(v) for v in rect_list])
        # 应用可见性
        self.update_mode_visibility(self.mode_combo.currentIndex())

    def save_settings(self, qsettings):
        """保存配置到 QSettings"""
        qsettings.setValue("mode", self.mode_combo.currentIndex())
        qsettings.setValue("text", self.text_input.text())
        qsettings.setValue("font", self.font_combo.currentText())
        qsettings.setValue("color", self.color_combo.currentText())
        qsettings.setValue("text_alpha", self.text_alpha.value())
        qsettings.setValue("fontfile", self.fontfile_edit.text())
        qsettings.setValue("image_path", self.img_path_edit.text())
        qsettings.setValue("scale_mode", self.scale_combo.currentIndex())
        qsettings.setValue("img_alpha", self.img_alpha.value())
        qsettings.setValue("encoder", self.encoder_combo.currentText().split()[0])
        qsettings.setValue("quality", self.quality_combo.currentText())
        qsettings.setValue("remove_before_add", self.remove_before_add_check.isChecked())
        qsettings.setValue("output_dir", self.output_path_edit.text())
        qsettings.setValue("output_format", self.format_combo.currentText())
        # 保存 ROI
        x, y, w, h = self.get_roi_values()
        if w > 0 and h > 0:
            qsettings.setValue("watermark_rect", [x, y, w, h])
        else:
            qsettings.remove("watermark_rect")
