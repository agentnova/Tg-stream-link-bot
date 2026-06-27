"""aiohttp server: /stream/<id>/<name> (direct) and /watch/<id> (browser)."""
import logging

from aiohttp import web

from . import config
from .streamer import ByteStreamer, plan_range

log = logging.getLogger("server")


def _parse_range(range_header: str, file_size: int):
    """Parse a single 'bytes=start-end' range. Returns (start, end) or None."""
    try:
        unit, _, rng = range_header.partition("=")
        if unit.strip() != "bytes":
            return None
        start_s, _, end_s = rng.strip().partition("-")
        if start_s == "":
            # suffix range: last N bytes
            length = int(end_s)
            start = max(file_size - length, 0)
            end = file_size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else file_size - 1
        end = min(end, file_size - 1)
        if start > end or start < 0:
            return None
        return start, end
    except (ValueError, AttributeError):
        return None


async def stream(request: web.Request) -> web.StreamResponse:
    streamer: ByteStreamer = request.app["streamer"]
    try:
        message_id = int(request.match_info["message_id"])
    except ValueError:
        raise web.HTTPNotFound(text="Invalid id")

    try:
        props = await streamer.get_props(message_id)
    except FileNotFoundError:
        raise web.HTTPNotFound(text="File not found or expired")

    file_size = props.file_size
    range_header = request.headers.get("Range")

    if range_header:
        parsed = _parse_range(range_header, file_size)
        if parsed is None:
            return web.Response(
                status=416, headers={"Content-Range": f"bytes */{file_size}"}
            )
        from_bytes, until_bytes = parsed
        status = 206
    else:
        from_bytes, until_bytes = 0, file_size - 1
        status = 200

    req_length = until_bytes - from_bytes + 1
    offset, first_cut, last_cut, part_count = plan_range(
        from_bytes, until_bytes, config.CHUNK_SIZE
    )

    headers = {
        "Content-Type": props.mime_type,
        "Content-Length": str(req_length),
        "Accept-Ranges": "bytes",
        "Content-Disposition": f'inline; filename="{props.file_name}"',
    }
    if status == 206:
        headers["Content-Range"] = f"bytes {from_bytes}-{until_bytes}/{file_size}"

    resp = web.StreamResponse(status=status, headers=headers)
    # HEAD: players probe before streaming.
    if request.method == "HEAD":
        await resp.prepare(request)
        return resp

    await resp.prepare(request)
    try:
        async for chunk in streamer.yield_file(
            props.file_id, offset, first_cut, last_cut, part_count, config.CHUNK_SIZE
        ):
            await resp.write(chunk)
    except (ConnectionResetError, ConnectionError, RuntimeError):
        # Client (VLC) closed or seeked; just stop this response.
        log.debug("client disconnected for %s", message_id)
    except Exception as e:  # noqa: BLE001
        # File reference may have aged out — drop cache so the next try refetches.
        streamer.invalidate(message_id)
        log.warning("stream error for %s: %s", message_id, e)
    return resp


async def watch(request: web.Request) -> web.Response:
    message_id = request.match_info["message_id"]
    streamer: ByteStreamer = request.app["streamer"]
    try:
        props = await streamer.get_props(int(message_id))
    except (FileNotFoundError, ValueError):
        raise web.HTTPNotFound(text="File not found or expired")

    src = f"{config.PUBLIC_BASE_URL}/stream/{message_id}"
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{props.file_name}</title>
<style>
  html,body{{margin:0;background:#0b0b0c;color:#e7e7ea;font-family:system-ui,sans-serif}}
  .wrap{{max-width:960px;margin:0 auto;padding:16px}}
  video{{width:100%;border-radius:8px;background:#000}}
  .name{{font-size:14px;opacity:.8;margin:12px 0 4px;word-break:break-all}}
  .row{{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap}}
  a.btn{{font-size:13px;text-decoration:none;background:#1d1d20;color:#9bd1ff;
    padding:8px 12px;border-radius:6px;border:1px solid #2a2a2e}}
</style></head>
<body><div class="wrap">
  <video controls preload="metadata" src="{src}"></video>
  <div class="name">{props.file_name}</div>
  <div class="row">
    <a class="btn" href="{src}">Direct link</a>
    <a class="btn" href="vlc://{config.PUBLIC_BASE_URL.split('://',1)[-1]}/stream/{message_id}">Open in VLC</a>
  </div>
</div></body></html>"""
    return web.Response(text=html, content_type="text/html")


async def index(_request: web.Request) -> web.Response:
    return web.Response(text="tg-stream-bot is running.\n")


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def create_web_app(client) -> web.Application:
    web_app = web.Application()
    web_app["streamer"] = ByteStreamer(client)
    web_app.add_routes(
        [
            web.get("/", index),
            web.get("/health", health),
            web.get("/watch/{message_id}", watch),
            # web.get registers HEAD automatically (allow_head=True), so the
            # HEAD probe players send before streaming hits the same handler.
            web.get("/stream/{message_id}", stream),
            web.get("/stream/{message_id}/{name}", stream),
        ]
    )
    return web_app
