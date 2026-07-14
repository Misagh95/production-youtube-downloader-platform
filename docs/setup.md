# Setup Guide

## Prerequisites

- **Python 3.11+** (3.12 recommended)
- **ffmpeg** — required for audio extraction and video merging
- **yt-dlp** — installed automatically as a Python dependency

### Installing ffmpeg

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/your-username/ytdl-platform.git
cd ytdl-platform
cp .env.example .env
# Edit .env with your settings
```

### 2. Install dependencies

```bash
pip install -e ".[dev]"
```

Or using the setup script:

```bash
bash scripts/dev.sh
```

### 3. Verify installation

```bash
python -c "from ytdl_platform.services.extractor import check_dependencies; print(check_dependencies())"
```

Should output: `{'yt_dlp': True, 'ffmpeg': True}`

### 4. Run the API server

```bash
make run-api
# or
python -m ytdl_platform.main api
```

The API will be available at http://localhost:8000 with auto-generated docs at http://localhost:8000/docs

### 5. Run the CLI

```bash
ytdl-tool analyze "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
ytdl-tool download "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --quality 1080p
ytdl-tool download "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --audio-only --audio-format mp3
```

### 6. Run the Telegram bot

Set `TELEGRAM_BOT_TOKEN` in `.env`, then:

```bash
make run-bot
# or
python -m ytdl_platform.main bot
```

See [telegram-bot.md](telegram-bot.md) for detailed bot setup.

## Configuration

All settings are configured via environment variables or the `.env` file. See `.env.example` for the full reference.

Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_PORT` | 8000 | API server port |
| `API_KEY` | change-me | API authentication key |
| `DOWNLOAD_DIR` | ./data/files | Download storage directory |
| `MAX_FILESIZE_MB` | 512 | Maximum download file size |
| `MAX_DURATION_SECONDS` | 7200 | Maximum video duration |
| `DEFAULT_VIDEO_QUALITY` | 1080p | Default quality for downloads |
| `DEFAULT_AUDIO_FORMAT` | mp3 | Default audio extraction format |
| `ENABLE_PLAYLISTS` | false | Enable playlist support |

## Docker Setup

See [deployment.md](deployment.md) for Docker and deployment instructions.
