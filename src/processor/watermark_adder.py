import os
import re
import subprocess
from PySide6.QtCore import QObject, Signal
from src.core.utils import get_video_duration, get_default_font

os.makedirs("temp", exist_ok=True)


class WatermarkAdder(QObject):
    progress_updated = Signal(int)
    status_updated = Signal(str)
    finished = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self._cancelled = False
        self._process = None
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

    def cancel(self):
        self._cancelled = True
        try:
            if self._process and self._process.poll() is None:
                self._process.terminate()
        except Exception:
            pass

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
                 remove_first=False, remove_rect=None,
                 rect=None):
        duration = get_video_duration(input_path)
        if duration is None:
            self.finished.emit(False, "无法读取视频时长")
            return
        if not fontfile:
            fontfile = get_default_font()
        if not fontfile:
            self.finished.emit(False, "未找到有效的中文字体文件，请手动选择")
            return
        fontfile = fontfile.replace("\\", "/")
        fontfile_escaped = fontfile.replace(":", "\\:")
        safe_text = self._escape(text)
        if rect and fontsize <= 0:
            fontsize = int(self._calc_adaptive_fontsize(safe_text, rect) * 1.05)
            rx, ry, rw, rh = [int(v) for v in rect]
            x_expr = f"{rx}+({rw}-tw)/2"
            y_expr = f"{ry}+(({rh}-{fontsize})/2)"
        else:
            x_expr = str(x)
            y_expr = str(y)
            if fontsize <= 0:
                fontsize = 24
        filters = []
        if remove_first and remove_rect:
            rx, ry, rw, rh = remove_rect
            filters.append(f"delogo=x={rx}:y={ry}:w={rw}:h={rh}:show=0")
        drawtext = (
            f"drawtext=text='{safe_text}':"
            f"x={x_expr}:y={y_expr}:"
            f"fontsize={fontsize}:"
            f"fontcolor={fontcolor}@{alpha}"
        )
        if fontfile_escaped:
            drawtext += f":fontfile='{fontfile_escaped}'"
        filters.append(drawtext)
        vf = ",".join(filters)
        segment_time = 30.0
        total_segments = max(1, int(duration / segment_time) + (1 if duration % segment_time else 0))
        temp_dir = os.path.join("temp", f"addtext_{os.getpid()}")
        os.makedirs(temp_dir, exist_ok=True)
        segment_files = []
        try:
            for i in range(total_segments):
                if self._cancelled:
                    self.finished.emit(False, "已取消")
                    return
                start = i * segment_time
                seg_file = os.path.join(temp_dir, f"seg_{i:04d}.mp4")
                self.status_updated.emit(f"处理片段 {i + 1}/{total_segments} ...")
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", str(start),
                    "-i", input_path,
                    "-t", str(segment_time),
                    "-vf", vf,
                    "-c:a", "copy",
                    *self._encoder_params(encoder, quality),
                    "-progress", "pipe:1",
                    "-nostats",
                    seg_file
                ]
                success, error_info = self._run_segment_with_progress(cmd, duration, start)
                if not success:
                    self.finished.emit(False, f"片段 {i + 1} 处理失败\n{error_info}")
                    return
                segment_files.append(seg_file)
                segment_end = min((i + 1) * segment_time, duration)
                self.progress_updated.emit(int((segment_end / duration) * 100))
            self.status_updated.emit("正在合并...")
            if not self._concat_segments(segment_files, temp_dir, output_path, encoder, quality):
                return
            self.progress_updated.emit(100)
            self.finished.emit(True, output_path)
        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def add_image(self, input_path, output_path, image_path, x, y,
                  width=0, height=0, alpha=1.0,
                  encoder='libx264', quality='标准',
                  remove_first=False, remove_rect=None):
        """
        图片水印完整实现 (使用 overlay 滤镜)
        """
        duration = get_video_duration(input_path)
        if duration is None:
            self.finished.emit(False, "无法读取视频时长")
            return
        image_path = image_path.replace("\\", "/")
        # 构建 filter_complex
        filter_complex = ""
        video_input = "0:v"
        # 1. 先去水印逻辑
        if remove_first and remove_rect:
            rx, ry, rw, rh = remove_rect
            filter_complex += f"[{video_input}]delogo=x={rx}:y={ry}:w={rw}:h={rh}:show=0[bg];"
            video_input = "bg"
        # 2. 图片缩放逻辑
        img_input = "1:v"
        if width > 0 and height > 0:
            filter_complex += f"[{img_input}]scale={width}:{height}[img];"
            img_input = "img"
        # 3. 叠加逻辑
        overlay_filter = f"[{video_input}][{img_input}]overlay=x={x}:y={y}:format=auto:alpha={alpha}"
        if remove_first and remove_rect:
            overlay_filter += "[outv]"
        filter_complex += overlay_filter
        # 构建命令 (全段处理，不分段，因为overlay多输入分段较复杂)
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-i", image_path,
            "-filter_complex", filter_complex,
            "-map", "[outv]" if remove_first and remove_rect else overlay_filter.split()[
                -1] if "outv" not in overlay_filter else "[outv]",
            "-map", "0:a?",
            "-c:a", "copy",
            *self._encoder_params(encoder, quality),
            "-progress", "pipe:1",
            "-nostats",
            output_path
        ]
        # 简化 map 逻辑：如果没加outv标记，则不需要map
        if "[outv]" not in filter_complex:
            cmd.remove("-map")
            cmd.remove("[outv]")
            # FFmpeg 默认会选择最高分辨率视频流，在有 -filter_complex 时通常足够
        self.status_updated.emit("图片水印处理中...")
        success, error_info = self._run_segment_with_progress(cmd, duration, 0)
        if success:
            self.progress_updated.emit(100)
            self.finished.emit(True, output_path)
        else:
            if not self._cancelled:
                self.finished.emit(False, f"图片水印处理失败\n{error_info}")

    def _concat_segments(self, segment_files, temp_dir, output_path, encoder, quality):
        import shutil
        concat_file = os.path.join(temp_dir, "concat.txt")
        with open(concat_file, "w", encoding="utf-8") as f:
            for seg in segment_files:
                abs_path = os.path.abspath(seg).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")
        merge_cmd_copy = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", output_path]
        result = subprocess.run(merge_cmd_copy, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if result.returncode != 0 or not os.path.exists(output_path):
            self.status_updated.emit("快速合并失败，使用重编码合并...")
            merge_cmd_encode = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k", output_path
            ]
            result2 = subprocess.run(merge_cmd_encode, capture_output=True, text=True, encoding="utf-8",
                                     errors="ignore")
            if result2.returncode != 0 or not os.path.exists(output_path):
                error_details = result2.stderr.strip() or result2.stdout.strip()
                self.finished.emit(False, f"合并失败：{error_details}")
                return False
        return True

    def _run_segment_with_progress(self, cmd, total_duration, segment_start):
        self._process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, encoding="utf-8", errors="ignore")
        time_pattern = re.compile(r"out_time_ms=(\d+)")
        output_lines = []
        while True:
            if self._cancelled:
                self._process.terminate()
                return False, "任务已取消"
            line = self._process.stdout.readline()
            if not line:
                if self._process.poll() is not None:
                    break
                continue
            output_lines.append(line.strip())
            if len(output_lines) > 20:
                output_lines.pop(0)
            match = time_pattern.search(line)
            if match and total_duration > 0:
                ms = int(match.group(1))
                current_sec = segment_start + ms / 1_000_000
                percent = int((current_sec / total_duration) * 100)
                self.progress_updated.emit(min(percent, 100))
        ret = self._process.wait()
        if ret != 0:
            error_info = "\n".join(output_lines[-10:])
            return False, f"FFmpeg 退出码 {ret}\n{error_info}"
        return True, None

    def _escape(self, text: str) -> str:
        return (text.replace("\\", "\\\\")
                .replace(":", "\\:")
                .replace("'", "\\'")
                .replace(",", "\\,")
                .replace("%", "\\%"))

    def _encoder_params(self, encoder, quality):
        if encoder == "nvenc":
            return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19",
                    "-b:v", "8M", "-maxrate", "12M", "-bufsize", "16M", "-pix_fmt", "yuv420p"]
        elif encoder == "qsv":
            return ["-c:v", "h264_qsv", "-global_quality", "18"]
        elif encoder == "amf":
            return ["-c:v", "h264_amf", "-qp_i", "18", "-qp_p", "18"]
        elif quality == "无损":
            return ["-c:v", "libx264", "-crf", "0", "-preset", "slow"]
        elif quality == "高质量":
            return ["-c:v", "libx264", "-crf", "18", "-preset", "slow"]
        else:
            return ["-c:v", "libx264", "-crf", "23", "-preset", "medium"]