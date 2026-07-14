"""Telegram bot message templates and keyboard builders."""

from __future__ import annotations

from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from ytdl_platform.domain.models import AudioFormat, DeliveryMode, FormatOption, VideoInfo


# ── Message templates ──

MSG_START = (
    "🎬 *YouTube Downloader Bot*\n\n"
    "Send me a YouTube link and I'll help you download it!\n\n"
    "Commands:\n"
    "/download \\<url\\> — Download a video\n"
    "/audio \\<url\\> — Quick audio\\-only download\n"
    "/formats \\<url\\> — Show available qualities\n"
    "/settings — View your preferences\n"
    "/help — Usage guide\n"
    "/cancel — Cancel current job\n"
)

MSG_HELP = (
    "📖 *How to use this bot*\n\n"
    "1\\. Send or paste a YouTube URL\n"
    "2\\. I'll analyze it and show quality options\n"
    "3\\. Pick your preferred quality\n"
    "4\\. Choose delivery: Direct file or Download link\n"
    "5\\. Receive your file\\!\n\n"
    "⚡ *Quick commands*\n"
    "/audio \\<url\\> — Skip quality picker, get best audio as MP3\n"
    "/formats \\<url\\> — See all available formats\n\n"
    "📌 *Notes*\n"
    "• Large files will be sent as download links\n"
    "• Links expire after 30 minutes\n"
    "• Only YouTube links are supported\n"
)

MSG_INVALID_URL = "❌ Invalid YouTube URL. Please send a valid YouTube link."

MSG_ANALYZING = "🔍 Analyzing link…"

MSG_VIDEO_INFO = (
    "📹 *{title}*\n"
    "Duration: {duration}\n"
    "Views: {views}\n\n"
    "Choose video quality:"
)

MSG_AUDIO_OPTIONS = "🎵 Choose audio quality:"

MSG_DELIVERY = "📦 Choose delivery method:"

MSG_DOWNLOADING = "⬇️ Downloading…"

MSG_PROCESSING = "🔄 Processing…"

MSG_MERGING = "🔗 Merging audio and video…"

MSG_UPLOADING = "📤 Uploading…"

MSG_READY_DIRECT = "✅ Your file is ready\\!"

MSG_READY_LINK = (
    "✅ File ready\\!\n\n"
    "🔗 [Download link]({url})\n"
    "⏰ Expires in {expiry} minutes\n"
    "📄 {filename}"
)

MSG_TOO_LARGE = (
    "⚠️ File is too large for Telegram direct send \\({size:.0f} MB\\)\\.\n\n"
    "🔗 [Download link]({url})\n"
    "⏰ Expires in {expiry} minutes"
)

MSG_ERROR = "❌ {error}"

MSG_CANCELLED = "🚫 Operation cancelled."

MSG_NO_JOB = "No active job to cancel."

MSG_SETTINGS = (
    "⚙️ *Your Settings*\n\n"
    "Default video quality: {video_quality}\n"
    "Default audio format: {audio_format}\n"
    "Delivery preference: {delivery}\n"
)

MSG_STATUS = "📊 Job status: {state} ({progress:.0%})"

MSG_PRIVATE_VIDEO = "🔒 Cannot access this video — it may be private or require login."
MSG_GEO_BLOCKED = "🌍 Not available in this region (geo-blocked)."
VIDEO_UNAVAILABLE = "📹 Video unavailable — it may have been removed or made private."
MSG_SIZE_LIMIT = "📏 File exceeds size limit. Try a lower quality or use link mode."
MSG_TIMEOUT = "⏱️ Processing timed out. Please try again."
MSG_RATE_LIMIT = "🚫 Too many requests. Please wait and try again."
MSG_SERVER_ERROR = "⚠️ An unexpected error occurred. Please try again later."


# ── Keyboards ──

def video_quality_keyboard(
    video_formats: list[FormatOption],
    url_id: str,
) -> InlineKeyboardMarkup:
    """Build inline keyboard with video quality options."""
    buttons = []
    for f in video_formats[:8]:  # Limit to 8 options
        label = f.label or f"{f.height or '?'}p"
        if f.filesize or f.filesize_approx:
            label += f" ~{f.filesize_human}"
        buttons.append([
            InlineKeyboardButton(
                label,
                callback_data=f"vq:{f.format_id}:{url_id}",
            )
        ])
    return InlineKeyboardMarkup(buttons)


def audio_quality_keyboard(
    audio_formats: list[FormatOption],
    url_id: str,
) -> InlineKeyboardMarkup:
    """Build inline keyboard with audio quality options."""
    buttons = []
    for f in audio_formats[:6]:
        label = f.label or f"Audio {f.ext}"
        if f.filesize or f.filesize_approx:
            label += f" ~{f.filesize_human}"
        buttons.append([
            InlineKeyboardButton(
                label,
                callback_data=f"aq:{f.format_id}:{url_id}",
            )
        ])
    return InlineKeyboardMarkup(buttons)


def media_type_keyboard(url_id: str) -> InlineKeyboardMarkup:
    """Build inline keyboard to choose video or audio."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Video", callback_data=f"mt:video:{url_id}")],
        [InlineKeyboardButton("🎵 Audio only", callback_data=f"mt:audio:{url_id}")],
    ])


def delivery_keyboard(url_id: str) -> InlineKeyboardMarkup:
    """Build inline keyboard for delivery mode selection."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📎 Direct file", callback_data=f"dm:direct:{url_id}")],
        [InlineKeyboardButton("🔗 Download link", callback_data=f"dm:link:{url_id}")],
    ])


def audio_format_keyboard(url_id: str) -> InlineKeyboardMarkup:
    """Build inline keyboard for audio format selection."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("MP3", callback_data=f"af:mp3:{url_id}"),
            InlineKeyboardButton("M4A", callback_data=f"af:m4a:{url_id}"),
            InlineKeyboardButton("OPUS", callback_data=f"af:opus:{url_id}"),
        ],
    ])
