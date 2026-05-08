# src/processor/watermark_adder.py
import subprocess
import re
import json
import os
import math
import tempfile
import shutil
from PySide6.QtCore import QObject, Signal


class WatermarkAdder(QObject):
    progress_updated = Signal(int)
    status_updated = Signal(str)
    finished = Signal(bool, str)

    def add_text(self, input_path: str, output_path: str,
                 text: str, x: int, y: int, fontfile: str = "",
                 fontsize: int = 24, fontcolor: str = "white",
                 alpha: float = 1.0, bold: bool = False,
                 italic: bool = False, angle: float = 0.0,
                 encoder: str = "libx264", quality: str = "标准",
                 remove_first: bool = False, remove_rect: tuple = None):

        # 安全转义文本
        safe_text = self._escape_drawtext(text)
        fontcolor_hex = self._color_to_hex(fontcolor)

        # 构建 drawtext 滤镜 (文本用单引号包裹)
        drawtext_vf = (
            f"drawtext=text='{safe_text}':"
            f"x={x}:y={y}:"
            f"fontsize={fontsize}:fontcolor={fontcolor_hex}@"
            f"{alpha}:angle={angle}"
        )

        # 如果同时要求先去水印
        if remove_first and remove_rect:
            rx, ry, rw, rh = remove_rect
            delogo_vf = f"delogo=x={rx}:y={ry}:w={rw}:h={rh}:show=0"
            combined_vf = f"{delogo_vf},{drawtext_vf}"
        else:
            combined_vf = drawtext_vf

        self._process_segmented(input_path, output_path, combined_vf,
                                encoder, quality)

    @staticmethod
    def _escape_drawtext(text: str) -> str:
        """
        对 drawtext 滤镜中 text= 的值进行 FFmpeg 要求的转义。
        顺序很重要：先转义反斜杠，再转义冒号、单引号、逗号。
        """
        # 1. 反斜杠
        text = text.replace('\\', '\\\\')
        # 2. 冒号
        text = text.replace(':', '\\:')
        # 3. 单引号 (因为我们用单引号包裹文本)
        text = text.replace("'", "\\'")
        # 4. 逗号 (如果文本要和其他滤镜用逗号连接，则必须转义)
        text = text.replace(',', '\\,')
        return text

    def add_image(self, input_path: str, output_path: str,
                  image_path: str, x: int, y: int,
                  width: int = 0, height: int = 0,
                  alpha: float = 1.0,
                  encoder: str = "libx264", quality: str = "标准",
                  remove_first: bool = False, remove_rect: tuple = None):
        if width > 0 and height > 0:
            scale_filter = f"[1:v]scale={width}:{height}[wm];"
            overlay_filter = f"[0:v][wm]overlay={x}:{y}:alpha={alpha}"
        else:
            scale_filter = ""
            overlay_filter = f"[0:v][1:v]overlay={x}:{y}:alpha={alpha}"

        if remove_first and remove_rect:
            rx, ry, rw, rh = remove_rect
            delogo_filter = f"[0:v]delogo=x={rx}:y={ry}:w={rw}:h={rh}:show=0[base];"
            if scale_filter:
                overlay_part = f"[base][wm]overlay={x}:{y}:alpha={alpha}"
                filter_complex = f"{delogo_filter}{scale_filter}{overlay_part}"
            else:
                overlay_part = f"[base][1:v]overlay={x}:{y}:alpha={alpha}"
                filter_complex = f"{delogo_filter}{overlay_part}"
        else:
            filter_complex = f"{scale_filter}{overlay_filter}"

        self._process_segmented_with_image(input_path, output_path,
                                           image_path, filter_complex,
                                           encoder, quality)

    def _process_segmented(self, input_path, output_path, vf,
                           encoder, quality):
        # 去掉 remove_first 和 remove_rect 参数，因为 vf 已经是完整的滤镜链
        duration = self._get_duration(input_path)
        if duration is None:
            self.finished.emit(False, "无法读取视频时长。")
            return

        segment_duration = 30.0
        num_segments = max(1, math.ceil(duration / segment_duration))
        temp_dir = tempfile.mkdtemp(prefix="adder_")
        segment_files = []

        try:
            for i in range(num_segments):
                start_time = i * segment_duration
                seg_file = os.path.join(temp_dir, f"seg_{i:04d}.mp4")

                self.status_updated.emit(f"正在处理片段 {i + 1}/{num_segments} ...")
                cmd = [
                    "ffmpeg",
                    "-ss", str(start_time),
                    "-i", input_path,
                    "-t", str(segment_duration),
                    "-vf", vf,  # ← 直接使用传入的完整 vf
                ]
                cmd.extend(self._build_encoder_params(encoder, quality))
                cmd.extend(["-y", seg_file])

                self._run_segment_cmd(cmd, start_time, duration, seg_file)
                segment_files.append(seg_file)

            self._merge_segments(temp_dir, segment_files, output_path)

        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _process_segmented_with_image(self, input_path, output_path,
                                      image_path, filter_complex,
                                      encoder, quality):
        duration = self._get_duration(input_path)
        if duration is None:
            self.finished.emit(False, "无法读取视频时长。")
            return

        segment_duration = 30.0
        num_segments = max(1, math.ceil(duration / segment_duration))
        temp_dir = tempfile.mkdtemp(prefix="adder_img_")
        segment_files = []

        try:
            for i in range(num_segments):
                start_time = i * segment_duration
                seg_file = os.path.join(temp_dir, f"seg_{i:04d}.mp4")

                self.status_updated.emit(f"正在处理片段 {i+1}/{num_segments} ...")
                cmd = [
                    "ffmpeg",
                    "-ss", str(start_time),
                    "-i", input_path,
                    "-i", image_path,
                    "-t", str(segment_duration),
                    "-filter_complex", filter_complex,
                ]
                cmd.extend(self._build_encoder_params(encoder, quality))
                cmd.extend(["-y", seg_file])

                self._run_segment_cmd(cmd, start_time, duration, seg_file)
                segment_files.append(seg_file)

            self._merge_segments(temp_dir, segment_files, output_path)

        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _run_segment_cmd(self, cmd, start_time, total_duration, seg_file):
        try:
            print("DEBUG CMD:", " ".join(cmd))
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1, universal_newlines=True
            )
        except FileNotFoundError:
            self.finished.emit(False, "未找到 FFmpeg，请确认已安装。")
            raise RuntimeError("FFmpeg not found")

        stderr_lines = []
        time_pattern = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")
        for line in process.stderr:
            stderr_lines.append(line)
            match = time_pattern.search(line)
            if match:
                h, m, s, cs = match.groups()
                current_sec = int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100
                absolute_sec = start_time + current_sec
                percent = min(100, int((absolute_sec / total_duration) * 100))
                self.progress_updated.emit(percent)

        process.wait()
        if process.returncode != 0 or not os.path.exists(seg_file):
            raise RuntimeError("片段处理失败，FFmpeg错误:\n" + "\n".join(stderr_lines[-5:]))

        final_sec = min(start_time + 30, total_duration)
        self.progress_updated.emit(min(100, int((final_sec / total_duration) * 100)))

    def _merge_segments(self, temp_dir, segment_files, output_path):
        self.status_updated.emit("正在合并片段...")
        concat_file = os.path.join(temp_dir, "files.txt")
        with open(concat_file, "w", encoding="utf-8") as f:
            for seg in segment_files:
                f.write(f"file '{seg}'\n")

        merge_cmd = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            "-y",
            output_path
        ]
        subprocess.run(merge_cmd, check=True, capture_output=True, text=True)

        if os.path.exists(output_path):
            self.finished.emit(True, output_path)
        else:
            raise RuntimeError("合并失败，输出文件未生成")

    def _build_encoder_params(self, encoder: str, quality: str):
        if encoder == "nvenc":
            vcodec = "h264_nvenc"
            if quality == "无损":
                return ["-c:v", vcodec, "-cq", "0", "-coder", "lossless", "-c:a", "aac", "-b:a", "128k"]
            elif quality == "高质量":
                return ["-c:v", vcodec, "-cq", "18", "-c:a", "aac", "-b:a", "128k"]
            else:
                return ["-c:v", vcodec, "-cq", "23", "-c:a", "aac", "-b:a", "128k"]
        elif encoder == "qsv":
            vcodec = "h264_qsv"
            if quality == "无损":
                return ["-c:v", vcodec, "-global_quality", "0", "-c:a", "aac", "-b:a", "128k"]
            elif quality == "高质量":
                return ["-c:v", vcodec, "-global_quality", "18", "-c:a", "aac", "-b:a", "128k"]
            else:
                return ["-c:v", vcodec, "-global_quality", "23", "-c:a", "aac", "-b:a", "128k"]
        elif encoder == "amf":
            vcodec = "h264_amf"
            if quality == "无损":
                return ["-c:v", vcodec, "-qp_i", "0", "-qp_p", "0", "-c:a", "aac", "-b:a", "128k"]
            elif quality == "高质量":
                return ["-c:v", vcodec, "-qp_i", "18", "-qp_p", "18", "-c:a", "aac", "-b:a", "128k"]
            else:
                return ["-c:v", vcodec, "-qp_i", "23", "-qp_p", "23", "-c:a", "aac", "-b:a", "128k"]
        else:
            if quality == "无损":
                return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "0", "-c:a", "aac", "-b:a", "128k"]
            elif quality == "高质量":
                return ["-c:v", "libx264", "-preset", "slow", "-crf", "18", "-c:a", "aac", "-b:a", "128k"]
            else:
                return ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "128k"]

    @staticmethod
    def _get_duration(filepath: str) -> float | None:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            filepath
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
        except Exception:
            return None

    @staticmethod
    def _color_to_hex(color: str) -> str:
        if color.startswith('#'):
            return color
        color_map = {
            "white": "#FFFFFF", "black": "#000000", "red": "#FF0000",
            "green": "#00FF00", "blue": "#0000FF", "yellow": "#FFFF00",
            "cyan": "#00FFFF", "magenta": "#FF00FF", "gray": "#808080"
        }
        return color_map.get(color.lower(), "#FFFFFF")