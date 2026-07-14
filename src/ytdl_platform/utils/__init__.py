"""Utility functions: URL validation, file helpers, security, and logging."""

from __future__ import annotations

import logging
import re
import secrets
import string
import structlog
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse


# ── Logging ──

def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging."""
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )


def get_logger(name: str) -> logging.Logger:
    """Return a logger with the given name."""
    return logging.getLogger(name)


# ── URL Validation ──

YOUTUBE_PATTERNS = [
    r"(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]{11}",
    r"(https?://)?(www\.)?youtube\.com/shorts/[\w-]{11}",
    r"(https?://)?(www\.)?youtube\.com/live/[\w-]{11}",
    r"(https?://)?music\.youtube\.com/watch\?v=[\w-]{11}",
    r"(https?://)?youtu\.be/[\w-]{11}",
    r"(https?://)?(www\.)?youtube\.com/embed/[\w-]{11}",
    r"(https?://)?(m\.)?youtube\.com/watch\?v=[\w-]{11}",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in YOUTUBE_PATTERNS]


def is_youtube_url(url: str) -> bool:
    """Return True if the URL matches a known YouTube pattern."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    return any(p.match(url) for p in _COMPILED_PATTERNS)


def validate_youtube_url(url: str) -> str:
    """Validate and normalize a YouTube URL. Raises ValueError if invalid."""
    if not url or not isinstance(url, str):
        raise ValueError("URL cannot be empty.")
    url = url.strip()
    if not is_youtube_url(url):
        raise ValueError("Invalid YouTube URL. Only YouTube links are supported.")
    return normalize_youtube_url(url)


def normalize_youtube_url(url: str) -> str:
    """Normalize a YouTube URL to a standard format."""
    url = url.strip()
    parsed = urlparse(url)

    # Handle youtu.be short URLs
    if "youtu.be" in parsed.netloc:
        video_id = parsed.path.strip("/")
        return f"https://www.youtube.com/watch?v={video_id}"

    # Handle youtube.com URLs
    if "youtube.com" in parsed.netloc:
        qs = parse_qs(parsed.query)
        video_id = qs.get("v", [None])[0]
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id}"
        # Handle /shorts/ and /live/ and /embed/
        for prefix in ("/shorts/", "/live/", "/embed/"):
            idx = parsed.path.find(prefix)
            if idx != -1:
                video_id = parsed.path[idx + len(prefix):].split("/")[0].split("?")[0]
                return f"https://www.youtube.com/watch?v={video_id}"

    return url


def extract_video_id(url: str) -> Optional[str]:
    """Extract the 11-character YouTube video ID from a URL."""
    try:
        normalized = normalize_youtube_url(url)
        parsed = urlparse(normalized)
        qs = parse_qs(parsed.query)
        vid = qs.get("v", [None])[0]
        if vid and re.match(r"^[\w-]{11}$", vid):
            return vid
    except (ValueError, Exception):
        pass
    return None


# ── File Helpers ──

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MULTIPLE_DOTS = re.compile(r"\.{2,}")
_MULTIPLE_SPACES = re.compile(r"\s+")


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Sanitize a string for use as a filename. Prevent path traversal."""
    if not name:
        return "untitled"
    # Remove path traversal attempts
    name = name.replace("..", "").replace("/", "").replace("\\", "")
    # Replace unsafe characters
    name = _UNSAFE_CHARS.sub("_", name)
    # Collapse multiple spaces/dots
    name = _MULTIPLE_SPACES.sub(" ", name)
    name = _MULTIPLE_DOTS.sub(".", name)
    # Strip leading/trailing whitespace and dots
    name = name.strip(" .")
    # Truncate
    if len(name) > max_length:
        name = name[:max_length].rstrip(" .")
    return name or "untitled"


def ensure_dir(path: Path) -> Path:
    """Create directory if it doesn't exist and return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_filepath(directory: Path, filename: str) -> Path:
    """Construct a safe file path, preventing directory traversal."""
    safe_name = sanitize_filename(filename)
    # Ensure the resolved path stays within the directory
    target = (directory / safe_name).resolve()
    if not str(target).startswith(str(directory.resolve())):
        raise ValueError("Path traversal detected.")
    return target


# ── Security ──

def generate_token(length: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_job_id() -> str:
    """Generate a unique job identifier."""
    return f"job_{generate_token(16)}"


def is_safe_path(base_dir: Path, target: Path) -> bool:
    """Verify that target path is within base_dir (prevents traversal)."""
    try:
        target.resolve().relative_to(base_dir.resolve())
        return True
    except ValueError:
        return False
