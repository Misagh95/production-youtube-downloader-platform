"""Application configuration via pydantic-settings and environment variables."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──
    app_name: str = "YouTube Downloader Platform"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    api_key: str = "change-me-to-a-secure-random-string"
    public_base_url: str = "http://localhost:8000"

    # ── Download ──
    download_dir: Path = Path("./data/files")
    max_concurrent_jobs: int = 3
    max_filesize_mb: int = 512
    max_duration_seconds: int = 7200
    link_expiry_minutes: int = 30
    cleanup_interval_minutes: int = 10

    # ── Telegram ──
    telegram_bot_token: Optional[str] = None
    telegram_admin_ids: str = ""
    telegram_allowed_user_ids: str = ""
    telegram_max_direct_file_mb: int = 49

    # ── yt-dlp / ffmpeg ──
    ytdlp_options_json: str = "{}"
    default_video_quality: str = "1080p"
    default_audio_format: str = "mp3"
    enable_playlists: bool = False

    # ── Logging ──
    log_level: str = "INFO"

    # ── Database ──
    database_url: str = "sqlite+aiosqlite:///./data/jobs.db"

    # ── Derived ──
    @property
    def ytdlp_options(self) -> dict:
        try:
            return json.loads(self.ytdlp_options_json) if self.ytdlp_options_json else {}
        except json.JSONDecodeError:
            return {}

    @property
    def admin_id_list(self) -> list[int]:
        if not self.telegram_admin_ids:
            return []
        return [int(x.strip()) for x in self.telegram_admin_ids.split(",") if x.strip()]

    @property
    def allowed_user_id_list(self) -> list[int]:
        if not self.telegram_allowed_user_ids:
            return []
        return [int(x.strip()) for x in self.telegram_allowed_user_ids.split(",") if x.strip()]

    @field_validator("app_env")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"app_env must be one of {allowed}")
        return v


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Return cached settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
