# Works on Raspberry Pi (linux/arm64) and x86_64.
FROM python:3.11-slim

# tgcrypto is a C extension. It needs a full toolchain *including* the C
# standard library headers (stdint.h etc.), so install build-essential —
# bare "gcc" alone is missing libc6-dev and the build fails.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY stream_bot ./stream_bot

# Persistent Pyrogram session lives here (mounted as a volume in compose).
RUN mkdir -p /app/session

ENV PORT=8082
EXPOSE 8082

CMD ["python", "-m", "stream_bot"]
