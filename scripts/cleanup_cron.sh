#!/usr/bin/env bash
# Cron job for cleanup of expired download tokens and files
# Add to crontab: */10 * * * * /path/to/scripts/cleanup_cron.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Run cleanup via CLI
python -c "
from ytdl_platform.services.storage import get_storage
storage = get_storage()
count = storage.cleanup_expired()
if count:
    print(f'Cleaned up {count} expired files')
else:
    print('No expired files to clean up')
"
