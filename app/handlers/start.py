from telegram import Update
from telegram.ext import ContextTypes


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /start."""

    if not update.message:
        return

    await update.message.reply_text(
        "🎬 Video Downloader Bot\n\n"
        "Send me a public video URL.\n\n"
        "I will try:\n"
        "• yt-dlp\n"
        "• Direct video\n"
        "• HLS (.m3u8)\n"
        "• DASH (.mpd)\n\n"
        "Use /help for more information."
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /help."""

    if not update.message:
        return

    await update.message.reply_text(
        "📖 Help\n\n"
        "Send a public video URL.\n\n"
        "Supported sources depend on "
        "whether the website exposes a "
        "downloadable public media stream.\n\n"
        "DRM/private/protected media "
        "cannot be bypassed."
    )