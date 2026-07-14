"""CLI entry point — ytdl-tool command."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from ytdl_platform import __version__
from ytdl_platform.config import get_settings
from ytdl_platform.domain.models import AudioFormat, MediaType
from ytdl_platform.services.downloader import DownloadError, download_video
from ytdl_platform.services.extractor import extract_info
from ytdl_platform.services.quality import group_formats_for_display


# ── Color helpers ──

class Colors:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"

    @classmethod
    def enabled(cls) -> bool:
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def c(text: str, color: str) -> str:
    """Colorize text if terminal supports it."""
    if Colors.enabled():
        return f"{color}{text}{Colors.RESET}"
    return text


# ── Commands ──


def cmd_analyze(url: str, json_output: bool = False) -> int:
    """Analyze a YouTube URL and print metadata + formats."""
    from ytdl_platform.utils import validate_youtube_url

    try:
        url = validate_youtube_url(url)
    except ValueError as exc:
        print(c(f"Error: {exc}", Colors.RED), file=sys.stderr)
        return 1

    try:
        video = extract_info_sync_wrapper(url)
    except RuntimeError as exc:
        print(c(f"Error: {exc}", Colors.RED), file=sys.stderr)
        return 1

    if json_output:
        data = {
            "id": video.id,
            "title": video.title,
            "duration": video.duration,
            "duration_human": video.duration_human,
            "thumbnail": video.thumbnail,
            "uploader": video.uploader,
            "view_count": video.view_count,
            "formats": [f.model_dump() for f in video.formats],
        }
        print(json.dumps(data, indent=2, default=str))
        return 0

    # Pretty output
    print(c(f"📹 {video.title}", Colors.BOLD))
    print(f"   ID: {video.id}")
    print(f"   Duration: {video.duration_human}")
    print(f"   Views: {video.view_count:,}" if video.view_count else "   Views: N/A")
    if video.uploader:
        print(f"   Uploader: {video.uploader}")
    print()

    grouped = group_formats_for_display(video.formats)

    print(c("🎬 Video formats:", Colors.CYAN))
    for f in grouped["video"]:
        size_str = f" ~{f.filesize_human}" if (f.filesize or f.filesize_approx) else ""
        print(f"   [{f.format_id:>5}] {f.label}{size_str}")

    print()
    print(c("🎵 Audio formats:", Colors.CYAN))
    for f in grouped["audio"]:
        size_str = f" ~{f.filesize_human}" if (f.filesize or f.filesize_approx) else ""
        print(f"   [{f.format_id:>5}] {f.label}{size_str}")

    return 0


def cmd_formats(url: str) -> int:
    """List available formats for a URL (alias for analyze)."""
    return cmd_analyze(url)


def cmd_download(
    url: str,
    quality: Optional[str] = None,
    audio_only: bool = False,
    audio_format: str = "mp3",
    output: str = "./downloads",
    format_id: Optional[str] = None,
) -> int:
    """Download a YouTube video/audio."""
    import asyncio
    from ytdl_platform.utils import validate_youtube_url

    try:
        url = validate_youtube_url(url)
    except ValueError as exc:
        print(c(f"Error: {exc}", Colors.RED), file=sys.stderr)
        return 1

    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    media_type = MediaType.AUDIO if audio_only else MediaType.VIDEO
    audio_fmt = AudioFormat(audio_format) if audio_only else None

    print(c(f"⬇️  Downloading {url}", Colors.BLUE))
    print(c(f"   Quality: {quality or 'best'}", Colors.DIM))
    print(c(f"   Type: {'Audio' if audio_only else 'Video'}", Colors.DIM))
    print(c(f"   Output: {output_dir}", Colors.DIM))

    try:
        result = asyncio.run(
            download_video(
                url=url,
                media_type=media_type,
                quality=quality,
                format_id=format_id,
                audio_format=audio_fmt,
                output_dir=output_dir,
            )
        )
    except DownloadError as exc:
        print(c(f"Error: {exc}", Colors.RED), file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(c(f"Error: {exc}", Colors.RED), file=sys.stderr)
        return 1

    print(c(f"✅ Downloaded: {result.filename}", Colors.GREEN))
    print(f"   Size: {result.filesize_mb:.1f} MB")
    print(f"   Path: {result.filepath}")

    return 0


def extract_info_sync_wrapper(url: str):
    """Synchronous wrapper for extract_info."""
    import asyncio
    return asyncio.run(extract_info(url))


# ── Main ──


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="ytdl-tool",
        description="YouTube Downloader Platform CLI",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Analyze a YouTube URL")
    p_analyze.add_argument("url", help="YouTube URL")
    p_analyze.add_argument("--json", action="store_true", help="JSON output")

    # formats
    p_formats = subparsers.add_parser("formats", help="List available formats")
    p_formats.add_argument("url", help="YouTube URL")

    # download
    p_download = subparsers.add_parser("download", help="Download a video/audio")
    p_download.add_argument("url", help="YouTube URL")
    p_download.add_argument("--quality", "-q", help="Quality label (best, 1080p, 720p, etc.)")
    p_download.add_argument("--format-id", "-f", help="Exact yt-dlp format ID")
    p_download.add_argument("--audio-only", action="store_true", help="Audio only")
    p_download.add_argument(
        "--audio-format",
        choices=["mp3", "m4a", "opus"],
        default="mp3",
        help="Audio format (default: mp3)",
    )
    p_download.add_argument("--output", "-o", default="./downloads", help="Output directory")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    # Initialize settings
    get_settings()

    if args.command == "analyze":
        return cmd_analyze(args.url, json_output=args.json)
    elif args.command == "formats":
        return cmd_formats(args.url)
    elif args.command == "download":
        return cmd_download(
            url=args.url,
            quality=args.quality,
            audio_only=args.audio_only,
            audio_format=args.audio_format,
            output=args.output,
            format_id=args.format_id,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
