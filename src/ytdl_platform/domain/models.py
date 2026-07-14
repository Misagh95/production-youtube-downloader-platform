"""Domain models and enums for the YouTube Downloader Platform."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ──


class JobState(str, enum.Enum):
    """Lifecycle states for a download job."""

    QUEUED = "queued"
    ANALYZING = "analyzing"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"
    UPLOADING = "uploading"
    READY = "ready"
    FAILED = "failed"
    EXPIRED = "expired"


class MediaType(str, enum.Enum):
    """Whether the user wants video or audio."""

    VIDEO = "video"
    AUDIO = "audio"


class DeliveryMode(str, enum.Enum):
    """How the user receives the result."""

    DIRECT = "direct"
    LINK = "link"


class AudioFormat(str, enum.Enum):
    """Output container for audio-only extraction."""

    MP3 = "mp3"
    M4A = "m4a"
    OPUS = "opus"


class QualityLabel(str, enum.Enum):
    """Human-friendly quality labels for video selection."""

    BEST = "best"
    P2160 = "2160p"
    P1440 = "1440p"
    P1080 = "1080p"
    P720 = "720p"
    P480 = "480p"
    P360 = "360p"
    P240 = "240p"
    WORST = "worst"


class AudioQualityLabel(str, enum.Enum):
    """Human-friendly labels for audio selection."""

    BEST = "best"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ── Models ──


class FormatOption(BaseModel):
    """A single available format returned by yt-dlp."""

    format_id: str
    ext: str = ""
    resolution: str = ""
    height: Optional[int] = None
    width: Optional[int] = None
    fps: Optional[int] = None
    vcodec: str = ""
    acodec: str = ""
    bitrate: Optional[int] = None
    filesize: Optional[int] = None
    filesize_approx: Optional[int] = None
    is_video: bool = False
    is_audio: bool = False
    is_progressive: bool = False  # video+audio in one stream
    tbr: Optional[float] = None
    abr: Optional[float] = None
    vbr: Optional[float] = None

    @property
    def filesize_human(self) -> str:
        size = self.filesize or self.filesize_approx
        if size is None:
            return "~unknown"
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        if size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        return f"{size / (1024 * 1024 * 1024):.1f} GB"

    @property
    def label(self) -> str:
        parts: list[str] = []
        if self.is_video and self.height:
            parts.append(f"{self.height}p")
        if self.fps:
            parts.append(f"{self.fps}fps")
        if self.vcodec and self.vcodec != "none":
            parts.append(self.vcodec[:4])
        if self.acodec and self.acodec != "none":
            parts.append(self.acodec[:4])
        parts.append(self.ext)
        if self.filesize or self.filesize_approx:
            parts.append(f"~{self.filesize_human}")
        return " | ".join(parts) if parts else self.format_id


class VideoInfo(BaseModel):
    """Metadata about a YouTube video from yt-dlp."""

    id: str
    title: str = "Unknown"
    duration: Optional[int] = None
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    view_count: Optional[int] = None
    description: Optional[str] = None
    webpage_url: str = ""
    formats: list[FormatOption] = Field(default_factory=list)

    # Grouped for display
    video_formats: list[FormatOption] = Field(default_factory=list)
    audio_formats: list[FormatOption] = Field(default_factory=list)

    @property
    def duration_human(self) -> str:
        if self.duration is None:
            return "unknown"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


class DownloadRequest(BaseModel):
    """User request to download a video."""

    url: str
    quality: Optional[str] = None
    format_id: Optional[str] = None
    type: MediaType = MediaType.VIDEO
    delivery: DeliveryMode = DeliveryMode.DIRECT
    audio_format: Optional[AudioFormat] = AudioFormat.MP3


class AnalyzeRequest(BaseModel):
    """Request to analyze a YouTube URL."""

    url: str


class AnalyzeResponse(BaseModel):
    """Response from the analyze endpoint."""

    video: VideoInfo
    video_options: list[FormatOption] = Field(default_factory=list)
    audio_options: list[FormatOption] = Field(default_factory=list)


class DownloadResponse(BaseModel):
    """Response from the download endpoint (link mode)."""

    job_id: str
    state: JobState
    download_url: Optional[str] = None
    filename: Optional[str] = None
    expires_at: Optional[datetime] = None
    message: str = ""


class JobInfo(BaseModel):
    """Status of a background download job."""

    job_id: str
    state: JobState
    url: str
    quality: Optional[str] = None
    type: MediaType = MediaType.VIDEO
    delivery: DeliveryMode = DeliveryMode.DIRECT
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    progress: float = 0.0
    download_url: Optional[str] = None
    filename: Optional[str] = None
    expires_at: Optional[datetime] = None
    error: Optional[str] = None
    title: Optional[str] = None


class FileToken(BaseModel):
    """A tokenized expiring download link."""

    token: str
    job_id: str
    filepath: str
    filename: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    max_downloads: Optional[int] = None
    download_count: int = 0
