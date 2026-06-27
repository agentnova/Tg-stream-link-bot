"""Single shared Pyrogram client with a persistent on-disk session.

The session file lives in config.SESSION_DIR, which is a mounted volume, so the
bot reuses its existing login across restarts instead of re-authenticating every
time (which previously triggered Telegram FloodWaits during rapid restarts).
"""
from pyrogram import Client

from . import patches  # noqa: F401  (patches Pyrogram before any peer resolution)
from . import config

app = Client(
    name=config.SESSION_NAME,
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    workers=config.WORKERS,
    workdir=config.SESSION_DIR,
    sleep_threshold=60,
)
