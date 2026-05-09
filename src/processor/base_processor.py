# src/processor/base_processor.py
import os
import re
import shutil
import subprocess
from PySide6.QtCore import QObject, Signal


class BaseProcessor(QObject):
    progress_updated = Signal(int)
    status_updated = Signal(str)
    finished = Signal(bool, str)
    SEGMENT_TIME = 30

    def __init__(self):
        super().__init__()
        self._cancelled = False
        self._process = None

    def cancel(self):
        self._cancelled = True
        try:
            if self._process and self._process.poll() is None:
                self._process.terminate()
        except Exception:
            pass

    def _encoder_params(self, encoder, quality):
        if encoder == "nvenc":
            return ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "8M", "-maxrate", "12M",
                    "-bufsize", "16M", "-pix_fmt", "yuv420p"]
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

    def _run_ffmpeg_progress(self, cmd, total_duration, segment_start):
        self._process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="ignore"
        )
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
            if len(output_lines) > 30:
                output_lines.pop(0)
            match = time_pattern.search(line)
            if match and total_duration > 0:
                ms = int(match.group(1))
                current_sec = segment_start + ms / 1_000_000
                percent = int((current_sec / total_duration) * 100)
                self.progress_updated.emit(min(percent, 100))
        ret = self._process.wait()
        if ret != 0:
            return False, "\n".join(output_lines[-10:])
        return True, None

    def _concat_segments(self, segment_files, temp_dir, output_path, encoder, quality):
        concat_file = os.path.join(temp_dir, "concat.txt")
        with open(concat_file, "w", encoding="utf-8") as f:
            for seg in segment_files:
                abs_path = os.path.abspath(seg).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")
        self.status_updated.emit("正在合并视频...")
        # 尝试无损合并
        merge_cmd_copy = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", output_path]
        result = subprocess.run(merge_cmd_copy, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        if result.returncode != 0 or not os.path.exists(output_path):
            self.status_updated.emit("快速合并失败，使用重编码合并...")
            merge_cmd_encode = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k", output_path
            ]
            # 重编码合并时，因为没有 -progress pipe:1，需要用进程等待模拟进度
            self._process = subprocess.Popen(merge_cmd_encode, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                             text=True)
            while self._process.poll() is None:
                if self._cancelled:
                    self._process.terminate()
                    return False
                self.msleep(100)
            if self._process.returncode != 0 or not os.path.exists(output_path):
                return False
        return True