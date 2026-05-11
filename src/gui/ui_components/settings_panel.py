"""
右侧属性面板 (380px 宽) – 紧凑卡片式布局，完美适配 Fluent Dark 主题
"""
import os
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget
)
from PySide6.QtCore import Qt
from qfluentwidgets import (
    ComboBox, SpinBox, DoubleSpinBox, LineEdit,
    CheckBox, PushButton, PrimaryPushButton, ToolButton,
    CardWidget, GroupHeaderCardWidget, FluentIcon as FIF
)
from ...core.utils import get_best_encoder

OUTPUT_FORMATS = ["mp4", "avi", "mov", "mkv", "flv"]


class SettingsPanel(QFrame):
    """右侧设置面板 – 紧凑卡片式设计"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPanel")
        self.setFixedWidth(380)
        self._setup_ui()
        self._apply_initial_state()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ---- 模式选择 (卡片) ----
        mode_card = CardWidget()
        mode_layout = QVBoxLayout(mode_card)
        mode_layout.setContentsMargins(16, 12, 16, 12)
        mode_layout.setSpacing(10)

        row = QHBoxLayout()
        row.addWidget(QLabel("模式"))
        self.mode_combo = ComboBox()
        self.mode_combo.addItems(["智能去水印", "文字水印", "图片水印"])
        self.mode_combo.setMinimumHeight(36)
        self.mode_combo.setFixedWidth(240)
        row.addWidget(self.mode_combo)
        row.addStretch()
        mode_layout.addLayout(row)
        layout.addWidget(mode_card)

        # ---- 水印区域 (卡片) ----
        roi_card = CardWidget()
        roi_layout = QVBoxLayout(roi_card)
        roi_layout.setContentsMargins(16, 12, 16, 12)
        roi_layout.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(QLabel("水印区域"))
        self.lock_ratio_btn = ToolButton(FIF.PIN)
        self.lock_ratio_btn.setCheckable(True)
        self.lock_ratio_btn.setFixedSize(28, 28)
        self.lock_ratio_btn.setToolTip("锁定宽高比例")
        header.addWidget(self.lock_ratio_btn)
        header.addStretch()
        roi_layout.addLayout(header)

        # 坐标输入网格
        grid = QHBoxLayout()
        grid.setSpacing(8)
        self.spin_x = SpinBox()
        self.spin_x.setPrefix("X")
        self.spin_x.setRange(0, 9999)
        self.spin_y = SpinBox()
        self.spin_y.setPrefix("Y")
        self.spin_y.setRange(0, 9999)
        self.spin_w = SpinBox()
        self.spin_w.setPrefix("W")
        self.spin_w.setRange(0, 9999)
        self.spin_h = SpinBox()
        self.spin_h.setPrefix("H")
        self.spin_h.setRange(0, 9999)
        grid.addWidget(self.spin_x)
        grid.addWidget(self.spin_y)
        grid.addWidget(self.spin_w)
        grid.addWidget(self.spin_h)
        roi_layout.addLayout(grid)

        btn_row = QHBoxLayout()
        self.clear_rect_btn = PushButton(FIF.DELETE, "清除区域")
        self.apply_rect_btn = PrimaryPushButton(FIF.ACCEPT, "应用区域")
        btn_row.addWidget(self.clear_rect_btn)
        btn_row.addWidget(self.apply_rect_btn)
        roi_layout.addLayout(btn_row)
        layout.addWidget(roi_card)

        # ---- 去水印高级选项 (卡片，条件显示) ----
        self.remove_card = self._create_remove_card()
        layout.addWidget(self.remove_card)

        # ---- 文字水印 (卡片) ----
        self.text_card = self._create_text_watermark_card()
        layout.addWidget(self.text_card)
        self.text_card.setVisible(False)

        # ---- 图片水印 (卡片) ----
        self.image_card = self._create_image_watermark_card()
        layout.addWidget(self.image_card)
        self.image_card.setVisible(False)

        # ---- 输出设置 (卡片) ----
        out_card = self._create_output_card()
        layout.addWidget(out_card)

        # ---- 全局选项 ----
        self.remove_before_add_check = CheckBox("先去原水印再添加（仅加水印模式生效）")
        layout.addWidget(self.remove_before_add_check)

        layout.addStretch()

    # ==================== 卡片构建器 ====================

    def _create_remove_card(self):
        """去水印高级选项卡片"""
        card = CardWidget()
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(16, 12, 16, 12)
        vbox.setSpacing(10)

        # 方法选择
        method_row = QHBoxLayout()
        method_row.addWidget(QLabel("处理方式"))
        self.remove_method_combo = ComboBox()
        self.remove_method_combo.addItems([
            "delogo (默认)", "delogo + 羽化", "delogo + 边界模糊",
            "邻近区域覆盖", "图片补丁覆盖", "OpenCV 修复"
        ])
        self.remove_method_combo.setMinimumHeight(36)
        method_row.addWidget(self.remove_method_combo)
        vbox.addLayout(method_row)

        # 动态参数区域
        self.band_widget = QWidget()
        band_lay = QHBoxLayout(self.band_widget)
        band_lay.setContentsMargins(0,0,0,0)
        band_lay.addWidget(QLabel("羽化宽度"))
        self.band_spin = SpinBox()
        self.band_spin.setRange(0, 20); self.band_spin.setValue(1)
        band_lay.addWidget(self.band_spin)
        vbox.addWidget(self.band_widget)

        self.blur_widget = QWidget()
        blur_lay = QHBoxLayout(self.blur_widget)
        blur_lay.setContentsMargins(0,0,0,0)
        blur_lay.addWidget(QLabel("模糊半径"))
        self.blur_radius_spin = SpinBox()
        self.blur_radius_spin.setRange(1, 20); self.blur_radius_spin.setValue(2)
        blur_lay.addWidget(self.blur_radius_spin)
        vbox.addWidget(self.blur_widget)

        self.crop_widget = QWidget()
        crop_lay = QHBoxLayout(self.crop_widget)
        crop_lay.setContentsMargins(0,0,0,0)
        crop_lay.addWidget(QLabel("邻近区域"))
        for name in ("crop_x", "crop_y", "crop_w", "crop_h"):
            sb = SpinBox()
            sb.setPrefix(name.replace("crop_","截取 ").upper())
            sb.setRange(0, 9999)
            setattr(self, name, sb)
            crop_lay.addWidget(sb)
        vbox.addWidget(self.crop_widget)

        self.patch_widget = QWidget()
        patch_lay = QHBoxLayout(self.patch_widget)
        patch_lay.setContentsMargins(0,0,0,0)
        self.patch_image_edit = LineEdit()
        self.patch_image_edit.setReadOnly(True)
        self.patch_image_edit.setPlaceholderText("选择补丁图片...")
        self.patch_browse_btn = PushButton(FIF.FOLDER, "浏览")
        self.patch_browse_btn.setFixedSize(60, 32)
        patch_lay.addWidget(self.patch_image_edit, 1)
        patch_lay.addWidget(self.patch_browse_btn)
        vbox.addWidget(self.patch_widget)

        self.inpaint_widget = QWidget()
        inpaint_lay = QHBoxLayout(self.inpaint_widget)
        inpaint_lay.setContentsMargins(0,0,0,0)
        inpaint_lay.addWidget(QLabel("修复半径"))
        self.inpaint_radius_spin = SpinBox()
        self.inpaint_radius_spin.setRange(1, 20); self.inpaint_radius_spin.setValue(5)
        inpaint_lay.addWidget(self.inpaint_radius_spin)
        vbox.addWidget(self.inpaint_widget)

        self.inpaint_warning = QLabel("⚠️ 处理速度极慢，仅适合短视频")
        self.inpaint_warning.setStyleSheet("color: orange; font-size: 11px;")
        vbox.addWidget(self.inpaint_warning)

        # 初始隐藏
        self.band_widget.hide()
        self.blur_widget.hide()
        self.crop_widget.hide()
        self.patch_widget.hide()
        self.inpaint_widget.hide()
        self.inpaint_warning.hide()

        self.remove_method_combo.currentIndexChanged.connect(self._on_remove_method_changed)
        return card

    def _on_remove_method_changed(self, index):
        self.band_widget.setVisible(index in (0, 1, 2))
        self.blur_widget.setVisible(index == 2)
        self.crop_widget.setVisible(index == 3)
        self.patch_widget.setVisible(index == 4)
        self.inpaint_widget.setVisible(index == 5)
        self.inpaint_warning.setVisible(index == 5)

    def _create_text_watermark_card(self):
        """文字水印卡片"""
        card = CardWidget()
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(16, 12, 16, 12)
        vbox.setSpacing(10)

        self.text_input = LineEdit()
        self.text_input.setPlaceholderText("输入水印文字...")
        vbox.addWidget(self.text_input)

        # 字体（使用原生 QFontComboBox，但样式会自动适配）
        from PySide6.QtWidgets import QFontComboBox
        self.font_combo = QFontComboBox()
        vbox.addWidget(self.font_combo)

        props_grid = QHBoxLayout()
        self.color_combo = ComboBox()
        self.color_combo.addItems(["white", "black", "red", "green", "blue", "yellow", "cyan"])
        props_grid.addWidget(QLabel("颜色"))
        props_grid.addWidget(self.color_combo)
        self.text_alpha = DoubleSpinBox()
        self.text_alpha.setRange(0.0, 1.0)
        self.text_alpha.setSingleStep(0.1)
        self.text_alpha.setValue(0.8)
        props_grid.addWidget(QLabel("透明度"))
        props_grid.addWidget(self.text_alpha)
        vbox.addLayout(props_grid)

        fontfile_row = QHBoxLayout()
        self.fontfile_edit = LineEdit()
        self.fontfile_edit.setReadOnly(True)
        self.fontfile_edit.setPlaceholderText("可选：指定字体文件路径...")
        self.fontfile_btn = PushButton(FIF.FOLDER, "浏览...")
        self.fontfile_btn.setFixedSize(60, 32)
        fontfile_row.addWidget(self.fontfile_edit, 1)
        fontfile_row.addWidget(self.fontfile_btn)
        vbox.addLayout(fontfile_row)

        return card

    def _create_image_watermark_card(self):
        """图片水印卡片"""
        card = CardWidget()
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(16, 12, 16, 12)
        vbox.setSpacing(10)

        img_row = QHBoxLayout()
        self.img_path_edit = LineEdit()
        self.img_path_edit.setReadOnly(True)
        self.img_path_edit.setPlaceholderText("选择水印图片...")
        self.img_browse_btn = PushButton(FIF.FOLDER, "浏览")
        self.img_browse_btn.setFixedSize(60, 32)
        img_row.addWidget(self.img_path_edit, 1)
        img_row.addWidget(self.img_browse_btn)
        vbox.addLayout(img_row)

        props_grid = QHBoxLayout()
        self.scale_combo = ComboBox()
        self.scale_combo.addItems(["适应区域", "原始大小"])
        props_grid.addWidget(QLabel("缩放"))
        props_grid.addWidget(self.scale_combo)
        self.img_alpha = DoubleSpinBox()
        self.img_alpha.setRange(0.0, 1.0)
        self.img_alpha.setSingleStep(0.1)
        self.img_alpha.setValue(0.9)
        props_grid.addWidget(QLabel("透明度"))
        props_grid.addWidget(self.img_alpha)
        vbox.addLayout(props_grid)

        return card

    def _create_output_card(self):
        """输出设置卡片"""
        card = CardWidget()
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(16, 12, 16, 12)
        vbox.setSpacing(10)

        path_row = QHBoxLayout()
        default_path = os.path.join(os.path.expanduser("~"), "Videos")
        self.output_path_edit = LineEdit()
        self.output_path_edit.setPlaceholderText(default_path)
        self.output_browse_btn = PushButton(FIF.FOLDER, "...")
        self.output_browse_btn.setFixedSize(36, 36)
        path_row.addWidget(self.output_path_edit, 1)
        path_row.addWidget(self.output_browse_btn)
        vbox.addLayout(path_row)

        # 格式 / 编码器 / 质量 三合一
        row = QHBoxLayout()
        self.format_combo = ComboBox()
        self.format_combo.addItems(OUTPUT_FORMATS)
        row.addWidget(QLabel("格式"))
        row.addWidget(self.format_combo)

        best_enc = get_best_encoder()
        self.encoder_combo = ComboBox()
        self.encoder_combo.addItems(["nvenc (NVIDIA)", "qsv (Intel)", "amf (AMD)", "libx264 (CPU)"])
        idx = ["nvenc", "qsv", "amf", "libx264"].index(best_enc) if best_enc in ["nvenc", "qsv", "amf"] else 3
        self.encoder_combo.setCurrentIndex(idx)
        row.addWidget(QLabel("编码"))
        row.addWidget(self.encoder_combo)

        self.quality_combo = ComboBox()
        self.quality_combo.addItems(["标准", "高质量", "无损"])
        row.addWidget(QLabel("质量"))
        row.addWidget(self.quality_combo)
        vbox.addLayout(row)

        return card

    def _apply_initial_state(self):
        self.update_mode_visibility(0)

    # ==================== 公共接口（保持不变） ====================
    @property
    def current_mode(self) -> int:
        return self.mode_combo.currentIndex()

    def get_roi_values(self) -> tuple:
        return (self.spin_x.value(), self.spin_y.value(), self.spin_w.value(), self.spin_h.value())

    def set_roi_values(self, x, y, w, h):
        for spin in [self.spin_x, self.spin_y, self.spin_w, self.spin_h]:
            spin.blockSignals(True)
        self.spin_x.setValue(x); self.spin_y.setValue(y)
        self.spin_w.setValue(w); self.spin_h.setValue(h)
        for spin in [self.spin_x, self.spin_y, self.spin_w, self.spin_h]:
            spin.blockSignals(False)

    def clear_roi(self):
        self.set_roi_values(0, 0, 0, 0)

    def update_mode_visibility(self, mode_idx):
        self.remove_card.setVisible(mode_idx == 0)
        self.text_card.setVisible(mode_idx == 1)
        self.image_card.setVisible(mode_idx == 2)
        self.remove_before_add_check.setVisible(mode_idx > 0)

    def get_output_config(self) -> dict:
        enc_text = self.encoder_combo.currentText()
        enc_key = enc_text.split()[0].lower()
        return {
            'path': self.output_path_edit.text().strip(),
            'format': self.format_combo.currentText(),
            'encoder': enc_key,
            'quality': self.quality_combo.currentText(),
            'remove_first': self.remove_before_add_check.isChecked() if self.remove_before_add_check.isVisible() else False
        }

    def get_remove_config(self) -> dict:
        method = self.remove_method_combo.currentIndex()
        config = {
            'method': method,
            'band': self.band_spin.value(),
            'blur_radius': self.blur_radius_spin.value() if method == 2 else 0,
            'crop_rect': (self.crop_x.value(), self.crop_y.value(), self.crop_w.value(), self.crop_h.value()) if method == 3 else None,
            'patch_image': self.patch_image_edit.text().strip() if method == 4 else '',
            'inpaint_radius': self.inpaint_radius_spin.value() if method == 5 else 5,
        }
        return config

    def get_text_watermark_config(self) -> dict:
        return {
            'text': self.text_input.text(),
            'font': self.font_combo.currentText(),
            'color': self.color_combo.currentText(),
            'alpha': self.text_alpha.value(),
            'fontfile': self.fontfile_edit.text().strip()
        }

    def get_image_watermark_config(self) -> dict:
        return {
            'path': self.img_path_edit.text().strip(),
            'scale_mode': self.scale_combo.currentIndex(),
            'alpha': self.img_alpha.value()
        }

    def validate_for_processing(self, mode: int) -> tuple[bool, str]:
        out_cfg = self.get_output_config()
        if not out_cfg['path']: return False, "请设置输出路径"
        x, y, w, h = self.get_roi_values()
        if w == 0 or h == 0: return False, "请在视频上框选水印区域"
        if mode == 0:
            rcfg = self.get_remove_config()
            if rcfg['method'] == 3 and (rcfg['crop_rect'] is None or rcfg['crop_rect'][2] <= 0 or rcfg['crop_rect'][3] <= 0):
                return False, "邻近区域覆盖需要设置有效的截取区域"
            if rcfg['method'] == 4 and (not rcfg['patch_image'] or not os.path.exists(rcfg['patch_image'])):
                return False, "请选择有效的补丁图片"
        elif mode == 1 and not self.text_input.text():
            return False, "请输入水印文字内容"
        elif mode == 2 and (not self.img_path_edit.text().strip() or not os.path.exists(self.img_path_edit.text().strip())):
            return False, "请选择有效的图片水印文件"
        return True, ""

    def load_settings(self, qsettings):
        self.mode_combo.setCurrentIndex(qsettings.value("mode", 0, type=int))
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
        self.img_path_edit.setText(qsettings.value("image_path", ""))
        self.scale_combo.setCurrentIndex(qsettings.value("scale_mode", 0, type=int))
        self.img_alpha.setValue(qsettings.value("img_alpha", 0.9, type=float))
        enc = qsettings.value("encoder", "libx264")
        idx = self.encoder_combo.findText(enc)
        if idx >= 0: self.encoder_combo.setCurrentIndex(idx)
        qual = qsettings.value("quality", "标准")
        idx = self.quality_combo.findText(qual)
        if idx >= 0: self.quality_combo.setCurrentIndex(idx)
        self.remove_before_add_check.setChecked(qsettings.value("remove_before_add", False, type=bool))
        self.output_path_edit.setText(qsettings.value("output_dir", os.path.join(os.path.expanduser("~"), "Videos")))
        self.format_combo.setCurrentText(qsettings.value("output_format", "mp4"))
        rect = qsettings.value("watermark_rect")
        if rect and len(rect) == 4:
            self.set_roi_values(*[int(v) for v in rect])
        self.remove_method_combo.setCurrentIndex(qsettings.value("remove_method", 0, type=int))
        self.band_spin.setValue(qsettings.value("remove_band", 1, type=int))
        self.blur_radius_spin.setValue(qsettings.value("remove_blur", 2, type=int))
        self.crop_x.setValue(qsettings.value("crop_x", 0, type=int))
        self.crop_y.setValue(qsettings.value("crop_y", 0, type=int))
        self.crop_w.setValue(qsettings.value("crop_w", 0, type=int))
        self.crop_h.setValue(qsettings.value("crop_h", 0, type=int))
        self.patch_image_edit.setText(qsettings.value("patch_image", ""))
        self.inpaint_radius_spin.setValue(qsettings.value("inpaint_radius", 5, type=int))
        self._on_remove_method_changed(self.remove_method_combo.currentIndex())
        self.update_mode_visibility(self.mode_combo.currentIndex())

    def save_settings(self, qsettings):
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
        x, y, w, h = self.get_roi_values()
        if w > 0 and h > 0:
            qsettings.setValue("watermark_rect", [x, y, w, h])
        else:
            qsettings.remove("watermark_rect")
        qsettings.setValue("remove_method", self.remove_method_combo.currentIndex())
        qsettings.setValue("remove_band", self.band_spin.value())
        qsettings.setValue("remove_blur", self.blur_radius_spin.value())
        qsettings.setValue("crop_x", self.crop_x.value())
        qsettings.setValue("crop_y", self.crop_y.value())
        qsettings.setValue("crop_w", self.crop_w.value())
        qsettings.setValue("crop_h", self.crop_h.value())
        qsettings.setValue("patch_image", self.patch_image_edit.text())
        qsettings.setValue("inpaint_radius", self.inpaint_radius_spin.value())