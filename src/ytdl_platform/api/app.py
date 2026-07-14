"""FastAPI application — YouTube Downloader Platform API."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from ytdl_platform import __version__
from ytdl_platform.api.deps import (
    can_start_job,
    decrement_active_jobs,
    increment_active_jobs,
    rate_limit_dependency,
    setup_cors,
    verify_api_key,
)
from ytdl_platform.api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DownloadRequest,
    DownloadResponse,
    ErrorResponse,
    FormatOptionResponse,
    HealthResponse,
    JobStatusResponse,
    VideoInfoResponse,
)
from ytdl_platform.config import get_settings
from ytdl_platform.domain.models import JobInfo, JobState, MediaType
from ytdl_platform.services.downloader import DownloadError, download_video
from ytdl_platform.services.extractor import check_dependencies, extract_info
from ytdl_platform.services.progress import get_tracker, remove_tracker
from ytdl_platform.services.quality import group_formats_for_display
from ytdl_platform.services.storage import get_job_store, get_storage
from ytdl_platform.utils import generate_job_id, validate_youtube_url

logger = logging.getLogger(__name__)


# ── Lifespan ──

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    settings = get_settings()
    # Ensure download directory exists
    from ytdl_platform.utils import ensure_dir
    ensure_dir(settings.download_dir)
    logger.info("YouTube Downloader Platform API starting (v%s)", __version__)
    yield
    logger.info("API shutting down")


# ── App ──

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="YouTube media download platform — analyze, download, and manage video/audio.",
        lifespan=lifespan,
    )

    # CORS
    setup_cors(app)

    # ── Health ──

    @app.get("/health", response_model=HealthResponse, tags=["System"])
    async def health():
        deps = check_dependencies()
        return HealthResponse(
            ok=True,
            yt_dlp=deps.get("yt_dlp", False),
            ffmpeg=deps.get("ffmpeg", False),
            version=__version__,
        )

    # ── Analyze ──

    @app.post(
        "/api/v1/analyze",
        response_model=AnalyzeResponse,
        tags=["Download"],
        dependencies=[Depends(verify_api_key), Depends(rate_limit_dependency)],
    )
    async def analyze(req: AnalyzeRequest):
        """Analyze a YouTube URL and return metadata + available formats."""
        try:
            url = validate_youtube_url(req.url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            video = await extract_info(url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            msg = str(exc)
            if "geo" in msg.lower():
                raise HTTPException(status_code=403, detail=msg) from exc
            if "private" in msg.lower() or "unavailable" in msg.lower():
                raise HTTPException(status_code=404, detail=msg) from exc
            raise HTTPException(status_code=500, detail=msg) from exc

        grouped = group_formats_for_display(video.formats)

        return AnalyzeResponse(
            video=VideoInfoResponse(
                id=video.id,
                title=video.title,
                duration=video.duration,
                duration_human=video.duration_human,
                thumbnail=video.thumbnail,
                uploader=video.uploader,
                view_count=video.view_count,
            ),
            video_options=[
                FormatOptionResponse(
                    format_id=f.format_id,
                    ext=f.ext,
                    resolution=f.resolution,
                    height=f.height,
                    fps=f.fps,
                    vcodec=f.vcodec,
                    acodec=f.acodec,
                    filesize=f.filesize,
                    filesize_approx=f.filesize_approx,
                    filesize_human=f.filesize_human,
                    is_video=f.is_video,
                    is_audio=f.is_audio,
                    label=f.label,
                )
                for f in grouped["video"]
            ],
            audio_options=[
                FormatOptionResponse(
                    format_id=f.format_id,
                    ext=f.ext,
                    resolution=f.resolution,
                    height=f.height,
                    fps=f.fps,
                    vcodec=f.vcodec,
                    acodec=f.acodec,
                    filesize=f.filesize,
                    filesize_approx=f.filesize_approx,
                    filesize_human=f.filesize_human,
                    is_video=f.is_video,
                    is_audio=f.is_audio,
                    label=f.label,
                )
                for f in grouped["audio"]
            ],
            advanced_formats=[
                FormatOptionResponse(
                    format_id=f.format_id,
                    ext=f.ext,
                    resolution=f.resolution,
                    height=f.height,
                    fps=f.fps,
                    vcodec=f.vcodec,
                    acodec=f.acodec,
                    filesize=f.filesize,
                    filesize_approx=f.filesize_approx,
                    filesize_human=f.filesize_human,
                    is_video=f.is_video,
                    is_audio=f.is_audio,
                    label=f.label,
                )
                for f in grouped["advanced"]
            ],
        )

    # ── Download ──

    @app.post(
        "/api/v1/download",
        tags=["Download"],
        dependencies=[Depends(verify_api_key), Depends(rate_limit_dependency)],
    )
    async def download(req: DownloadRequest):
        """Download a video/audio. Returns file (direct) or download link."""
        try:
            url = validate_youtube_url(req.url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if not can_start_job():
            raise HTTPException(
                status_code=503,
                detail="Too many concurrent downloads. Please try again later.",
            )

        job_id = generate_job_id()
        job_store = get_job_store()
        storage = get_storage()
        tracker = get_tracker(job_id)

        # Create job
        job = JobInfo(
            job_id=job_id,
            state=JobState.ANALYZING,
            url=url,
            quality=req.quality or req.format_id,
            type=req.type,
            delivery=req.delivery,
        )
        job_store.create_job(job)

        try:
            increment_active_jobs()
            job_store.update_job(job_id, state=JobState.DOWNLOADING)
            await tracker.update(0.0, "Downloading…")

            result = await download_video(
                url=url,
                media_type=req.type,
                quality=req.quality,
                format_id=req.format_id,
                audio_format=req.audio_format,
                progress_callback=tracker.make_callback(),
                job_id=job_id,
            )

            job_store.update_job(
                job_id,
                state=JobState.PROCESSING,
                title=result.title,
            )
            await tracker.update(0.9, "Processing…")

            # Store the file
            stored_path = storage.store_file(
                source=result.filepath,
                job_id=job_id,
                filename=result.filename,
            )

            if req.delivery == MediaType.VIDEO.value and req.delivery == "link" or \
               req.delivery == "link":
                # Generate download link
                token_obj = storage.create_download_link(
                    filepath=stored_path,
                    filename=result.filename,
                    job_id=job_id,
                )
                download_url = storage.get_download_url(token_obj.token)

                job_store.update_job(
                    job_id,
                    state=JobState.READY,
                    download_url=download_url,
                    filename=result.filename,
                    expires_at=token_obj.expires_at.isoformat(),
                )
                await tracker.update(1.0, "Ready")

                return DownloadResponse(
                    job_id=job_id,
                    state=JobState.READY.value,
                    download_url=download_url,
                    filename=result.filename,
                    expires_at=token_obj.expires_at.isoformat(),
                    message="Your download link is ready.",
                )
            else:
                # Direct download — return the file
                job_store.update_job(job_id, state=JobState.READY)
                await tracker.update(1.0, "Ready")

                return FileResponse(
                    path=str(stored_path),
                    filename=result.filename,
                    media_type=_guess_media_type(result.filename),
                )

        except DownloadError as exc:
            job_store.update_job(job_id, state=JobState.FAILED, error=str(exc))
            remove_tracker(job_id)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            job_store.update_job(job_id, state=JobState.FAILED, error=str(exc))
            remove_tracker(job_id)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except Exception as exc:
            job_store.update_job(job_id, state=JobState.FAILED, error=str(exc))
            remove_tracker(job_id)
            logger.exception("Unexpected download error for job %s", job_id)
            raise HTTPException(status_code=500, detail="An unexpected error occurred.") from exc
        finally:
            decrement_active_jobs()

    # ── Jobs ──

    @app.get(
        "/api/v1/jobs/{job_id}",
        response_model=JobStatusResponse,
        tags=["Jobs"],
        dependencies=[Depends(verify_api_key)],
    )
    async def get_job_status(job_id: str):
        """Get the status of a download job."""
        job_store = get_job_store()
        job = job_store.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        tracker = get_tracker(job_id)
        return JobStatusResponse(
            job_id=job.job_id,
            state=job.state.value,
            url=job.url,
            quality=job.quality,
            type=job.type.value,
            progress=tracker.progress,
            download_url=job.download_url,
            filename=job.filename,
            expires_at=str(job.expires_at) if job.expires_at else None,
            error=job.error,
            title=job.title,
        )

    # ── Files (download by token) ──

    @app.get("/api/v1/files/{token}", tags=["Files"])
    async def download_file(token: str):
        """Download a file using an expiring token."""
        storage = get_storage()
        token_obj = storage.validate_token(token)
        if token_obj is None:
            raise HTTPException(status_code=404, detail="Download link expired or invalid")

        filepath = Path(token_obj.filepath)
        if not filepath.exists():
            raise HTTPException(status_code=404, detail="File no longer available")

        return FileResponse(
            path=str(filepath),
            filename=token_obj.filename,
            media_type=_guess_media_type(token_obj.filename),
        )

    @app.delete(
        "/api/v1/files/{token}",
        tags=["Files"],
        dependencies=[Depends(verify_api_key)],
    )
    async def revoke_file(token: str):
        """Revoke a download link."""
        storage = get_storage()
        if storage.revoke_token(token):
            return JSONResponse({"message": "Link revoked"})
        raise HTTPException(status_code=404, detail="Token not found")

    # ── Exception handlers ──

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=400,
            content={"error": str(exc)},
        )

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request: Request, exc: RuntimeError):
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )

    return app


def _guess_media_type(filename: str) -> str:
    """Guess MIME type from filename extension."""
    ext = Path(filename).suffix.lower()
    types = {
        ".mp4": "video/mp4",
        ".mkv": "video/x-matroska",
        ".webm": "video/webm",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".opus": "audio/opus",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".wav": "audio/wav",
    }
    return types.get(ext, "application/octet-stream")
