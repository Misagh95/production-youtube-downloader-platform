#!/usr/bin/env bash
set -euo pipefail

echo "🔧 Setting up YouTube Downloader Platform…"

# Create .env if missing
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ Created .env from .env.example — edit it with your settings"
fi

# Create data directories
mkdir -p data/files

# Install Python dependencies
pip install -e ".[dev]"

# Verify dependencies
echo "🔍 Checking system dependencies…"
python -c "
from ytdl_platform.services.extractor import check_dependencies
deps = check_dependencies()
for name, ok in deps.items():
    status = '✅' if ok else '❌'
    print(f'  {status} {name}')
if not all(deps.values()):
    print()
    print('⚠️  Some dependencies are missing.')
    print('   ffmpeg: apt install ffmpeg  or  brew install ffmpeg')
    print('   yt-dlp: pip install yt-dlp')
"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Run the API:      make run-api"
echo "Run the bot:      make run-bot"
echo "Run CLI:          ytdl-tool analyze <url>"
echo ""
