import os
import re
import shutil
import tempfile
import subprocess

from PySide6.QtCore import QObject, Signal

from src.core.utils import get_video_duration, normalize_rect

os.makedirs("temp", exist_ok=True)


class WatermarkRemover(QObject):

    progress_updated = Signal(int)
    status_updated = Signal(str)
    finished = Signal(bool, str)

    SEGMENT_TIME = 30

    def __init__(self):
        super().__init__()

        self._cancelled = False
        self._process = None
        self._params = {}

    # =========================================================
    # public
    # =========================================================

    def setup_remove(self, **kwargs):
        self._params = kwargs

    def run(self):
        try:
            self.remove(**self._params)
        except Exception as e:
            self.finished.emit(False, str(e))

    def cancel(self):
        self._cancelled = True

        try:
            if self._process and self._process.poll() is None:
                self._process.kill()
        except Exception:
            pass

    # =========================================================
    # main
    # =========================================================

    def remove(
        self,
        input_path,
        output_path,
        x,
        y,
        width,
        height,
        encoder="libx264",
        quality="标准"
    ):

        duration = get_video_duration(input_path)

        if not duration:
            self.finished.emit(False, "无法读取视频时长")
            return

        x, y, width, height = normalize_rect(
            x,
            y,
            width,
            height
        )

        total_segments = int(duration // self.SEGMENT_TIME)

        if duration % self.SEGMENT_TIME:
            total_segments += 1

        temp_dir = tempfile.mkdtemp(
            prefix="wm_remove_",
            dir="temp"
        )

        segment_files = []

        try:

            # =====================================================
            # split process
            # =====================================================

            for index in range(total_segments):

                if self._cancelled:
                    self.finished.emit(False, "任务已取消")
                    return

                start = index * self.SEGMENT_TIME

                seg_file = os.path.join(
                    temp_dir,
                    f"segment_{index:04d}.mp4"
                )

                self.status_updated.emit(
                    f"处理中 {index + 1}/{total_segments}"
                )

                vf = (
                    f"delogo="
                    f"x={x}:"
                    f"y={y}:"
                    f"w={width}:"
                    f"h={height}:"
                    f"show=0"
                )

                cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-y",

                    "-ss", str(start),
                    "-i", input_path,

                    "-t", str(self.SEGMENT_TIME),

                    "-vf", vf,

                    *self._encoder_params(
                        encoder,
                        quality
                    ),

                    "-pix_fmt", "yuv420p",

                    "-movflags", "+faststart",

                    "-c:a", "aac",
                    "-b:a", "192k",

                    "-progress", "pipe:1",
                    "-nostats",

                    seg_file
                ]

                success, err = self._run_ffmpeg_progress(
                    cmd,
                    duration,
                    start
                )

                if not success:
                    self.finished.emit(
                        False,
                        f"片段处理失败：\n{err}"
                    )
                    return

                segment_files.append(seg_file)

            # =====================================================
            # concat
            # =====================================================

            concat_file = os.path.join(
                temp_dir,
                "concat.txt"
            )

            with open(concat_file, "w", encoding="utf-8") as f:

                for seg in segment_files:

                    seg = os.path.abspath(seg)
                    seg = seg.replace("\\", "/")

                    f.write(f"file '{seg}'\n")

            self.status_updated.emit("正在合并视频...")

            merge_cmd = [
                "ffmpeg",
                "-hide_banner",
                "-y",

                "-f", "concat",
                "-safe", "0",

                "-i", concat_file,

                "-c", "copy",

                output_path
            ]

            result = subprocess.run(
                merge_cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore"
            )

            # fallback
            if (
                result.returncode != 0 or
                not os.path.exists(output_path)
            ):

                self.status_updated.emit(
                    "快速合并失败，使用重编码..."
                )

                merge_cmd = [
                    "ffmpeg",
                    "-hide_banner",
                    "-y",

                    "-f", "concat",
                    "-safe", "0",

                    "-i", concat_file,

                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-crf", "18",

                    "-c:a", "aac",
                    "-b:a", "192k",

                    output_path
                ]

                result = subprocess.run(
                    merge_cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="ignore"
                )

                if result.returncode != 0:

                    error = (
                        result.stderr.strip()
                        or
                        result.stdout.strip()
                    )

                    raise RuntimeError(
                        f"合并失败:\n{error}"
                    )

            self.progress_updated.emit(100)

            self.finished.emit(True, output_path)

        except Exception as e:

            self.finished.emit(False, str(e))

        finally:

            try:
                shutil.rmtree(
                    temp_dir,
                    ignore_errors=True
                )
            except Exception:
                pass

    # =========================================================
    # ffmpeg progress
    # =========================================================

    def _run_ffmpeg_progress(
        self,
        cmd,
        total_duration,
        segment_start
    ):

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )

        time_pattern = re.compile(
            r"out_time_ms=(\d+)"
        )

        last_lines = []

        while True:

            if self._cancelled:

                try:
                    self._process.kill()
                except Exception:
                    pass

                return False, "任务已取消"

            line = self._process.stdout.readline()

            if not line:

                if self._process.poll() is not None:
                    break

                continue

            line = line.strip()

            last_lines.append(line)

            if len(last_lines) > 30:
                last_lines.pop(0)

            match = time_pattern.search(line)

            if match:

                out_time = int(match.group(1))

                current = (
                    segment_start +
                    out_time / 1_000_000
                )

                percent = int(
                    current /
                    total_duration *
                    100
                )

                self.progress_updated.emit(
                    min(percent, 100)
                )

        ret = self._process.wait()

        if ret != 0:

            return (
                False,
                "\n".join(last_lines[-15:])
            )

        return True, None

    # =========================================================
    # encoder
    # =========================================================

    def _encoder_params(self, encoder, quality):

        if encoder == "nvenc":

            return [
                "-c:v", "h264_nvenc",
                "-preset", "p5",
                "-cq", "19",
                "-rc", "vbr"
            ]

        if encoder == "qsv":

            return [
                "-c:v", "h264_qsv",
                "-global_quality", "20"
            ]

        if encoder == "amf":

            return [
                "-c:v", "h264_amf",
                "-quality", "quality"
            ]

        if quality == "无损":

            return [
                "-c:v", "libx264",
                "-preset", "slow",
                "-crf", "0"
            ]

        if quality == "高质量":

            return [
                "-c:v", "libx264",
                "-preset", "slow",
                "-crf", "18"
            ]

        return [
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23"
        ]