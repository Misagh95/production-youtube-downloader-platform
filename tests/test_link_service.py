"""Tests for the storage and expiring link service."""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from ytdl_platform.services.storage import StorageService
from ytdl_platform.domain.models import FileToken


class TestFileTokenModel:
    """Test FileToken domain model."""

    def test_create_token(self):
        now = datetime.utcnow()
        token = FileToken(
            token="abc123",
            job_id="job_1",
            filepath="/data/files/abc/video.mp4",
            filename="video.mp4",
            created_at=now,
            expires_at=now + timedelta(minutes=30),
        )
        assert token.token == "abc123"
        assert token.download_count == 0

    def test_token_expiry(self):
        expired_token = FileToken(
            token="expired",
            job_id="job_2",
            filepath="/data/files/abc/video.mp4",
            filename="video.mp4",
            created_at=datetime.utcnow() - timedelta(hours=1),
            expires_at=datetime.utcnow() - timedelta(minutes=1),
        )
        assert expired_token.expires_at < datetime.utcnow()


class TestStorageService:
    """Test storage service with temp directory."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create a StorageService with a temp directory."""
        with patch("ytdl_platform.services.storage.get_settings") as mock_settings:
            settings = MagicMock()
            settings.download_dir = tmp_path
            settings.link_expiry_minutes = 30
            mock_settings.return_value = settings
            svc = StorageService()
            svc.files_dir = tmp_path
            svc.tokens_file = tmp_path / ".tokens.json"
            return svc

    def test_create_and_validate_token(self, storage, tmp_path):
        # Create a dummy file
        test_file = tmp_path / "test_video.mp4"
        test_file.write_text("fake video content")

        token_obj = storage.create_download_link(
            filepath=test_file,
            filename="test_video.mp4",
            job_id="job_test",
        )
        assert token_obj.token
        assert token_obj.expires_at > datetime.utcnow()

        # Validate the token
        validated = storage.validate_token(token_obj.token)
        assert validated is not None
        assert validated.filename == "test_video.mp4"

    def test_expired_token_invalid(self, storage, tmp_path):
        test_file = tmp_path / "test.mp4"
        test_file.write_text("content")

        token_obj = storage.create_download_link(
            filepath=test_file,
            filename="test.mp4",
            job_id="job_test",
        )

        # Manually expire the token
        storage._tokens[token_obj.token]["expires_at"] = (
            datetime.utcnow() - timedelta(minutes=1)
        ).isoformat()
        storage._save_tokens()

        result = storage.validate_token(token_obj.token)
        assert result is None

    def test_revoke_token(self, storage, tmp_path):
        test_file = tmp_path / "test.mp4"
        test_file.write_text("content")

        token_obj = storage.create_download_link(
            filepath=test_file,
            filename="test.mp4",
            job_id="job_test",
        )

        assert storage.revoke_token(token_obj.token) is True
        assert storage.validate_token(token_obj.token) is None

    def test_revoke_nonexistent_token(self, storage):
        assert storage.revoke_token("nonexistent") is False

    def test_max_downloads(self, storage, tmp_path):
        test_file = tmp_path / "test.mp4"
        test_file.write_text("content")

        token_obj = storage.create_download_link(
            filepath=test_file,
            filename="test.mp4",
            job_id="job_test",
            max_downloads=1,
        )

        # First download should succeed
        validated = storage.validate_token(token_obj.token)
        assert validated is not None

        # Second download should fail (max reached)
        validated = storage.validate_token(token_obj.token)
        assert validated is None

    def test_cleanup_expired(self, storage, tmp_path):
        test_file1 = tmp_path / "test1.mp4"
        test_file1.write_text("content1")
        test_file2 = tmp_path / "test2.mp4"
        test_file2.write_text("content2")

        # Create two tokens, expire one
        token1 = storage.create_download_link(
            filepath=test_file1, filename="test1.mp4", job_id="job1"
        )
        token2 = storage.create_download_link(
            filepath=test_file2, filename="test2.mp4", job_id="job2"
        )

        # Expire token1
        storage._tokens[token1.token]["expires_at"] = (
            datetime.utcnow() - timedelta(minutes=1)
        ).isoformat()
        storage._save_tokens()

        count = storage.cleanup_expired()
        assert count == 1
        assert storage.validate_token(token1.token) is None
        assert storage.validate_token(token2.token) is not None

    def test_get_download_url(self, storage, tmp_path):
        test_file = tmp_path / "test.mp4"
        test_file.write_text("content")

        token_obj = storage.create_download_link(
            filepath=test_file, filename="test.mp4", job_id="job_test"
        )

        url = storage.get_download_url(token_obj.token)
        assert token_obj.token in url
        assert "/api/v1/files/" in url


# Need MagicMock import
from unittest.mock import MagicMock
