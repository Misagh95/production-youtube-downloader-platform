"""Progress tracking for download jobs."""

from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class ProgressTracker:
    """Track progress of a download job and notify callbacks."""

    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self._progress: float = 0.0
        self._status: str = "queued"
        self._callbacks: list[Callable[[float, str], None]] = []

    @property
    def progress(self) -> float:
        return self._progress

    @property
    def status(self) -> str:
        return self._status

    def add_callback(self, cb: Callable[[float, str], None]) -> None:
        self._callbacks.append(cb)

    async def update(self, progress: float, status: str) -> None:
        """Update progress and notify all callbacks."""
        self._progress = max(0.0, min(1.0, progress))
        self._status = status
        for cb in self._callbacks:
            try:
                result = cb(self._progress, self._status)
                # Handle async callbacks
                import asyncio
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.debug("Progress callback error (ignored)")

    def make_callback(self) -> Callable[[float, str], None]:
        """Return a callback suitable for passing to the downloader."""
        def callback(progress: float, status: str) -> None:
            # This will be called from yt-dlp's progress hook (sync context)
            self._progress = max(0.0, min(1.0, progress))
            self._status = status
            for cb in self._callbacks:
                try:
                    cb(self._progress, self._status)
                except Exception:
                    pass
        return callback


# ── Active jobs tracker ──

_active_trackers: dict[str, ProgressTracker] = {}


def get_tracker(job_id: str) -> ProgressTracker:
    """Get or create a progress tracker for a job."""
    if job_id not in _active_trackers:
        _active_trackers[job_id] = ProgressTracker(job_id)
    return _active_trackers[job_id]


def remove_tracker(job_id: str) -> None:
    """Remove a tracker when a job completes."""
    _active_trackers.pop(job_id, None)
