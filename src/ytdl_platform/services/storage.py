"""Storage, expiring link service, and cleanup logic."""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from ytdl_platform.config import get_settings
from ytdl_platform.domain.models import FileToken, JobInfo, JobState
from ytdl_platform.utils import ensure_dir, generate_token, is_safe_path

logger = logging.getLogger(__name__)


class StorageService:
    """Manages local file storage and expiring download tokens."""

    def __init__(self) -> None:
        settings = get_settings()
        self.files_dir = ensure_dir(settings.download_dir)
        self.tokens_file = self.files_dir / ".tokens.json"
        self._tokens: dict[str, dict] = {}
        self._load_tokens()

    def _load_tokens(self) -> None:
        """Load tokens from disk."""
        if self.tokens_file.exists():
            try:
                data = json.loads(self.tokens_file.read_text())
                self._tokens = data
            except (json.JSONDecodeError, OSError):
                self._tokens = {}

    def _save_tokens(self) -> None:
        """Persist tokens to disk."""
        try:
            self.tokens_file.write_text(json.dumps(self._tokens, indent=2, default=str))
        except OSError:
            logger.warning("Failed to save tokens file")

    def store_file(self, source: Path, job_id: str, filename: str) -> Path:
        """Move a downloaded file into the storage directory.

        Returns the final stored path.
        """
        # Create a tokenized subdirectory to avoid filename collisions and predictability
        token = generate_token(12)
        dest_dir = ensure_dir(self.files_dir / token)
        dest = dest_dir / filename

        if not is_safe_path(self.files_dir, dest):
            raise ValueError("Path traversal detected in filename")

        # Move file
        try:
            shutil.move(str(source), str(dest))
        except shutil.Error:
            # If move fails (cross-device), copy then delete
            shutil.copy2(str(source), str(dest))
            source.unlink(missing_ok=True)

        # Clean up the job directory if empty
        try:
            source.parent.rmdir()
        except OSError:
            pass

        return dest

    def create_download_link(
        self,
        filepath: Path,
        filename: str,
        job_id: str,
        expiry_minutes: Optional[int] = None,
        max_downloads: Optional[int] = None,
    ) -> FileToken:
        """Create a time-limited download token for a file."""
        settings = get_settings()
        expiry_minutes = expiry_minutes or settings.link_expiry_minutes

        token = generate_token(32)
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=expiry_minutes)

        token_data = {
            "token": token,
            "job_id": job_id,
            "filepath": str(filepath),
            "filename": filename,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "max_downloads": max_downloads,
            "download_count": 0,
        }

        self._tokens[token] = token_data
        self._save_tokens()

        return FileToken(
            token=token,
            job_id=job_id,
            filepath=str(filepath),
            filename=filename,
            created_at=now,
            expires_at=expires_at,
            max_downloads=max_downloads,
            download_count=0,
        )

    def validate_token(self, token: str) -> Optional[FileToken]:
        """Validate a download token. Returns None if invalid/expired."""
        data = self._tokens.get(token)
        if data is None:
            return None

        expires_at = datetime.fromisoformat(data["expires_at"])
        if datetime.utcnow() > expires_at:
            # Token expired — clean up
            self._revoke_token(token)
            return None

        # Check download count
        max_dl = data.get("max_downloads")
        if max_dl is not None and data.get("download_count", 0) >= max_dl:
            return None

        # Check file still exists
        filepath = Path(data["filepath"])
        if not filepath.exists():
            self._revoke_token(token)
            return None

        # Increment download count
        data["download_count"] = data.get("download_count", 0) + 1
        self._save_tokens()

        return FileToken(
            token=token,
            job_id=data["job_id"],
            filepath=data["filepath"],
            filename=data["filename"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=expires_at,
            max_downloads=max_dl,
            download_count=data["download_count"],
        )

    def revoke_token(self, token: str) -> bool:
        """Revoke a download token and delete the associated file."""
        return self._revoke_token(token)

    def _revoke_token(self, token: str) -> bool:
        """Internal: revoke token and clean up file."""
        data = self._tokens.pop(token, None)
        if data:
            # Try to delete the file and its directory
            filepath = Path(data["filepath"])
            try:
                filepath.unlink(missing_ok=True)
                # Try to remove the tokenized directory
                if filepath.parent != self.files_dir:
                    shutil.rmtree(filepath.parent, ignore_errors=True)
            except OSError:
                pass
            self._save_tokens()
            return True
        return False

    def get_download_url(self, token: str) -> str:
        """Generate the full download URL for a token."""
        settings = get_settings()
        base = settings.public_base_url.rstrip("/")
        return f"{base}/api/v1/files/{token}"

    def cleanup_expired(self) -> int:
        """Remove all expired tokens and their files. Returns count cleaned."""
        now = datetime.utcnow()
        expired_tokens: list[str] = []

        for token, data in list(self._tokens.items()):
            try:
                expires_at = datetime.fromisoformat(data["expires_at"])
                if now > expires_at:
                    expired_tokens.append(token)
            except (ValueError, KeyError):
                expired_tokens.append(token)

        for token in expired_tokens:
            self._revoke_token(token)

        if expired_tokens:
            logger.info("Cleaned up %d expired download tokens", len(expired_tokens))

        return len(expired_tokens)

    def get_storage_usage_mb(self) -> float:
        """Return total storage usage in MB."""
        total = 0
        for f in self.files_dir.rglob("*"):
            if f.is_file() and f.name != ".tokens.json":
                total += f.stat().st_size
        return total / (1024 * 1024)


# ── Singleton ──

_storage: Optional[StorageService] = None


def get_storage() -> StorageService:
    """Return cached storage service singleton."""
    global _storage
    if _storage is None:
        _storage = StorageService()
    return _storage


# ── Job Store (simple dict-based, persisted to JSON) ──


class JobStore:
    """Simple persistent job store using JSON file."""

    def __init__(self) -> None:
        settings = get_settings()
        self.jobs_dir = ensure_dir(settings.download_dir)
        self.jobs_file = self.jobs_dir / ".jobs.json"
        self._jobs: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if self.jobs_file.exists():
            try:
                self._jobs = json.loads(self.jobs_file.read_text())
            except (json.JSONDecodeError, OSError):
                self._jobs = {}

    def _save(self) -> None:
        try:
            self.jobs_file.write_text(json.dumps(self._jobs, indent=2, default=str))
        except OSError:
            logger.warning("Failed to save jobs file")

    def create_job(self, job: JobInfo) -> None:
        self._jobs[job.job_id] = job.model_dump(mode="json")
        self._save()

    def get_job(self, job_id: str) -> Optional[JobInfo]:
        data = self._jobs.get(job_id)
        if data is None:
            return None
        try:
            return JobInfo(**data)
        except Exception:
            return None

    def update_job(self, job_id: str, **kwargs) -> None:
        data = self._jobs.get(job_id)
        if data:
            data.update(kwargs)
            data["updated_at"] = datetime.utcnow().isoformat()
            self._jobs[job_id] = data
            self._save()

    def list_jobs(self, limit: int = 50) -> list[JobInfo]:
        jobs = []
        for data in list(self._jobs.values())[-limit:]:
            try:
                jobs.append(JobInfo(**data))
            except Exception:
                pass
        return jobs

    def delete_job(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)
        self._save()


_job_store: Optional[JobStore] = None


def get_job_store() -> JobStore:
    global _job_store
    if _job_store is None:
        _job_store = JobStore()
    return _job_store
