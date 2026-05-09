import os
from PySide6.QtCore import Signal
from src.core.utils import get_video_duration, get_default_font
from .base_processor import BaseProcessor


class WatermarkAdder(BaseProcessor):
    def __init__(self):
        super().__init__()
        self._params = {}
        self._task = None

    def run(self):
        try:
            if self._task == "text":
                self.add_text(**self._params)
            elif self._task == "image":
                self.add_image(**self._params)
        except Exception as e:
            self.finished.emit(False, str(e))

    def setup_add_text(self, **kwargs):
        self._task = "text"
        self._params = kwargs

    def setup_add_image(self, **kwargs):
        self._task = "image"
        self._params = kwargs

    @staticmethod
    def _estimate_text_size(text, fontsize):
        return fontsize * 1.2

    @classmethod
    def _calc_adaptive_fontsize(cls, text, rect):
        rx, ry, rw, rh = [int(v) for v in rect]
        target_h = rh * 0.98
        low, high = 8, 600
        best_size = 24
        while low <= high:
            mid = (low + high) // 2
            h = cls._estimate_text_size(text, mid)
            if h <= target_h:
                best_size = mid
                low = mid + 1
            else:
                high = mid - 1
        return best_size

    def add_text(self, input_path, output_path, text, x, y, fontfile='',
                 fontsize=0, fontcolor='white', alpha=1.0, angle=0,
                 encoder='libx264', quality='标准',
                 remove_first=False, remove_rect=None, rect=None):
        duration = get_video_duration(input_path)
        if duration is None:
            self.finished.emit(False, "无法读取视频时长")
            return
        if not fontfile:
            fontfile = get_default_font()
        if not fontfile:
            self.finished.emit(False, "未找到有效的中文字体文件，请手动选择")
            return
        fontfile = fontfile.replace("\\", "/").replace(":", "\\:")
        safe_text = self._escape(text)
        if rect and fontsize <= 0:
            fontsize = int(self._calc_adaptive_fontsize(safe_text, rect) * 1.05)
            rx, ry, rw, rh = [int(v) for v in rect]
            x_expr = f"{rx}+({rw}-tw)/2"
            y_expr = f"{ry}+(({rh}-{fontsize})/2)"
        else:
            x_expr = str(x)
            y_expr = str(y)
            if fontsize <= 0: fontsize = 24
        filters = []
        if remove_first and remove_rect:
            rx, ry, rw, rh = remove_rect
            filters.append(f"delogo=x={rx}:y={ry}:w={rw}:h={rh}:show=0")
        drawtext = f"drawtext=text='{safe_text}':x={x_expr}:y={y_expr}:fontsize={fontsize}:fontcolor={fontcolor}@{alpha}"
        if fontfile: drawtext += f":fontfile='{fontfile}'"
        filters.append(drawtext)
        vf = ",".join(filters)
        total_segments = max(1, int(duration / self.SEGMENT_TIME) + (1 if duration % self.SEGMENT_TIME else 0))
        temp_dir = os.path.join("temp", f"addtext_{os.getpid()}")
        os.makedirs(temp_dir, exist_ok=True)
        segment_files = []
        try:
            for i in range(total_segments):
                if self._cancelled:
                    self.finished.emit(False, "已取消")
                    return
                start = i * self.SEGMENT_TIME
                seg_file = os.path.join(temp_dir, f"seg_{i:04d}.mp4")
                self.status_updated.emit(f"处理片段 {i + 1}/{total_segments} ...")
                cmd = ["ffmpeg", "-y", "-ss", str(start), "-i", input_path, "-t", str(self.SEGMENT_TIME),
                       "-vf", vf, "-c:a", "copy", *self._encoder_params(encoder, quality),
                       "-progress", "pipe:1", "-nostats", seg_file]
                success, error_info = self._run_ffmpeg_progress(cmd, duration, start)
                if not success:
                    self.finished.emit(False, f"片段 {i + 1} 处理失败\n{error_info}")
                    return
                segment_files.append(seg_file)
                self.status_updated.emit(f"segment_complete:{seg_file}")
                segment_end = min((i + 1) * self.SEGMENT_TIME, duration)
                self.progress_updated.emit(int((segment_end / duration) * 100))
            if not self._concat_segments(segment_files, temp_dir, output_path, encoder, quality):
                raise RuntimeError("视频合并失败")
            self.progress_updated.emit(100)
            self.finished.emit(True, output_path)
        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def add_image(self, input_path, output_path, image_path, x, y,
                  width=0, height=0, alpha=1.0, encoder='libx264', quality='标准',
                  remove_first=False, remove_rect=None):
        duration = get_video_duration(input_path)
        if duration is None:
            self.finished.emit(False, "无法读取视频时长")
            return
        image_path = image_path.replace("\\", "/")
        filter_complex = ""
        video_input = "0:v"
        if remove_first and remove_rect:
            rx, ry, rw, rh = remove_rect
            filter_complex += f"[{video_input}]delogo=x={rx}:y={ry}:w={rw}:h={rh}:show=0[bg];"
            video_input = "bg"
        img_input = "1:v"
        if width > 0 and height > 0:
            filter_complex += f"[{img_input}]scale={width}:{height}[img];"
            img_input = "img"
        overlay_filter = f"[{video_input}][{img_input}]overlay=x={x}:y={y}:format=auto:alpha={alpha}"
        if remove_first and remove_rect:
            overlay_filter += "[outv]"
        filter_complex += overlay_filter
        cmd = ["ffmpeg", "-y", "-i", input_path, "-i", image_path, "-filter_complex", filter_complex,
               "-map", "[outv]" if "[outv]" in filter_complex else "",
               "-map", "0:a?", "-c:a", "copy", *self._encoder_params(encoder, quality),
               "-progress", "pipe:1", "-nostats", output_path]
        if "[outv]" not in filter_complex:
            cmd.remove("-map")
            cmd.remove("")
        self.status_updated.emit("图片水印处理中...")
        success, error_info = self._run_ffmpeg_progress(cmd, duration, 0)
        if success:
            self.progress_updated.emit(100)
            self.finished.emit(True, output_path)
        else:
            if not self._cancelled:
                self.finished.emit(False, f"图片水印处理失败\n{error_info}")

    def _escape(self, text: str) -> str:
        return (text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
                .replace(",", "\\,").replace("%", "\\%"))