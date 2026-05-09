# src/processor/remover.py
import os
import shutil
import tempfile
from PySide6.QtCore import Signal
from src.core.utils import get_video_duration, normalize_rect
from .base_processor import BaseProcessor


class WatermarkRemover(BaseProcessor):
    def __init__(self):
        super().__init__()
        self._params = {}

    def setup_remove(self, **kwargs):
        self._params = kwargs

    def run(self):
        try:
            self.remove(**self._params)
        except Exception as e:
            self.finished.emit(False, str(e))

    def remove(self, input_path, output_path, x, y, width, height, encoder="libx264", quality="标准"):
        duration = get_video_duration(input_path)
        if not duration:
            self.finished.emit(False, "无法读取视频时长")
            return
        x, y, width, height = normalize_rect(x, y, width, height)
        total_segments = int(duration // self.SEGMENT_TIME) + (1 if duration % self.SEGMENT_TIME else 0)
        temp_dir = tempfile.mkdtemp(prefix="wm_remove_", dir="temp")
        segment_files = []
        try:
            for index in range(total_segments):
                if self._cancelled:
                    self.finished.emit(False, "任务已取消")
                    return
                start = index * self.SEGMENT_TIME
                seg_file = os.path.join(temp_dir, f"segment_{index:04d}.mp4")
                self.status_updated.emit(f"处理中 {index + 1}/{total_segments}")
                vf = f"delogo=x={x}:y={y}:w={width}:h={height}:show=0"
                cmd = [
                    "ffmpeg", "-hide_banner", "-y",
                    "-ss", str(start), "-i", input_path,
                    "-t", str(self.SEGMENT_TIME),
                    "-vf", vf,
                    *self._encoder_params(encoder, quality),
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    "-c:a", "aac", "-b:a", "192k",
                    "-progress", "pipe:1", "-nostats",
                    seg_file
                ]
                success, err = self._run_ffmpeg_progress(cmd, duration, start)
                if not success:
                    self.finished.emit(False, f"片段处理失败：\n{err}")
                    return
                segment_files.append(seg_file)
            if not self._concat_segments(segment_files, temp_dir, output_path, encoder, quality):
                raise RuntimeError("视频合并失败")
            self.progress_updated.emit(100)
            self.finished.emit(True, output_path)
        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)