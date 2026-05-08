import os
import cv2
import traceback

from PySide6.QtCore import (
    Qt,
    QThread,
    QSettings,
    Slot
)

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QSlider,
    QFileDialog,
    QLabel,
    QMessageBox,
    QGroupBox,
    QRadioButton,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QCheckBox,
    QFontComboBox,
    QApplication
)

from .video_player import VideoPlayer
from .progress_dialog import ProgressDialog

from ..processor.remover import WatermarkRemover
from ..processor.watermark_adder import WatermarkAdder

from ..core.logger import logger
from ..core.utils import get_best_encoder


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("视频去/加水印工具")
        self.resize(1400, 900)

        self.video_path = None
        self.cap = None

        self.total_frames = 0
        self.current_frame_idx = 0

        self.watermark_rect = None

        self.processing = False

        self.worker_thread = None
        self.worker = None

        self.progress_dialog = None

        self.settings = QSettings("JVSClaw", "WatermarkTool")

        self._setup_ui()
        self._connect_signals()
        self._load_settings()

    # =========================================================
    # UI
    # =========================================================

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)

        # ======================
        # Left
        # ======================
        left_layout = QVBoxLayout()

        self.player = VideoPlayer()
        left_layout.addWidget(self.player, 1)

        slider_layout = QHBoxLayout()

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setEnabled(False)

        self.time_label = QLabel("00:00:00 / 00:00:00")

        slider_layout.addWidget(self.slider)
        slider_layout.addWidget(self.time_label)

        left_layout.addLayout(slider_layout)

        btn_layout = QHBoxLayout()

        self.open_btn = QPushButton("打开视频")
        self.confirm_rect_btn = QPushButton("确认区域")
        self.start_btn = QPushButton("开始处理")

        self.confirm_rect_btn.setEnabled(False)
        self.start_btn.setEnabled(False)

        btn_layout.addWidget(self.open_btn)
        btn_layout.addWidget(self.confirm_rect_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.start_btn)

        left_layout.addLayout(btn_layout)

        self.info_label = QLabel("提示：拖拽框选区域，可移动/缩放选框")
        left_layout.addWidget(self.info_label)

        root.addLayout(left_layout, 2)

        # ======================
        # Right
        # ======================
        settings_panel = self._create_settings_panel()
        root.addWidget(settings_panel, 1)

    def _create_settings_panel(self):
        group = QGroupBox("设置")
        layout = QVBoxLayout(group)

        # ======================
        # mode
        # ======================
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("模式"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["去水印", "加文字水印", "加图片水印"])
        mode_row.addWidget(self.mode_combo)
        layout.addLayout(mode_row)

        # ======================
        # rect
        # ======================
        self.rect_label = QLabel("未选择区域")
        layout.addWidget(self.rect_label)

        # ======================
        # text watermark
        # ======================
        self.text_group = QGroupBox("文字水印")
        text_layout = QVBoxLayout(self.text_group)

        text_layout.addWidget(QLabel("文字"))
        self.text_input = QLineEdit("我的水印")
        text_layout.addWidget(self.text_input)

        font_row = QHBoxLayout()
        font_row.addWidget(QLabel("字体"))
        self.font_combo = QFontComboBox()
        font_row.addWidget(self.font_combo)
        text_layout.addLayout(font_row)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("颜色"))
        self.color_combo = QComboBox()
        self.color_combo.addItems([
            "white", "black", "red", "green", "blue", "yellow", "cyan"
        ])
        color_row.addWidget(self.color_combo)
        text_layout.addLayout(color_row)

        alpha_row = QHBoxLayout()
        alpha_row.addWidget(QLabel("透明度"))
        self.text_alpha = QDoubleSpinBox()
        self.text_alpha.setRange(0.0, 1.0)
        self.text_alpha.setSingleStep(0.1)
        self.text_alpha.setValue(0.8)
        alpha_row.addWidget(self.text_alpha)
        text_layout.addLayout(alpha_row)

        angle_row = QHBoxLayout()
        angle_row.addWidget(QLabel("旋转"))
        self.angle_spin = QDoubleSpinBox()
        self.angle_spin.setRange(-360, 360)
        angle_row.addWidget(self.angle_spin)
        text_layout.addLayout(angle_row)

        # ---- 新增：字体文件选择 (解决中文方框) ----
        fontfile_row = QHBoxLayout()
        fontfile_row.addWidget(QLabel("字体文件"))
        self.fontfile_edit = QLineEdit()
        self.fontfile_edit.setReadOnly(True)
        self.fontfile_browse_btn = QPushButton("浏览")
        fontfile_row.addWidget(self.fontfile_edit)
        fontfile_row.addWidget(self.fontfile_browse_btn)
        text_layout.addLayout(fontfile_row)
        # -----------------------------------------

        layout.addWidget(self.text_group)

        # ======================
        # image watermark
        # ======================
        self.image_group = QGroupBox("图片水印")
        image_layout = QVBoxLayout(self.image_group)

        img_row = QHBoxLayout()
        self.img_path_edit = QLineEdit()
        self.img_path_edit.setReadOnly(True)
        self.img_browse_btn = QPushButton("浏览")
        img_row.addWidget(self.img_path_edit)
        img_row.addWidget(self.img_browse_btn)
        image_layout.addLayout(img_row)

        scale_row = QHBoxLayout()
        scale_row.addWidget(QLabel("缩放"))
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["适应区域", "原始大小"])
        scale_row.addWidget(self.scale_combo)
        image_layout.addLayout(scale_row)

        alpha2_row = QHBoxLayout()
        alpha2_row.addWidget(QLabel("透明度"))
        self.img_alpha = QDoubleSpinBox()
        self.img_alpha.setRange(0.0, 1.0)
        self.img_alpha.setSingleStep(0.1)
        self.img_alpha.setValue(0.9)
        alpha2_row.addWidget(self.img_alpha)
        image_layout.addLayout(alpha2_row)

        layout.addWidget(self.image_group)

        # ======================
        # encoder
        # ======================
        output_group = QGroupBox("输出")
        output_layout = QVBoxLayout(output_group)

        enc_row = QHBoxLayout()
        enc_row.addWidget(QLabel("编码器"))
        self.encoder_combo = QComboBox()
        self.encoder_combo.addItems(["nvenc", "qsv", "amf", "libx264"])
        self.encoder_combo.setCurrentText(get_best_encoder())
        enc_row.addWidget(self.encoder_combo)
        output_layout.addLayout(enc_row)

        quality_row = QHBoxLayout()
        quality_row.addWidget(QLabel("质量"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["标准", "高质量", "无损"])
        quality_row.addWidget(self.quality_combo)
        output_layout.addLayout(quality_row)

        layout.addWidget(output_group)

        # ======================
        # option
        # ======================
        self.remove_before_add_check = QCheckBox("先去原水印再添加")
        layout.addWidget(self.remove_before_add_check)

        layout.addStretch()
        self._update_mode_ui()

        return group

    # =========================================================
    # signals
    # =========================================================

    def _connect_signals(self):
        self.open_btn.clicked.connect(self._open_video)
        self.slider.valueChanged.connect(self._slider_changed)
        self.player.area_selected.connect(self._on_area_selected)
        self.confirm_rect_btn.clicked.connect(self._confirm_rect)
        self.start_btn.clicked.connect(self._start_process)
        self.mode_combo.currentIndexChanged.connect(self._update_mode_ui)
        self.img_browse_btn.clicked.connect(self._browse_image)
        self.fontfile_browse_btn.clicked.connect(self._browse_font)

    # =========================================================
    # settings
    # =========================================================

    def _load_settings(self):
        mode = self.settings.value("mode", 0, type=int)
        self.mode_combo.setCurrentIndex(mode)

        self.text_input.setText(self.settings.value("text", "我的水印"))
        font = self.settings.value("font", "")
        if font:
            idx = self.font_combo.findText(font)
            if idx >= 0:
                self.font_combo.setCurrentIndex(idx)
        color = self.settings.value("color", "white")
        idx = self.color_combo.findText(color)
        if idx >= 0:
            self.color_combo.setCurrentIndex(idx)
        self.text_alpha.setValue(self.settings.value("text_alpha", 0.8, type=float))
        self.angle_spin.setValue(self.settings.value("angle", 0.0, type=float))
        self.fontfile_edit.setText(self.settings.value("fontfile", ""))

        self.img_path_edit.setText(self.settings.value("image_path", ""))
        scale = self.settings.value("scale_mode", 0, type=int)
        self.scale_combo.setCurrentIndex(scale)
        self.img_alpha.setValue(self.settings.value("img_alpha", 0.9, type=float))

        enc = self.settings.value("encoder", "libx264")
        idx = self.encoder_combo.findText(enc)
        if idx >= 0:
            self.encoder_combo.setCurrentIndex(idx)
        qual = self.settings.value("quality", "标准")
        idx = self.quality_combo.findText(qual)
        if idx >= 0:
            self.quality_combo.setCurrentIndex(idx)

        self.remove_before_add_check.setChecked(
            self.settings.value("remove_before_add", False, type=bool)
        )

        rect_list = self.settings.value("watermark_rect")
        if rect_list and len(rect_list) == 4:
            self.watermark_rect = tuple(rect_list)
        else:
            self.watermark_rect = None

        self._update_mode_ui()

    def _save_settings(self):
        self.settings.setValue("mode", self.mode_combo.currentIndex())
        self.settings.setValue("text", self.text_input.text())
        self.settings.setValue("font", self.font_combo.currentText())
        self.settings.setValue("color", self.color_combo.currentText())
        self.settings.setValue("text_alpha", self.text_alpha.value())
        self.settings.setValue("angle", self.angle_spin.value())
        self.settings.setValue("fontfile", self.fontfile_edit.text())

        self.settings.setValue("image_path", self.img_path_edit.text())
        self.settings.setValue("scale_mode", self.scale_combo.currentIndex())
        self.settings.setValue("img_alpha", self.img_alpha.value())

        self.settings.setValue("encoder", self.encoder_combo.currentText())
        self.settings.setValue("quality", self.quality_combo.currentText())
        self.settings.setValue("remove_before_add", self.remove_before_add_check.isChecked())

        if self.watermark_rect:
            self.settings.setValue("watermark_rect", list(self.watermark_rect))
        else:
            self.settings.remove("watermark_rect")

    # =========================================================
    # mode ui
    # =========================================================

    def _update_mode_ui(self):
        idx = self.mode_combo.currentIndex()
        self.text_group.setVisible(idx == 1)
        self.image_group.setVisible(idx == 2)

    # =========================================================
    # open video
    # =========================================================

    def _open_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择视频", "", "Video (*.mp4 *.avi *.mov *.mkv *.flv)"
        )
        if not path:
            return

        try:
            if self.cap:
                self.cap.release()
            self.cap = cv2.VideoCapture(path)
            if not self.cap.isOpened():
                raise RuntimeError("无法打开视频")
            self.video_path = path
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.slider.setEnabled(True)
            self.slider.setRange(0, max(0, self.total_frames - 1))
            self.confirm_rect_btn.setEnabled(True)

            self._show_frame(0)

            # 恢复选框
            if self.watermark_rect:
                x, y, w, h = self.watermark_rect
                self.player.set_selection_by_video_coords(x, y, w, h)
                self.rect_label.setText(f"x={x}, y={y}, w={w}, h={h}")
                self.start_btn.setEnabled(True)
            else:
                self.rect_label.setText("未选择区域")
                self.start_btn.setEnabled(False)

            logger.info("video opened: %s", path)

        except Exception as e:
            logger.exception(e)
            QMessageBox.critical(self, "错误", str(e))

    # =========================================================
    # frame
    # =========================================================

    def _show_frame(self, idx):
        if not self.cap:
            return

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = self.cap.read()

        if not ret:
            return

        self.current_frame_idx = idx
        self.player.set_frame(frame)

        self.slider.blockSignals(True)
        self.slider.setValue(idx)
        self.slider.blockSignals(False)

        fps = self.cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25

        cur = idx / fps
        total = self.total_frames / fps
        self.time_label.setText(
            f"{self._sec_to_hms(cur)} / {self._sec_to_hms(total)}"
        )

    def _slider_changed(self, value):
        self._show_frame(value)

    # =========================================================
    # area
    # =========================================================

    @Slot(int, int, int, int)
    def _on_area_selected(self, x, y, w, h):
        self.watermark_rect = (x, y, w, h)
        self.rect_label.setText(f"x={x}, y={y}, w={w}, h={h}")
        self.start_btn.setEnabled(True)

    def _confirm_rect(self):
        if not self.watermark_rect:
            QMessageBox.warning(self, "提示", "请先框选区域")
            return
        QMessageBox.information(self, "确认", str(self.watermark_rect))

    # =========================================================
    # image & font browse
    # =========================================================

    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", "", "Image (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self.img_path_edit.setText(path)

    def _browse_font(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择字体文件", "", "字体文件 (*.ttf *.otf)"
        )
        if path:
            self.fontfile_edit.setText(path)

    # =========================================================
    # process
    # =========================================================

    def _start_process(self):
        if self.processing:
            return

        if not self.video_path:
            QMessageBox.warning(self, "提示", "请先打开视频")
            return

        if not self.watermark_rect:
            QMessageBox.warning(self, "提示", "请先框选区域")
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self, "保存视频", "output.mp4", "MP4 (*.mp4)"
        )
        if not save_path:
            return

        self.processing = True
        self.start_btn.setEnabled(False)

        self.progress_dialog = ProgressDialog(self)
        self.progress_dialog.show()
        QApplication.processEvents()

        x, y, w, h = self.watermark_rect
        encoder = self.encoder_combo.currentText()
        quality = self.quality_combo.currentText()
        mode = self.mode_combo.currentIndex()

        self.worker_thread = QThread()

        try:
            if mode == 0:  # 去水印
                self.worker = WatermarkRemover()
                self.worker.moveToThread(self.worker_thread)
                self.worker_thread.started.connect(
                    lambda: self.worker.remove(
                        self.video_path, save_path, x, y, w, h,
                        encoder, quality
                    )
                )

            elif mode == 1:  # 加文字水印
                self.worker = WatermarkAdder()
                self.worker.moveToThread(self.worker_thread)
                self.worker_thread.started.connect(
                    lambda: self.worker.add_text(
                        input_path=self.video_path,
                        output_path=save_path,
                        text=self.text_input.text(),
                        x=x, y=y,
                        fontsize=0,   # 自适应
                        fontcolor=self.color_combo.currentText(),
                        alpha=self.text_alpha.value(),
                        fontfile=self.fontfile_edit.text().strip() or "",
                        encoder=encoder,
                        quality=quality,
                        remove_first=self.remove_before_add_check.isChecked(),
                        remove_rect=self.watermark_rect,
                        rect=self.watermark_rect
                    )
                )

            else:  # 加图片水印
                image_path = self.img_path_edit.text().strip()
                if not image_path:
                    QMessageBox.warning(self, "错误", "请选择图片")
                    self.processing = False
                    self.start_btn.setEnabled(True)
                    return

                self.worker = WatermarkAdder()
                self.worker.moveToThread(self.worker_thread)
                if self.scale_combo.currentIndex() == 0:
                    scale_w, scale_h = w, h
                else:
                    scale_w, scale_h = 0, 0
                self.worker_thread.started.connect(
                    lambda: self.worker.add_image(
                        input_path=self.video_path,
                        output_path=save_path,
                        image_path=image_path,
                        x=x, y=y,
                        width=scale_w,
                        height=scale_h,
                        alpha=self.img_alpha.value(),
                        encoder=encoder,
                        quality=quality,
                        remove_first=self.remove_before_add_check.isChecked(),
                        remove_rect=self.watermark_rect
                    )
                )

            # 通用信号连接
            self.worker.progress_updated.connect(self.progress_dialog.set_progress)
            self.worker.status_updated.connect(self.progress_dialog.set_status)
            self.worker.finished.connect(self._on_finished)
            self.progress_dialog.cancel_btn.clicked.connect(self._cancel_task)

            self.worker_thread.start()

        except Exception as e:
            if self.worker_thread:
                self.worker_thread.deleteLater()
                self.worker_thread = None
            logger.exception(e)
            traceback.print_exc()
            self.processing = False
            self.start_btn.setEnabled(True)
            QMessageBox.critical(self, "错误", str(e))

    # =========================================================
    # cancel
    # =========================================================

    def _cancel_task(self):
        try:
            if self.worker:
                self.worker.cancel()
        except Exception as e:
            logger.exception(e)

    # =========================================================
    # finished
    # =========================================================

    @Slot(bool, str)
    def _on_finished(self, success, message):
        self.processing = False
        self.start_btn.setEnabled(True)

        # 关闭进度对话框
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        # 先退出工作线程，等待完成
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(5000)

        # 安全释放 worker 对象
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

        # 释放线程对象
        if self.worker_thread:
            self.worker_thread.deleteLater()
            self.worker_thread = None

        self.activateWindow()
        self.raise_()

        if success:
            QMessageBox.information(self, "完成", f"处理完成：\n{message}")
        else:
            QMessageBox.critical(self, "错误", message)

    # =========================================================
    # close
    # =========================================================

    def closeEvent(self, event):
        self._save_settings()

        # 取消正在运行的任务
        if self.worker:
            self.worker.cancel()

        # 请求线程退出并等待
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            if not self.worker_thread.wait(3000):
                # 超时则强制终止
                self.worker_thread.terminate()
                self.worker_thread.wait()

        # 释放视频资源
        try:
            if self.cap:
                self.cap.release()
                self.cap = None
        except Exception:
            pass

        super().closeEvent(event)

    # =========================================================
    # utils
    # =========================================================

    @staticmethod
    def _sec_to_hms(seconds):
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02}:{m:02}:{s:02}"