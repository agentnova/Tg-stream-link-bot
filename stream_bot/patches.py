"""Compatibility patch for Pyrogram 2.0.106.

Telegram now issues channel IDs whose raw part exceeds 2^31 (e.g. the marked
ID like -100xxxxxxxxxx with a large raw part). Pyrogram 2.0.106's utils.get_peer_type() uses an outdated
range check and raises "Peer id invalid" for them whenever the peer isn't
already in the session cache. We replace it with a prefix-based check that
handles the larger IDs. Importing this module applies the patch.
"""
from pyrogram import utils as _utils


def _get_peer_type(peer_id: int) -> str:
    s = str(peer_id)
    if not s.startswith("-"):
        return "user"
    if s.startswith("-100"):
        return "channel"
    return "chat"


_utils.get_peer_type = _get_peer_type
