from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)


def quality_keyboard(
    qualities: list[int],
    media_type: str,
) -> InlineKeyboardMarkup:
    """Build quality keyboard."""

    rows = []

    if media_type == "ytdlp":

        buttons = [
            InlineKeyboardButton(
                f"{quality}p",
                callback_data=(
                    f"quality:{quality}"
                ),
            )
            for quality in qualities
        ]

        for index in range(
            0,
            len(buttons),
            2,
        ):

            rows.append(
                buttons[
                    index:index + 2
                ]
            )

        rows.append(
            [
                InlineKeyboardButton(
                    "🏆 Best Quality",
                    callback_data=(
                        "quality:best"
                    ),
                )
            ]
        )

        rows.append(
            [
                InlineKeyboardButton(
                    "🎵 Audio",
                    callback_data=(
                        "quality:audio"
                    ),
                ),
            ]
        )

    else:

        rows.append(
            [
                InlineKeyboardButton(
                    "▶️ Download Video",
                    callback_data=(
                        "quality:best"
                    ),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data=(
                    "quality:cancel"
                ),
            )
        ]
    )

    return InlineKeyboardMarkup(
        rows
    )