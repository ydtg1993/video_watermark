"""
主窗口 - 协调者模式
职责：组装组件、连接信号、编排业务流程
不包含任何 UI 构建细节，全部委托给子组件
"""
import os
import datetime
import cv2
from pathlib import Path
from PySide6.QtCore import (
    Qt, QThread, QSettings, Slot, Signal, QTimer
)
from PySide6.QtGui import QFont, QDesktopServices, QShortcut, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMessageBox, QDialog, QListWidget, QListWidgetItem,
    QDialogButtonBox, QAbstractItemView, QApplication, QLabel, QPushButton, QFileDialog
)
# 导入 UI 组件
from .ui_components.side_bar import SideBar
from .ui_components.top_toolbar import TopToolbar
from .ui_components.video_panel import VideoPanel
from .ui_components.control_bar import ControlBar
from .ui_components.settings_panel import SettingsPanel
from .video_player import VideoPlayer
from ..core.gpu_monitor import GPUMonitor
# 导入业务层
from ..processor.remover import WatermarkRemover
from ..processor.watermark_adder import WatermarkAdder
from ..core.logger import logger
from ..core.history_manager import HistoryManager
from ..core.theme_manager import ThemeManager


class HistoryDialog(QDialog):
    """历史任务弹窗（轻量级）"""
    def __init__(self, history_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("历史任务")
        self.resize(650, 450)
        self.parent_ref = parent
        self.history_data = history_data
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.itemDoubleClicked.connect(self._open_file_location)
        layout.addWidget(self.list_widget)
        btn_box = QDialogButtonBox()
        clear_btn = QPushButton("清空历史")
        clear_btn.clicked.connect(self._clear_history)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_box.addButton(clear_btn, QDialogButtonBox.ActionRole)
        btn_box.addButton(close_btn, QDialogButtonBox.RejectRole)
        layout.addWidget(btn_box)
        self._refresh_list()

    def _refresh_list(self):
        self.list_widget.clear()
        for rec in reversed(self.history_data):
            text = f"[{rec.get('time', '')}] {rec.get('status', '')}: {Path(rec.get('output', '')).name}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, rec.get("output", ""))
            self.list_widget.addItem(item)

    def _open_file_location(self, item):
        file_path = item.data(Qt.UserRole)
        if file_path and Path(file_path).exists():
            QDesktopServices.openUrl(Path(file_path).parent.as_uri())
        else:
            QMessageBox.information(self, "提示", "文件不存在或已被移动")

    def _clear_history(self):
        reply = QMessageBox.question(self, "确认", "确定要清空所有历史记录吗？",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.history_data.clear()
            if hasattr(self.parent_ref, 'history_manager'):
                self.parent_ref.history_manager.save_history(self.history_data)
            self._refresh_list()


class MainWindow(QMainWindow):
    """主窗口 - 纯粹的协调者"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("视频去/加水印工具")
        self.resize(1600, 960)
        self.setMinimumSize(1400, 860)
        # 1. 初始化服务与数据
        self._init_services()
        self._init_state()
        # 2. 构建 UI（组合模式）
        self._build_ui()
        # 3. 连接信号
        self._connect_signals()
        self._setup_shortcuts()
        # 4. 恢复状态
        self.settings_panel.load_settings(self.app_settings)
        self._apply_theme(self.theme_manager.current_theme)

    def _init_services(self):
        """初始化服务层"""
        self.history_manager = HistoryManager()
        self.theme_manager = ThemeManager()
        self.app_settings = QSettings("JVSClaw", "WatermarkTool")
        self.history_records = self.history_manager.load_history()

    def _init_state(self):
        """初始化业务状态"""
        self.video_path = None
        self.cap = None
        self.total_frames = 0
        self.current_frame_idx = 0
        self.watermark_rect = None
        self.processing = False
        self.worker_thread = None
        self.worker = None
        self.is_playing = False
        # 播放定时器
        self.play_timer = QTimer(self)
        self.play_timer.setInterval(40)
        self.play_timer.timeout.connect(self._next_frame)

    def _build_ui(self):
        """组装 UI 组件（Builder Pattern）"""
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 左侧导航栏 - 注入 theme_manager
        self.sidebar = SideBar(self.theme_manager)
        root.addWidget(self.sidebar)

        # 中间工作区容器
        self.main_content = QWidget()
        self.main_content.setObjectName("mainContent")
        main_layout = QVBoxLayout(self.main_content)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(12)

        # 顶部工具栏 - 注入 theme_manager
        self.toolbar = TopToolbar(self.theme_manager)
        main_layout.addWidget(self.toolbar)

        # 视频预览区（含进度覆盖层）
        self.video_panel = VideoPanel()
        main_layout.addWidget(self.video_panel, 1)

        # 底部控制栏 - 注入 theme_manager
        self.control_bar = ControlBar(self.theme_manager)
        main_layout.addWidget(self.control_bar)

        root.addWidget(self.main_content, 1)

        # 右侧属性面板
        self.settings_panel = SettingsPanel()
        root.addWidget(self.settings_panel)

        # 状态栏
        self.status_label = QLabel("准备就绪")
        self.status_label.setObjectName("statusBar")
        self.statusBar().addWidget(self.status_label, 1)

        # GPU 监控指示器
        from .ui_components.gpu_indicator import GPUIndicator
        self.gpu_indicator = GPUIndicator()
        self.statusBar().addPermanentWidget(self.gpu_indicator)

        self.time_label = QLabel("")
        self.time_label.setObjectName("statusTime")
        self.statusBar().addPermanentWidget(self.time_label)

    def _connect_signals(self):
        """建立清晰的信号映射表"""
        # === 导航栏 ===
        self.sidebar.nav_history_btn.clicked.connect(self._show_history)
        self.sidebar.theme_btn.clicked.connect(self._toggle_theme)
        # === 工具栏 ===
        self.toolbar.open_btn.clicked.connect(self._open_video)
        self.toolbar.start_btn.clicked.connect(self._start_process)
        self.toolbar.theme_toggle.clicked.connect(self._toggle_theme)
        # === 视频面板 ===
        self.video_panel.player.area_selected.connect(self._on_area_selected)
        self.video_panel.cancel_btn.clicked.connect(self._cancel_task)
        # === 控制栏 ===
        self.control_bar.play_btn.clicked.connect(self._toggle_play)
        self.control_bar.prev_btn.clicked.connect(lambda: self._seek_frame(-1))
        self.control_bar.next_btn.clicked.connect(lambda: self._seek_frame(1))
        self.control_bar.seek_requested.connect(self._on_timeline_seek)
        # === 设置面板（ROI 双向绑定）===
        sp = self.settings_panel
        sp.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        sp.spin_x.valueChanged.connect(self._on_roi_spinbox_changed)
        sp.spin_y.valueChanged.connect(self._on_roi_spinbox_changed)
        sp.spin_w.valueChanged.connect(self._on_roi_spinbox_changed)
        sp.spin_h.valueChanged.connect(self._on_roi_spinbox_changed)
        sp.clear_rect_btn.clicked.connect(self._clear_rect)
        sp.apply_rect_btn.clicked.connect(self._confirm_rect)
        # 浏览按钮
        sp.img_browse_btn.clicked.connect(self._browse_image)
        sp.fontfile_btn.clicked.connect(self._browse_font)
        sp.output_browse_btn.clicked.connect(self._browse_output_path)

    @Slot(float)
    def _on_timeline_seek(self, pos):
        """时间轴拖动跳转"""
        if self.total_frames > 0:
            idx = int(pos * (self.total_frames - 1))
            self._show_frame(idx)

    # ==================== 业务逻辑处理 ====================
    @Slot(int, int, int, int)
    def _on_area_selected(self, x, y, w, h):
        """视频区域选择回调 -> 同步到设置面板"""
        self.watermark_rect = (x, y, w, h)
        self.settings_panel.set_roi_values(x, y, w, h)
        self.toolbar.set_processing_enabled(True)

    def _on_roi_spinbox_changed(self):
        """坐标框数值改变 -> 同步到视频预览"""
        x, y, w, h = self.settings_panel.get_roi_values()
        # 处理锁定比例逻辑
        if self.settings_panel.lock_ratio_btn.isChecked() and self.watermark_rect:
            old_w, old_h = self.watermark_rect[2], self.watermark_rect[3]
            if old_w > 0 and old_h > 0:
                ratio = old_h / old_w
                sender = self.sender()
                if sender == self.settings_panel.spin_w:
                    h = int(w * ratio)
                    self.settings_panel.spin_h.blockSignals(True)
                    self.settings_panel.spin_h.setValue(h)
                    self.settings_panel.spin_h.blockSignals(False)
                elif sender == self.settings_panel.spin_h:
                    w = int(h / ratio)
                    self.settings_panel.spin_w.blockSignals(True)
                    self.settings_panel.spin_w.setValue(w)
                    self.settings_panel.spin_w.blockSignals(False)
        self.watermark_rect = (x, y, w, h)
        self.video_panel.player.set_selection_by_video_coords(x, y, w, h)
        self.toolbar.set_processing_enabled(w > 0 and h > 0)

    @Slot(int)
    def _on_mode_changed(self, index):
        """模式切换 -> 更新 UI 可见性"""
        self.settings_panel.update_mode_visibility(index)
        self.video_panel.player.set_preview_mode(index)

    def _clear_rect(self):
        """清除选区"""
        self.watermark_rect = None
        self.video_panel.player.clear_selection()
        self.settings_panel.clear_roi()
        self.toolbar.set_processing_enabled(False)

    def _confirm_rect(self):
        """确认选区（视觉反馈）"""
        if not self.watermark_rect:
            QMessageBox.warning(self, "提示", "请先框选区域")
            return
        self.video_panel.player.update()

    def _toggle_play(self):
        """播放/暂停切换"""
        if not self.cap:
            return
        if self.is_playing:
            self.play_timer.stop()
        else:
            fps = self.cap.get(cv2.CAP_PROP_FPS) or 25
            self.play_timer.start(int(1000 / fps))
        self.is_playing = not self.is_playing
        self.control_bar.set_play_icon(self.is_playing)

    def _next_frame(self):
        """播放下一帧"""
        if self.current_frame_idx < self.total_frames - 1:
            self._show_frame(self.current_frame_idx + 1)
        else:
            self._toggle_play()

    def _seek_frame(self, offset):
        """快进/快退"""
        if not self.cap:
            return
        new_idx = max(0, min(self.total_frames - 1, self.current_frame_idx + offset))
        self._show_frame(new_idx)

    def _show_frame(self, idx):
        """显示指定帧（核心渲染方法）"""
        if not self.cap:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = self.cap.read()
        if not ret:
            return
        self.current_frame_idx = idx
        self.video_panel.player.set_frame(frame)
        # 更新控制栏状态
        fps = self.cap.get(cv2.CAP_PROP_FPS) or 25
        cur_sec = idx / fps
        total_sec = self.total_frames / fps
        self.control_bar.update_time(cur_sec, total_sec)
        self.control_bar.update_slider(idx, self.total_frames)

    def _open_video(self):
        """打开视频文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择视频", "",
            "Video (*.mp4 *.avi *.mov *.mkv *.flv);;All Files (*)"
        )
        if not path:
            return
        try:
            if self.cap:
                self.cap.release()
            self.cap = cv2.VideoCapture(path)
            if not self.cap.isOpened():
                raise RuntimeError("无法打开视频文件")
            self.video_path = path
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = self.cap.get(cv2.CAP_PROP_FPS) or 25
            w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.toolbar.update_video_info(Path(path).name, w, h, fps)
            self.control_bar.enable_controls(True)
            self.control_bar.update_slider(0, self.total_frames)
            self._show_frame(0)
            if self.watermark_rect:
                x, y, rw, rh = self.watermark_rect
                self.video_panel.player.set_selection_by_video_coords(x, y, rw, rh)
                self.toolbar.set_processing_enabled(True)
            else:
                self._clear_rect()
            self.status_label.setText(f"已加载: {Path(path).name}")
            logger.info("视频打开成功: %s (%dx%d@%.2ffps)", path, w, h, fps)
            if hasattr(self.control_bar, 'timeline'):
                self.control_bar.timeline.generate_waveform(path)
        except Exception as e:
            logger.exception("打开视频失败")
            QMessageBox.critical(self, "错误", f"无法打开视频:\n{str(e)}")

    def _start_process(self):
        """启动处理任务（核心业务流程）"""
        if self.processing:
            return
        if not self.video_path:
            QMessageBox.warning(self, "提示", "请先打开视频文件")
            return
        mode = self.settings_panel.current_mode
        valid, err_msg = self.settings_panel.validate_for_processing(mode)
        if not valid:
            QMessageBox.warning(self, "配置错误", err_msg)
            return
        out_cfg = self.settings_panel.get_output_config()
        base_name = Path(self.video_path).stem
        save_path = os.path.join(out_cfg['path'], f"{base_name}_processed.{out_cfg['format']}")
        if os.path.exists(save_path):
            reply = QMessageBox.question(
                self, "文件已存在",
                f"输出文件已存在:\n{save_path}\n\n是否覆盖？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        if hasattr(self, 'gpu_indicator'):
            self.gpu_indicator.start_monitoring()
        self.processing = True
        self.toolbar.set_processing_enabled(False)
        self.video_panel.show_progress(True)
        self.video_panel.reset_progress()
        self.control_bar.enable_controls(False)
        x, y, w, h = self.settings_panel.get_roi_values()
        self.worker_thread = QThread()
        try:
            if mode == 0:
                self.worker = WatermarkRemover()
                self.worker.setup_remove(
                    input_path=self.video_path, output_path=save_path,
                    x=x, y=y, width=w, height=h,
                    encoder=out_cfg['encoder'], quality=out_cfg['quality']
                )
            elif mode == 1:
                txt_cfg = self.settings_panel.get_text_watermark_config()
                self.worker = WatermarkAdder()
                self.worker.setup_add_text(
                    input_path=self.video_path, output_path=save_path,
                    text=txt_cfg['text'], x=x, y=y,
                    fontsize=0, fontcolor=txt_cfg['color'],
                    alpha=txt_cfg['alpha'], fontfile=txt_cfg['fontfile'],
                    encoder=out_cfg['encoder'], quality=out_cfg['quality'],
                    remove_first=out_cfg['remove_first'],
                    remove_rect=self.watermark_rect, rect=self.watermark_rect
                )
            else:
                img_cfg = self.settings_panel.get_image_watermark_config()
                scale_w, scale_h = (w, h) if img_cfg['scale_mode'] == 0 else (0, 0)
                self.worker = WatermarkAdder()
                self.worker.setup_add_image(
                    input_path=self.video_path, output_path=save_path,
                    image_path=img_cfg['path'], x=x, y=y,
                    width=scale_w, height=scale_h, alpha=img_cfg['alpha'],
                    encoder=out_cfg['encoder'], quality=out_cfg['quality'],
                    remove_first=out_cfg['remove_first'],
                    remove_rect=self.watermark_rect
                )
            self.worker.moveToThread(self.worker_thread)
            self.worker_thread.started.connect(self.worker.run)
            self.worker.progress_updated.connect(self._on_progress)
            self.worker.status_updated.connect(self._on_status_update)
            self.worker.finished.connect(self._on_finished)
            self.worker_thread.start()
        except Exception as e:
            logger.exception("启动处理任务失败")
            self._on_finished(False, str(e))

    @Slot(int)
    def _on_progress(self, value):
        self.video_panel.update_progress(value)

    @Slot(str)
    def _on_status_update(self, text):
        self.video_panel.update_progress(None, text)

    @Slot(bool, str)
    def _on_finished(self, success, message):
        self.processing = False
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(3000)
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        if self.worker_thread:
            self.worker_thread.deleteLater()
            self.worker_thread = None
        if hasattr(self, 'gpu_indicator'):
            self.gpu_indicator.stop_monitoring()
        self.toolbar.set_processing_enabled(True)
        self.video_panel.show_progress(False)
        self.control_bar.enable_controls(True)
        if success and self.video_path:
            self._add_history(self.video_path, message, "成功")
            self.status_label.setText("处理完成")
            QMessageBox.information(self, "完成", f"处理完成！\n\n{message}")
        else:
            self.status_label.setText("处理失败")
            QMessageBox.critical(self, "错误", f"处理失败:\n\n{message}")

    def _cancel_task(self):
        if self.worker:
            self.worker.cancel()
        self.video_panel.update_progress(None, "正在取消...")

    def _browse_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择水印图片", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp);;All Files (*)"
        )
        if path:
            self.settings_panel.img_path_edit.setText(path)

    def _browse_font(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择字体文件", "",
            "Font Files (*.ttf *.otf *.ttc);;All Files (*)"
        )
        if path:
            self.settings_panel.fontfile_edit.setText(path)

    def _browse_output_path(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, "选择输出目录",
            self.settings_panel.output_path_edit.text()
        )
        if dir_path:
            self.settings_panel.output_path_edit.setText(dir_path)

    # ==================== 主题与历史 ====================
    def _toggle_theme(self):
        """切换深色/浅色主题"""
        new_theme = "light" if self.theme_manager.current_theme == "dark" else "dark"
        self.theme_manager.set_theme(new_theme)
        self._apply_theme(new_theme)
        # 图标刷新已在 _apply_theme 中统一处理，不再单独设置文字

    def _apply_theme(self, theme_name):
        """应用主题样式并刷新所有图标"""
        qss = self.theme_manager.load_stylesheet(theme_name)
        if qss:
            QApplication.instance().setStyleSheet(qss)
        # 刷新各组件的图标
        self.sidebar.refresh_all_icons()
        self.toolbar.refresh_all_icons()
        self.control_bar.refresh_all_icons()
        QApplication.processEvents()

    def _show_history(self):
        dlg = HistoryDialog(self.history_records, self)
        dlg.exec()

    def _add_history(self, source, output, status):
        rec = {
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": source,
            "output": output,
            "status": status
        }
        self.history_records.append(rec)
        self.history_manager.save_history(self.history_records)

    # ==================== 快捷键 ====================
    def _setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key_Space), self, self._toggle_play)
        QShortcut(QKeySequence(Qt.Key_Left), self, lambda: self._seek_frame(-1))
        QShortcut(QKeySequence(Qt.Key_Right), self, lambda: self._seek_frame(1))
        QShortcut(QKeySequence("Ctrl+O"), self, self._open_video)
        QShortcut(QKeySequence(Qt.Key_Delete), self, self._clear_rect)

    @Slot(dict)
    def _on_gpu_data_updated(self, data: dict):
        self.gpu_indicator.update_data(data)

    # ==================== 生命周期 ====================
    def closeEvent(self, event):
        self.settings_panel.save_settings(self.app_settings)
        if self.processing:
            self._cancel_task()
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            if not self.worker_thread.wait(3000):
                logger.warning("工作线程等待超时")
        if hasattr(self, 'gpu_indicator'):
            self.gpu_indicator.stop_monitoring()
        try:
            if self.cap:
                self.cap.release()
                self.cap = None
        except Exception:
            pass
        super().closeEvent(event)