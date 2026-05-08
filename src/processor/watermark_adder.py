import os
import tempfile
import subprocess
import re
from PySide6.QtCore import QObject, Signal
from src.core.utils import get_video_duration, get_default_font


class WatermarkAdder(QObject):
    progress_updated = Signal(int)
    status_updated = Signal(str)
    finished = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def add_text(self, input_path, output_path, text, x, y, fontfile='',
                 fontsize=24, fontcolor='white', alpha=1.0, angle=0,
                 encoder='libx264', quality='标准',
                 remove_first=False, remove_rect=None):
        duration = get_video_duration(input_path)
        if duration is None:
            self.finished.emit(False, "无法读取视频时长")
            return

        # 字体回退
        if not fontfile:
            fontfile = get_default_font()

        if fontfile:
            # 路径处理：转义冒号，使用正斜杠，最后用单引号包裹
            fontfile = fontfile.replace("\\", "/")
            fontfile_escaped = fontfile.replace(":", "\\:")   # 关键：转义盘符冒号
        else:
            fontfile_escaped = None

        # 文本转义
        safe_text = self._escape(text)

        # 构建滤镜
        filters = []
        if remove_first and remove_rect:
            rx, ry, rw, rh = remove_rect
            filters.append(f"delogo=x={rx}:y={ry}:w={rw}:h={rh}:show=0")

        drawtext = (
            f"drawtext=text='{safe_text}':"
            f"x={x}:y={y}:"
            f"fontsize={fontsize}:"
            f"fontcolor={fontcolor}@{alpha}"
        )
        if fontfile_escaped:
            drawtext += f":fontfile='{fontfile_escaped}'"
        # 如果 FFmpeg 升级后支持 angle，可恢复下面这行
        # drawtext += f":angle={angle}"

        filters.append(drawtext)
        vf = ",".join(filters)

        segment_time = 30.0
        total_segments = max(1, int(duration / segment_time) + (1 if duration % segment_time else 0))
        temp_dir = tempfile.mkdtemp(prefix="addtext_")
        segment_files = []

        try:
            for i in range(total_segments):
                if self._cancelled:
                    self.finished.emit(False, "已取消")
                    return

                start = i * segment_time
                seg_file = os.path.join(temp_dir, f"seg_{i:04d}.mp4")
                self.status_updated.emit(f"处理片段 {i+1}/{total_segments} ...")

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
                    self.finished.emit(False, f"片段 {i+1} 处理失败\n{error_info}")
                    return

                segment_files.append(seg_file)
                segment_end = min((i + 1) * segment_time, duration)
                self.progress_updated.emit(int((segment_end / duration) * 100))

            # ---------- 合并（优先使用流复制，失败则快速重编码） ----------
            self.status_updated.emit("正在快速合并...")
            concat_file = os.path.join(temp_dir, "concat.txt")
            with open(concat_file, "w", encoding="utf-8") as f:
                for seg in segment_files:
                    safe_path = seg.replace("\\", "/")
                    f.write(f"file '{safe_path}'\n")

            # 方案1：尝试无编码复制（极快）
            merge_cmd_copy = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                output_path
            ]
            result = subprocess.run(merge_cmd_copy, capture_output=True, text=True, encoding="utf-8", errors="ignore")

            if result.returncode == 0 and os.path.exists(output_path):
                self.progress_updated.emit(100)
                self.finished.emit(True, output_path)
                return

            # 方案2：快速重编码（合并保底，速度优化）
            self.status_updated.emit("快速重编码合并中...")
            merge_cmd_encode = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_file,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k",
                output_path
            ]
            result2 = subprocess.run(merge_cmd_encode, capture_output=True, text=True, encoding="utf-8", errors="ignore")
            if result2.returncode != 0 or not os.path.exists(output_path):
                error_details = result2.stderr.strip() or result2.stdout.strip()
                raise RuntimeError(f"合并失败：{error_details}")

            self.progress_updated.emit(100)
            self.finished.emit(True, output_path)

        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _run_segment_with_progress(self, cmd, total_duration, segment_start):
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="ignore")
        time_pattern = re.compile(r"out_time_ms=(\d+)")
        output_lines = []

        while True:
            if self._cancelled:
                process.terminate()
                return False, "任务已取消"

            line = process.stdout.readline()
            if not line:
                if process.poll() is not None:
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

        ret = process.wait()
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

    def add_image(self, input_path, output_path, image_path, x, y,
                  width=0, height=0, alpha=1.0,
                  encoder='libx264', quality='标准',
                  remove_first=False, remove_rect=None):
        """图片水印暂未实现"""
        self.finished.emit(False, "图片水印功能暂未实现")