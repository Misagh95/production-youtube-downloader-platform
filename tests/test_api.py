"""Tests for the FastAPI endpoints (mocked yt-dlp)."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ytdl_platform.domain.models import FormatOption, VideoInfo
from ytdl_platform.api.app import create_app

from fastapi.testclient import TestClient


# ── Fixtures ──

def make_sample_video_info() -> VideoInfo:
    return VideoInfo(
        id="dQw4w9WgXcQ",
        title="Rick Astley - Never Gonna Give You Up",
        duration=213,
        thumbnail="https://img.youtube.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
        uploader="Rick Astley",
        view_count=1_400_000_000,
        webpage_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        formats=[
            FormatOption(
                format_id="137",
                ext="mp4",
                resolution="1080p",
                height=1080,
                vcodec="avc1",
                acodec="none",
                is_video=True,
                is_audio=False,
                filesize=100_000_000,
            ),
            FormatOption(
                format_id="22",
                ext="mp4",
                resolution="720p",
                height=720,
                vcodec="avc1",
                acodec="mp4a",
                is_video=True,
                is_audio=True,
                is_progressive=True,
                filesize=55_000_000,
            ),
            FormatOption(
                format_id="140",
                ext="m4a",
                resolution="audio only",
                vcodec="none",
                acodec="mp4a",
                abr=128.0,
                is_video=False,
                is_audio=True,
                filesize=5_000_000,
            ),
        ],
        video_formats=[
            FormatOption(format_id="137", ext="mp4", resolution="1080p", height=1080,
                         vcodec="avc1", acodec="none", is_video=True, is_audio=False,
                         filesize=100_000_000),
            FormatOption(format_id="22", ext="mp4", resolution="720p", height=720,
                         vcodec="avc1", acodec="mp4a", is_video=True, is_audio=True,
                         is_progressive=True, filesize=55_000_000),
        ],
        audio_formats=[
            FormatOption(format_id="140", ext="m4a", resolution="audio only",
                         vcodec="none", acodec="mp4a", abr=128.0,
                         is_video=False, is_audio=True, filesize=5_000_000),
        ],
    )


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def sample_info():
    return make_sample_video_info()


# ── Tests ──


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "version" in data


class TestAnalyzeEndpoint:
    @patch("ytdl_platform.api.app.extract_info", new_callable=AsyncMock)
    def test_analyze_success(self, mock_extract, client, sample_info):
        mock_extract.return_value = sample_info
        response = client.post(
            "/api/v1/analyze",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["video"]["id"] == "dQw4w9WgXcQ"
        assert data["video"]["title"] == "Rick Astley - Never Gonna Give You Up"
        assert len(data["video_options"]) > 0
        assert len(data["audio_options"]) > 0

    def test_analyze_invalid_url(self, client):
        response = client.post(
            "/api/v1/analyze",
            json={"url": "https://google.com"},
        )
        assert response.status_code == 400

    def test_analyze_empty_url(self, client):
        response = client.post(
            "/api/v1/analyze",
            json={"url": ""},
        )
        assert response.status_code == 400

    @patch("ytdl_platform.api.app.extract_info", new_callable=AsyncMock)
    def test_analyze_private_video(self, mock_extract, client):
        mock_extract.side_effect = RuntimeError("Cannot access this video — it may be private.")
        response = client.post(
            "/api/v1/analyze",
            json={"url": "https://www.youtube.com/watch?v=private12345"},
        )
        assert response.status_code in (403, 404, 500)

    @patch("ytdl_platform.api.app.extract_info", new_callable=AsyncMock)
    def test_analyze_geo_blocked(self, mock_extract, client):
        mock_extract.side_effect = RuntimeError("Not available in this region (geo-blocked).")
        response = client.post(
            "/api/v1/analyze",
            json={"url": "https://www.youtube.com/watch?v=geo12345678"},
        )
        assert response.status_code == 403


class TestNonYouTubeRejection:
    def test_rejects_vimeo(self, client):
        response = client.post(
            "/api/v1/analyze",
            json={"url": "https://vimeo.com/123456"},
        )
        assert response.status_code == 400

    def test_rejects_random_url(self, client):
        response = client.post(
            "/api/v1/analyze",
            json={"url": "https://example.com/video"},
        )
        assert response.status_code == 400
