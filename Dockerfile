# ── Stage 1: builder ──
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir --prefix=/install .

# ── Stage 2: runtime ──
FROM python:3.12-slim

# Install ffmpeg and yt-dlp system binary as fallback
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        curl && \
    curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
         -o /usr/local/bin/yt-dlp && \
    chmod +x /usr/local/bin/yt-dlp && \
    apt-get purge -y curl && \
    rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root user
RUN groupadd -r app && useradd -r -g app -d /home/app -s /sbin/nologin app

# Create data directories
RUN mkdir -p /app/data/files /app/data/tmp && chown -R app:app /app

WORKDIR /app

# Copy source (for editable installs / reference)
COPY --chown=app:app . .

USER app

ENV PYTHONUNBUFFERED=1
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8000

EXPOSE 8000

CMD ["python", "-m", "ytdl_platform.main", "api"]
