# 🎬 tg-stream-link-bot

> Turn any file you send a Telegram bot into an **instant, seekable streaming link** for VLC, MX Player, or your browser.

The bot never downloads the whole file — for each request it pulls only the byte
range the player asks for, straight from Telegram, so playback starts in a
second or two and seeking works on files of any size.

Built with **[Pyrogram](https://docs.pyrogram.org/)** (MTProto — no 20 MB
Bot-API limit) and **aiohttp**. Runs as a Docker container; designed for a
Raspberry Pi but works anywhere.

## ✨ Features

- ⚡ **Instant streaming** — no full download, no disk usage for the media.
- ⏩ **Seekable** — proper HTTP `Range` / `206 Partial Content` support.
- 🔮 **Read-ahead buffering** — fetches chunks ahead of the player for smooth playback.
- 📦 **Any file size** — limited only by Telegram's upload cap (2 GB free / 4 GB Premium), not by the bot or the host's RAM.
- 💾 **Persistent session** — survives restarts without re-authenticating.
- 🌐 **Browser player** — a simple `/watch/<id>` page in addition to direct links.

## ⚙️ How it works

1. You send a file to the bot in a private chat.
2. The bot copies it into a **private storage channel** (where it is an admin)
   and replies with a stream link like `https://your-domain/stream/<id>/<name>`.
3. When a player opens the link, the server reads the `Range` header, fetches
   only the overlapping 1 MiB Telegram chunks via `upload.GetFile`, trims the
   edges, and streams them out — fetching the next chunks ahead of time so
   playback stays smooth.

The file itself lives in your Telegram storage channel; the bot is just a smart
range-relay between Telegram and your player.

## 📋 Requirements

- 🐳 Docker + Docker Compose
- 💬 A Telegram account and a bot
- 🔌 A way to expose the bot's port behind a domain (any reverse proxy: Caddy,
  nginx, Cloudflare Tunnel, Tailscale Serve, …)

## 🚀 Setup

### 1️⃣ Telegram credentials
- <https://my.telegram.org> -> **API development tools** -> `API_ID`, `API_HASH`.
- Create a bot with [@BotFather](https://t.me/BotFather) -> `BOT_TOKEN`.

### 2️⃣ Storage channel
- Create a **private channel**.
- Add your bot as an **admin** with "Post Messages".
- Get its id (`-100xxxxxxxxxx`): forward any message from it to
  [@userinfobot](https://t.me/userinfobot).

### 3️⃣ Configure
```bash
cp .env.example .env
# edit .env with your values
```

| Variable             | Description                                              |
|----------------------|----------------------------------------------------------|
| `API_ID` / `API_HASH`| From my.telegram.org (reusable across your projects)     |
| `BOT_TOKEN`          | From @BotFather                                          |
| `STORAGE_CHANNEL_ID` | `-100…` id of your private channel (bot must be admin)   |
| `PUBLIC_BASE_URL`    | Public URL your reverse proxy serves, e.g. `https://stream.example.com` |
| `PORT`               | Internal port the bot listens on (default `8082`)       |
| `PREFETCH_CHUNKS`    | Read-ahead buffer in ~1 MiB chunks (default `3`)         |
| `CACHE_TTL`          | Seconds to cache file metadata (default `1800`)          |

### 4️⃣ Run
```bash
mkdir -p session                 # persistent Pyrogram login (gitignored)
docker compose up -d --build
docker compose logs -f           # wait for: "Bot started as @yourbot"
```

## 🌍 Exposing it (pick one)

The bot listens on `127.0.0.1:8082` by default; put any reverse proxy in front.

**🔒 Tailscale + Caddy (private — only your devices):**
Point a DNS A record at your Pi's Tailscale IP (`100.x.x.x`, set to *DNS only*
if using Cloudflare DNS), then in your `Caddyfile`:
```
http://stream.example.com {
    reverse_proxy 127.0.0.1:8082
}
```
HTTP is fine here since Tailscale (WireGuard) already encrypts the traffic.
Every streaming device must have Tailscale connected.

**☁️ Cloudflare Tunnel (public):**
Create a tunnel and add a public hostname pointing `stream.example.com` to
`http://localhost:8082`. Note the free tier may interrupt very long streams.

**🔧 Any reverse proxy / direct port** also works — just set `PUBLIC_BASE_URL`
to match.

## ▶️ Usage

Send a file to the bot. It replies with a **direct link** (paste into VLC /
MX Player) and a **/watch/** link (plays in a browser).

## ⚠️ Caveats

- 📌 **Storage channel is the source of truth** — don't delete messages from it,
  that breaks their links.
- 🔓 **Public links** contain a sequential message id, so links are guessable.
  Keep the bot behind private access (Tailscale) or add signed tokens if you
  expose it publicly.
- 🩹 **Pyrogram 2.0.106** is lightly maintained; this project includes a small
  compatibility patch (`patches.py`) for newer channel IDs. If you hit further
  layer issues, the API-compatible fork `kurigram` is a drop-in swap.

## 🗂️ Project layout
```
stream_bot/
  __main__.py   start client + web server
  config.py     env vars
  client.py     Pyrogram client
  patches.py    Pyrogram 2.0.106 compatibility shim
  handlers.py   /start + media -> store + reply links
  media.py      pull file metadata from a message
  streamer.py   ByteStreamer: chunked range download + read-ahead
  server.py     aiohttp routes + Range handling + /watch page
```

## 📜 Disclaimer

For personal use with content you have the right to store and stream. You are
responsible for complying with Telegram's Terms of Service and applicable law.

## 📄 License

[MIT](LICENSE) © 2026
