"""yt-dlp wrapper — extract metadata and format information from YouTube URLs."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

import yt_dlp

from ytdl_platform.config import get_settings
from ytdl_platform.domain.models import FormatOption, VideoInfo
from ytdl_platform.utils import validate_youtube_url

logger = logging.getLogger(__name__)

# Thread pool for blocking yt-dlp calls
_executor = ThreadPoolExecutor(max_workers=4)


def _extract_info_sync(url: str, extra_opts: dict | None = None) -> dict[str, Any]:
    """Synchronous yt-dlp extraction (runs in thread pool)."""
    settings = get_settings()
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "no_playlist": not settings.enable_playlists,
    }
    if extra_opts:
        opts.update(extra_opts)
    # Merge user-provided yt-dlp options
    opts.update(settings.ytdlp_options)

    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def _parse_formats(info: dict[str, Any]) -> list[FormatOption]:
    """Parse yt-dlp format dicts into our FormatOption model."""
    raw_formats = info.get("formats", [])
    result: list[FormatOption] = []

    for f in raw_formats:
        vcodec = f.get("vcodec", "none") or "none"
        acodec = f.get("acodec", "none") or "none"
        is_video = vcodec != "none"
        is_audio = acodec != "none"

        # Skip formats with no useful streams
        if not is_video and not is_audio:
            continue

        height = f.get("height")
        width = f.get("width")
        fps = f.get("fps")
        tbr = f.get("tbr")
        abr = f.get("abr")
        vbr = f.get("vbr")
        filesize = f.get("filesize")
        filesize_approx = f.get("filesize_approx")

        ext = f.get("ext", "")
        format_id = str(f.get("format_id", ""))
        resolution = f.get("resolution", "")

        # Mark progressive (both audio and video)
        is_progressive = is_video and is_audio

        result.append(
            FormatOption(
                format_id=format_id,
                ext=ext,
                resolution=resolution,
                height=height,
                width=width,
                fps=fps,
                vcodec=vcodec,
                acodec=acodec,
                filesize=filesize,
                filesize_approx=filesize_approx,
                is_video=is_video,
                is_audio=is_audio,
                is_progressive=is_progressive,
                tbr=tbr,
                abr=abr,
                vbr=vbr,
            )
        )

    return result


async def extract_info(url: str) -> VideoInfo:
    """Extract video metadata and available formats asynchronously.

    Raises ValueError for invalid URLs.
    Raises RuntimeError for unavailable/restricted videos.
    """
    # Validate URL
    url = validate_youtube_url(url)

    logger.info("Extracting info for: %s", url)

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(_executor, _extract_info_sync, url)
    except yt_dlp.utils.DownloadError as exc:
        msg = str(exc).lower()
        if "private" in msg or "login" in msg:
            raise RuntimeError("Cannot access this video — it may be private or require login.") from exc
        if "age" in msg or "sign" in msg:
            raise RuntimeError("Cannot access this video — age restriction or sign-in required.") from exc
        if "country" in msg or "geo" in msg or "region" in msg:
            raise RuntimeError("Not available in this region (geo-blocked).") from exc
        if "not found" in msg or "does not exist" in msg or "removed" in msg or "deleted" in msg:
            raise RuntimeError("Video unavailable — it may have been removed or made private.") from exc
        raise RuntimeError(f"Failed to extract video info: {exc}") from exc
    except Exception as exc:
        logger.exception("Unexpected error extracting info for %s", url)
        raise RuntimeError(f"Unexpected error: {exc}") from exc

    if info is None:
        raise RuntimeError("No video information returned. The video may be unavailable.")

    # Check duration limit
    settings = get_settings()
    duration = info.get("duration")
    if duration and duration > settings.max_duration_seconds:
        raise RuntimeError(
            f"Video duration ({int(duration)}s) exceeds the maximum allowed "
            f"({settings.max_duration_seconds}s)."
        )

    formats = _parse_formats(info)

    # Separate video and audio formats for display
    video_formats = [f for f in formats if f.is_video]
    audio_formats = [f for f in formats if f.is_audio and not f.is_video]

    return VideoInfo(
        id=info.get("id", ""),
        title=info.get("title", "Unknown"),
        duration=info.get("duration"),
        thumbnail=info.get("thumbnail"),
        uploader=info.get("uploader"),
        view_count=info.get("view_count"),
        description=info.get("description", "")[:500] if info.get("description") else None,
        webpage_url=info.get("webpage_url", url),
        formats=formats,
        video_formats=video_formats,
        audio_formats=audio_formats,
    )


def check_dependencies() -> dict[str, bool]:
    """Check if yt-dlp and ffmpeg are available."""
    results: dict[str, bool] = {}

    # Check yt-dlp
    try:
        results["yt_dlp"] = True
    except Exception:
        results["yt_dlp"] = False

    # Check ffmpeg
    import subprocess
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        results["ffmpeg"] = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        results["ffmpeg"] = False

    return results
