"""
音频可视化工具 - 生成波形图/频谱图
"""
import subprocess
import os
import tempfile
from pathlib import Path
from typing import Optional


class AudioVisualizer:
    """音频可视化生成器（静态工具类）"""

    @staticmethod
    def generate_waveform(input_video: str, output_image: str,
                          width: int = 1200, height: int = 200) -> bool:
        """
        生成音频波形图
        Args:
            input_video: 视频文件路径
            output_image: 输出图片路径
            width: 图片宽度
            height: 图片高度
        Returns:
            是否成功
        """
        try:
            cmd = [
                "ffmpeg", "-i", input_video,
                "-filter_complex", f"showwavespic=s={width}x{height}:colors=white@0.5:scale=linear",
                "-frames:v", "1",
                "-y", output_image
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            return result.returncode == 0 and Path(output_image).exists()
        except Exception as e:
            print(f"波形生成失败: {e}")
            return False

    @staticmethod
    def generate_spectrum(input_video: str, output_image: str,
                          width: int = 1200, height: int = 400) -> bool:
        """生成频谱图"""
        try:
            cmd = [
                "ffmpeg", "-i", input_video,
                "-filter_complex", f"showspectrumpic=s={width}x{height}:legend=disabled:color=intensity",
                "-frames:v", "1",
                "-y", output_image
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            return result.returncode == 0 and Path(output_image).exists()
        except Exception as e:
            print(f"频谱生成失败: {e}")
            return False

    @staticmethod
    def get_audio_duration(input_video: str) -> Optional[float]:
        """获取音频时长（秒）"""
        try:
            import json
            cmd = [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", "-select_streams", "a",
                input_video
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                if data.get("streams"):
                    return float(data["streams"][0].get("duration", 0))
        except:
            pass
        return None
