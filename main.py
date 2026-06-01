import asyncio, logging
import bot.fix  # patches hydrogram.errors — must be first

from hydrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import Update, StreamEnded

from bot.config import API_ID, API_HASH, BOT_TOKEN, SESSION_STRING
from bot.queue import Q
from bot.media import play, fmt_dur
from bot.handlers import register

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger("bot")


async def run():
    userbot = Client(
        "userbot", api_id=API_ID, api_hash=API_HASH,
        session_string=SESSION_STRING,
    )
    bot = Client(
        "bot", api_id=API_ID, api_hash=API_HASH,
        bot_token=BOT_TOKEN,
    )
    call = PyTgCalls(userbot)

    # auto-advance queue when a track finishes
    @call.on_update()
    async def _on_ended(client: PyTgCalls, update: Update):
        if not isinstance(update, StreamEnded):
            return
        cid = update.chat_id
        nxt = Q.pop_next(cid)
        if nxt:
            try:
                await play(call, cid, nxt)
                icon = "📺" if nxt.is_video else "🎵"
                await bot.send_message(
                    cid,
                    f"{icon} **{'Now Streaming' if nxt.is_video else 'Now Playing'}**\n\n"
                    f"**{nxt.title}**\n⏱ `{fmt_dur(nxt.duration)}`\n👤 {nxt.requested_by}",
                )
            except Exception as e:
                Q.set_current(cid, None)
                log.error("auto-play failed: %s", e)
        else:
            Q.set_current(cid, None)
            try:
                await client.leave_call(cid)
            except Exception:
                pass

    register(bot, call, userbot)

    log.info("Starting…")
    async with userbot, bot:
        await call.start()
        log.info("✅ Video Chat Bot is running!")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(run())
