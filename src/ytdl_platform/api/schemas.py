"""API request/response schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from ytdl_platform.domain.models import AudioFormat, DeliveryMode, MediaType


# ── Requests ──

class AnalyzeRequest(BaseModel):
    url: str


class DownloadRequest(BaseModel):
    url: str
    quality: Optional[str] = None
    format_id: Optional[str] = None
    type: MediaType = MediaType.VIDEO
    delivery: DeliveryMode = DeliveryMode.DIRECT
    audio_format: Optional[AudioFormat] = AudioFormat.MP3


# ── Responses ──

class FormatOptionResponse(BaseModel):
    format_id: str
    ext: str = ""
    resolution: str = ""
    height: Optional[int] = None
    fps: Optional[int] = None
    vcodec: str = ""
    acodec: str = ""
    filesize: Optional[int] = None
    filesize_approx: Optional[int] = None
    filesize_human: str = ""
    is_video: bool = False
    is_audio: bool = False
    label: str = ""


class VideoInfoResponse(BaseModel):
    id: str
    title: str = "Unknown"
    duration: Optional[int] = None
    duration_human: str = ""
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    view_count: Optional[int] = None


class AnalyzeResponse(BaseModel):
    video: VideoInfoResponse
    video_options: list[FormatOptionResponse] = Field(default_factory=list)
    audio_options: list[FormatOptionResponse] = Field(default_factory=list)
    advanced_formats: list[FormatOptionResponse] = Field(default_factory=list)


class DownloadResponse(BaseModel):
    job_id: str
    state: str
    download_url: Optional[str] = None
    filename: Optional[str] = None
    expires_at: Optional[str] = None
    message: str = ""


class JobStatusResponse(BaseModel):
    job_id: str
    state: str
    url: str
    quality: Optional[str] = None
    type: str = "video"
    progress: float = 0.0
    download_url: Optional[str] = None
    filename: Optional[str] = None
    expires_at: Optional[str] = None
    error: Optional[str] = None
    title: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    ok: bool
    yt_dlp: bool = False
    ffmpeg: bool = False
    version: str = ""
