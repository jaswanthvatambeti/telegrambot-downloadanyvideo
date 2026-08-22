import asyncio
from typing import Any

import yt_dlp


class MediaInfoError(Exception):
    """Raised when yt-dlp cannot extract media."""


def extract_media_info(
    url: str,
) -> dict[str, Any]:
    """Try extracting media information with yt-dlp."""

    options = {
        "quiet": False,
        "no_warnings": False,
        "skip_download": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:

            info = ydl.extract_info(
                url,
                download=False,
            )

            if not info:
                raise MediaInfoError(
                    "No media information returned."
                )

            formats = info.get(
                "formats"
            ) or []

            qualities = get_available_qualities(
                formats
            )

            return {
                "type": "ytdlp",
                "url": url,
                "title": (
                    info.get("title")
                    or "Video"
                ),
                "thumbnail": info.get(
                    "thumbnail"
                ),
                "duration": info.get(
                    "duration"
                ),
                "formats": formats,
                "qualities": qualities,
                "extractor": info.get(
                    "extractor_key"
                ),
            }

    except yt_dlp.utils.DownloadError as exc:

        raise MediaInfoError(
            str(exc)
        ) from exc


def get_available_qualities(
    formats: list[dict[str, Any]],
) -> list[int]:
    """Return video resolutions found by yt-dlp."""

    qualities = set()

    for fmt in formats:

        height = fmt.get(
            "height"
        )

        vcodec = fmt.get(
            "vcodec"
        )

        if (
            isinstance(height, int)
            and height > 0
            and vcodec
            and vcodec != "none"
        ):
            qualities.add(height)

    return sorted(
        qualities,
        reverse=True,
    )


async def extract_media_info_async(
    url: str,
) -> dict[str, Any]:
    """Run yt-dlp outside the event loop."""

    return await asyncio.to_thread(
        extract_media_info,
        url,
    )