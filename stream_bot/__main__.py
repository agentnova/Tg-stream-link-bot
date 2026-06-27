"""Entrypoint: runs the Pyrogram client and the aiohttp server together."""
import logging

from aiohttp import web
from pyrogram import idle

from . import config
from .client import app
from . import handlers  # noqa: F401  (registers message handlers)
from .server import create_web_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("main")


async def main():
    await app.start()
    me = await app.get_me()
    log.info("Bot started as @%s", me.username)

    web_app = create_web_app(app)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, config.BIND_ADDRESS, config.PORT)
    await site.start()
    log.info("HTTP server on %s:%s  ->  %s", config.BIND_ADDRESS, config.PORT,
             config.PUBLIC_BASE_URL)

    await idle()

    await runner.cleanup()
    await app.stop()
    log.info("Stopped.")


if __name__ == "__main__":
    # IMPORTANT: app.run() runs the coroutine on Pyrogram's *own* event loop
    # (the one the Client captured at construction). Using asyncio.run() here
    # would create a second loop, leaving the update dispatcher on a different
    # loop than the network — so handlers would never fire.
    app.run(main())
