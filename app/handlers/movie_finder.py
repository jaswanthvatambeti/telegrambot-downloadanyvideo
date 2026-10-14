
import logging
import os
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    TypeHandler,
)

from app.services.movie_catalog import (
    get_movie,
    save_movie,
    search_movies,
)

logger = logging.getLogger(__name__)


def get_authorized_channels():
    value = os.getenv("AUTHORIZED_CHANNEL_IDS", "")
    result = set()

    for item in value.split(","):
        item = item.strip()
        if item:
            try:
                result.add(int(item))
            except ValueError:
                logger.warning("Ignoring invalid channel ID")

    return result


def extract_media(message):
    if message.video:
        return message.video.file_id, message.video.file_name

    if message.document:
        return message.document.file_id, message.document.file_name

    return None, None


async def index_channel_post(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.channel_post

    if not message:
        return

    if message.chat.id not in get_authorized_channels():
        return

    file_id, filename = extract_media(message)

    if not file_id:
        return

    title = (message.caption or filename or "").strip()

    # Remove a file extension and make common separators searchable.
    title = re.sub(r"\.[a-zA-Z0-9]{2,5}$", "", title)
    title = re.sub(r"[_\.]+", " ", title).strip()

    if not title:
        title = f"Movie {message.message_id}"

    try:
        save_movie(
            title=title[:250],
            chat_id=message.chat.id,
            message_id=message.message_id,
            file_id=file_id,
        )
        logger.info("Indexed movie message %s", message.message_id)
    except Exception:
        logger.exception("Failed to index channel post")


async def search_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = " ".join(context.args).strip()

    if not query:
        await update.effective_message.reply_text(
            "Search for a movie like this:\n/search Interstellar"
        )
        return

    results = search_movies(query)

    if not results:
        await update.effective_message.reply_text(
            "No matching movies found in the indexed channel posts."
        )
        return

    buttons = []

    for movie in results:
        buttons.append([
            InlineKeyboardButton(
                movie["title"][:60],
                callback_data=f"movie:{movie['id']}",
            )
        ])

    await update.effective_message.reply_text(
        f"Found {len(results)} matching result(s). Select one:",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def send_movie(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    try:
        movie_id = int(query.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await query.message.reply_text("Invalid selection.")
        return

    movie = get_movie(movie_id)

    if not movie:
        await query.message.reply_text("Movie not found in the catalog.")
        return

    try:
        await context.bot.copy_message(
            chat_id=query.message.chat.id,
            from_chat_id=movie["source_chat_id"],
            message_id=movie["source_message_id"],
        )
    except Exception:
        logger.exception("Failed to copy movie message")
        await query.message.reply_text(
            "Unable to send this movie. Check the source channel "
            "permissions and whether the original message still exists."
        )


def register_movie_handlers(application):
    application.add_handler(
        CommandHandler("search", search_command)
    )

    application.add_handler(
        CallbackQueryHandler(
            send_movie,
            pattern=r"^movie:\d+$",
        )
    )

    # Index channel posts without interfering with existing handlers.
    application.add_handler(
        TypeHandler(Update, index_channel_post),
        group=1,
    )
