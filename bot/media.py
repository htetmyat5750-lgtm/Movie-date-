"""
Build the right MediaStream for audio vs video tracks,
and resolve Telegram / YouTube links to streamable sources.

Key principle: always stream from a LOCAL file, never from a remote URL.
This eliminates stuttering caused by network jitter.
"""
import os, re, asyncio, hashlib, time
import yt_dlp
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality, GroupCallConfig
from pytgcalls import PyTgCalls
from bot.queue import Track

DOWNLOAD_DIR = "/tmp/tgvids"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

TG_PUB  = re.compile(r"https?://t\.me/([a-zA-Z0-9_]+)/(\d+)")
TG_PRIV = re.compile(r"https?://t\.me/c/(\d+)/(\d+)")


# ── stream builders ──────────────────────────────────────────────

def audio_stream(src: str) -> MediaStream:
    return MediaStream(src, audio_parameters=AudioQuality.HIGH)


def video_stream(src: str) -> MediaStream:
    # 720p is the sweet-spot: smooth playback, lower CPU/network load
    return MediaStream(
        src,
        audio_parameters=AudioQuality.HIGH,
        video_parameters=VideoQuality.HD_720p,
    )


def track_stream(t: Track) -> MediaStream:
    return video_stream(t.stream) if t.is_video else audio_stream(t.stream)


async def play(call: PyTgCalls, cid: int, t: Track):
    await call.play(cid, track_stream(t), config=GroupCallConfig(auto_start=True))


# ── YouTube download → local file ────────────────────────────────

def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def _yt_download_video(url: str, out_path: str) -> dict | None:
    """Download best mp4 video+audio merged. Returns info dict or None."""
    opts = {
        "format": (
            "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[height<=720]+bestaudio"
            "/best[height<=720][ext=mp4]"
            "/best[height<=720]"
            "/best"
        ),
        "outtmpl": out_path,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        # buffer aggressively to avoid stalling
        "http_chunk_size": 10 * 1024 * 1024,  # 10 MB chunks
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            if "entries" in info:
                info = info["entries"][0]
            return info
        except Exception:
            return None


def _yt_download_audio(query: str, out_path: str) -> dict | None:
    """Download best audio for a search query or URL. Returns info dict or None."""
    opts = {
        "format": "bestaudio/best",
        "outtmpl": out_path,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(query, download=True)
            if "entries" in info:
                info = info["entries"][0]
            return info
        except Exception:
            return None


def _yt_info_only(query: str) -> dict | None:
    """Extract info without downloading (for title/duration preview)."""
    opts = {
        "format": "best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "default_search": "ytsearch",
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        try:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                info = info["entries"][0]
            return info
        except Exception:
            return None


async def resolve_youtube_video(url: str, requested_by: str,
                                on_status=None) -> Track | None:
    """
    Download YouTube video to /tmp/tgvids/<hash>.mp4, then return a Track
    pointing to the local file — guarantees stutter-free playback.
    """
    loop = asyncio.get_event_loop()

    # quick metadata fetch first (fast, no download)
    if on_status:
        await on_status("🔍 Video info ရယူနေသည်...")
    info = await loop.run_in_executor(None, _yt_info_only, url)
    if not info:
        return None

    title    = info.get("title", url)
    duration = info.get("duration") or 0
    h_id     = _url_hash(url)
    out_tmpl = os.path.join(DOWNLOAD_DIR, f"yt_{h_id}.%(ext)s")
    final    = os.path.join(DOWNLOAD_DIR, f"yt_{h_id}.mp4")

    # serve from cache if already downloaded
    if os.path.exists(final):
        if on_status:
            await on_status(
                f"✅ Cache မှ load လုပ်နေသည်...\n**{title}**"
            )
        return Track(title=title, stream=final, requested_by=requested_by,
                     is_video=True, duration=duration)

    size_mb = info.get("filesize") or info.get("filesize_approx") or 0
    size_mb /= 1024 * 1024
    if on_status:
        size_txt = f" (~{size_mb:.0f} MB)" if size_mb > 1 else ""
        await on_status(
            f"⬇️ **Download လုပ်နေသည်{size_txt}...**\n"
            f"**{title}**\n\n"
            f"_(ပြီးမှ ထစ်ကင်းစွာ stream ဖွင့်မည်)_"
        )

    info2 = await loop.run_in_executor(None, _yt_download_video, url, out_tmpl)
    if not info2:
        return None

    # yt-dlp may produce .mp4 or a merged file — find it
    if not os.path.exists(final):
        candidates = [f for f in os.listdir(DOWNLOAD_DIR) if f.startswith(f"yt_{h_id}")]
        if not candidates:
            return None
        # use the largest file (most likely the merged video)
        candidates.sort(key=lambda f: os.path.getsize(os.path.join(DOWNLOAD_DIR, f)), reverse=True)
        src = os.path.join(DOWNLOAD_DIR, candidates[0])
        os.rename(src, final)

    return Track(title=title, stream=final, requested_by=requested_by,
                 is_video=True, duration=duration)


async def resolve_youtube_audio(query: str, requested_by: str,
                                on_status=None) -> Track | None:
    """
    Download YouTube audio to /tmp/tgvids/<hash>.mp3 and return a Track.
    """
    loop = asyncio.get_event_loop()

    if on_status:
        await on_status(f"🔍 **{query}** ရှာဖွေနေသည်...")

    info = await loop.run_in_executor(None, _yt_info_only, query)
    if not info:
        return None

    title    = info.get("title", query)
    duration = info.get("duration") or 0
    h_id     = _url_hash(info.get("webpage_url", query))
    out_tmpl = os.path.join(DOWNLOAD_DIR, f"au_{h_id}.%(ext)s")
    final    = os.path.join(DOWNLOAD_DIR, f"au_{h_id}.mp3")

    if os.path.exists(final):
        if on_status:
            await on_status(f"✅ Cache မှ load လုပ်နေသည်...\n**{title}**")
        return Track(title=title, stream=final, requested_by=requested_by,
                     is_video=False, duration=duration)

    if on_status:
        await on_status(
            f"⬇️ **Download လုပ်နေသည်...**\n**{title}**\n"
            f"⏱ `{fmt_dur(duration)}`"
        )

    info2 = await loop.run_in_executor(None, _yt_download_audio, query, out_tmpl)
    if not info2:
        return None

    if not os.path.exists(final):
        candidates = [f for f in os.listdir(DOWNLOAD_DIR) if f.startswith(f"au_{h_id}")]
        if not candidates:
            return None
        candidates.sort(key=lambda f: os.path.getsize(os.path.join(DOWNLOAD_DIR, f)), reverse=True)
        src = os.path.join(DOWNLOAD_DIR, candidates[0])
        os.rename(src, final)

    return Track(title=title, stream=final, requested_by=requested_by,
                 is_video=False, duration=duration)


# ── Telegram file download ───────────────────────────────────────

async def resolve_tg_link(userbot, url: str, on_status=None) -> tuple[str | None, str]:
    """Return (file_path, title) or (None, error_message)."""
    m = TG_PRIV.search(url)
    if m:
        chat_id = int("-100" + m.group(1))
        msg_id  = int(m.group(2))
    else:
        m = TG_PUB.search(url)
        if not m:
            return None, "Link format မမှန်ပါ"
        chat_id = m.group(1)
        msg_id  = int(m.group(2))

    if on_status:
        await on_status("🔗 Telegram message ရှာဖွေနေသည်...")

    try:
        msg = await userbot.get_messages(chat_id, msg_id)
    except Exception as e:
        return None, f"Message မရပါ: {e}\n\nUserbot ကို channel/group မှာ ထည့်ထားပါ"

    if not msg or msg.empty:
        return None, "Message မတွေ့ပါ (ဖျက်ထားနိုင်သည်)"

    media = msg.video or msg.document or msg.animation or msg.audio
    if not media:
        return None, "ဤ message တွင် video/audio မပါပါ"

    raw_name = (getattr(media, "file_name", None)
                or getattr(media, "title", None)
                or f"video_{msg_id}")
    safe = re.sub(r'[^\w\-_\. ]', '_', raw_name)
    path = os.path.join(DOWNLOAD_DIR, f"{msg_id}_{safe}")

    if os.path.exists(path):
        if on_status:
            await on_status(f"✅ Cache မှ load လုပ်နေသည်...\n`{raw_name}`")
        return path, raw_name

    size_mb = getattr(media, "file_size", 0) / 1024 / 1024
    if on_status:
        await on_status(
            f"⬇️ Download လုပ်နေသည်...\n`{raw_name}`\n"
            f"📦 {size_mb:.1f} MB\n\n_(ပြီးမှ ထစ်ကင်းစွာ stream ဖွင့်မည်)_"
        )

    try:
        dl = await userbot.download_media(msg, file_name=path)
        if not dl:
            return None, "Download မအောင်မြင်ပါ"
    except Exception as e:
        return None, f"Download error: {e}"

    return path, raw_name


# ── helpers ──────────────────────────────────────────────────────

def fmt_dur(s: int) -> str:
    if s <= 0:
        return "Live / Unknown"
    m, sec = divmod(s, 60)
    h, m   = divmod(m, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def cleanup_old_files(max_files: int = 20):
    """Remove oldest downloaded files if too many accumulate."""
    try:
        files = [
            os.path.join(DOWNLOAD_DIR, f)
            for f in os.listdir(DOWNLOAD_DIR)
            if os.path.isfile(os.path.join(DOWNLOAD_DIR, f))
        ]
        if len(files) > max_files:
            files.sort(key=os.path.getmtime)
            for f in files[:len(files) - max_files]:
                os.remove(f)
    except Exception:
        pass
