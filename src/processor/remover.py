import os
import shutil
import tempfile
import cv2
import numpy as np
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

    def remove(self, input_path, output_path, x, y, width, height,
               encoder="libx264", quality="标准", remove_config=None):
        duration = get_video_duration(input_path)
        if not duration:
            self.finished.emit(False, "无法读取视频时长")
            return
        x, y, width, height = normalize_rect(x, y, width, height)

        if remove_config is None:
            remove_config = {'method': 0, 'band': 1, 'blur_radius': 0,
                             'crop_rect': None, 'patch_image': '', 'inpaint_radius': 5}
        method = remove_config.get('method', 0)

        # 分支处理
        if method == 5:
            self._remove_opencv(input_path, output_path, x, y, width, height,
                                remove_config.get('inpaint_radius', 5))
            return
        if method == 3:
            crop_rect = remove_config.get('crop_rect')
            if not crop_rect or crop_rect[2] <= 0 or crop_rect[3] <= 0:
                self.finished.emit(False, "邻近区域覆盖未提供有效的截取区域")
                return
            self._remove_crop_overlay(input_path, output_path, x, y, width, height,
                                      crop_rect, encoder, quality)
            return
        if method == 4:
            patch_image = remove_config.get('patch_image', '')
            if not patch_image or not os.path.exists(patch_image):
                self.finished.emit(False, "补丁图片不存在")
                return
            self._remove_patch_overlay(input_path, output_path, x, y, width, height,
                                       patch_image, encoder, quality)
            return

        # 方法 0,1,2：使用 delogo（无 band 参数！）
        filters = [f"delogo=x={x}:y={y}:w={width}:h={height}:show=0"]
        if method == 1:
            filters.append("boxblur=luma_radius=1:luma_power=1")
        elif method == 2:
            blur_r = remove_config.get('blur_radius', 2)
            filters.append(f"boxblur=luma_radius={blur_r}:luma_power=1")
        vf = ",".join(filters)

        # 分段处理...
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
                self.status_updated.emit(f"segment_complete:{seg_file}")
            if not self._concat_segments(segment_files, temp_dir, output_path, encoder, quality):
                raise RuntimeError("视频合并失败")
            self.progress_updated.emit(100)
            self.finished.emit(True, output_path)
        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # ---------- 邻近区域覆盖 ----------
    def _remove_crop_overlay(self, input_path, output_path, x, y, w, h, crop_rect, encoder, quality):
        cx, cy, cw, ch = crop_rect
        filter_complex = (
            f"[0:v]crop={cw}:{ch}:{cx}:{cy},scale={w}:{h}[patch];"
            f"[0:v][patch]overlay={x}:{y}:shortest=1"
        )
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter_complex", filter_complex,
            "-map", "0:a?", "-c:a", "aac", "-b:a", "192k",
            *self._encoder_params(encoder, quality),
            "-progress", "pipe:1", "-nostats",
            output_path
        ]
        duration = get_video_duration(input_path)
        self.status_updated.emit("邻近区域覆盖处理中...")
        success, err = self._run_ffmpeg_progress(cmd, duration, 0)
        if success:
            self.progress_updated.emit(100)
            self.finished.emit(True, output_path)
        else:
            self.finished.emit(False, f"邻近区域覆盖失败\n{err}")

    # ---------- 图片补丁覆盖 ----------
    def _remove_patch_overlay(self, input_path, output_path, x, y, w, h, patch_image, encoder, quality):
        filter_complex = (
            f"[1:v]scale={w}:{h}[patch];"
            f"[0:v][patch]overlay={x}:{y}:shortest=1"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-i", patch_image,
            "-filter_complex", filter_complex,
            "-map", "0:a?", "-c:a", "aac", "-b:a", "192k",
            *self._encoder_params(encoder, quality),
            "-progress", "pipe:1", "-nostats",
            output_path
        ]
        duration = get_video_duration(input_path)
        self.status_updated.emit("图片补丁覆盖处理中...")
        success, err = self._run_ffmpeg_progress(cmd, duration, 0)
        if success:
            self.progress_updated.emit(100)
            self.finished.emit(True, output_path)
        else:
            self.finished.emit(False, f"图片补丁覆盖失败\n{err}")

    # ---------- OpenCV 修复 ----------
    def _remove_opencv(self, input_path, output_path, x, y, w, h, inpaint_radius):
        self.status_updated.emit("OpenCV 修复处理中（速度较慢）...")
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            self.finished.emit(False, "无法打开视频")
            return
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width_v = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height_v = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # 临时无声音视频
        temp_video = tempfile.mktemp(suffix=".mp4", dir="temp")
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_video, fourcc, fps, (width_v, height_v))

        try:
            for idx in range(total_frames):
                if self._cancelled:
                    self.finished.emit(False, "任务已取消")
                    return
                ret, frame = cap.read()
                if not ret:
                    break
                # 创建掩码
                mask = np.zeros(frame.shape[:2], dtype=np.uint8)
                mask[y:y+h, x:x+w] = 255
                repaired = cv2.inpaint(frame, mask, inpaint_radius, cv2.INPAINT_NS)
                out.write(repaired)

                if idx % 10 == 0:  # 每10帧更新进度
                    percent = int((idx / total_frames) * 100)
                    self.progress_updated.emit(percent)
                    self.status_updated.emit(f"OpenCV 修复: {idx}/{total_frames}")
        except Exception as e:
            self.finished.emit(False, f"OpenCV 修复出错: {e}")
            return
        finally:
            cap.release()
            out.release()

        # 合并音频（如果有）
        if not self._cancelled:
            self.status_updated.emit("正在合并音频...")
            if not BaseProcessor.merge_audio_to_video(input_path, temp_video, output_path):
                self.finished.emit(False, "音频合并失败")
                return
            self.progress_updated.emit(100)
            self.finished.emit(True, output_path)
        # 清理临时视频
        if os.path.exists(temp_video):
            os.remove(temp_video)