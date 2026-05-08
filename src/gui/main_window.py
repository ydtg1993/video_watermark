# src/gui/main_window.py
import os
import cv2
import subprocess
from PySide6.QtCore import Qt, QThread, QSettings
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QFileDialog, QLabel, QMessageBox, QProgressBar,
    QGroupBox, QRadioButton, QButtonGroup, QLineEdit, QSpinBox,
    QDoubleSpinBox, QComboBox, QCheckBox, QFontComboBox
)
from PySide6.QtGui import QColor
from .video_player import VideoPlayer
from .progress_dialog import ProgressDialog
from ..processor.remover import WatermarkRemover
from ..processor.watermark_adder import WatermarkAdder


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("视频去/加水印工具")
        self.resize(1200, 800)

        self.video_path = None
        self.cap = None
        self.total_frames = 0
        self.current_frame_idx = 0
        self.watermark_rect = None   # (x, y, w, h)
        self.mode = "remove"        # "remove" 或 "add"

        self.settings = QSettings("JVSClaw", "WatermarkTool")  # 用于保存配置
        self._setup_ui()
        self._connect_signals()
        self._load_settings()         # 加载上次配置

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # 左侧：播放器 + 控制
        left_panel = QVBoxLayout()
        self.player = VideoPlayer()
        left_panel.addWidget(self.player, 1)

        slider_row = QHBoxLayout()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setEnabled(False)
        self.time_label = QLabel("00:00 / 00:00")
        slider_row.addWidget(self.slider)
        slider_row.addWidget(self.time_label)
        left_panel.addLayout(slider_row)

        # 按钮栏
        btn_row = QHBoxLayout()
        self.open_btn = QPushButton("打开视频")
        self.confirm_rect_btn = QPushButton("确认框选区域")
        self.confirm_rect_btn.setEnabled(False)
        self.start_btn = QPushButton("开始处理")
        self.start_btn.setEnabled(False)
        btn_row.addWidget(self.open_btn)
        btn_row.addWidget(self.confirm_rect_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.start_btn)
        left_panel.addLayout(btn_row)

        self.info_label = QLabel("提示：打开视频后，选择模式并框选区域（可拖拽移动选框）")
        left_panel.addWidget(self.info_label)

        main_layout.addLayout(left_panel, 2)

        # 右侧：水印设置面板
        right_panel = self._create_settings_panel()
        main_layout.addWidget(right_panel, 1)

        self._apply_stylesheet()

    def _apply_stylesheet(self):
        """加载外部 QSS 样式表"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        qss_path = os.path.join(current_dir, "..", "styles", "dark_theme.qss")
        qss_path = os.path.normpath(qss_path)
        try:
            with open(qss_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print(f"警告: 未找到样式文件 {qss_path}，使用默认样式")

    def _create_settings_panel(self):
        group = QGroupBox("水印设置")
        layout = QVBoxLayout(group)

        # 模式选择
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("处理模式:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["去水印", "加水印"])
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_layout.addWidget(self.mode_combo)
        layout.addLayout(mode_layout)

        # 当前区域显示
        self.rect_label = QLabel("未选择区域")
        layout.addWidget(self.rect_label)

        # 水印类型（仅加水印模式可见）
        self.add_type_group = QGroupBox("水印类型")
        type_layout = QHBoxLayout(self.add_type_group)
        self.type_text_radio = QRadioButton("文字")
        self.type_image_radio = QRadioButton("图片")
        self.type_text_radio.setChecked(True)
        type_layout.addWidget(self.type_text_radio)
        type_layout.addWidget(self.type_image_radio)
        self.add_type_group.setVisible(False)
        layout.addWidget(self.add_type_group)

        # 同时去水印选项
        self.remove_before_add_check = QCheckBox("先去除框选区域的原水印，再添加新水印")
        self.remove_before_add_check.setVisible(False)
        layout.addWidget(self.remove_before_add_check)

        # 文字水印设置
        self.text_settings_group = QGroupBox("文字样式")
        text_layout = QVBoxLayout(self.text_settings_group)
        text_layout.addWidget(QLabel("水印文字:"))
        self.text_input = QLineEdit("我的水印")
        text_layout.addWidget(self.text_input)

        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("字体:"))
        self.font_combo = QFontComboBox()
        font_row.addWidget(self.font_combo)
        text_layout.addLayout(font_row)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("字号:"))
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 200)
        self.font_size.setValue(24)
        size_row.addWidget(self.font_size)
        text_layout.addLayout(size_row)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("颜色:"))
        self.color_combo = QComboBox()
        self.color_combo.addItems(["white", "black", "red", "green", "blue", "yellow", "cyan"])
        color_row.addWidget(self.color_combo)
        text_layout.addLayout(color_row)

        alpha_row = QHBoxLayout()
        alpha_row.addWidget(QLabel("透明度:"))
        self.text_alpha = QDoubleSpinBox()
        self.text_alpha.setRange(0.0, 1.0)
        self.text_alpha.setSingleStep(0.1)
        self.text_alpha.setValue(0.8)
        alpha_row.addWidget(self.text_alpha)
        text_layout.addLayout(alpha_row)

        style_row = QHBoxLayout()
        self.bold_check = QCheckBox("粗体")
        self.bold_check.setEnabled(False)
        self.bold_check.setToolTip("需要选择具体的粗体字体文件，暂不支持")
        self.italic_check = QCheckBox("斜体")
        self.italic_check.setEnabled(False)
        self.italic_check.setToolTip("需要选择具体的斜体字体文件，暂不支持")
        style_row.addWidget(self.bold_check)
        style_row.addWidget(self.italic_check)
        text_layout.addLayout(style_row)

        angle_row = QHBoxLayout()
        angle_row.addWidget(QLabel("旋转:"))
        self.angle_spin = QDoubleSpinBox()
        self.angle_spin.setRange(-360.0, 360.0)
        self.angle_spin.setValue(0.0)
        angle_row.addWidget(self.angle_spin)
        text_layout.addLayout(angle_row)

        self.text_settings_group.setVisible(True)
        layout.addWidget(self.text_settings_group)

        # 图片水印设置
        self.image_settings_group = QGroupBox("图片样式")
        image_layout = QVBoxLayout(self.image_settings_group)
        img_path_row = QHBoxLayout()
        img_path_row.addWidget(QLabel("图片文件:"))
        self.img_path_edit = QLineEdit()
        self.img_path_edit.setReadOnly(True)
        img_path_row.addWidget(self.img_path_edit)
        self.img_browse_btn = QPushButton("浏览")
        img_path_row.addWidget(self.img_browse_btn)
        image_layout.addLayout(img_path_row)

        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("缩放模式:"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["适应框选区域", "原始大小"])
        scale_row.addWidget(self.scale_combo)
        image_layout.addLayout(scale_row)

        img_alpha_row = QHBoxLayout()
        img_alpha_row.addWidget(QLabel("透明度:"))
        self.img_alpha = QDoubleSpinBox()
        self.img_alpha.setRange(0.0, 1.0)
        self.img_alpha.setSingleStep(0.1)
        self.img_alpha.setValue(0.9)
        img_alpha_row.addWidget(self.img_alpha)
        image_layout.addLayout(img_alpha_row)

        self.image_settings_group.setVisible(False)
        layout.addWidget(self.image_settings_group)

        # 输出设置
        self.output_group = QGroupBox("输出设置")
        output_layout = QVBoxLayout(self.output_group)

        enc_layout = QHBoxLayout()
        enc_layout.addWidget(QLabel("视频编码器:"))
        self.encoder_combo = QComboBox()
        encoders = self._detect_encoders()
        self.encoder_combo.addItems(encoders)
        self.encoder_combo.setToolTip("选择用于编码的硬件加速器或 CPU")
        enc_layout.addWidget(self.encoder_combo)
        output_layout.addLayout(enc_layout)

        qual_layout = QHBoxLayout()
        qual_layout.addWidget(QLabel("输出质量:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["标准", "高质量", "无损"])
        self.quality_combo.setToolTip("无损：视觉无损，文件极大；高质量：接近原画；标准：均衡文件大小")
        qual_layout.addWidget(self.quality_combo)
        output_layout.addLayout(qual_layout)

        layout.addWidget(self.output_group)
        layout.addStretch()
        return group

    def _detect_encoders(self):
        options = ["自动 (libx264)"]
        try:
            result = subprocess.run(
                ["ffmpeg", "-encoders"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                output = result.stdout
                if "h264_nvenc" in output:
                    options.append("NVIDIA NVENC (h264_nvenc)")
                if "h264_qsv" in output:
                    options.append("Intel QSV (h264_qsv)")
                if "h264_amf" in output:
                    options.append("AMD AMF (h264_amf)")
        except Exception:
            pass
        return options

    def _current_encoder_params(self):
        encoder_text = self.encoder_combo.currentText()
        quality = self.quality_combo.currentText()
        if "NVENC" in encoder_text:
            encoder = "nvenc"
        elif "QSV" in encoder_text:
            encoder = "qsv"
        elif "AMF" in encoder_text:
            encoder = "amf"
        else:
            encoder = "libx264"
        return encoder, quality

    def _on_mode_changed(self, index):
        if index == 0:   # 去水印
            self.mode = "remove"
            self.add_type_group.setVisible(False)
            self.text_settings_group.setVisible(False)
            self.image_settings_group.setVisible(False)
            self.remove_before_add_check.setVisible(False)
        else:            # 加水印
            self.mode = "add"
            self.add_type_group.setVisible(True)
            self.remove_before_add_check.setVisible(True)
            self._update_add_sub_settings()

    def _update_add_sub_settings(self):
        if self.type_text_radio.isChecked():
            self.text_settings_group.setVisible(True)
            self.image_settings_group.setVisible(False)
        else:
            self.text_settings_group.setVisible(False)
            self.image_settings_group.setVisible(True)

    def _connect_signals(self):
        self.open_btn.clicked.connect(self._open_video)
        self.confirm_rect_btn.clicked.connect(self._confirm_rect)
        self.start_btn.clicked.connect(self._start_process)
        self.slider.valueChanged.connect(self._slider_moved)
        self.player.area_selected.connect(self._on_area_selected)
        self.type_text_radio.toggled.connect(self._update_add_sub_settings)
        self.img_browse_btn.clicked.connect(self._browse_image)

    # ---------- 配置持久化 ----------
    def _load_settings(self):
        """启动时恢复上次的界面配置"""
        # 模式
        mode_idx = self.settings.value("mode", 0, type=int)
        self.mode_combo.setCurrentIndex(mode_idx)

        # 文字水印设置
        self.text_input.setText(self.settings.value("text_input", "我的水印"))
        font_family = self.settings.value("font_family", "")
        if font_family:
            idx = self.font_combo.findText(font_family)
            if idx >= 0:
                self.font_combo.setCurrentIndex(idx)
        self.font_size.setValue(self.settings.value("font_size", 24, type=int))
        self.color_combo.setCurrentText(self.settings.value("color", "white"))
        self.text_alpha.setValue(self.settings.value("text_alpha", 0.8, type=float))
        self.bold_check.setChecked(self.settings.value("bold", False, type=bool))
        self.italic_check.setChecked(self.settings.value("italic", False, type=bool))
        self.angle_spin.setValue(self.settings.value("angle", 0.0, type=float))

        # 图片水印设置
        self.img_path_edit.setText(self.settings.value("img_path", ""))
        self.scale_combo.setCurrentIndex(self.settings.value("scale_mode", 0, type=int))
        self.img_alpha.setValue(self.settings.value("img_alpha", 0.9, type=float))

        # 水印类型
        type_text = self.settings.value("watermark_type", "text")
        if type_text == "image":
            self.type_image_radio.setChecked(True)

        # 去除原水印选项
        self.remove_before_add_check.setChecked(
            self.settings.value("remove_before_add", False, type=bool)
        )

        # 框选区域
        rect = self.settings.value("watermark_rect")
        if rect and len(rect) == 4:
            self.watermark_rect = tuple(rect)
            x, y, w, h = self.watermark_rect
            self.rect_label.setText(f"选择区域: x={x}, y={y}, 宽={w}, 高={h}")
            self.start_btn.setEnabled(True)
            # 注意：此时播放器还没加载视频，无法设置矩形；等打开视频后再恢复矩形

        # 编码器与质量
        enc_text = self.settings.value("encoder", "自动 (libx264)")
        idx = self.encoder_combo.findText(enc_text)
        if idx >= 0:
            self.encoder_combo.setCurrentIndex(idx)
        qual_text = self.settings.value("quality", "标准")
        idx = self.quality_combo.findText(qual_text)
        if idx >= 0:
            self.quality_combo.setCurrentIndex(idx)
        # 最后同步一下当前模式下的UI控件可见性
        self._on_mode_changed(self.mode_combo.currentIndex())

    def _save_settings(self):
        """关闭时保存当前配置"""
        self.settings.setValue("mode", self.mode_combo.currentIndex())
        self.settings.setValue("text_input", self.text_input.text())
        self.settings.setValue("font_family", self.font_combo.currentFont().family())
        self.settings.setValue("font_size", self.font_size.value())
        self.settings.setValue("color", self.color_combo.currentText())
        self.settings.setValue("text_alpha", self.text_alpha.value())
        self.settings.setValue("bold", self.bold_check.isChecked())
        self.settings.setValue("italic", self.italic_check.isChecked())
        self.settings.setValue("angle", self.angle_spin.value())
        self.settings.setValue("img_path", self.img_path_edit.text())
        self.settings.setValue("scale_mode", self.scale_combo.currentIndex())
        self.settings.setValue("img_alpha", self.img_alpha.value())
        self.settings.setValue("watermark_type", "image" if self.type_image_radio.isChecked() else "text")
        self.settings.setValue("remove_before_add", self.remove_before_add_check.isChecked())
        if self.watermark_rect:
            self.settings.setValue("watermark_rect", self.watermark_rect)
        self.settings.setValue("encoder", self.encoder_combo.currentText())
        self.settings.setValue("quality", self.quality_combo.currentText())

    def closeEvent(self, event):
        self._save_settings()
        super().closeEvent(event)

    # ---------- 原有功能方法 ----------
    def _open_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择视频文件", "", "视频文件 (*.mp4 *.avi *.mov *.mkv *.flv);;所有文件 (*)"
        )
        if not path:
            return
        if self.cap is not None:
            self.cap.release()
        self.video_path = path
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            QMessageBox.critical(self, "错误", "无法打开视频文件")
            return
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.slider.setRange(0, max(0, self.total_frames - 1))
        self.slider.setEnabled(True)
        self._show_frame(0)
        self.confirm_rect_btn.setEnabled(True)
        self.start_btn.setEnabled(False)
        # 不清空 watermarm_rect，允许恢复上次矩形
        if self.watermark_rect:
            self.rect_label.setText(f"上次区域: x={self.watermark_rect[0]}, y={self.watermark_rect[1]}, "
                                    f"宽={self.watermark_rect[2]}, 高={self.watermark_rect[3]}")
            self.start_btn.setEnabled(True)
        else:
            self.rect_label.setText("未选择区域")

    def _show_frame(self, idx):
        if self.cap is None:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = self.cap.read()
        if ret:
            self.player.set_frame(frame)
            self.current_frame_idx = idx
            self.slider.blockSignals(True)
            self.slider.setValue(idx)
            self.slider.blockSignals(False)
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            if fps > 0:
                cur_sec = idx / fps
                total_sec = self.total_frames / fps
                self.time_label.setText(f"{self._sec_to_hms(cur_sec)} / {self._sec_to_hms(total_sec)}")

    def _slider_moved(self, value):
        self._show_frame(value)

    def _on_area_selected(self, x, y, w, h):
        self.watermark_rect = (x, y, w, h)
        self.rect_label.setText(f"选择区域: x={x}, y={y}, 宽={w}, 高={h}")
        self.start_btn.setEnabled(True)

    def _confirm_rect(self):
        if self.watermark_rect:
            QMessageBox.information(self, "确认", f"当前区域: {self.watermark_rect}")
        else:
            QMessageBox.warning(self, "提示", "请先在播放器上框选区域")

    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片水印", "", "图片文件 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*)"
        )
        if path:
            self.img_path_edit.setText(path)

    def _start_process(self):
        if not self.video_path or not self.watermark_rect:
            QMessageBox.warning(self, "提示", "请先打开视频并框选区域")
            return
        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存输出视频", "output.mp4", "MP4文件 (*.mp4)"
        )
        if not save_path:
            return

        x, y, w, h = self.watermark_rect
        encoder, quality = self._current_encoder_params()

        self.progress_dialog = ProgressDialog(self)
        self.progress_dialog.show()

        if self.mode == "remove":
            self.worker_thread = QThread()
            self.remover = WatermarkRemover()
            self.remover.moveToThread(self.worker_thread)
            self.remover.progress_updated.connect(self.progress_dialog.set_progress)
            self.remover.status_updated.connect(self.progress_dialog.set_status)
            self.remover.finished.connect(self._on_finished)
            self.worker_thread.started.connect(
                lambda: self.remover.remove(
                    self.video_path, save_path, x, y, w, h,
                    encoder=encoder, quality=quality
                )
            )
        else:   # add watermark
            self.worker_thread = QThread()
            self.adder = WatermarkAdder()
            self.adder.moveToThread(self.worker_thread)
            self.adder.progress_updated.connect(self.progress_dialog.set_progress)
            self.adder.status_updated.connect(self.progress_dialog.set_status)
            self.adder.finished.connect(self._on_finished)

            remove_first = self.remove_before_add_check.isChecked()
            remove_rect = (x, y, w, h) if remove_first else None

            if self.type_text_radio.isChecked():
                text = self.text_input.text()
                font = self.font_combo.currentFont().family()
                size = self.font_size.value()
                color = self.color_combo.currentText()
                alpha = self.text_alpha.value()
                bold = self.bold_check.isChecked()
                italic = self.italic_check.isChecked()
                angle = self.angle_spin.value()
                self.worker_thread.started.connect(
                    lambda: self.adder.add_text(
                        self.video_path, save_path, text, x, y,
                        fontfile=font, fontsize=size, fontcolor=color,
                        alpha=alpha, bold=bold, italic=italic, angle=angle,
                        encoder=encoder, quality=quality,
                        remove_first=remove_first, remove_rect=remove_rect
                    )
                )
            else:
                img_path = self.img_path_edit.text()
                if not img_path or not os.path.exists(img_path):
                    QMessageBox.warning(self, "错误", "请选择有效的图片文件")
                    self.progress_dialog.close()
                    return
                alpha = self.img_alpha.value()
                if self.scale_combo.currentIndex() == 0:
                    scale_w, scale_h = w, h
                else:
                    scale_w, scale_h = 0, 0
                self.worker_thread.started.connect(
                    lambda: self.adder.add_image(
                        self.video_path, save_path, img_path, x, y,
                        width=scale_w, height=scale_h, alpha=alpha,
                        encoder=encoder, quality=quality,
                        remove_first=remove_first, remove_rect=remove_rect
                    )
                )

        if self.mode == "remove":
            self.remover.finished.connect(self.worker_thread.quit)
            self.remover.finished.connect(self.remover.deleteLater)
        else:
            self.adder.finished.connect(self.worker_thread.quit)
            self.adder.finished.connect(self.adder.deleteLater)

        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def _on_finished(self, success, message):
        self.progress_dialog.close()
        if success:
            QMessageBox.information(self, "完成", f"处理完成，已保存至：\n{message}")
        else:
            QMessageBox.critical(self, "错误", message)

    @staticmethod
    def _sec_to_hms(seconds):
        m, s = divmod(int(seconds), 60)
        h, m = divmod(m, 60)
        return f"{h:02}:{m:02}:{s:02}"