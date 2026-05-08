import os
import tempfile
import subprocess
import re
from PySide6.QtCore import QObject, Signal
from src.core.utils import get_video_duration, normalize_rect

# 确保项目 temp 目录存在
os.makedirs("temp", exist_ok=True)

class WatermarkRemover(QObject):
    progress_updated = Signal(int)
    status_updated = Signal(str)
    finished = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def remove(self, input_path, output_path, x, y, width, height, encoder='nvenc', quality='标准'):
        duration = get_video_duration(input_path)
        if duration is None:
            self.finished.emit(False, "无法读取视频时长")
            return

        x, y, width, height = normalize_rect(x, y, width, height)
        segment_time = 30.0
        total_segments = max(1, int(duration / segment_time) + (1 if duration % segment_time else 0))

        temp_dir = tempfile.mkdtemp(prefix="delogo_", dir="temp")
        segment_files = []

        try:
            for i in range(total_segments):
                if self._cancelled:
                    self.finished.emit(False, "已取消")
                    return

                start = i * segment_time
                seg_file = os.path.join(temp_dir, f"seg_{i:04d}.mp4")
                self.status_updated.emit(f"处理片段 {i+1}/{total_segments} ...")

                vf = f"delogo=x={x}:y={y}:w={width}:h={height}:show=0"
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
                overall_percent = int((segment_end / duration) * 100)
                self.progress_updated.emit(min(overall_percent, 100))

            # 合并片段
            self.status_updated.emit("合并片段中...")
            concat_file = os.path.join(temp_dir, "concat.txt")
            with open(concat_file, "w", encoding="utf-8") as f:
                for seg in segment_files:
                    # 强制使用正斜杠，避免 FFmpeg 路径解析错误
                    safe_path = seg.replace("\\", "/")
                    f.write(f"file '{safe_path}'\n")

            merge_cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_file,
                "-c:v", "libx264", "-crf", "23", "-preset", "fast",
                "-c:a", "aac", "-b:a", "128k",
                output_path
            ]
            result = subprocess.run(merge_cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
            if result.returncode != 0:
                error_details = result.stderr.strip() or result.stdout.strip()
                raise RuntimeError(f"合并失败，FFmpeg 输出：\n{error_details}")

            if os.path.exists(output_path):
                self.progress_updated.emit(100)
                self.finished.emit(True, output_path)
            else:
                self.finished.emit(False, "合并失败：输出文件未生成")

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