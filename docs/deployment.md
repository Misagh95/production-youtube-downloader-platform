# Deployment Guide

## Docker Compose (Recommended)

The easiest way to deploy the full platform.

### 1. Configure

```bash
cp .env.example .env
# Edit .env — set API_KEY, TELEGRAM_BOT_TOKEN, PUBLIC_BASE_URL, etc.
```

### 2. Build and start

```bash
docker compose up --build -d
```

This starts:
- **api** service on port 8000
- **bot** service (Telegram bot)
- **cleanup** service (periodic file cleanup)

### 3. Verify

```bash
curl http://localhost:8000/health
```

### 4. View logs

```bash
docker compose logs -f api
docker compose logs -f bot
```

### 5. Stop

```bash
docker compose down
```

---

## VPS Deployment (Docker)

### Requirements

- Ubuntu 22.04+ or similar Linux
- Docker + Docker Compose
- At least 2 GB RAM
- Sufficient disk space for downloads

### Steps

1. **SSH into your server**

2. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/ytdl-platform.git
   cd ytdl-platform
   ```

3. **Configure environment**
   ```bash
   cp .env.example .env
   nano .env
   ```
   
   Important settings for production:
   ```env
   APP_ENV=production
   API_KEY=a-secure-random-string-here
   PUBLIC_BASE_URL=https://your-domain.com
   APP_PORT=8000
   MAX_FILESIZE_MB=512
   MAX_CONCURRENT_JOBS=3
   ```

4. **Set up reverse proxy (nginx)**
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_read_timeout 300s;
           client_max_body_size 600M;
       }
   }
   ```

5. **Enable HTTPS** (recommended with certbot)
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d your-domain.com
   ```

6. **Start services**
   ```bash
   docker compose up -d
   ```

### Auto-restart

Docker Compose services are configured with `restart: unless-stopped`.

---

## Railway / Render / Fly.io

These platforms work well for the API component. Notes:

1. **Build command:** Docker builds automatically from Dockerfile
2. **Start command:** `python -m ytdl_platform.main api`
3. **Environment:** Set all variables from `.env.example` in the platform dashboard
4. **Persistent storage:** Use a persistent volume mounted at `/app/data/files`
5. **Bot:** Run as a separate service/worker process

### Limitations on PaaS

- File size limits depend on available disk
- Some platforms have request timeout limits (e.g., 30s on free tiers)
- Use link mode for large files to avoid timeouts
- May need to increase worker timeout

---

## Local Machine (No Docker)

### Prerequisites

- Python 3.11+
- ffmpeg

### Install

```bash
pip install -e ".[dev]"
```

### Run API

```bash
python -m ytdl_platform.main api
```

### Run Bot (separate terminal)

```bash
python -m ytdl_platform.main bot
```

### Run Cleanup (separate terminal or cron)

```bash
python -m ytdl_platform.main cleanup
```

Or add to crontab:

```bash
*/10 * * * * /path/to/scripts/cleanup_cron.sh
```

---

## Scaling Considerations

### Concurrent Downloads

Set `MAX_CONCURRENT_JOBS` based on your server resources:
- 2 GB RAM: 2-3 concurrent jobs
- 4 GB RAM: 3-5 concurrent jobs
- 8 GB RAM: 5-10 concurrent jobs

### Disk Space

Monitor disk usage with the storage service. Implement a maximum storage limit and cleanup strategy.

### S3 Storage (Future)

For large-scale deployments, an S3-compatible storage backend is planned. This would allow:
- Unlimited storage
- CDN-backed download links
- Automatic lifecycle management

---

## Monitoring

### Health Endpoint

```bash
curl http://localhost:8000/health
```

Returns dependency status (yt-dlp, ffmpeg availability).

### Logs

All services log to stdout/stderr. Configure `LOG_LEVEL` in `.env`:
- `DEBUG` — verbose output
- `INFO` — standard operation
- `WARNING` — only warnings and errors
- `ERROR` — errors only

### Job Monitoring

Check active jobs via API:

```bash
curl http://localhost:8000/api/v1/jobs/job_id -H "X-API-Key: your-key"
```
