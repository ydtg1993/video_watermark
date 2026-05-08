import json
import subprocess
import os
from .logger import logger
from .ffmpeg import has_encoder

def escape_drawtext(text: str) -> str:
    return (
        text
        .replace("\\", "\\\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
        .replace(",", r"\,")
    )

def get_default_font():
    """
    Windows 中文字体兜底，按优先级查找
    """
    possible_fonts = [
        r"C:/Windows/Fonts/msyh.ttc",   # 微软雅黑
        r"C:/Windows/Fonts/msyhbd.ttc",
        r"C:/Windows/Fonts/simhei.ttf", # 黑体
        r"C:/Windows/Fonts/simsun.ttc", # 宋体
    ]
    for f in possible_fonts:
        if os.path.exists(f):
            logger.info("Using fallback font: %s", f)
            return f
    logger.warning("No Chinese font found in system.")
    return ""

def get_best_encoder() -> str:
    if has_encoder("h264_nvenc"):
        return "nvenc"
    if has_encoder("h264_qsv"):
        return "qsv"
    if has_encoder("h264_amf"):
        return "amf"
    return "libx264"

def get_video_duration(filepath: str) -> float | None:
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        filepath
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore"
        )
        if result.returncode != 0:
            logger.error(result.stderr)
            return None
        data = json.loads(result.stdout)
        duration = data.get("format", {}).get("duration")
        return float(duration) if duration else None
    except Exception:
        logger.exception("get_video_duration failed")
        return None

def normalize_rect(x, y, w, h):
    x = int(x)
    y = int(y)
    w = int(w)
    h = int(h)
    if w < 0:
        x += w
        w = abs(w)
    if h < 0:
        y += h
        h = abs(h)
    return x, y, w, h