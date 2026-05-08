import shutil
import subprocess
from typing import Optional

from .logger import logger


def check_ffmpeg() -> bool:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")

    logger.info("ffmpeg=%s", ffmpeg)
    logger.info("ffprobe=%s", ffprobe)

    return bool(ffmpeg and ffprobe)


def has_encoder(name: str) -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore"
        )
        return name in result.stdout
    except Exception:
        logger.exception("has_encoder failed")
        return False


def run_ffmpeg_command(cmd: list[str]) -> subprocess.Popen:
    logger.info("FFmpeg CMD:")
    logger.info(" ".join(cmd))

    creation_flags = 0

    try:
        import subprocess as sp
        if hasattr(sp, "CREATE_NO_WINDOW"):
            creation_flags = sp.CREATE_NO_WINDOW
    except Exception:
        pass

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="ignore",
        creationflags=creation_flags
    )


def terminate_process(proc: Optional[subprocess.Popen]):
    if not proc:
        return

    try:
        if proc.poll() is not None:
            return

        logger.warning("Terminating FFmpeg process...")

        try:
            proc.stdin.write("q\n")
            proc.stdin.flush()
        except Exception:
            pass

        proc.terminate()

        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

    except Exception:
        logger.exception("terminate_process failed")