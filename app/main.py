import logging

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import settings
from app.handlers.download import (
    handle_url,
    quality_callback,
)
from app.handlers.start import (
    help_command,
    start_command,
)


logging.basicConfig(
    format=(
        "%(asctime)s - "
        "%(name)s - "
        "%(levelname)s - "
        "%(message)s"
    ),
    level=logging.INFO,
)


logger = logging.getLogger(
    __name__
)


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Log unexpected errors."""

    logger.exception(
        "Unhandled exception",
        exc_info=context.error,
    )


def create_application() -> Application:
    """Create Telegram application."""

    application = (
        Application.builder()
        .token(settings.BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            quality_callback,
            pattern=r"^quality:",
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            handle_url,
        )
    )

    application.add_error_handler(
        error_handler
    )

    return application


def main() -> None:
    """Start bot."""

    application = (
        create_application()
    )

    logger.info(
        "Starting Telegram Video Downloader Bot..."
    )

    application.run_polling()


if __name__ == "__main__":
    main()