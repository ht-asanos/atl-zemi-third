"""yt-dlp によるメディアダウンロード

YouTube 動画の音声・低解像度動画のダウンロード処理を担う。
"""

import asyncio
import logging
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# --- yt-dlp 定数 ---
YTDLP_TIMEOUT = 120


async def download_video_audio(video_id: str, output_dir: Path) -> Path | None:
    """yt-dlp で音声のみダウンロード（m4a）。"""
    ytdlp_bin = shutil.which("yt-dlp")
    base_cmd = [ytdlp_bin] if ytdlp_bin else [sys.executable, "-m", "yt_dlp"]
    output_path = output_dir / f"{video_id}.%(ext)s"
    cmd = base_cmd + [
        "-x",
        "--audio-format",
        "m4a",
        "-o",
        str(output_path),
        "--no-playlist",
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
        if proc.returncode != 0:
            logger.warning("yt-dlp audio download failed for %s: %s", video_id, stderr.decode()[:500])
            return None
        # yt-dlp が実際に出力したファイルを探す
        files = list(output_dir.glob(f"{video_id}.*"))
        return files[0] if files else None
    except FileNotFoundError:
        logger.warning("yt-dlp command not found. Please install yt-dlp in the backend environment.")
        return None
    except TimeoutError:
        logger.warning("yt-dlp audio download timed out for %s", video_id)
        return None
    except Exception:
        logger.exception("yt-dlp audio download error for %s", video_id)
        return None


async def download_video_lowres(video_id: str, output_dir: Path) -> Path | None:
    """yt-dlp で 360p 動画ダウンロード。音声抽出失敗時のフォールバック用。"""
    ytdlp_bin = shutil.which("yt-dlp")
    base_cmd = [ytdlp_bin] if ytdlp_bin else [sys.executable, "-m", "yt_dlp"]
    output_path = output_dir / f"{video_id}_video.%(ext)s"
    cmd = base_cmd + [
        "-f",
        "worst[height>=360]",
        "-o",
        str(output_path),
        "--no-playlist",
        f"https://www.youtube.com/watch?v={video_id}",
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
        if proc.returncode != 0:
            logger.warning("yt-dlp video download failed for %s: %s", video_id, stderr.decode()[:500])
            return None
        files = list(output_dir.glob(f"{video_id}_video.*"))
        return files[0] if files else None
    except FileNotFoundError:
        logger.warning("yt-dlp command not found. Please install yt-dlp in the backend environment.")
        return None
    except TimeoutError:
        logger.warning("yt-dlp video download timed out for %s", video_id)
        return None
    except Exception:
        logger.exception("yt-dlp video download error for %s", video_id)
        return None
