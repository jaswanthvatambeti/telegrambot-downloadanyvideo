import asyncio
import subprocess
from pathlib import Path

import requests
import yt_dlp


class DownloadError(Exception):
    """Raised when downloading fails."""


def _download_direct(
    url: str,
    output_path: Path,
) -> Path:
    """Download a directly accessible video file."""

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/151.0.0.0 Safari/537.36"
        )
    }

    try:
        with requests.get(
            url,
            headers=headers,
            stream=True,
            timeout=30,
        ) as response:
            response.raise_for_status()

            with open(output_path, "wb") as file:
                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        file.write(chunk)

    except requests.RequestException as exc:
        raise DownloadError(
            "Direct video download failed."
        ) from exc

    return output_path


def _download_stream(
    url: str,
    output_path: Path,
) -> Path:
    """Download HLS or DASH stream using FFmpeg."""

    command = [
        "ffmpeg",
        "-y",
        "-i",
        url,
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    except FileNotFoundError as exc:
        raise DownloadError(
            "FFmpeg is not installed or is not available in PATH."
        ) from exc

    except subprocess.CalledProcessError as exc:
        raise DownloadError(
            "FFmpeg could not download the stream."
        ) from exc

    return output_path


def _download_ytdlp(
    url: str,
    quality: str,
    output_dir: Path,
) -> Path:
    """Download using yt-dlp."""

    output_template = str(
        output_dir / "%(title).80s_%(id)s.%(ext)s"
    )

    if quality == "audio":
        options = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": False,
            "no_warnings": False,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

    elif quality == "best":
        options = {
            "format": (
                "bestvideo+bestaudio/"
                "best"
            ),
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": False,
            "no_warnings": False,
        }

    else:
        try:
            height = int(quality)
        except ValueError as exc:
            raise DownloadError(
                "Invalid video quality."
            ) from exc

        options = {
            "format": (
                f"bestvideo[height<={height}]"
                f"+bestaudio/"
                f"best[height<={height}]"
            ),
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": False,
            "no_warnings": False,
        }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])

    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(
            str(exc)
        ) from exc

    files = [
        file
        for file in output_dir.iterdir()
        if file.is_file()
    ]

    if not files:
        raise DownloadError(
            "yt-dlp finished but no file was found."
        )

    files.sort(
        key=lambda file: file.stat().st_mtime,
        reverse=True,
    )

    return files[0]


def download_media(
    media: dict,
    quality: str,
    output_dir: Path,
) -> Path:
    """Download media using the detected strategy."""

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    media_type = media.get("type")
    url = media.get("url")

    if not url:
        raise DownloadError(
            "Media URL is missing."
        )

    # yt-dlp
    if media_type == "ytdlp":
        return _download_ytdlp(
            url=url,
            quality=quality,
            output_dir=output_dir,
        )

    # Direct video
    if media_type == "direct":
        output_path = (
            output_dir / "video.mp4"
        )

        return _download_direct(
            url=url,
            output_path=output_path,
        )

    # HLS
    if media_type == "hls":
        output_path = (
            output_dir / "video.mp4"
        )

        return _download_stream(
            url=url,
            output_path=output_path,
        )

    # DASH
    if media_type == "dash":
        output_path = (
            output_dir / "video.mp4"
        )

        return _download_stream(
            url=url,
            output_path=output_path,
        )

    raise DownloadError(
        f"Unsupported media type: {media_type}"
    )


async def download_media_async(
    media: dict,
    quality: str,
    output_dir: Path,
) -> Path:
    """Run downloading outside the asyncio event loop."""

    return await asyncio.to_thread(
        download_media,
        media,
        quality,
        output_dir,
    )