
from telegram import Update
from telegram.ext import ContextTypes

from app.config import settings
from app.keyboards.inline import quality_keyboard
from app.services.downloader import (
    DownloadError,
    download_media_async,
    get_video_metadata_async,
    generate_video_thumbnail_async,
)
from app.services.media_detector import (
    detect_media_async,
)
from app.services.media_info import (
    MediaInfoError,
)
from app.utils.validators import (
    is_valid_url,
)


async def handle_url(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Detect a video URL and display download options."""

    if not update.message or not update.message.text:
        return

    url = update.message.text.strip()

    if not is_valid_url(url):
        await update.message.reply_text(
            "❌ Invalid URL.\n\n"
            "Please send a valid HTTP/HTTPS URL."
        )
        return

    message = await update.message.reply_text(
        "🔍 Detecting video..."
    )

    try:
        media = await detect_media_async(url)

    except MediaInfoError as exc:
        print("MEDIA DETECTION ERROR:", str(exc))

        await message.edit_text(
            "❌ Unable to find a downloadable public video source.\n\n"
            "The website may be unsupported, private, protected, "
            "or require authentication."
        )
        return

    media_type = media.get("type")
    title = media.get("title", "Video")
    qualities = media.get("qualities", [])

    # Store detected media for the quality callback.
    context.user_data["media"] = media

    # YT-DLP SOURCES
    if media_type == "ytdlp":

        if qualities:
            quality_text = ", ".join(
                f"{quality}p" for quality in qualities
            )

            await message.edit_text(
                f"🎬 {title}\n\n"
                f"Available qualities:\n{quality_text}\n\n"
                "Choose a quality:",
                reply_markup=quality_keyboard(
                    qualities,
                    media_type,
                ),
            )

        else:
            await message.edit_text(
                f"🎬 {title}\n\n"
                "⚠️ Specific video qualities could not be detected.\n\n"
                "You can try the best available format:",
                reply_markup=quality_keyboard(
                    [],
                    media_type,
                ),
            )

        return

    # DIRECT / HLS / DASH SOURCES
    if media_type in {"direct", "hls", "dash"}:
        await message.edit_text(
            f"🎬 {title}\n\n"
            f"Detected source: {media_type.upper()}\n\n"
            "Choose Download to continue.",
            reply_markup=quality_keyboard(
                [],
                media_type,
            ),
        )
        return

    await message.edit_text(
        "❌ Unsupported media source."
    )


async def quality_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Download the selected video and send it to Telegram."""

    query = update.callback_query

    if not query:
        return

    await query.answer()

    data = query.data

    if not data or not data.startswith("quality:"):
        return

    selection = data.split(":", 1)[1]

    # CANCEL DOWNLOAD
    if selection == "cancel":
        context.user_data.pop("media", None)

        await query.edit_message_text(
            "❌ Download cancelled."
        )
        return

    # GET STORED MEDIA
    media = context.user_data.get("media")

    if not media:
        await query.edit_message_text(
            "❌ Download session expired.\n\n"
            "Please send the URL again."
        )
        return

    media_type = media.get("type")

    print("\n========== DOWNLOAD ==========")
    print("Media type:", media_type)
    print("URL:", media.get("url"))
    print("Quality:", selection)
    print("==============================\n")

    await query.edit_message_text(
        "⏳ Downloading video...\n\nPlease wait."
    )

    if not update.effective_user:
        return

    user_id = update.effective_user.id

    output_dir = settings.DOWNLOAD_DIR / str(user_id)

    try:
        file_path = await download_media_async(
            media=media,
            quality=selection,
            output_dir=output_dir,
        )

    except DownloadError as exc:
        print("DOWNLOAD ERROR:", str(exc))

        await query.edit_message_text(
            "❌ Download failed.\n\n"
            f"{str(exc)[:500]}"
        )
        return

    except Exception as exc:
        print("UNEXPECTED DOWNLOAD ERROR:", repr(exc))

        await query.edit_message_text(
            "❌ Unexpected download error.\n\n"
            f"{str(exc)[:500]}"
        )
        return

    # VERIFY DOWNLOADED FILE
    if not file_path.exists():
        await query.edit_message_text(
            "❌ Download finished, but the file could not be found."
        )
        return

    file_size = file_path.stat().st_size

    if file_size == 0:
        await query.edit_message_text(
            "❌ Downloaded file is empty."
        )
        return

    print("Downloaded file:", file_path)
    print(f"File size: {file_size / (1024 * 1024):.2f} MB")

    context.user_data["downloaded_file"] = str(file_path)

    # EXTRACT VIDEO METADATA AND GENERATE THUMBNAIL
    await query.edit_message_text(
        "🖼️ Preparing video thumbnail..."
    )

    duration = None
    width = None
    height = None
    thumbnail_path = None

    try:
        metadata = await get_video_metadata_async(file_path)

        duration_value = metadata.get("duration")
        width_value = metadata.get("width")
        height_value = metadata.get("height")

        if duration_value is not None:
            duration = int(float(duration_value))

        if width_value is not None:
            width = int(width_value)

        if height_value is not None:
            height = int(height_value)

    except Exception as exc:
        print("VIDEO METADATA ERROR:", repr(exc))

    try:
        thumbnail_path = await generate_video_thumbnail_async(
            file_path,
            output_dir,
        )

    except Exception as exc:
        print("THUMBNAIL GENERATION ERROR:", repr(exc))

    # UPLOAD VIDEO TO TELEGRAM
    await query.edit_message_text(
        "📤 Uploading video to Telegram..."
    )

    try:
        with open(file_path, "rb") as video:

            if thumbnail_path and thumbnail_path.exists():
                with open(thumbnail_path, "rb") as thumbnail:
                    await query.message.reply_video(
                        video=video,
                        duration=duration,
                        width=width,
                        height=height,
                        thumbnail=thumbnail,
                        supports_streaming=True,
                        read_timeout=300,
                        write_timeout=300,
                        connect_timeout=60,
                        pool_timeout=60,
                    )

            else:
                await query.message.reply_video(
                    video=video,
                    duration=duration,
                    width=width,
                    height=height,
                    supports_streaming=True,
                    read_timeout=300,
                    write_timeout=300,
                    connect_timeout=60,
                    pool_timeout=60,
                )

    except Exception as exc:
        print("TELEGRAM UPLOAD ERROR:", repr(exc))

        await query.edit_message_text(
            "⚠️ Download completed, but Telegram upload failed."
        )
        return

    await query.edit_message_text(
        "✅ Video downloaded and sent!"
    )
