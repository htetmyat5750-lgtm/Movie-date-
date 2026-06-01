# 🎬 Telegram Video Chat Bot

  Telegram group Video Chat တွင် Telegram link နှင့် YouTube video ကြည့်ရှုနိုင်သော Bot။

  ## Features
  - `/vplay <link>` — Telegram link သို့မဟုတ် YouTube ဖြင့် Video ဖွင့်သည် (ထစ်ကင်း)
  - `/play <song>` — YouTube မှ Audio ဖွင့်သည်
  - `/skip` `/pause` `/resume` `/stop` — Playback controls
  - `/queue` — Queue ကြည့်သည်
  - ✅ Download ပြီးမှ stream ဆောင်ရွက်သောကြောင့် ထစ်ကင်းသည်

  ## Setup
  ```
  API_ID=your_api_id
  API_HASH=your_api_hash
  BOT_TOKEN=your_bot_token
  SESSION_STRING=your_session_string
  ```

  ## Install
  ```bash
  pip install -r requirements.txt
  sudo apt install ffmpeg
  python main.py
  ```

  ## Group Setup
  1. Bot ကို Group Admin လုပ်ပေးပါ
  2. Video Chat ဖွင့်ထားပါ
  3. Userbot (SESSION_STRING) ကို Group ထဲ ထည့်ပေးပါ

  ## Stack
  - Python 3.11
  - hydrogram 0.2.0
  - pytgcalls 2.2.11
  - yt-dlp
  - ffmpeg
  