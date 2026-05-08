# src/processor/remover.py
import subprocess
import re
import json
import os
import math
import tempfile
import shutil
from PySide6.QtCore import QObject, Signal


class WatermarkRemover(QObject):
    progress_updated = Signal(int)
    status_updated = Signal(str)
    finished = Signal(bool, str)

    def remove(self, input_path: str, output_path: str,
               x: int, y: int, width: int, height: int,
               encoder: str = "libx264", quality: str = "标准"):
        duration = self._get_duration(input_path)
        if duration is None:
            self.finished.emit(False, "无法读取视频时长，请检查文件。")
            return

        segment_duration = 30.0
        num_segments = max(1, math.ceil(duration / segment_duration))
        temp_dir = tempfile.mkdtemp(prefix="remover_")
        segment_files = []

        try:
            for i in range(num_segments):
                start_time = i * segment_duration
                seg_file = os.path.join(temp_dir, f"seg_{i:04d}.mp4")

                self.status_updated.emit(f"正在处理片段 {i + 1}/{num_segments} ...")
                vf = f"delogo=x={x}:y={y}:w={width}:h={height}:show=0"
                cmd = [
                    "ffmpeg",
                    "-ss", str(start_time),
                    "-i", input_path,
                    "-t", str(segment_duration),
                    "-vf", vf,
                ]
                enc_params = self._build_encoder_params(encoder, quality)
                cmd.extend(enc_params)
                cmd.extend(["-y", seg_file])

                try:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        bufsize=1,
                        universal_newlines=True
                    )
                except FileNotFoundError:
                    self.finished.emit(False, "未找到 FFmpeg，请确认已安装并配置到环境变量。")
                    return

                # 解析进度并收集 stderr 内容
                stderr_lines = []
                time_pattern = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")
                for line in process.stderr:
                    stderr_lines.append(line)
                    match = time_pattern.search(line)
                    if match:
                        h, m, s, cs = match.groups()
                        current_sec = int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100
                        absolute_sec = start_time + current_sec
                        percent = min(100, int((absolute_sec / duration) * 100))
                        self.progress_updated.emit(percent)

                process.wait()
                if process.returncode != 0 or not os.path.exists(seg_file):
                    error_detail = "\n".join(stderr_lines[-5:])  # 最后5行通常包含出错信息
                    raise RuntimeError(f"片段{i + 1}处理失败，FFmpeg错误:\n{error_detail}")

                segment_files.append(seg_file)
                final_sec = min((i + 1) * segment_duration, duration)
                self.progress_updated.emit(min(100, int((final_sec / duration) * 100)))

            # 合并
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
            result = subprocess.run(merge_cmd, capture_output=True, text=True)
            if result.returncode != 0 or not os.path.exists(output_path):
                raise RuntimeError(f"合并失败:\n{result.stderr.strip()}")

            self.finished.emit(True, output_path)

        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _build_encoder_params(self, encoder: str, quality: str):
        """根据编码器和质量返回对应的编码器参数列表"""
        # 基础：视频编码器、音频编码
        if encoder == "nvenc":
            vcodec = "h264_nvenc"
            # NVENC 质量控制使用 -cq (0-51)，无损需添加 -coder lossless
            if quality == "无损":
                return ["-c:v", vcodec, "-cq", "0", "-coder", "lossless", "-c:a", "aac", "-b:a", "128k"]
            elif quality == "高质量":
                return ["-c:v", vcodec, "-cq", "18", "-c:a", "aac", "-b:a", "128k"]
            else:  # 标准
                return ["-c:v", vcodec, "-cq", "23", "-c:a", "aac", "-b:a", "128k"]
        elif encoder == "qsv":
            vcodec = "h264_qsv"
            # QSV 质量用 -global_quality (0-51)
            if quality == "无损":
                return ["-c:v", vcodec, "-global_quality", "0", "-c:a", "aac", "-b:a", "128k"]
            elif quality == "高质量":
                return ["-c:v", vcodec, "-global_quality", "18", "-c:a", "aac", "-b:a", "128k"]
            else:
                return ["-c:v", vcodec, "-global_quality", "23", "-c:a", "aac", "-b:a", "128k"]
        elif encoder == "amf":
            vcodec = "h264_amf"
            # AMF 质量用 -qp_p / -qp_i 等，简化处理
            if quality == "无损":
                return ["-c:v", vcodec, "-qp_i", "0", "-qp_p", "0", "-c:a", "aac", "-b:a", "128k"]
            elif quality == "高质量":
                return ["-c:v", vcodec, "-qp_i", "18", "-qp_p", "18", "-c:a", "aac", "-b:a", "128k"]
            else:
                return ["-c:v", vcodec, "-qp_i", "23", "-qp_p", "23", "-c:a", "aac", "-b:a", "128k"]
        else:  # 默认 libx264
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