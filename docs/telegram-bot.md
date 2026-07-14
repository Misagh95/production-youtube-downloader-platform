# Telegram Bot Guide

## Setup

### 1. Create a Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token you receive

### 2. Configure

Add the token to your `.env` file:

```env
TELEGRAM_BOT_TOKEN=your-bot-token-here
```

Optional access control:

```env
# Comma-separated Telegram user IDs (admin has full access)
TELEGRAM_ADMIN_IDS=123456789

# Restrict to specific users (leave empty to allow everyone)
TELEGRAM_ALLOWED_USER_IDS=123456789,987654321
```

To find your Telegram user ID, message [@userinfobot](https://t.me/userinfobot).

### 3. Run

```bash
python -m ytdl_platform.main bot
```

Or via Docker:

```bash
docker compose up bot
```

---

## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and quick help |
| `/help` | Detailed usage guide |
| `/download <url>` | Download a video (or just paste a URL) |
| `/audio <url>` | Quick audio-only download (MP3 by default) |
| `/formats <url>` | List all available formats and qualities |
| `/settings` | View your current preferences |
| `/cancel` | Cancel the current download job |

---

## User Flow

### Standard Download

1. User sends a YouTube URL (or uses `/download <url>`)
2. Bot validates the URL
3. Bot shows: **"🔍 Analyzing link…"**
4. Bot displays video info: title, duration, views
5. Bot shows inline keyboard to choose: **🎬 Video** or **🎵 Audio only**
6. User picks media type
7. Bot shows quality options as inline buttons
8. User picks quality
9. Bot shows delivery options: **📎 Direct file** or **🔗 Download link**
10. User picks delivery mode
11. Bot shows progress: **⬇️ Downloading…** → **🔄 Processing…**
12. Bot delivers the file or download link

### Quick Audio

1. User sends `/audio <url>`
2. Bot downloads best audio in the default format (MP3)
3. Bot sends the audio file or a download link if too large

### Format Listing

1. User sends `/formats <url>`
2. Bot analyzes and shows all available video and audio formats with details

---

## Handling Telegram Constraints

### File Size Limits

Telegram has strict file size limits for bots:
- **Documents:** 50 MB (default)
- **With self-hosted Bot API:** up to 2 GB

When a file exceeds the limit, the bot automatically:
1. Switches to link mode
2. Generates a time-limited download URL
3. Sends the link with expiry information

Configure the threshold:

```env
TELEGRAM_MAX_DIRECT_FILE_MB=49
```

### Rate Limiting

The bot implements:
- Per-user rate limiting
- Concurrent download queue
- Flood control compliance with Telegram API limits

### Timeouts

Long downloads are handled with:
- Configurable timeouts
- Background processing
- Progress updates

---

## Example Interactions

### Sending a URL

```
User: https://www.youtube.com/watch?v=dQw4w9WgXcQ

Bot: 🔍 Analyzing link…

Bot: 📹 Rick Astley - Never Gonna Give You Up
     Duration: 3:33
     Views: 1,400,000,000

     Choose video quality:
     [1080p | 30fps | avc1 | mp4 | ~100 MB]
     [720p | 30fps | avc1 | mp4 | ~55 MB]
     [480p | 30fps | avc1 | mp4 | ~25 MB]
```

### Quick Audio

```
User: /audio https://www.youtube.com/watch?v=dQw4w9WgXcQ

Bot: ⬇️ Downloading audio…

Bot: ✅ Your file is ready!
     [sends audio file]
```

### Large File Fallback

```
Bot: ⚠️ File is too large for Telegram direct send (150.0 MB).

     🔗 Download link: http://your-server.com/api/v1/files/TOKEN
     ⏰ Expires in 30 minutes
```

---

## Webhook Mode (Advanced)

For production deployments, consider using webhook mode instead of polling. This requires:
- A public HTTPS URL
- SSL certificate

Webhook mode is not yet implemented but is on the roadmap.
