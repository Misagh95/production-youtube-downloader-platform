# API Reference

Base URL: `http://localhost:8000`

Authentication: Include `X-API-Key` header with requests (if configured).

---

## Health Check

```
GET /health
```

Returns system health and dependency status.

**Response:**
```json
{
  "ok": true,
  "yt_dlp": true,
  "ffmpeg": true,
  "version": "1.0.0"
}
```

---

## Analyze URL

```
POST /api/v1/analyze
```

Analyze a YouTube URL and return metadata with available formats.

**Request Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

**Response:**
```json
{
  "video": {
    "id": "dQw4w9WgXcQ",
    "title": "Rick Astley - Never Gonna Give You Up",
    "duration": 213,
    "duration_human": "3:33",
    "thumbnail": "https://i.ytimg.com/vi/...",
    "uploader": "Rick Astley",
    "view_count": 1400000000
  },
  "video_options": [
    {
      "format_id": "137",
      "ext": "mp4",
      "resolution": "1080p",
      "height": 1080,
      "fps": 30,
      "vcodec": "avc1",
      "acodec": "merged",
      "filesize": 105000000,
      "filesize_human": "~100.1 MB",
      "is_video": true,
      "is_audio": true,
      "label": "1080p | 30fps | avc1 | merged | mp4 | ~100.1 MB"
    }
  ],
  "audio_options": [
    {
      "format_id": "251",
      "ext": "webm",
      "resolution": "",
      "height": null,
      "fps": null,
      "vcodec": "",
      "acodec": "opus",
      "filesize": 6000000,
      "filesize_human": "~5.7 MB",
      "is_video": false,
      "is_audio": true,
      "label": "opus | webm | ~5.7 MB"
    }
  ],
  "advanced_formats": [...]
}
```

**Errors:**

| Status | Condition |
|--------|-----------|
| 400 | Invalid YouTube URL |
| 403 | Geo-blocked video |
| 404 | Private or deleted video |
| 500 | Extraction failed |

---

## Download

```
POST /api/v1/download
```

Download a video or audio file.

**Request Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "quality": "1080p",
  "type": "video",
  "delivery": "link",
  "audio_format": "mp3"
}
```

**Parameters:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | required | YouTube URL |
| `quality` | string | null | Quality label: `best`, `2160p`, `1440p`, `1080p`, `720p`, `480p`, `360p`, `worst` |
| `format_id` | string | null | Exact yt-dlp format ID (overrides quality) |
| `type` | string | `video` | `video` or `audio` |
| `delivery` | string | `direct` | `direct` (file stream) or `link` (expiring URL) |
| `audio_format` | string | `mp3` | `mp3`, `m4a`, or `opus` (audio-only mode) |

**Direct download response:** Returns the file as an attachment.

**Link mode response:**
```json
{
  "job_id": "job_abc123def456",
  "state": "ready",
  "download_url": "http://localhost:8000/api/v1/files/TOKEN_HERE",
  "filename": "Rick Astley - Never Gonna Give You Up.mp4",
  "expires_at": "2024-01-15T10:30:00",
  "message": "Your download link is ready."
}
```

---

## Job Status

```
GET /api/v1/jobs/{job_id}
```

Check the status of a download job.

**Response:**
```json
{
  "job_id": "job_abc123def456",
  "state": "downloading",
  "url": "https://www.youtube.com/watch?v=...",
  "quality": "1080p",
  "type": "video",
  "progress": 0.65,
  "download_url": null,
  "filename": null,
  "expires_at": null,
  "error": null,
  "title": "Video Title"
}
```

---

## Download by Token

```
GET /api/v1/files/{token}
```

Download a file using an expiring token (from link mode).

No authentication required for this endpoint.

**Errors:**

| Status | Condition |
|--------|-----------|
| 404 | Token expired, invalid, or file removed |

---

## Revoke Download Link

```
DELETE /api/v1/files/{token}
```

Revoke a download token and delete the associated file. Requires API key.

**Response:**
```json
{
  "message": "Link revoked"
}
```

---

## Example curl Commands

```bash
# Analyze
curl -X POST "$BASE/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'

# Download video as link (1080p)
curl -X POST "$BASE/api/v1/download" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","quality":"1080p","type":"video","delivery":"link"}'

# Download audio direct (MP3)
curl -X POST "$BASE/api/v1/download" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","type":"audio","audio_format":"mp3","delivery":"direct"}' \
  --output song.mp3

# Check job status
curl "$BASE/api/v1/jobs/job_abc123" \
  -H "X-API-Key: $API_KEY"

# Download by token
curl "$BASE/api/v1/files/TOKEN_HERE" --output video.mp4
```
