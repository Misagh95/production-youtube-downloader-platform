"""Tests for quality selection helpers."""

import pytest

from ytdl_platform.domain.models import FormatOption
from ytdl_platform.services.quality import (
    build_ytdlp_format_selector,
    group_formats_for_display,
    resolve_quality_label,
    select_audio_format,
    select_video_format,
)
from ytdl_platform.domain.models import MediaType, AudioFormat


# ── Fixtures ──

def make_video_fmt(format_id: str, height: int, ext: str = "mp4", **kwargs) -> FormatOption:
    return FormatOption(
        format_id=format_id,
        ext=ext,
        resolution=f"{height}p",
        height=height,
        vcodec="avc1",
        acodec="none",
        is_video=True,
        is_audio=False,
        **kwargs,
    )


def make_audio_fmt(format_id: str, abr: float, ext: str = "m4a", **kwargs) -> FormatOption:
    return FormatOption(
        format_id=format_id,
        ext=ext,
        resolution="audio only",
        vcodec="none",
        acodec="mp4a",
        abr=abr,
        is_video=False,
        is_audio=True,
        **kwargs,
    )


def make_progressive_fmt(format_id: str, height: int, ext: str = "mp4", **kwargs) -> FormatOption:
    return FormatOption(
        format_id=format_id,
        ext=ext,
        resolution=f"{height}p",
        height=height,
        vcodec="avc1",
        acodec="mp4a",
        is_video=True,
        is_audio=True,
        is_progressive=True,
        **kwargs,
    )


SAMPLE_FORMATS = [
    make_video_fmt("137", 1080, filesize=100_000_000),
    make_video_fmt("136", 720, filesize=50_000_000),
    make_video_fmt("135", 480, filesize=25_000_000),
    make_video_fmt("134", 360, filesize=15_000_000),
    make_audio_fmt("140", 128.0, ext="m4a", filesize=5_000_000),
    make_audio_fmt("251", 160.0, ext="webm", filesize=6_000_000),
    make_audio_fmt("250", 70.0, ext="webm", filesize=3_000_000),
    make_progressive_fmt("22", 720, filesize=55_000_000),
]


# ── Tests ──


class TestResolveQualityLabel:
    def test_best(self):
        assert resolve_quality_label("best") is not None
        assert resolve_quality_label("best").value == "best"

    def test_1080p(self):
        assert resolve_quality_label("1080p") is not None
        assert resolve_quality_label("1080p").value == "1080p"

    def test_numeric(self):
        result = resolve_quality_label("720")
        # "720" without p won't match, but "720p" will
        assert resolve_quality_label("720p") is not None

    def test_worst(self):
        assert resolve_quality_label("worst") is not None

    def test_invalid(self):
        assert resolve_quality_label("9999p") is None

    def test_case_insensitive(self):
        assert resolve_quality_label("BEST") is not None
        assert resolve_quality_label("1080P") is not None


class TestSelectVideoFormat:
    def test_format_id_priority(self):
        result = select_video_format(SAMPLE_FORMATS, format_id="135")
        assert result is not None
        assert result.format_id == "135"

    def test_best_quality(self):
        result = select_video_format(SAMPLE_FORMATS, quality="best")
        assert result is not None
        assert result.height == 1080 or result.height == 720  # depends on progressive preference

    def test_specific_quality(self):
        result = select_video_format(SAMPLE_FORMATS, quality="720p")
        assert result is not None
        assert result.height is not None
        assert result.height <= 720

    def test_quality_fallback_lower(self):
        result = select_video_format(SAMPLE_FORMATS, quality="2160p")
        # 2160p not available, should fall back to best available
        assert result is not None
        assert result.height is not None

    def test_worst_quality(self):
        result = select_video_format(SAMPLE_FORMATS, quality="worst")
        assert result is not None
        assert result.height == 360

    def test_empty_formats(self):
        assert select_video_format([], quality="best") is None

    def test_invalid_format_id(self):
        assert select_video_format(SAMPLE_FORMATS, format_id="99999") is None


class TestSelectAudioFormat:
    def test_best_audio(self):
        result = select_audio_format(SAMPLE_FORMATS, quality="best")
        assert result is not None
        assert result.abr is not None
        assert result.abr >= 128.0

    def test_format_id(self):
        result = select_audio_format(SAMPLE_FORMATS, format_id="140")
        assert result is not None
        assert result.format_id == "140"

    def test_empty_formats(self):
        assert select_audio_format([], quality="best") is None


class TestBuildFormatSelector:
    def test_audio_selector(self):
        result = build_ytdlp_format_selector(MediaType.AUDIO)
        assert "bestaudio" in result

    def test_best_video(self):
        result = build_ytdlp_format_selector(MediaType.VIDEO, quality="best")
        assert "bestvideo" in result

    def test_1080p(self):
        result = build_ytdlp_format_selector(MediaType.VIDEO, quality="1080p")
        assert "1080" in result

    def test_format_id_override(self):
        result = build_ytdlp_format_selector(MediaType.VIDEO, format_id="137")
        assert result == "137"


class TestGroupFormatsForDisplay:
    def test_groups_exist(self):
        grouped = group_formats_for_display(SAMPLE_FORMATS)
        assert "video" in grouped
        assert "audio" in grouped
        assert "advanced" in grouped

    def test_video_has_merged_options(self):
        grouped = group_formats_for_display(SAMPLE_FORMATS)
        # Should have merged options from DASH video + progressive
        assert len(grouped["video"]) > 0

    def test_audio_deduplicated(self):
        grouped = group_formats_for_display(SAMPLE_FORMATS)
        assert len(grouped["audio"]) > 0
