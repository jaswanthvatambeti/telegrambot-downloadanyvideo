import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


class Settings:
    """Application configuration."""

    BOT_TOKEN = os.getenv(
        "TELEGRAM_BOT_TOKEN",
        "",
    )

    DOWNLOAD_DIR = BASE_DIR / os.getenv(
        "DOWNLOAD_DIR",
        "downloads",
    )

    MAX_DOWNLOAD_SIZE_MB = int(
        os.getenv(
            "MAX_DOWNLOAD_SIZE_MB",
            "2000",
        )
    )


settings = Settings()


if not settings.BOT_TOKEN:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN is missing from .env"
    )


settings.DOWNLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)