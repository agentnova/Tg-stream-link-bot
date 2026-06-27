"""
On-demand chunked downloader.

This does NOT download the whole file. For each HTTP Range request it pulls
only the 1 MiB Telegram chunks that overlap the requested byte range, trims the
edges, and yields them straight to the response. That is what lets VLC / MX
Player start instantly and seek to any position.

The session-pool / auth-export logic is the standard pattern required to read a
file that lives on a different Telegram data center than the bot's own session.
"""
import asyncio
import logging
import math
import time

from pyrogram import Client, raw
from pyrogram.errors import AuthBytesInvalid, FloodWait
from pyrogram.file_id import FileType
from pyrogram.session import Auth, Session

from . import config
from .media import FileProps, build_props

log = logging.getLogger("streamer")


class ByteStreamer:
    def __init__(self, client: Client):
        self.client = client
        # message_id -> (FileProps, inserted_at)
        self._cache: dict[int, tuple[FileProps, float]] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ cache
    async def get_props(self, message_id: int) -> FileProps:
        cached = self._cache.get(message_id)
        if cached and (time.monotonic() - cached[1]) < config.CACHE_TTL:
            return cached[0]

        message = await self.client.get_messages(config.STORAGE_CHANNEL_ID, message_id)
        if not message or getattr(message, "empty", False):
            raise FileNotFoundError(f"No stored message with id {message_id}")

        props = build_props(message)
        self._cache[message_id] = (props, time.monotonic())
        return props

    def invalidate(self, message_id: int) -> None:
        self._cache.pop(message_id, None)

    # ------------------------------------------------------------ media session
    async def _media_session(self, file_id) -> Session:
        client = self.client
        dc_id = file_id.dc_id
        session = client.media_sessions.get(dc_id)
        if session is not None:
            return session

        async with self._lock:
            session = client.media_sessions.get(dc_id)
            if session is not None:
                return session

            test_mode = await client.storage.test_mode()
            if dc_id != await client.storage.dc_id():
                session = Session(
                    client, dc_id,
                    await Auth(client, dc_id, test_mode).create(),
                    test_mode, is_media=True,
                )
                await session.start()
                for _ in range(6):
                    exported = await client.invoke(
                        raw.functions.auth.ExportAuthorization(dc_id=dc_id)
                    )
                    try:
                        await session.invoke(
                            raw.functions.auth.ImportAuthorization(
                                id=exported.id, bytes=exported.bytes
                            )
                        )
                        break
                    except AuthBytesInvalid:
                        continue
                else:
                    await session.stop()
                    raise AuthBytesInvalid
            else:
                session = Session(
                    client, dc_id,
                    await client.storage.auth_key(),
                    test_mode, is_media=True,
                )
                await session.start()

            client.media_sessions[dc_id] = session
            return session

    def _location(self, file_id):
        ftype = file_id.file_type
        if ftype == FileType.PHOTO:
            return raw.types.InputPhotoFileLocation(
                id=file_id.media_id,
                access_hash=file_id.access_hash,
                file_reference=file_id.file_reference,
                thumb_size=file_id.thumbnail_size,
            )
        return raw.types.InputDocumentFileLocation(
            id=file_id.media_id,
            access_hash=file_id.access_hash,
            file_reference=file_id.file_reference,
            thumb_size=file_id.thumbnail_size,
        )

    # ----------------------------------------------------------------- yield
    async def _fetch(self, session, location, off, chunk_size):
        """Fetch one chunk at byte offset `off`, retrying past FloodWaits."""
        while True:
            try:
                return await session.invoke(
                    raw.functions.upload.GetFile(
                        location=location, offset=off, limit=chunk_size
                    )
                )
            except FloodWait as e:
                log.warning("FloodWait %ss while streaming", e.value)
                await asyncio.sleep(e.value)

    async def yield_file(
        self, file_id, offset, first_cut, last_cut, part_count, chunk_size
    ):
        """
        Stream the requested chunks with read-ahead.

        A producer task fetches up to PREFETCH_CHUNKS chunks ahead into a bounded
        queue while the consumer writes the current chunk to the player. The
        next chunk's Telegram fetch therefore overlaps the current chunk's
        network write, so the player rarely waits on a fetch. The bounded queue
        provides backpressure, so memory stays at ~PREFETCH_CHUNKS MiB per
        stream even for a whole-file request.
        """
        session = await self._media_session(file_id)
        location = self._location(file_id)
        queue: asyncio.Queue = asyncio.Queue(maxsize=config.PREFETCH_CHUNKS)

        async def producer():
            off = offset
            try:
                for _ in range(part_count):
                    r = await self._fetch(session, location, off, chunk_size)
                    if not isinstance(r, raw.types.upload.File) or not r.bytes:
                        await queue.put(None)
                        return
                    await queue.put(r.bytes)
                    off += chunk_size
                await queue.put(None)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001  (surface to consumer)
                await queue.put(e)

        prod = asyncio.create_task(producer())
        current = 1
        try:
            while current <= part_count:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, BaseException):
                    raise item
                chunk = item
                if part_count == 1:
                    yield chunk[first_cut:last_cut]
                elif current == 1:
                    yield chunk[first_cut:]
                elif current == part_count:
                    yield chunk[:last_cut]
                else:
                    yield chunk
                current += 1
        finally:
            # Stop reading ahead the moment the consumer stops (e.g. the player
            # seeks away or disconnects) so we don't waste Telegram bandwidth.
            prod.cancel()
            try:
                await prod
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass


def plan_range(from_bytes: int, until_bytes: int, chunk_size: int):
    """Translate an HTTP byte range into chunk-aligned download parameters."""
    offset = from_bytes - (from_bytes % chunk_size)
    first_cut = from_bytes - offset
    last_cut = (until_bytes % chunk_size) + 1
    part_count = math.ceil((until_bytes + 1) / chunk_size) - (offset // chunk_size)
    return offset, first_cut, last_cut, part_count
