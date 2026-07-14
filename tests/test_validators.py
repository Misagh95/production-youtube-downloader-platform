"""Tests for URL validators, file helpers, and security utilities."""

import pytest
from pathlib import Path

from ytdl_platform.utils import (
    extract_video_id,
    generate_job_id,
    generate_token,
    is_youtube_url,
    is_safe_path,
    sanitize_filename,
    validate_youtube_url,
    normalize_youtube_url,
)


class TestYouTubeURLValidation:
    """Test YouTube URL validation and normalization."""

    VALID_URLS = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
        "https://www.youtube.com/live/dQw4w9WgXcQ",
        "https://music.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/embed/dQw4w9WgXcQ",
        "http://youtube.com/watch?v=dQw4w9WgXcQ",
    ]

    INVALID_URLS = [
        "",
        "not a url",
        "https://google.com",
        "https://vimeo.com/123456",
        "https://youtube.com/",
        "https://youtube.com/watch",
        "javascript:alert(1)",
        "ftp://youtube.com/watch?v=dQw4w9WgXcQ",
    ]

    @pytest.mark.parametrize("url", VALID_URLS)
    def test_valid_urls(self, url: str):
        assert is_youtube_url(url) is True

    @pytest.mark.parametrize("url", INVALID_URLS)
    def test_invalid_urls(self, url: str):
        assert is_youtube_url(url) is False

    def test_validate_accepts_valid(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        result = validate_youtube_url(url)
        assert result is not None

    def test_validate_rejects_invalid(self):
        with pytest.raises(ValueError, match="Invalid YouTube URL"):
            validate_youtube_url("https://google.com")

    def test_validate_rejects_empty(self):
        with pytest.raises(ValueError, match="empty"):
            validate_youtube_url("")

    def test_validate_rejects_none(self):
        with pytest.raises(ValueError):
            validate_youtube_url(None)


class TestURLNormalization:
    """Test URL normalization to standard format."""

    def test_short_url(self):
        result = normalize_youtube_url("https://youtu.be/dQw4w9WgXcQ")
        assert "youtube.com/watch?v=dQw4w9WgXcQ" in result

    def test_mobile_url(self):
        result = normalize_youtube_url("https://m.youtube.com/watch?v=dQw4w9WgXcQ")
        assert "youtube.com/watch?v=dQw4w9WgXcQ" in result

    def test_shorts_url(self):
        result = normalize_youtube_url("https://www.youtube.com/shorts/dQw4w9WgXcQ")
        assert "youtube.com/watch?v=dQw4w9WgXcQ" in result

    def test_embed_url(self):
        result = normalize_youtube_url("https://www.youtube.com/embed/dQw4w9WgXcQ")
        assert "youtube.com/watch?v=dQw4w9WgXcQ" in result

    def test_preserves_standard_url(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert normalize_youtube_url(url) == url


class TestExtractVideoId:
    """Test video ID extraction."""

    def test_standard_url(self):
        vid = extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert vid == "dQw4w9WgXcQ"

    def test_short_url(self):
        vid = extract_video_id("https://youtu.be/dQw4w9WgXcQ")
        assert vid == "dQw4w9WgXcQ"

    def test_invalid_url(self):
        vid = extract_video_id("https://google.com")
        assert vid is None


class TestSanitizeFilename:
    """Test filename sanitization and path traversal prevention."""

    def test_normal_name(self):
        assert sanitize_filename("My Video Title") == "My Video Title"

    def test_removes_unsafe_chars(self):
        result = sanitize_filename('Video: "Best" <Ever>')
        assert ":" not in result
        assert '"' not in result
        assert "<" not in result
        assert ">" not in result

    def test_prevents_path_traversal(self):
        result = sanitize_filename("../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_empty_input(self):
        assert sanitize_filename("") == "untitled"

    def test_truncates_long_name(self):
        long_name = "x" * 300
        result = sanitize_filename(long_name, max_length=100)
        assert len(result) <= 100

    def test_strips_dots(self):
        result = sanitize_filename("...hidden...")
        assert not result.startswith(".")
        assert not result.endswith(".")


class TestSecurity:
    """Test security utilities."""

    def test_generate_token_length(self):
        token = generate_token(32)
        assert len(token) == 32

    def test_generate_token_uniqueness(self):
        tokens = {generate_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_generate_job_id(self):
        job_id = generate_job_id()
        assert job_id.startswith("job_")
        assert len(job_id) > 4

    def test_is_safe_path(self):
        base = Path("/app/data")
        safe = Path("/app/data/video.mp4")
        assert is_safe_path(base, safe) is True

    def test_is_unsafe_path(self):
        base = Path("/app/data")
        unsafe = Path("/app/data/../../etc/passwd")
        assert is_safe_path(base, unsafe) is False
