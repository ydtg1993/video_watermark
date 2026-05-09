import os
from PySide6.QtCore import QObject, Signal, QThread, Slot
from ...processor.remover import WatermarkRemover
from ...processor.watermark_adder import WatermarkAdder
from ...core.logger import logger


class TaskController(QObject):
    """管理视频处理任务的生命周期"""
    progress_updated = Signal(int)
    status_updated = Signal(str)
    task_started = Signal()
    task_finished = Signal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.processing = False
        self.worker_thread = None
        self.worker = None

    @Slot(dict, str, int, tuple)
    def start_process(self, out_cfg: dict, video_path: str, mode: int, watermark_rect: tuple):
        if self.processing: return
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        save_path = os.path.join(out_cfg['path'], f"{base_name}_processed.{out_cfg['format']}")
        self.processing = True
        self.task_started.emit()
        x, y, w, h = watermark_rect if watermark_rect else (0, 0, 0, 0)
        self.worker_thread = QThread()
        try:
            if mode == 0:
                self.worker = WatermarkRemover()
                self.worker.setup_remove(
                    input_path=video_path, output_path=save_path,
                    x=x, y=y, width=w, height=h,
                    encoder=out_cfg['encoder'], quality=out_cfg['quality']
                )
            elif mode == 1:
                self.worker = WatermarkAdder()
                self.worker.setup_add_text(
                    input_path=video_path, output_path=save_path,
                    text=out_cfg.get('text', ''), x=x, y=y,
                    fontsize=0, fontcolor=out_cfg.get('color', 'white'),
                    alpha=out_cfg.get('alpha', 1.0), fontfile=out_cfg.get('fontfile', ''),
                    encoder=out_cfg['encoder'], quality=out_cfg['quality'],
                    remove_first=out_cfg['remove_first'],
                    remove_rect=watermark_rect, rect=watermark_rect
                )
            else:
                self.worker = WatermarkAdder()
                self.worker.setup_add_image(
                    input_path=video_path, output_path=save_path,
                    image_path=out_cfg.get('path', ''), x=x, y=y,
                    width=w if out_cfg.get('scale_mode', 0) == 0 else 0,
                    height=h if out_cfg.get('scale_mode', 0) == 0 else 0,
                    alpha=out_cfg.get('alpha', 0.9),
                    encoder=out_cfg['encoder'], quality=out_cfg['quality'],
                    remove_first=out_cfg['remove_first'],
                    remove_rect=watermark_rect
                )
            self.worker.moveToThread(self.worker_thread)
            self.worker_thread.started.connect(self.worker.run)
            self.worker.progress_updated.connect(self.progress_updated)
            self.worker.status_updated.connect(self.status_updated)
            self.worker.finished.connect(self._on_finished)
            self.worker_thread.start()
        except Exception as e:
            logger.exception("启动处理任务失败")
            self._on_finished(False, str(e))

    @Slot()
    def cancel_task(self):
        if self.worker:
            self.worker.cancel()
            self.status_updated.emit("正在取消...")

    @Slot(bool, str)
    def _on_finished(self, success: bool, message: str):
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
        self.task_finished.emit(success, message)

    def cleanup(self):
        if self.processing:
            self.cancel_task()
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(3000)