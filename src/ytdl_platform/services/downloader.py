"""Download and post-processing service — handles yt-dlp download + ffmpeg merge/convert."""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

import yt_dlp

from ytdl_platform.config import get_settings
from ytdl_platform.domain.models import AudioFormat, MediaType
from ytdl_platform.services.quality import (
    build_ytdlp_format_selector,
    get_audio_codec_for_format,
    get_audio_ext_for_format,
)
from ytdl_platform.utils import generate_job_id, sanitize_filename, safe_filepath

logger = logging.getLogger(__name__)


class DownloadResult:
    """Result of a download operation."""

    def __init__(
        self,
        job_id: str,
        filepath: Path,
        filename: str,
        title: str = "",
        filesize: Optional[int] = None,
    ):
        self.job_id = job_id
        self.filepath = filepath
        self.filename = filename
        self.title = title
        self.filesize = filesize

    @property
    def filesize_mb(self) -> float:
        if self.filesize is None:
            return 0.0
        return self.filesize / (1024 * 1024)


class DownloadError(Exception):
    """Error during download or processing."""

    pass


async def download_video(
    url: str,
    media_type: MediaType = MediaType.VIDEO,
    quality: Optional[str] = None,
    format_id: Optional[str] = None,
    audio_format: Optional[AudioFormat] = None,
    output_dir: Optional[Path] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    job_id: Optional[str] = None,
) -> DownloadResult:
    """Download a YouTube video/audio with the specified quality.

    Args:
        url: Validated YouTube URL.
        media_type: VIDEO or AUDIO.
        quality: Quality label like '1080p', 'best', etc.
        format_id: Exact yt-dlp format ID (overrides quality).
        audio_format: Target audio container for audio-only.
        output_dir: Where to save the file. Defaults to settings.download_dir.
        progress_callback: Async callback(progress_pct, status_text).
        job_id: Optional job identifier.

    Returns:
        DownloadResult with path and metadata.

    Raises:
        DownloadError: On download/processing failure.
    """
    settings = get_settings()
    job_id = job_id or generate_job_id()

    if output_dir is None:
        output_dir = settings.download_dir

    # Create job-specific temp directory
    job_dir = output_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        if media_type == MediaType.AUDIO:
            result = await _download_audio(
                url=url,
                audio_format=audio_format or AudioFormat.MP3,
                output_dir=job_dir,
                quality=quality,
                format_id=format_id,
                progress_callback=progress_callback,
            )
        else:
            result = await _download_video(
                url=url,
                quality=quality,
                format_id=format_id,
                output_dir=job_dir,
                progress_callback=progress_callback,
            )

        # Check filesize limit
        if result.filesize and result.filesize > settings.max_filesize_mb * 1024 * 1024:
            raise DownloadError(
                f"File size ({result.filesize_mb:.1f} MB) exceeds the limit "
                f"({settings.max_filesize_mb} MB). Try a lower quality or use link mode."
            )

        return result

    except DownloadError:
        # Clean up on failure
        _cleanup_dir(job_dir)
        raise
    except Exception as exc:
        _cleanup_dir(job_dir)
        raise DownloadError(f"Download failed: {exc}") from exc


async def _download_video(
    url: str,
    quality: Optional[str],
    format_id: Optional[str],
    output_dir: Path,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> DownloadResult:
    """Download video (with audio merge if needed)."""
    format_selector = build_ytdlp_format_selector(
        media_type=MediaType.VIDEO,
        quality=quality,
        format_id=format_id,
    )

    outtmpl = str(output_dir / "%(title)s.%(ext)s")

    opts: dict[str, Any] = {
        "format": format_selector,
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    if progress_callback:
        opts["progress_hooks"] = [_make_progress_hook(progress_callback, "Downloading")]

    # Notify
    if progress_callback:
        await _call_progress(progress_callback, 0.0, "Downloading video…")

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: _run_ytdlp(opts, url))
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(f"yt-dlp download error: {exc}") from exc

    # Find the output file
    filepath = _find_output_file(output_dir)
    if filepath is None:
        raise DownloadError("Download completed but output file not found.")

    title = info.get("title", "Unknown") if info else "Unknown"
    filesize = filepath.stat().st_size if filepath.exists() else None

    if progress_callback:
        await _call_progress(progress_callback, 1.0, "Download complete")

    return DownloadResult(
        job_id="",
        filepath=filepath,
        filename=filepath.name,
        title=title,
        filesize=filesize,
    )


async def _download_audio(
    url: str,
    audio_format: AudioFormat,
    output_dir: Path,
    quality: Optional[str] = None,
    format_id: Optional[str] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> DownloadResult:
    """Download audio only and convert to the specified format."""
    format_selector = build_ytdlp_format_selector(
        media_type=MediaType.AUDIO,
        format_id=format_id,
    )

    ext = get_audio_ext_for_format(audio_format)
    codec = get_audio_codec_for_format(audio_format)

    outtmpl = str(output_dir / "%(title)s.%(ext)s")

    postprocessors = [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": ext,
            "preferredquality": "0",  # best
        },
    ]

    # Add codec-specific postprocessor args for quality
    pp_args: dict[str, Any] = {}
    if audio_format == AudioFormat.MP3:
        pp_args["postprocessor_args"] = {"extractaudio": ["-ar", "44100"]}
    elif audio_format == AudioFormat.OPUS:
        pp_args["postprocessor_args"] = {"extractaudio": ["-ar", "48000"]}

    opts: dict[str, Any] = {
        "format": format_selector,
        "outtmpl": outtmpl,
        "postprocessors": postprocessors,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "prefer_ffmpeg": True,
    }
    opts.update(pp_args)

    if progress_callback:
        opts["progress_hooks"] = [_make_progress_hook(progress_callback, "Downloading audio")]
        await _call_progress(progress_callback, 0.0, "Downloading audio…")

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: _run_ytdlp(opts, url))
    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(f"yt-dlp audio download error: {exc}") from exc

    # Find the output file (may have different extension after conversion)
    filepath = _find_output_file(output_dir, preferred_ext=ext)
    if filepath is None:
        raise DownloadError("Audio download completed but output file not found.")

    title = info.get("title", "Unknown") if info else "Unknown"
    filesize = filepath.stat().st_size if filepath.exists() else None

    if progress_callback:
        await _call_progress(progress_callback, 1.0, "Audio extraction complete")

    return DownloadResult(
        job_id="",
        filepath=filepath,
        filename=filepath.name,
        title=title,
        filesize=filesize,
    )


def _run_ytdlp(opts: dict[str, Any], url: str) -> dict[str, Any] | None:
    """Run yt-dlp synchronously with the given options."""
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=True)


def _find_output_file(directory: Path, preferred_ext: str | None = None) -> Path | None:
    """Find the most recently created file in a directory."""
    files = list(directory.iterdir())
    if not files:
        return None

    # Filter to media files
    media_exts = {".mp4", ".mkv", ".webm", ".mp3", ".m4a", ".opus", ".ogg", ".flac", ".wav"}
    media_files = [f for f in files if f.is_file() and f.suffix.lower() in media_exts]

    if not media_files:
        # Fallback: just get the most recent file
        media_files = [f for f in files if f.is_file()]

    if not media_files:
        return None

    # If preferred extension, try to find it first
    if preferred_ext:
        ext_match = [f for f in media_files if f.suffix.lower() == f".{preferred_ext}"]
        if ext_match:
            return max(ext_match, key=lambda f: f.stat().st_mtime)

    return max(media_files, key=lambda f: f.stat().st_mtime)


def _make_progress_hook(
    callback: Callable[[float, str], Any],
    stage: str,
) -> Callable[[dict], None]:
    """Create a yt-dlp progress hook that calls our async callback."""
    def hook(d: dict) -> None:
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            if total and total > 0:
                pct = downloaded / total
                try:
                    # Try to schedule the callback
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(callback(pct, f"{stage}… {pct:.0%}"))
                except RuntimeError:
                    pass
    return hook


async def _call_progress(
    callback: Callable[[float, str], Any],
    progress: float,
    status: str,
) -> None:
    """Safely call an async progress callback."""
    try:
        result = callback(progress, status)
        if asyncio.iscoroutine(result):
            await result
    except Exception:
        logger.debug("Progress callback error (ignored)")


def _cleanup_dir(directory: Path) -> None:
    """Remove a directory and its contents."""
    try:
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)
    except Exception:
        logger.warning("Failed to clean up directory: %s", directory)


def cleanup_temp_fragments(directory: Path) -> None:
    """Clean up temporary .part and .temp files left by yt-dlp."""
    for f in directory.rglob("*.part"):
        try:
            f.unlink()
        except OSError:
            pass
    for f in directory.rglob("*.temp"):
        try:
            f.unlink()
        except OSError:
            pass
    for f in directory.rglob("*.ytdl"):
        try:
            f.unlink()
        except OSError:
            pass
