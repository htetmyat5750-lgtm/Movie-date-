"""
All bot command handlers.
"""
from hydrogram import Client, filters
from hydrogram.types import Message
from pytgcalls import PyTgCalls

from bot.queue import Q, Track
from bot.media import (
    play, track_stream,
    resolve_tg_link, resolve_youtube_video, resolve_youtube_audio,
    fmt_dur, cleanup_old_files,
)


def register(app: Client, call: PyTgCalls, userbot: Client):

    # ── /start /help ─────────────────────────────────────────────
    @app.on_message(filters.command(["start", "help"]) & (filters.private | filters.group))
    async def cmd_help(_, msg: Message):
        await msg.reply(
            "🎬 **Video Chat Bot**\n\n"
            "**📺 Video Commands:**\n"
            "`/vplay <link>` — Telegram link (သို့) YouTube link ဖြင့် Video ဖွင့်သည်\n\n"
            "**🎵 Audio Commands:**\n"
            "`/play <song name>` — YouTube မှ သီချင်း ဖွင့်သည်\n\n"
            "**⏯ Controls:**\n"
            "`/skip` — နောက်တစ်ပုဒ် ကျော်သည်\n"
            "`/pause` — ရပ်ဆိုင်းသည်\n"
            "`/resume` — ဆက်ဖွင့်သည်\n"
            "`/stop` — ရပ်ပြီး VC မှ ထွက်သည်\n"
            "`/queue` — Queue ကြည့်သည်\n\n"
            "**ℹ️ Tips:**\n"
            "• Video download ပြီးမှ stream မြင်မှာဆို ထစ်မည်မဟုတ်\n"
            "• Cache ရှိပြီးသား file ကို ချက်ချင်း ဖွင့်သည်\n"
            "• Bot ကို Group **Admin** လုပ်ပေးပါ\n"
            "• **Video Chat** ဖွင့်ထားပါ"
        )

    # ── /vplay ────────────────────────────────────────────────────
    @app.on_message(filters.command(["vplay", "vp"]) & filters.group)
    async def cmd_vplay(_, msg: Message):
        cid = msg.chat.id
        if len(msg.command) < 2:
            await msg.reply(
                "❌ Link ထည့်ပေးပါ\n"
                "ဥပမာ:\n"
                "`/vplay https://t.me/channel/123`\n"
                "`/vplay https://youtube.com/watch?v=xxx`"
            )
            return

        link = msg.command[1].strip()
        by   = msg.from_user.first_name if msg.from_user else "Unknown"
        sm   = await msg.reply("⏳ ပြင်ဆင်နေသည်...")

        # ── resolve source ──
        if "t.me/" in link:
            path, title = await resolve_tg_link(
                userbot, link, on_status=sm.edit
            )
            if not path:
                await sm.edit(f"❌ {title}")
                return
            track = Track(title=title, stream=path, requested_by=by, is_video=True)
        else:
            track = await resolve_youtube_video(link, by, on_status=sm.edit)
            if not track:
                await sm.edit("❌ Video မတွေ့ပါ သို့မဟုတ် download မအောင်မြင်ပါ")
                return

        # always replace current stream immediately
        Q.clear(cid)
        Q.set_current(cid, track)
        await sm.edit(
            f"📺 **{track.title}**\n\n"
            f"⏱ `{fmt_dur(track.duration)}`\n"
            "▶️ Stream စတင်နေသည်..."
        )

        try:
            await play(call, cid, track)
            cleanup_old_files(max_files=15)
            await sm.edit(
                f"📺 **Now Streaming**\n\n"
                f"**{track.title}**\n"
                f"⏱ `{fmt_dur(track.duration)}`\n"
                f"👤 Requested by: {by}\n\n"
                "🎥 Video Chat ကို ဖွင့်ကြည့်ပါ!"
            )
        except Exception as e:
            Q.set_current(cid, None)
            await sm.edit(
                f"❌ Stream မဖြစ်ပါ:\n`{e}`\n\n"
                "• Bot ကို Admin လုပ်ပေးပါ\n"
                "• Video Chat ဖွင့်ထားပါ\n"
                "• Userbot ကို Group မှာ ထည့်ထားပါ"
            )

    # ── /play ─────────────────────────────────────────────────────
    @app.on_message(filters.command(["play", "p"]) & filters.group)
    async def cmd_play(_, msg: Message):
        cid   = msg.chat.id
        if len(msg.command) < 2:
            await msg.reply("❌ သီချင်းအမည် ထည့်ပေးပါ\nဥပမာ: `/play Floke Rose`")
            return

        query = " ".join(msg.command[1:])
        by    = msg.from_user.first_name if msg.from_user else "Unknown"
        sm    = await msg.reply(f"🔍 **{query}** ရှာဖွေနေသည်...")

        t = await resolve_youtube_audio(query, by, on_status=sm.edit)
        if not t:
            await sm.edit("❌ သီချင်း မတွေ့ပါ သို့မဟုတ် download မအောင်မြင်ပါ")
            return

        cur = Q.current(cid)
        if cur is None:
            Q.set_current(cid, t)
            await sm.edit(f"▶️ **{t.title}** stream စတင်နေသည်...")
            try:
                await play(call, cid, t)
                await sm.edit(
                    f"🎵 **Now Playing**\n\n"
                    f"**{t.title}**\n"
                    f"⏱ `{fmt_dur(t.duration)}`\n"
                    f"👤 {by}"
                )
            except Exception as e:
                Q.set_current(cid, None)
                await sm.edit(
                    f"❌ Join မဝင်နိုင်ပါ:\n`{e}`\n\n"
                    "Bot ကို Admin လုပ်ပြီး Voice Chat ဖွင့်ပါ"
                )
        else:
            Q.enqueue(cid, t)
            pos = len(Q.list(cid))
            await sm.edit(
                f"✅ Queue #{pos} မှာ ထည့်လိုက်သည်\n"
                f"**{t.title}**\n"
                f"⏱ `{fmt_dur(t.duration)}`\n"
                f"👤 {by}"
            )

    # ── /skip ─────────────────────────────────────────────────────
    @app.on_message(filters.command(["skip", "s"]) & filters.group)
    async def cmd_skip(_, msg: Message):
        cid = msg.chat.id
        cur = Q.current(cid)
        if not cur:
            await msg.reply("❌ ယခု play နေသော track မရှိပါ")
            return

        nxt = Q.pop_next(cid)
        if not nxt:
            Q.set_current(cid, None)
            try:
                await call.leave_call(cid)
            except Exception:
                pass
            await msg.reply(f"⏭ **{cur.title}** ကျော်လိုက်သည်\n✅ Queue ကုန်ပြီ")
            return

        try:
            await play(call, cid, nxt)
            icon = "📺" if nxt.is_video else "🎵"
            await msg.reply(
                f"⏭ ကျော်လိုက်သည်\n\n"
                f"{icon} **{nxt.title}**\n"
                f"⏱ `{fmt_dur(nxt.duration)}`\n"
                f"👤 {nxt.requested_by}"
            )
        except Exception as e:
            Q.set_current(cid, None)
            await msg.reply(f"❌ Stream error: `{e}`")

    # ── /stop ─────────────────────────────────────────────────────
    @app.on_message(filters.command(["stop", "end"]) & filters.group)
    async def cmd_stop(_, msg: Message):
        cid = msg.chat.id
        Q.clear(cid)
        try:
            await call.leave_call(cid)
            await msg.reply("⏹ ရပ်လိုက်ပြီး Video Chat မှ ထွက်လိုက်သည်")
        except Exception:
            await msg.reply("⏹ Queue ဖျက်လိုက်သည်")

    # ── /pause /resume ────────────────────────────────────────────
    @app.on_message(filters.command("pause") & filters.group)
    async def cmd_pause(_, msg: Message):
        try:
            await call.pause(msg.chat.id)
            await msg.reply("⏸ ရပ်ဆိုင်းလိုက်သည်")
        except Exception as e:
            await msg.reply(f"❌ {e}")

    @app.on_message(filters.command("resume") & filters.group)
    async def cmd_resume(_, msg: Message):
        try:
            await call.resume(msg.chat.id)
            await msg.reply("▶️ ဆက်ဖွင့်လိုက်သည်")
        except Exception as e:
            await msg.reply(f"❌ {e}")

    # ── /queue ────────────────────────────────────────────────────
    @app.on_message(filters.command(["queue", "q"]) & filters.group)
    async def cmd_queue(_, msg: Message):
        cid  = msg.chat.id
        cur  = Q.current(cid)
        lst  = Q.list(cid)
        if not cur and not lst:
            await msg.reply("📋 Queue တွင် track မရှိပါ")
            return
        txt = "🎬 **Queue**\n\n"
        if cur:
            icon = "📺" if cur.is_video else "🎵"
            txt += f"▶️ **Now:** {icon} {cur.title} — {cur.requested_by}\n\n"
        for i, t in enumerate(lst[:10], 1):
            icon = "📺" if t.is_video else "🎵"
            txt += f"{i}. {icon} {t.title} — {t.requested_by}\n"
        if len(lst) > 10:
            txt += f"\n...+{len(lst)-10} more"
        await msg.reply(txt)
