"""Quality selection helpers — map human labels to yt-dlp format selectors."""

from __future__ import annotations

from typing import Optional

from ytdl_platform.domain.models import (
    AudioFormat,
    AudioQualityLabel,
    FormatOption,
    MediaType,
    QualityLabel,
)

# ── Height mapping ──

QUALITY_HEIGHT_MAP: dict[QualityLabel, int] = {
    QualityLabel.P2160: 2160,
    QualityLabel.P1440: 1440,
    QualityLabel.P1080: 1080,
    QualityLabel.P720: 720,
    QualityLabel.P480: 480,
    QualityLabel.P360: 360,
    QualityLabel.P240: 240,
}

# ── Audio bitrate thresholds (kbps) ──

AUDIO_BITRATE_MAP: dict[AudioQualityLabel, tuple[Optional[int], Optional[int]]] = {
    AudioQualityLabel.BEST: (160, None),    # >= 160 kbps
    AudioQualityLabel.HIGH: (128, 160),     # 128-160 kbps
    AudioQualityLabel.MEDIUM: (64, 128),    # 64-128 kbps
    AudioQualityLabel.LOW: (0, 64),         # < 64 kbps
}


def resolve_quality_label(label: str) -> Optional[QualityLabel]:
    """Parse a string like '1080p' or 'best' into a QualityLabel enum."""
    label = label.strip().lower()
    # Direct match
    for ql in QualityLabel:
        if ql.value == label:
            return ql
    # Numeric shorthand
    if label.endswith("p") and label[:-1].isdigit():
        height = int(label[:-1])
        for ql, h in QUALITY_HEIGHT_MAP.items():
            if h == height:
                return ql
    return None


def select_video_format(
    formats: list[FormatOption],
    quality: Optional[str] = None,
    format_id: Optional[str] = None,
) -> Optional[FormatOption]:
    """Select the best video format matching the requested quality.

    If format_id is given, it wins. Otherwise, we try to find a progressive
    (video+audio) stream first, falling back to a video-only stream that
    would need merging.

    If exact quality is unavailable, we pick the nearest lower quality.
    """
    if not formats:
        return None

    # format_id takes priority
    if format_id:
        for f in formats:
            if f.format_id == format_id and f.is_video:
                return f
        return None

    # No quality specified → best
    if not quality or quality.lower() == QualityLabel.BEST.value:
        return _pick_best_video(formats)

    ql = resolve_quality_label(quality)
    if ql is None:
        return _pick_best_video(formats)

    if ql == QualityLabel.WORST:
        return _pick_worst_video(formats)

    target_height = QUALITY_HEIGHT_MAP.get(ql)
    if target_height is None:
        return _pick_best_video(formats)

    # Try progressive first, then DASH video-only
    return _pick_nearest_video(formats, target_height)


def select_audio_format(
    formats: list[FormatOption],
    quality: Optional[str] = None,
    format_id: Optional[str] = None,
) -> Optional[FormatOption]:
    """Select the best audio format matching the requested quality."""
    if not formats:
        return None

    audio_fmts = [f for f in formats if f.is_audio and not f.is_video]
    if not audio_fmts:
        return None

    if format_id:
        for f in audio_fmts:
            if f.format_id == format_id:
                return f
        return None

    if not quality or quality.lower() == AudioQualityLabel.BEST.value:
        return max(audio_fmts, key=lambda f: f.abr or f.tbr or 0)

    aql = None
    for aq in AudioQualityLabel:
        if aq.value == quality.lower():
            aql = aq
            break

    if aql is None:
        return max(audio_fmts, key=lambda f: f.abr or f.tbr or 0)

    low, high = AUDIO_BITRATE_MAP.get(aql, (0, None))
    candidates = []
    for f in audio_fmts:
        br = f.abr or (f.tbr if f.tbr else 0)
        if low is not None and br < low:
            continue
        if high is not None and br > high:
            continue
        candidates.append(f)

    if candidates:
        return max(candidates, key=lambda f: f.abr or f.tbr or 0)

    # Fallback: nearest lower
    return max(audio_fmts, key=lambda f: f.abr or f.tbr or 0)


def group_formats_for_display(formats: list[FormatOption]) -> dict:
    """Group formats into video (merged-friendly), audio-only, and advanced/raw."""
    video_progressive: list[FormatOption] = []
    video_dash: list[FormatOption] = []
    audio_only: list[FormatOption] = []

    for f in formats:
        if f.is_video and f.is_audio:
            video_progressive.append(f)
        elif f.is_video:
            video_dash.append(f)
        elif f.is_audio:
            audio_only.append(f)

    # For normal users, offer merged video options
    # These are the qualities we can produce via merge
    merged_options = _build_merged_options(video_dash, audio_only)
    # Add progressive options (already have audio)
    merged_options.extend(video_progressive)
    # Deduplicate by height
    seen: set[int] = set()
    unique_merged: list[FormatOption] = []
    for f in sorted(merged_options, key=lambda x: x.height or 0, reverse=True):
        h = f.height or 0
        if h not in seen:
            seen.add(h)
            unique_merged.append(f)

    return {
        "video": unique_merged,
        "audio": _build_audio_options(audio_only),
        "advanced": formats,
    }


def build_ytdlp_format_selector(
    media_type: MediaType,
    quality: Optional[str] = None,
    format_id: Optional[str] = None,
    audio_format: Optional[AudioFormat] = None,
) -> str:
    """Build a yt-dlp format selector string.

    Examples:
        "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
        "bestaudio"
        "251"  (specific format_id)
    """
    if format_id:
        return format_id

    if media_type == MediaType.AUDIO:
        return "bestaudio/best"

    # Video
    if not quality or quality.lower() == QualityLabel.BEST.value:
        return "bestvideo+bestaudio/best"

    if quality.lower() == QualityLabel.WORST.value:
        return "worstvideo+worstaudio/worst"

    ql = resolve_quality_label(quality)
    if ql is None:
        return "bestvideo+bestaudio/best"

    height = QUALITY_HEIGHT_MAP.get(ql)
    if height is None:
        return "bestvideo+bestaudio/best"

    return f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"


def get_audio_codec_for_format(audio_format: Optional[AudioFormat]) -> str:
    """Return the ffmpeg codec name for the target audio format."""
    mapping = {
        AudioFormat.MP3: "libmp3lame",
        AudioFormat.M4A: "aac",
        AudioFormat.OPUS: "libopus",
    }
    if audio_format is None:
        return "libmp3lame"
    return mapping.get(audio_format, "libmp3lame")


def get_audio_ext_for_format(audio_format: Optional[AudioFormat]) -> str:
    """Return the file extension for the target audio format."""
    if audio_format is None:
        return "mp3"
    return audio_format.value


# ── Internal helpers ──


def _pick_best_video(formats: list[FormatOption]) -> Optional[FormatOption]:
    """Pick the best quality video format."""
    video_fmts = [f for f in formats if f.is_video]
    if not video_fmts:
        return None
    # Prefer progressive
    progressive = [f for f in video_fmts if f.is_progressive or f.is_audio]
    if progressive:
        return max(progressive, key=lambda f: f.height or 0)
    return max(video_fmts, key=lambda f: f.height or 0)


def _pick_worst_video(formats: list[FormatOption]) -> Optional[FormatOption]:
    """Pick the lowest quality video format."""
    video_fmts = [f for f in formats if f.is_video]
    if not video_fmts:
        return None
    return min(video_fmts, key=lambda f: f.height or 0)


def _pick_nearest_video(
    formats: list[FormatOption], target_height: int
) -> Optional[FormatOption]:
    """Pick the nearest video format at or below the target height."""
    video_fmts = [f for f in formats if f.is_video and f.height and f.height <= target_height]
    if video_fmts:
        return max(video_fmts, key=lambda f: f.height or 0)
    # If nothing at or below target, pick the best available
    return _pick_best_video(formats)


def _build_merged_options(
    video_dash: list[FormatOption], audio_only: list[FormatOption]
) -> list[FormatOption]:
    """Build virtual 'merged' options from separate video+audio streams."""
    if not video_dash:
        return []
    # Group video by unique height, pick best per height
    by_height: dict[int, FormatOption] = {}
    for f in video_dash:
        h = f.height or 0
        if h not in by_height or (f.height or 0) > (by_height[h].height or 0):
            by_height[h] = f

    merged: list[FormatOption] = []
    for h, vf in sorted(by_height.items(), key=lambda x: x[0], reverse=True):
        # Estimate combined size
        best_audio = max(audio_only, key=lambda a: a.abr or a.tbr or 0) if audio_only else None
        est_size = (vf.filesize or vf.filesize_approx or 0)
        if best_audio:
            est_size += best_audio.filesize or best_audio.filesize_approx or 0

        merged.append(
            FormatOption(
                format_id=vf.format_id,
                ext="mp4",
                resolution=f"{vf.height}p" if vf.height else "",
                height=vf.height,
                width=vf.width,
                fps=vf.fps,
                vcodec=vf.vcodec,
                acodec="merged",
                filesize=est_size or None,
                is_video=True,
                is_audio=True,
                is_progressive=True,
            )
        )
    return merged


def _build_audio_options(audio_only: list[FormatOption]) -> list[FormatOption]:
    """Build a deduplicated list of audio options grouped by quality tier."""
    if not audio_only:
        return []

    # Sort by bitrate descending
    sorted_audio = sorted(audio_only, key=lambda f: f.abr or f.tbr or 0, reverse=True)

    # Pick best per codec group
    seen_exts: set[str] = set()
    result: list[FormatOption] = []
    for f in sorted_audio:
        ext = f.ext or "audio"
        if ext not in seen_exts:
            seen_exts.add(ext)
            result.append(f)

    return result
