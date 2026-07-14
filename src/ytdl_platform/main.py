"""Application entry point — run API server, Telegram bot, or cleanup worker."""

from __future__ import annotations

import asyncio
import logging
import sys

from ytdl_platform.config import get_settings
from ytdl_platform.utils import setup_logging

logger = logging.getLogger(__name__)


def run_api() -> None:
    """Start the FastAPI server."""
    import uvicorn
    from ytdl_platform.api.app import create_app

    settings = get_settings()
    app = create_app()
    uvicorn.run(
        app,
        host=settings.app_host,
        port=settings.app_port,
        log_level=settings.log_level.lower(),
    )


def run_bot() -> None:
    """Start the Telegram bot."""
    from ytdl_platform.bot.app import run_bot as _run_bot
    _run_bot()


def run_cleanup() -> None:
    """Start the cleanup worker (runs indefinitely)."""
    from ytdl_platform.services.storage import get_storage

    settings = get_settings()
    storage = get_storage()

    logger.info(
        "Cleanup worker started (interval: %d minutes)",
        settings.cleanup_interval_minutes,
    )

    async def _loop():
        while True:
            try:
                count = storage.cleanup_expired()
                if count:
                    logger.info("Cleaned up %d expired files", count)
            except Exception:
                logger.exception("Cleanup error")
            await asyncio.sleep(settings.cleanup_interval_minutes * 60)

    asyncio.run(_loop())


def main() -> None:
    """Main entry point — dispatch based on argument."""
    setup_logging()

    command = sys.argv[1] if len(sys.argv) > 1 else "api"

    if command == "api":
        run_api()
    elif command == "bot":
        run_bot()
    elif command == "cleanup":
        run_cleanup()
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print("Usage: python -m ytdl_platform [api|bot|cleanup]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
