from urllib.parse import urlparse


def is_valid_url(
    value: str,
) -> bool:
    """Validate an HTTP/HTTPS URL."""

    if not value:
        return False

    value = value.strip()

    try:
        parsed = urlparse(value)

        return (
            parsed.scheme in {"http", "https"}
            and bool(parsed.netloc)
        )

    except ValueError:
        return False