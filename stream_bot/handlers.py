"""Telegram handlers. Receiving media stores it and replies with stream links."""
import logging

from pyrogram import filters
from pyrogram.errors import FloodWait

from . import config
from .client import app
from .media import get_media, url_safe_name

log = logging.getLogger("handlers")

_MEDIA_FILTER = (
    filters.document | filters.video | filters.audio
    | filters.voice | filters.animation
)


@app.on_message(group=1)
async def _debug_log_all(_client, message):
    chat = message.chat.id if message.chat else None
    log.info("UPDATE received: chat=%s from=%s media=%s text=%r",
             chat,
             message.from_user.id if message.from_user else None,
             message.media, (message.text or "")[:40])


@app.on_message(filters.command("start") & filters.private)
async def start(_client, message):
    log.info("start handler fired")
    await message.reply_text(
        "Send me a video, movie or any media file and I'll give you an instant "
        "streamable link you can paste into VLC or MX Player."
    )


@app.on_message(filters.private & _MEDIA_FILTER)
async def on_media(client, message):
    log.info("media handler fired")
    media = get_media(message)
    if media is None:
        return

    try:
        stored = await message.copy(config.STORAGE_CHANNEL_ID)
    except FloodWait as e:
        await __import__("asyncio").sleep(e.value)
        stored = await message.copy(config.STORAGE_CHANNEL_ID)
    except Exception as e:  # noqa: BLE001
        log.exception("failed to store media")
        await message.reply_text(
            "Couldn't store the file. Make sure the bot is an admin in the "
            f"storage channel.\n`{e}`",
            quote=True,
        )
        return

    name = getattr(media, "file_name", None) or f"{stored.id}"
    direct = f"{config.PUBLIC_BASE_URL}/stream/{stored.id}/{url_safe_name(name)}"
    watch = f"{config.PUBLIC_BASE_URL}/watch/{stored.id}"
    size = getattr(media, "file_size", 0) or 0

    await message.reply_text(
        f"**{name}**\n"
        f"`{_human(size)}`\n\n"
        f"**Stream / download:**\n{direct}\n\n"
        f"**Watch in browser:**\n{watch}",
        quote=True,
        disable_web_page_preview=True,
    )


def _human(num: int) -> str:
    step = 1024.0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < step:
            return f"{num:.1f} {unit}"
        num /= step
    return f"{num:.1f} PB"
