
import asyncio
import json
import subprocess
from pathlib import Path

import requests
import yt_dlp


class DownloadError(Exception):
    """Raised when downloading fails."""


def get_video_metadata(video_path: Path) -> dict:
    """Extract video duration and dimensions using ffprobe."""

    command = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries",
        "format=duration:stream=width,height",
        "-of", "json",
        str(video_path),
    ]

    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

        data = json.loads(result.stdout)
        streams = data.get("streams", [])

        duration = float(
            data.get("format", {}).get("duration", 0)
        )

        video_stream = streams[0] if streams else {}

        return {
            "duration": max(0, round(duration)),
            "width": video_stream.get("width"),
            "height": video_stream.get("height"),
        }

    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        print("FFPROBE ERROR:", repr(exc))

        return {
            "duration": 0,
            "width": None,
            "height": None,
        }


def generate_video_thumbnail(
    video_path: Path,
) -> Path | None:
    """Generate a JPEG thumbnail using FFmpeg."""

    thumbnail_path = video_path.with_name(
        f"{video_path.stem}_thumb.jpg"
    )

    command = [
        "ffmpeg",
        "-y",
        "-i", str(video_path),
        "-ss", "1",
        "-frames:v", "1",
        "-vf", "scale=320:-2",
        "-q:v", "4",
        str(thumbnail_path),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            timeout=30,
        )

        if (
            thumbnail_path.exists()
            and thumbnail_path.stat().st_size > 0
        ):
            return thumbnail_path

    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ) as exc:
        print("FFMPEG THUMBNAIL ERROR:", repr(exc))

    thumbnail_path.unlink(missing_ok=True)
    return None


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
            timeout=(30, 120),
        ) as response:
            response.raise_for_status()

            with output_path.open("wb") as file:
                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        file.write(chunk)

    except requests.RequestException as exc:
        output_path.unlink(missing_ok=True)

        raise DownloadError(
            "Direct video download failed."
        ) from exc

    return output_path


def _download_stream(
    url: str,
    output_path: Path,
) -> Path:
    """Download an HLS or DASH stream using FFmpeg."""

    command = [
        "ffmpeg",
        "-y",
        "-i", url,
        "-c", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=1800,
        )

    except FileNotFoundError as exc:
        raise DownloadError(
            "FFmpeg is not installed or is not available in PATH."
        ) from exc

    except subprocess.TimeoutExpired as exc:
        output_path.unlink(missing_ok=True)

        raise DownloadError(
            "Stream download timed out."
        ) from exc

    except subprocess.CalledProcessError as exc:
        output_path.unlink(missing_ok=True)

        error = exc.stderr or b""
        if isinstance(error, bytes):
            error = error.decode("utf-8", errors="replace")

        raise DownloadError(
            "FFmpeg could not download the stream. "
            f"{error[-300:]}"
        ) from exc

    return output_path


def _download_ytdlp(
    url: str,
    quality: str,
    output_dir: Path,
) -> Path:
    """Download media using yt-dlp."""

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
            "format": "bestvideo+bestaudio/best",
            "outtmpl": output_template,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": False,
            "no_warnings": False,
        }

    else:
        try:
            height = int(quality)
        except (ValueError, TypeError) as exc:
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
            info = ydl.extract_info(url, download=True)

            # Prefer the actual downloaded file path.
            requested = info.get("requested_downloads") or []
            candidates = [
                Path(item["filepath"])
                for item in requested
                if item.get("filepath")
            ]

            if info.get("_filename"):
                candidates.append(Path(info["_filename"]))

            for candidate in candidates:
                if candidate.exists() and candidate.is_file():
                    if candidate.suffix.lower() != ".part":
                        return candidate

            # Handle postprocessed/merged output.
            prepare = ydl.prepare_filename(info)
            prepared_path = Path(prepare)

            if prepared_path.exists():
                return prepared_path

            mp4_path = prepared_path.with_suffix(".mp4")
            if mp4_path.exists():
                return mp4_path

    except yt_dlp.utils.DownloadError as exc:
        raise DownloadError(str(exc)) from exc

    raise DownloadError(
        "yt-dlp finished but the downloaded file could not be found."
    )


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
        raise DownloadError("Media URL is missing.")

    if media_type == "ytdlp":
        return _download_ytdlp(
            url=url,
            quality=quality,
            output_dir=output_dir,
        )

    if media_type in {"direct", "hls", "dash"}:
        output_path = output_dir / "video.mp4"

        if media_type == "direct":
            return _download_direct(url, output_path)

        return _download_stream(url, output_path)

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


async def get_video_metadata_async(
    video_path: Path,
) -> dict:
    """Extract metadata without blocking the event loop."""

    return await asyncio.to_thread(
        get_video_metadata,
        video_path,
    )


async def generate_video_thumbnail_async(
    video_path: Path,
    output_dir: Path | None = None,
) -> Path | None:
    """Generate a thumbnail without blocking the event loop.

    output_dir is optional for compatibility with download.py.
    """

    if output_dir is not None:
        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    return await asyncio.to_thread(
        generate_video_thumbnail,
        video_path,
    )
