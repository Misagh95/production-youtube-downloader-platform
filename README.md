# 🎬 YouTube Downloader Platform

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

A complete, production-ready YouTube media download platform. Analyze, select quality, and download YouTube videos and audio — via REST API, Telegram bot, or CLI.

> **⚠️ Legal Notice:** This tool is for personal/archival use only. Users are responsible for compliance with YouTube Terms of Service and local copyright laws. See [Legal Disclaimer](docs/legal-disclaimer.md).

---

## ✨ Features

- **🔗 URL Analysis** — Fetch metadata, thumbnail, and all available formats
- **🎬 Quality Selection** — Choose from video qualities (4K → 144p) and audio qualities (best → low)
- **📹 Video Download** — Merged MP4 (video+audio) for maximum player compatibility
- **🎵 Audio Extraction** — Extract audio to MP3, M4A, or OPUS
- **📎 Direct Download** — Stream file directly to user
- **🔗 Link Mode** — Generate time-limited, tokenized download URLs
- **🤖 Telegram Bot** — Full interactive bot with inline keyboards and auto-fallback
- **🖥️ CLI** — Colorized terminal tool for quick downloads
- **🌐 REST API** — FastAPI with OpenAPI docs, validation, and error handling
- **🐳 Docker** — One-command deployment with Docker Compose
- **🔒 Security** — Path traversal prevention, rate limiting, API key auth, allowlists
- **🧹 Auto-cleanup** — Expired file cleanup with configurable intervals

---

## 📸 Screenshots

*Screenshots placeholder — API docs, Telegram bot, CLI output, web UI*

---

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐
│   Web UI     │────▶│   REST API   │────▶│  yt-dlp +      │
│   (Next.js)  │     │   (FastAPI)  │     │  ffmpeg        │
└─────────────┘     └──────┬───────┘     └────────────────┘
                           │
                    ┌──────┴───────┐
                    │              │
              ┌─────▼─────┐ ┌────▼──────┐
              │  Storage   │ │  Job      │
              │  + Links   │ │  Store    │
              └───────────┘ └───────────┘
                           │
                    ┌──────┴───────┐
                    │              │
              ┌─────▼─────┐ ┌────▼──────┐
              │  Cleanup   │ │ Telegram  │
              │  Worker    │ │   Bot     │
              └───────────┘ └───────────┘
```

---

## 📋 Requirements

- **Python 3.11+**
- **ffmpeg** — for audio extraction and video merging
- **yt-dlp** — installed as Python dependency
- **Docker** (optional, for containerized deployment)

---

## 🚀 Quick Start (60 Seconds)

```bash
# Clone
git clone https://github.com/your-username/ytdl-platform.git
cd ytdl-platform

# Configure
cp .env.example .env

# Install
pip install -e ".[dev]"

# Run API
python -m ytdl_platform.main api

# In another terminal, test it:
curl http://localhost:8000/health
```

For Docker:

```bash
cp .env.example .env
docker compose up --build -d
curl http://localhost:8000/health
```

---

## 🎯 Quality Options

### Video Qualities

| Label | Resolution | Notes |
|-------|-----------|-------|
| `best` | Highest available | Default if not specified |
| `2160p` | 4K | If available |
| `1440p` | 2K | If available |
| `1080p` | Full HD | Most common |
| `720p` | HD | Good quality, smaller size |
| `480p` | SD | Moderate quality |
| `360p` | Low | Small size |
| `worst` | Lowest available | Smallest file |

### Audio Qualities

| Label | Bitrate | Notes |
|-------|---------|-------|
| `best` | Highest available | Default |
| `high` | ≥160 kbps | High quality |
| `medium` | 64-128 kbps | Medium quality |
| `low` | <64 kbps | Smallest size |

### Audio Formats

| Format | Codec | Extension |
|--------|-------|-----------|
| MP3 | libmp3lame | `.mp3` |
| M4A | AAC | `.m4a` |
| OPUS | libopus | `.opus` |

---

## 📎 Direct Download vs Link Mode

### Direct Download
- File is streamed directly in the HTTP response
- Best for: CLI, small files, one-time downloads
- API returns file attachment

### Link Mode
- File is saved and a time-limited URL is generated
- Best for: Large files, Telegram bot, sharing
- URL contains secure random token
- Configurable expiry (default: 30 minutes)
- Optional max download count
- Auto-cleanup of expired files

---

## 📡 API Usage

### Analyze a URL

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

### Download video (1080p, link mode)

```bash
curl -X POST http://localhost:8000/api/v1/download \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "quality": "1080p",
    "type": "video",
    "delivery": "link"
  }'
```

### Download audio (MP3, direct)

```bash
curl -X POST http://localhost:8000/api/v1/download \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-me" \
  -d '{
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "type": "audio",
    "audio_format": "mp3",
    "delivery": "direct"
  }' --output song.mp3
```

Full API docs: http://localhost:8000/docs (Swagger UI)

---

## 🤖 Telegram Bot Setup

1. Create a bot via [@BotFather](https://t.me/BotFather)
2. Add the token to `.env`:

```env
TELEGRAM_BOT_TOKEN=your-token-here
```

3. Run the bot:

```bash
python -m ytdl_platform.main bot
```

See [Telegram Bot Guide](docs/telegram-bot.md) for detailed instructions.

---

## 🖥️ CLI Usage

```bash
# Analyze a URL
ytdl-tool analyze "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# List formats
ytdl-tool formats "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Download video at 1080p
ytdl-tool download "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --quality 1080p --out ./downloads

# Download audio as MP3
ytdl-tool download "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --audio-only --audio-format mp3
```

---

## 🐳 Docker Deployment

```bash
# Configure
cp .env.example .env
# Edit .env with your settings

# Build and start all services
docker compose up --build -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

Services:
- **api** — FastAPI server on port 8000
- **bot** — Telegram bot
- **cleanup** — Background file cleanup worker

See [Deployment Guide](docs/deployment.md) for VPS, PaaS, and production setup.

---

## ⚙️ Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | YouTube Downloader Platform | Application name |
| `APP_ENV` | development | `development`, `staging`, or `production` |
| `APP_HOST` | 0.0.0.0 | API server bind address |
| `APP_PORT` | 8000 | API server port |
| `API_KEY` | change-me | API authentication key (set a secure value!) |
| `PUBLIC_BASE_URL` | http://localhost:8000 | Public URL for generating download links |
| `DOWNLOAD_DIR` | ./data/files | Directory for downloaded files |
| `MAX_CONCURRENT_JOBS` | 3 | Maximum simultaneous downloads |
| `MAX_FILESIZE_MB` | 512 | Maximum file size in MB |
| `MAX_DURATION_SECONDS` | 7200 | Maximum video duration (2 hours) |
| `LINK_EXPIRY_MINUTES` | 30 | Download link expiry time |
| `CLEANUP_INTERVAL_MINUTES` | 10 | How often to clean expired files |
| `TELEGRAM_BOT_TOKEN` | | Telegram bot token (required for bot) |
| `TELEGRAM_ADMIN_IDS` | | Comma-separated admin user IDs |
| `TELEGRAM_ALLOWED_USER_IDS` | | Comma-separated allowed user IDs |
| `TELEGRAM_MAX_DIRECT_FILE_MB` | 49 | Max file size for Telegram direct send |
| `DEFAULT_VIDEO_QUALITY` | 1080p | Default video quality |
| `DEFAULT_AUDIO_FORMAT` | mp3 | Default audio format |
| `ENABLE_PLAYLISTS` | false | Enable playlist downloads |
| `LOG_LEVEL` | INFO | Logging level |

---

## 📁 Project Structure

```
ytdl-platform/
├── README.md
├── LICENSE
├── .gitignore
├── .env.example
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── docs/
│   ├── setup.md
│   ├── api.md
│   ├── telegram-bot.md
│   ├── deployment.md
│   └── legal-disclaimer.md
├── src/ytdl_platform/
│   ├── __init__.py
│   ├── main.py                 # Entry point (api/bot/cleanup)
│   ├── config.py               # Settings via pydantic
│   ├── domain/
│   │   └── models.py           # Domain models + enums
│   ├── services/
│   │   ├── extractor.py        # yt-dlp wrapper
│   │   ├── downloader.py       # Download + merge/convert
│   │   ├── quality.py          # Quality selection logic
│   │   ├── storage.py          # Storage + link service + job store
│   │   └── progress.py         # Progress tracking
│   ├── api/
│   │   ├── app.py              # FastAPI app + routes
│   │   ├── schemas.py          # Request/response schemas
│   │   └── deps.py             # Dependencies + middleware
│   ├── bot/
│   │   ├── app.py              # Telegram bot + handlers
│   │   └── messages.py         # Bot messages + keyboards
│   ├── cli/
│   │   └── main.py             # CLI tool
│   └── utils/
│       └── __init__.py         # Validators, files, security, logging
├── tests/
│   ├── test_quality.py
│   ├── test_validators.py
│   ├── test_api.py
│   └── test_link_service.py
├── scripts/
│   ├── dev.sh
│   └── cleanup_cron.sh
└── web/                        # Next.js web frontend
    └── (served by Next.js app)
```

---

## 🔒 Security Notes

- **No hardcoded secrets** — all secrets via environment variables
- **API key authentication** — required for API endpoints (configurable)
- **Rate limiting** — in-memory per-IP rate limiting
- **Path traversal prevention** — all file paths are sanitized and validated
- **Tokenized download URLs** — high-entropy random tokens, not predictable
- **Time-limited links** — automatic expiry enforced on access
- **Concurrent job limits** — prevents resource exhaustion
- **File size and duration caps** — configurable limits
- **Optional allowlists** — restrict Telegram bot to specific users
- **Playlists disabled by default** — prevents mass downloading

---

## ⚠️ Limitations

- YouTube can change their API at any time, breaking yt-dlp extraction
- Some videos may be geo-blocked, age-restricted, or private
- Large file downloads may time out on some hosting platforms
- Telegram bot has a ~50 MB file size limit (configurable, auto-fallback to links)
- In-memory rate limiting doesn't persist across restarts
- Job store uses JSON files (not suitable for very high traffic)

---

## 🛡️ Legal / Terms of Use

**This tool is for personal/archival use and only for content the user has rights to download.**

- Users are responsible for compliance with YouTube Terms of Service and local copyright laws.
- The authors do not encourage copyright infringement.
- Do not use for piracy, redistribution of copyrighted content, or bypassing paid restrictions abusively.
- Respect rate limits and website terms.

See the full [Legal Disclaimer](docs/legal-disclaimer.md).

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add my feature'`
4. Push to the branch: `git push origin feature/my-feature`
5. Open a Pull Request

Please ensure:
- Code is well-documented and typed
- Tests pass: `make test`
- No hardcoded secrets
- Legal compliance is maintained

---

## 📜 License

[MIT License](LICENSE) — Copyright (c) 2024 YTDL Platform Contributors

---

## 🗺️ Roadmap

- [ ] Playlist support with confirmation dialog
- [ ] Subtitles download (SRT/VTT)
- [ ] Thumbnail download
- [ ] S3/MinIO storage backend
- [ ] Telegram webhook mode
- [ ] Prometheus metrics
- [ ] Multi-language bot UI (en/fa)
- [ ] Admin stats command
- [ ] SponsorBlock integration (optional)
- [ ] WebSocket progress updates
- [ ] SQLite → PostgreSQL for job store
- [ ] User preferences persistence
- [ ] Video preview/trimming
