import asyncio
import re
from typing import Any
from urllib.parse import urljoin

import requests

from app.services.media_info import (
    MediaInfoError,
    extract_media_info,
)


VIDEO_EXTENSIONS = {
    ".mp4",
    ".webm",
    ".mov",
    ".m4v",
    ".avi",
    ".mkv",
}


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36"
)


def _extension(url: str) -> str:
    """Get video extension from URL."""

    clean_url = url.split(
        "?",
        1,
    )[0].lower()

    for extension in VIDEO_EXTENSIONS:
        if clean_url.endswith(extension):
            return extension

    return ""


def _find_streams_in_html(
    html: str,
    page_url: str,
) -> list[dict[str, Any]]:
    """Find public video streams exposed in HTML."""

    results = []

    # HLS .m3u8
    hls_matches = re.findall(
        r"""["']([^"']+\.m3u8(?:\?[^"']*)?)["']""",
        html,
        flags=re.IGNORECASE,
    )

    for value in hls_matches:
        results.append(
            {
                "type": "hls",
                "url": urljoin(
                    page_url,
                    value,
                ),
                "title": "HLS Stream",
                "qualities": [],
            }
        )

    # DASH .mpd
    dash_matches = re.findall(
        r"""["']([^"']+\.mpd(?:\?[^"']*)?)["']""",
        html,
        flags=re.IGNORECASE,
    )

    for value in dash_matches:
        results.append(
            {
                "type": "dash",
                "url": urljoin(
                    page_url,
                    value,
                ),
                "title": "DASH Stream",
                "qualities": [],
            }
        )

    # Direct video files
    video_matches = re.findall(
        r"""["']([^"']+\.(?:mp4|webm|mov|m4v)(?:\?[^"']*)?)["']""",
        html,
        flags=re.IGNORECASE,
    )

    for value in video_matches:
        results.append(
            {
                "type": "direct",
                "url": urljoin(
                    page_url,
                    value,
                ),
                "title": "Direct Video",
                "qualities": [],
            }
        )

    return results


def detect_media(
    url: str,
) -> dict[str, Any]:
    """Detect a publicly accessible media source."""

    # --------------------------------
    # 1. Try yt-dlp
    # --------------------------------

    try:
        media = extract_media_info(url)

        if media.get("formats"):
            return media

    except MediaInfoError:
        pass

    # --------------------------------
    # 2. Inspect URL / webpage
    # --------------------------------

    headers = {
        "User-Agent": USER_AGENT,
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            stream=True,
            timeout=20,
            allow_redirects=True,
        )

        final_url = response.url

        content_type = (
            response.headers
            .get(
                "content-type",
                "",
            )
            .lower()
        )

        # Direct video
        if (
            content_type.startswith("video/")
            or _extension(final_url)
            in VIDEO_EXTENSIONS
        ):
            response.close()

            return {
                "type": "direct",
                "url": final_url,
                "title": "Direct Video",
                "qualities": [],
            }

        # Direct HLS
        if (
            ".m3u8" in final_url.lower()
            or "mpegurl" in content_type
        ):
            response.close()

            return {
                "type": "hls",
                "url": final_url,
                "title": "HLS Stream",
                "qualities": [],
            }

        # Direct DASH
        if (
            ".mpd" in final_url.lower()
            or "dash+xml" in content_type
        ):
            response.close()

            return {
                "type": "dash",
                "url": final_url,
                "title": "DASH Stream",
                "qualities": [],
            }

        # HTML page
        if "text/html" in content_type:
            html = response.text
            response.close()

            candidates = _find_streams_in_html(
                html,
                final_url,
            )

            if candidates:
                # Prefer HLS.
                for candidate in candidates:
                    if candidate["type"] == "hls":
                        return candidate

                # Then DASH.
                for candidate in candidates:
                    if candidate["type"] == "dash":
                        return candidate

                return candidates[0]

        response.close()

    except requests.RequestException:
        pass

    raise MediaInfoError(
        "No publicly downloadable media source was found."
    )


async def detect_media_async(
    url: str,
) -> dict[str, Any]:
    """Run detection outside the asyncio event loop."""

    return await asyncio.to_thread(
        detect_media,
        url,
    )