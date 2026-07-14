"""Telegram bot — YouTube Downloader Platform."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ytdl_platform.bot.messages import (
    MSG_ANALYZING,
    MSG_AUDIO_OPTIONS,
    MSG_CANCELLED,
    MSG_DELIVERY,
    MSG_ERROR,
    MSG_GEO_BLOCKED,
    MSG_HELP,
    MSG_INVALID_URL,
    MSG_NO_JOB,
    MSG_PRIVATE_VIDEO,
    MSG_READY_DIRECT,
    MSG_READY_LINK,
    MSG_SETTINGS,
    MSG_SIZE_LIMIT,
    MSG_START,
    MSG_TOO_LARGE,
    MSG_UPLOADING,
    MSG_VIDEO_INFO,
    VIDEO_UNAVAILABLE,
    audio_format_keyboard,
    audio_quality_keyboard,
    delivery_keyboard,
    media_type_keyboard,
    video_quality_keyboard,
)
from ytdl_platform.config import get_settings
from ytdl_platform.domain.models import AudioFormat, DeliveryMode, MediaType
from ytdl_platform.services.downloader import DownloadError, download_video
from ytdl_platform.services.extractor import extract_info
from ytdl_platform.services.quality import group_formats_for_display
from ytdl_platform.services.storage import get_storage
from ytdl_platform.utils import extract_video_id, is_youtube_url, validate_youtube_url

logger = logging.getLogger(__name__)

# Per-user state (in-memory, keyed by user_id)
_user_state: dict[int, dict] = {}


def _is_allowed(user_id: int) -> bool:
    """Check if a Telegram user is allowed to use the bot."""
    settings = get_settings()
    admin_ids = settings.admin_id_list
    allowed_ids = settings.allowed_user_id_list
    if not admin_ids and not allowed_ids:
        return True  # No restrictions configured
    return user_id in admin_ids or user_id in allowed_ids


# ── Handlers ──


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not update.message:
        return
    await update.message.reply_text(MSG_START, parse_mode="Markdown")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    if not update.message:
        return
    await update.message.reply_text(MSG_HELP, parse_mode="Markdown")


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancel command."""
    if not update.message:
        return
    user_id = update.message.from_user.id
    if user_id in _user_state:
        del _user_state[user_id]
        await update.message.reply_text(MSG_CANCELLED)
    else:
        await update.message.reply_text(MSG_NO_JOB)


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command."""
    if not update.message:
        return
    settings = get_settings()
    await update.message.reply_text(
        MSG_SETTINGS.format(
            video_quality=settings.default_video_quality,
            audio_format=settings.default_audio_format,
            delivery="direct",
        ),
        parse_mode="Markdown",
    )


async def cmd_formats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /formats <url> command."""
    if not update.message:
        return
    user_id = update.message.from_user.id
    if not _is_allowed(user_id):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return

    url = " ".join(context.args) if context.args else ""
    if not url or not is_youtube_url(url):
        await update.message.reply_text(MSG_INVALID_URL)
        return

    msg = await update.message.reply_text(MSG_ANALYZING)
    try:
        video = await extract_info(url)
    except ValueError:
        await msg.edit_text(MSG_INVALID_URL)
        return
    except RuntimeError as exc:
        await msg.edit_text(_map_error(str(exc)))
        return

    grouped = group_formats_for_display(video.formats)

    text = f"📹 *{video.title}*\nDuration: {video.duration_human}\n\n*Video formats:*\n"
    for f in grouped["video"][:10]:
        text += f"• {f.label}\n"
    text += "\n*Audio formats:*\n"
    for f in grouped["audio"][:6]:
        text += f"• {f.label}\n"

    await msg.edit_text(text, parse_mode="Markdown")


async def cmd_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /audio <url> — quick audio-only flow."""
    if not update.message:
        return
    user_id = update.message.from_user.id
    if not _is_allowed(user_id):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return

    url = " ".join(context.args) if context.args else ""
    if not url or not is_youtube_url(url):
        await update.message.reply_text(MSG_INVALID_URL)
        return

    msg = await update.message.reply_text(MSG_ANALYZING)
    try:
        url = validate_youtube_url(url)
    except ValueError:
        await msg.edit_text(MSG_INVALID_URL)
        return

    settings = get_settings()
    audio_fmt = AudioFormat(settings.default_audio_format)

    await msg.edit_text("⬇️ Downloading audio…")
    try:
        result = await download_video(
            url=url,
            media_type=MediaType.AUDIO,
            audio_format=audio_fmt,
            job_id=f"tg_{user_id}",
        )
    except DownloadError as exc:
        await msg.edit_text(MSG_ERROR.format(error=str(exc)))
        return
    except RuntimeError as exc:
        await msg.edit_text(_map_error(str(exc)))
        return

    storage = get_storage()
    stored_path = storage.store_file(
        source=result.filepath,
        job_id=f"tg_{user_id}",
        filename=result.filename,
    )

    await _deliver_file(
        msg=msg,
        chat_id=update.message.chat_id,
        context=context,
        filepath=stored_path,
        filename=result.filename,
        title=result.title,
        is_audio=True,
    )


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle a plain YouTube URL message."""
    if not update.message or not update.message.text:
        return
    user_id = update.message.from_user.id
    if not _is_allowed(user_id):
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return

    text = update.message.text.strip()
    if not is_youtube_url(text):
        return  # Not a YouTube URL, ignore

    try:
        url = validate_youtube_url(text)
    except ValueError:
        await update.message.reply_text(MSG_INVALID_URL)
        return

    msg = await update.message.reply_text(MSG_ANALYZING)

    try:
        video = await extract_info(url)
    except ValueError:
        await msg.edit_text(MSG_INVALID_URL)
        return
    except RuntimeError as exc:
        await msg.edit_text(_map_error(str(exc)))
        return

    url_id = video.id or extract_video_id(url) or "unknown"

    # Store state
    _user_state[user_id] = {
        "url": url,
        "video": video,
        "url_id": url_id,
        "media_type": None,
        "format_id": None,
        "audio_format": None,
    }

    # Show video info and media type choice
    info_text = MSG_VIDEO_INFO.format(
        title=video.title[:100],
        duration=video.duration_human,
        views=f"{video.view_count:,}" if video.view_count else "N/A",
    )

    await msg.edit_text(
        info_text,
        parse_mode="Markdown",
        reply_markup=media_type_keyboard(url_id),
    )


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline keyboard button presses."""
    if not update.callback_query:
        return
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data or ""

    state = _user_state.get(user_id, {})

    if data.startswith("mt:"):
        # Media type selection
        parts = data.split(":")
        media_type = parts[1]
        state["media_type"] = media_type
        _user_state[user_id] = state

        video = state.get("video")
        if not video:
            await query.edit_message_text("Session expired. Please send the URL again.")
            return

        grouped = group_formats_for_display(video.formats)

        if media_type == "video":
            kb = video_quality_keyboard(grouped["video"], state.get("url_id", ""))
            await query.edit_message_text("🎬 Choose video quality:", reply_markup=kb)
        else:
            kb = audio_quality_keyboard(grouped["audio"], state.get("url_id", ""))
            await query.edit_message_text(MSG_AUDIO_OPTIONS, reply_markup=kb)

    elif data.startswith("vq:"):
        # Video quality selected
        parts = data.split(":")
        format_id = parts[1]
        state["format_id"] = format_id
        _user_state[user_id] = state
        kb = delivery_keyboard(state.get("url_id", ""))
        await query.edit_message_text(MSG_DELIVERY, reply_markup=kb)

    elif data.startswith("aq:"):
        # Audio quality selected
        parts = data.split(":")
        format_id = parts[1]
        state["format_id"] = format_id
        _user_state[user_id] = state
        # Ask audio format
        kb = audio_format_keyboard(state.get("url_id", ""))
        await query.edit_message_text("🎵 Choose audio format:", reply_markup=kb)

    elif data.startswith("af:"):
        # Audio format selected
        parts = data.split(":")
        audio_fmt = parts[1]
        state["audio_format"] = audio_fmt
        _user_state[user_id] = state
        kb = delivery_keyboard(state.get("url_id", ""))
        await query.edit_message_text(MSG_DELIVERY, reply_markup=kb)

    elif data.startswith("dm:"):
        # Delivery mode selected — start download
        parts = data.split(":")
        delivery = parts[1]
        state["delivery"] = delivery
        _user_state[user_id] = state

        url = state.get("url")
        media_type = state.get("media_type", "video")
        format_id = state.get("format_id")
        audio_fmt = state.get("audio_format", "mp3")

        if not url:
            await query.edit_message_text("Session expired. Please send the URL again.")
            return

        await query.edit_message_text("⬇️ Downloading…")

        try:
            result = await download_video(
                url=url,
                media_type=MediaType(media_type),
                format_id=format_id,
                audio_format=AudioFormat(audio_fmt) if media_type == "audio" else None,
                job_id=f"tg_{user_id}",
            )
        except DownloadError as exc:
            await query.edit_message_text(MSG_ERROR.format(error=str(exc)))
            del _user_state[user_id]
            return
        except RuntimeError as exc:
            await query.edit_message_text(_map_error(str(exc)))
            del _user_state[user_id]
            return

        storage = get_storage()
        stored_path = storage.store_file(
            source=result.filepath,
            job_id=f"tg_{user_id}",
            filename=result.filename,
        )

        is_audio = media_type == "audio"

        if delivery == "link":
            token_obj = storage.create_download_link(
                filepath=stored_path,
                filename=result.filename,
                job_id=f"tg_{user_id}",
            )
            download_url = storage.get_download_url(token_obj.token)
            settings = get_settings()
            await query.edit_message_text(
                MSG_READY_LINK.format(
                    url=download_url,
                    expiry=settings.link_expiry_minutes,
                    filename=result.filename,
                ),
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
        else:
            await _deliver_file(
                msg=None,
                chat_id=query.message.chat_id if query.message else None,
                context=context,
                filepath=stored_path,
                filename=result.filename,
                title=result.title or "video",
                is_audio=is_audio,
                query=query,
            )

        # Clean up state
        _user_state.pop(user_id, None)


# ── File delivery ──


async def _deliver_file(
    msg=None,
    chat_id: Optional[int] = None,
    context=None,
    filepath: Path = Path(),
    filename: str = "video",
    title: str = "video",
    is_audio: bool = False,
    query=None,
) -> None:
    """Send a file to the user, or fall back to link mode if too large / send fails."""
    import re
    from pathlib import Path as _Path

    settings = get_settings()
    storage = get_storage()
    max_mb = settings.telegram_max_direct_file_mb
    file_size = filepath.stat().st_size if filepath.exists() else 0
    file_mb = file_size / (1024 * 1024)

    if chat_id is None or context is None:
        return

    # Safe ASCII filename for Telegram (Persian/emoji titles often break uploads)
    ext = _Path(filename).suffix or (".mp3" if is_audio else ".mp4")
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", _Path(filename).stem).strip("._") or "download"
    safe_name = f"{safe_name[:80]}{ext}"

    # Only skip direct send when truly too large
    if file_mb > max_mb:
        token_obj = storage.create_download_link(
            filepath=filepath,
            filename=filename,
            job_id="tg_link",
        )
        download_url = storage.get_download_url(token_obj.token)
        text = (
            f"⚠️ File is too large for Telegram direct send ({file_mb:.1f} MB).\n\n"
            f"Download link:\n{download_url}\n\n"
            f"Expires in {settings.link_expiry_minutes} minutes"
        )
        if query:
            await query.edit_message_text(text)
        elif msg:
            await msg.edit_text(text)
        return

    # Try direct send
    try:
        with open(filepath, "rb") as f:
            if is_audio:
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=f,
                    filename=safe_name,
                    title=(title or "audio")[:64],
                )
            else:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=f,
                    filename=safe_name,
                )
        if query:
            await query.edit_message_text("✅ Your file is ready!")
        return
    except Exception as exc:
        logger.warning("Failed to send file directly: %s", exc)

        # Fallback link + show REAL error (not fake "too large")
        token_obj = storage.create_download_link(
            filepath=filepath,
            filename=filename,
            job_id="tg_link",
        )
        download_url = storage.get_download_url(token_obj.token)
        text = (
            f"⚠️ Could not send file directly to Telegram.\n"
            f"Reason: {str(exc)[:180]}\n\n"
            f"Size: {file_mb:.1f} MB\n"
            f"Download link (open on the PC running the bot):\n{download_url}\n\n"
            f"Expires in {settings.link_expiry_minutes} minutes"
        )
        if query:
            await query.edit_message_text(text)
        elif msg:
            await msg.edit_text(text)


def _map_error(error: str) -> str:
    """Map internal errors to user-friendly Telegram messages."""
    error_lower = error.lower()
    if "private" in error_lower or "login" in error_lower:
        return MSG_PRIVATE_VIDEO
    if "geo" in error_lower or "region" in error_lower:
        return MSG_GEO_BLOCKED
    if "unavailable" in error_lower or "removed" in error_lower:
        return VIDEO_UNAVAILABLE
    if "size" in error_lower or "exceeds" in error_lower:
        return MSG_SIZE_LIMIT
    if "timeout" in error_lower:
        return "⏱️ Processing timed out. Please try again."
    if "invalid" in error_lower:
        return MSG_INVALID_URL
    return MSG_ERROR.format(error=error[:200])


# ── Bot runner ──


def run_bot() -> None:
    """Start the Telegram bot."""
    settings = get_settings()

    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is required to run the bot.")
        raise SystemExit(1)

    app = Application.builder().token(settings.telegram_bot_token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("formats", cmd_formats))
    app.add_handler(CommandHandler("audio", cmd_audio))
    app.add_handler(CommandHandler("download", handle_url))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    logger.info("Starting Telegram bot…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
