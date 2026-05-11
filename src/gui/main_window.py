import datetime, os, cv2
from pathlib import Path
from PySide6.QtCore import Qt, QSettings, Slot
from PySide6.QtGui import QKeySequence, QShortcut, QImage
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMessageBox, QFileDialog, QLabel)
from qfluentwidgets import (FluentIcon as FIF, InfoBar, InfoBarPosition, setTheme, Theme)

from .title_bar import TitleBar
from .ui_components.side_bar import SideBar
from .ui_components.top_toolbar import TopToolbar
from .ui_components.video_panel import VideoPanel
from .ui_components.control_bar import ControlBar
from .ui_components.settings_panel import SettingsPanel
from .ui_components.history_dialog import HistoryDialog
from .ui_components.status_bar import setup_status_bar
from .controller import PlaybackController, TaskController
from ..core.history_manager import HistoryManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # ===== 根容器 =====
        self.container = QWidget()
        self.setCentralWidget(self.container)
        self.root_layout = QVBoxLayout(self.container)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # ===== Fluent 标题栏 =====
        self.titleBar = TitleBar(self)
        self.root_layout.addWidget(self.titleBar)

        self._init_services()
        self._init_controllers()
        self._build_ui()
        self._init_status_bar()
        self._connect_signals()
        self._setup_shortcuts()
        self.settings_panel.load_settings(self.app_settings)
        self.last_output_path = None

    def _init_services(self):
        self.history_manager = HistoryManager()
        self.app_settings = QSettings("JVSClaw", "WatermarkTool")
        self.history_records = self.history_manager.load_history()
        self.watermark_rect = None

    def _init_controllers(self):
        self.playback_ctrl = PlaybackController(self)
        self.task_ctrl = TaskController(self)

    def _build_ui(self):
        self.contentWidget = QWidget()
        self.contentWidget.setStyleSheet("""
            background-color: #11151d;
        """)
        self.root_layout.addWidget(self.contentWidget)

        root = QHBoxLayout(self.contentWidget)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = SideBar()
        root.addWidget(self.sidebar)

        self.main_content = QWidget()
        self.main_content.setStyleSheet("background-color: #0b0e13;")
        main_layout = QVBoxLayout(self.main_content)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)

        self.toolbar = TopToolbar()
        main_layout.addWidget(self.toolbar)
        self.video_panel = VideoPanel()
        main_layout.addWidget(self.video_panel, 1)
        self.control_bar = ControlBar()
        main_layout.addWidget(self.control_bar)
        root.addWidget(self.main_content, 1)

        self.settings_panel = SettingsPanel()
        root.addWidget(self.settings_panel)

    def _init_status_bar(self):
        self.status_label, self.gpu_indicator = setup_status_bar(self)

    def _connect_signals(self):
        self.sidebar.history_btn.clicked.connect(self._show_history)
        self.toolbar.open_btn.clicked.connect(self._open_video)
        self.toolbar.start_btn.clicked.connect(self._start_process)
        self.video_panel.player.area_selected.connect(self._on_area_selected)
        self.video_panel.cancel_btn.clicked.connect(self.task_ctrl.cancel_task)
        self.control_bar.play_btn.clicked.connect(self.playback_ctrl.toggle_play)
        self.control_bar.prev_btn.clicked.connect(
            lambda: self.playback_ctrl.seek(self.playback_ctrl.current_frame_idx - 1))
        self.control_bar.next_btn.clicked.connect(
            lambda: self.playback_ctrl.seek(self.playback_ctrl.current_frame_idx + 1))
        self.control_bar.seek_requested.connect(self.playback_ctrl.seek_percent)
        sp = self.settings_panel
        sp.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        sp.spin_x.valueChanged.connect(self._on_roi_spinbox_changed)
        sp.spin_y.valueChanged.connect(self._on_roi_spinbox_changed)
        sp.spin_w.valueChanged.connect(self._on_roi_spinbox_changed)
        sp.spin_h.valueChanged.connect(self._on_roi_spinbox_changed)
        sp.clear_rect_btn.clicked.connect(self._clear_rect)
        sp.apply_rect_btn.clicked.connect(self._confirm_rect)
        sp.img_browse_btn.clicked.connect(self._browse_image)
        sp.fontfile_btn.clicked.connect(self._browse_font)
        sp.output_browse_btn.clicked.connect(self._browse_output_path)
        if hasattr(sp, 'patch_browse_btn'):
            sp.patch_browse_btn.clicked.connect(self._browse_patch_image)
        self.playback_ctrl.video_loaded.connect(self._on_video_loaded)
        self.playback_ctrl.frame_changed.connect(self.video_panel.player.set_qimage)
        self.playback_ctrl.play_state_changed.connect(self.control_bar.set_play_icon)
        self.playback_ctrl.time_updated.connect(self.control_bar.update_time)
        self.task_ctrl.progress_updated.connect(self._on_task_progress)
        self.task_ctrl.status_updated.connect(self._on_status_update)
        self.task_ctrl.task_started.connect(self._on_task_started)
        self.task_ctrl.task_finished.connect(self._on_task_finished)

    # ==================== 业务逻辑（完全不变） ====================
    @Slot(str, int, int, float, int)
    def _on_video_loaded(self, path, w, h, fps, total_frames):
        self.toolbar.update_video_info(Path(path).name, w, h, fps)
        self.control_bar.enable_controls(True)
        self.control_bar.update_slider(0, total_frames)
        self.status_label.setText(f"已加载: {Path(path).name}")
        if hasattr(self.control_bar, 'timeline'):
            self.control_bar.timeline.generate_waveform(path)
        if self.watermark_rect:
            x, y, rw, rh = self.watermark_rect
            self.video_panel.player.set_selection_by_video_coords(x, y, rw, rh)
            self.settings_panel.set_roi_values(x, y, rw, rh)
            self.toolbar.set_processing_enabled(True)
        else:
            self._clear_rect()

    @Slot(int, int, int, int)
    def _on_area_selected(self, x, y, w, h):
        self.watermark_rect = (x, y, w, h)
        self.settings_panel.set_roi_values(x, y, w, h)
        self.toolbar.set_processing_enabled(True)

    def _on_roi_spinbox_changed(self):
        x, y, w, h = self.settings_panel.get_roi_values()
        self.watermark_rect = (x, y, w, h)
        self.video_panel.player.set_selection_by_video_coords(x, y, w, h)
        self.toolbar.set_processing_enabled(w > 0 and h > 0)

    @Slot(int)
    def _on_mode_changed(self, index):
        self.settings_panel.update_mode_visibility(index)
        self.video_panel.player.set_preview_mode(index)

    def _clear_rect(self):
        self.watermark_rect = None
        self.video_panel.player.clear_selection()
        self.settings_panel.clear_roi()
        self.toolbar.set_processing_enabled(False)

    def _confirm_rect(self):
        if not self.watermark_rect:
            InfoBar.warning(self, "提示", "请先框选区域", duration=2000, position=InfoBarPosition.TOP)
            return
        self.video_panel.player.update()

    def _open_video(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择视频", "",
                                              "Video (*.mp4 *.avi *.mov *.mkv *.flv);;All Files (*)")
        if not path: return
        try:
            self.playback_ctrl.load_video(path)
        except Exception as e:
            InfoBar.error(self, "错误", f"无法打开视频:\n{str(e)}", duration=5000, position=InfoBarPosition.TOP_RIGHT)

    def _start_process(self):
        if not self.playback_ctrl.video_path:
            InfoBar.warning(self, "提示", "请先打开视频文件", duration=2000, position=InfoBarPosition.TOP)
            return
        mode = self.settings_panel.current_mode
        valid, err_msg = self.settings_panel.validate_for_processing(mode)
        if not valid:
            InfoBar.error(self, "配置错误", err_msg, duration=3000, position=InfoBarPosition.TOP_RIGHT)
            return
        out_cfg = self.settings_panel.get_output_config()
        save_path = os.path.join(out_cfg['path'],
                                 f"{Path(self.playback_ctrl.video_path).stem}_processed.{out_cfg['format']}")
        self.last_output_path = save_path
        if os.path.exists(save_path):
            reply = QMessageBox.question(self, "文件已存在", f"输出文件已存在:\n{save_path}\n\n是否覆盖？",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes: return
        if mode == 0:
            remove_cfg = self.settings_panel.get_remove_config()
        else:
            remove_cfg = None
        if mode == 1:
            txt_cfg = self.settings_panel.get_text_watermark_config()
            out_cfg.update(txt_cfg)
        elif mode == 2:
            img_cfg = self.settings_panel.get_image_watermark_config()
            out_cfg.update(img_cfg)
        self.gpu_indicator.start_monitoring()
        self.task_ctrl.start_process(out_cfg, self.playback_ctrl.video_path, mode, self.watermark_rect, remove_cfg)

    def _on_task_started(self):
        self.toolbar.set_processing_enabled(False)
        self.video_panel.show_progress(True)
        self.video_panel.reset_progress()
        self.control_bar.enable_controls(False)

    @Slot(int)
    def _on_task_progress(self, value):
        self.video_panel.update_progress(value)
        self.control_bar.set_processing_progress(value)

    @Slot(bool, str)
    def _on_task_finished(self, success, message):
        self.gpu_indicator.stop_monitoring()
        self.toolbar.set_processing_enabled(True)
        self.video_panel.show_progress(False)
        self.control_bar.enable_controls(True)
        self.control_bar.set_processing_progress(-1)
        if success and self.playback_ctrl.video_path:
            self._add_history(self.playback_ctrl.video_path, message, "成功")
            self.status_label.setText("处理完成")
            self._show_last_frame()
            InfoBar.success(self, "完成", f"处理完成！输出: {message}", duration=5000, position=InfoBarPosition.TOP_RIGHT)
        else:
            self.status_label.setText("处理失败")
            InfoBar.error(self, "失败", f"处理失败:\n{message}", duration=8000, position=InfoBarPosition.TOP_RIGHT)

    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择水印图片", "",
                                              "Images (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)")
        if path: self.settings_panel.img_path_edit.setText(path)

    def _browse_patch_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择补丁图片", "",
                                              "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)")
        if path: self.settings_panel.patch_image_edit.setText(path)

    def _browse_font(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择字体文件", "", "Font Files (*.ttf *.otf *.ttc);;All Files (*)")
        if path: self.settings_panel.fontfile_edit.setText(path)

    def _browse_output_path(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录", self.settings_panel.output_path_edit.text())
        if dir_path: self.settings_panel.output_path_edit.setText(dir_path)

    def _show_history(self):
        dlg = HistoryDialog(self.history_records, self)
        dlg.exec()

    def _add_history(self, source, output, status):
        rec = {"time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "source": source, "output": output,
               "status": status}
        self.history_records.append(rec)
        self.history_manager.save_history(self.history_records)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key_Space), self, self.playback_ctrl.toggle_play)
        QShortcut(QKeySequence(Qt.Key_Left), self,
                  lambda: self.playback_ctrl.seek(self.playback_ctrl.current_frame_idx - 1))
        QShortcut(QKeySequence(Qt.Key_Right), self,
                  lambda: self.playback_ctrl.seek(self.playback_ctrl.current_frame_idx + 1))
        QShortcut(QKeySequence("Ctrl+O"), self, self._open_video)
        QShortcut(QKeySequence(Qt.Key_Delete), self, self._clear_rect)

    def closeEvent(self, event):
        self.settings_panel.save_settings(self.app_settings)
        self.task_ctrl.cleanup()
        self.playback_ctrl.release()
        self.gpu_indicator.stop_monitoring()
        super().closeEvent(event)

    def _show_last_frame(self):
        if not self.last_output_path or not os.path.exists(self.last_output_path):
            return
        self.playback_ctrl.frame_reader.pause()
        self.playback_ctrl.is_playing = False
        cap = cv2.VideoCapture(self.last_output_path)
        if not cap.isOpened():
            cap.release()
            return
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, total - 1)
            ret, frame = cap.read()
            if ret:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                bytes_per_line = ch * w
                img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
                self.video_panel.player.set_qimage(img, total - 1)
                self.control_bar.set_play_icon(False)
        cap.release()

    @Slot(str)
    def _on_status_update(self, text):
        if text.startswith("segment_complete:"):
            seg_file = text.split(":", 1)[1]
            self._show_segment_last_frame(seg_file)
        else:
            self.video_panel.update_progress(None, text)

    def _show_segment_last_frame(self, seg_file: str):
        if not seg_file or not os.path.exists(seg_file):
            return
        self.playback_ctrl.frame_reader.pause()
        self.playback_ctrl.is_playing = False
        cap = cv2.VideoCapture(seg_file)
        if not cap.isOpened():
            cap.release()
            return
        ret, frame = cap.read()
        if ret:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            bytes_per_line = ch * w
            img = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888).copy()
            self.video_panel.player.set_qimage(img, 0)
        cap.release()