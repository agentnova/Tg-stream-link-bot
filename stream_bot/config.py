"""Environment configuration for the stream bot."""
import os
import sys


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"[config] Missing required environment variable: {name}")
    return value


# --- Telegram credentials (https://my.telegram.org -> API development tools) ---
API_ID = int(_require("API_ID"))
API_HASH = _require("API_HASH")
BOT_TOKEN = _require("BOT_TOKEN")

# Private channel where incoming media is copied/stored.
# The bot MUST be an admin there. Format: -100xxxxxxxxxx
STORAGE_CHANNEL_ID = int(_require("STORAGE_CHANNEL_ID"))

# Public base URL served via Cloudflare Tunnel, e.g. https://stream.example.com
PUBLIC_BASE_URL = _require("PUBLIC_BASE_URL").rstrip("/")

# Web server bind settings (internal; Cloudflare Tunnel points here).
BIND_ADDRESS = os.environ.get("BIND_ADDRESS", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))

# Pyrogram in-memory session name and worker count.
SESSION_NAME = os.environ.get("SESSION_NAME", "stream_bot")
WORKERS = int(os.environ.get("WORKERS", "4"))

# Directory for the persistent .session file (mounted as a volume so the
# login survives container restarts).
SESSION_DIR = os.environ.get("SESSION_DIR", "/app/session")

# 1 MiB chunks — the maximum allowed by Telegram's upload.GetFile.
CHUNK_SIZE = 1024 * 1024
# How many chunks to fetch ahead of the player (read-ahead buffer). Each is
# up to 1 MiB, so this is roughly the per-stream memory ceiling.
PREFETCH_CHUNKS = int(os.environ.get("PREFETCH_CHUNKS", "3"))
# Seconds before the FileId metadata cache is flushed (file references age out).
CACHE_TTL = int(os.environ.get("CACHE_TTL", str(30 * 60)))
