"""Small helpers for pulling media metadata out of a Pyrogram message."""
from dataclasses import dataclass
from urllib.parse import quote

from pyrogram.file_id import FileId

# Order matters: a video sent as a document should still resolve correctly.
_MEDIA_ATTRS = ("document", "video", "audio", "voice", "video_note", "animation", "photo")


@dataclass
class FileProps:
    file_id: FileId
    file_size: int
    file_name: str
    mime_type: str


def get_media(message):
    """Return the first media object found on a message, or None."""
    if not message:
        return None
    for attr in _MEDIA_ATTRS:
        media = getattr(message, attr, None)
        if media:
            return media
    return None


def _guess_extension(mime_type: str) -> str:
    table = {
        "video/mp4": ".mp4",
        "video/x-matroska": ".mkv",
        "video/webm": ".webm",
        "video/quicktime": ".mov",
        "video/x-msvideo": ".avi",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/ogg": ".ogg",
    }
    return table.get(mime_type, ".bin")


def build_props(message) -> FileProps:
    media = get_media(message)
    if media is None:
        raise FileNotFoundError("Message has no downloadable media")

    mime_type = getattr(media, "mime_type", None) or "application/octet-stream"
    file_name = getattr(media, "file_name", None)
    if not file_name:
        file_name = f"{message.id}{_guess_extension(mime_type)}"

    return FileProps(
        file_id=FileId.decode(media.file_id),
        file_size=getattr(media, "file_size", 0) or 0,
        file_name=file_name,
        mime_type=mime_type,
    )


def url_safe_name(name: str) -> str:
    """Filename suffix for the URL so players detect the container format."""
    return quote(name)
