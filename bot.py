import re
import asyncio
import threading
import os
import http.server
import socketserver
import difflib  
from pyrogram import Client, filters, enums, StopPropagation
from pyrogram.errors import MessageNotModified
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from pymongo import MongoClient
from bson.objectid import ObjectId

# ==========================================
# 1. 🚀 CREDENTIALS & DB SETUP
# ==========================================
BOT_TOKEN = "8600027374:AAFjSg_NeOf53zl5XTE94h8ceK0kOgwaABw" 
ADMIN_ID = 6855375693
API_ID = 33056032
API_HASH = "4b04c50c2004752cee284a3f533a8dd3"
MONGO_URL = "mongodb+srv://Movie123:Yash123@cluster0.bi61te2.mongodb.net/?appName=Cluster0&compressors=zlib"
DB_CHANNEL_ID = -1004448866853 
FSUB_CHANNEL_ID = -1004442475534 
FSUB_CHANNEL_LINK = "https://t.me/+KAQT3ciLAfExMTY1" 
START_PIC = "https://telegra.ph/file/a7cc9bb4cf0d6c8e3cc50.jpg" 

mongo_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
db = mongo_client["MovieBot"]
movies_col = db["Movies"]
users_col = db["Users"] 
watchlist_col = db["Watchlist"] 

app = Client("ProMovieBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# ==========================================
# ⚡ FORCE SUB LOGIC
# ==========================================
async def check_fsub(client, user_id):
    if not FSUB_CHANNEL_ID: return True 
    try:
        member = await client.get_chat_member(FSUB_CHANNEL_ID, user_id)
        if member.status in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]: return False
        return True
    except: return False

async def ensure_fsub(client, message):
    if await check_fsub(client, message.from_user.id): return True
    btn = [[InlineKeyboardButton("📢 Join Our Channel", url=FSUB_CHANNEL_LINK)], [InlineKeyboardButton("✅ Verify", callback_data="verify_fsub")]]
    await message.reply_text("⚠️ **Pehle hamara official channel join karein, fir 'Verify' dabayein!**", reply_markup=InlineKeyboardMarkup(btn))
    return False

# ==========================================
# 🛠️ SET MENU
# ==========================================
@app.on_message(filters.command("setmenu") & filters.private & filters.user(ADMIN_ID))
async def set_bot_menus(client, message):
    cmds = [
        BotCommand("start", "🔄 Restart Bot"),
        BotCommand("request", "📩 Request Movie"),
        BotCommand("watchlist", "📌 My Saved Movies")
    ]
    await client.set_bot_commands(cmds, scope=BotCommandScopeDefault())
    admin_cmds = cmds + [BotCommand("stats", "📊 Stats"), BotCommand("broadcast", "📢 Broadcast"), BotCommand("setmenu", "🛠️ Set Menu")]
    await client.set_bot_commands(admin_cmds, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
    await message.reply_text("✅ **Fresh Menu Set!**")
    raise StopPropagation

# ==========================================
# 📩 BASIC COMMANDS & REQUEST
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    if not users_col.find_one({"user_id": message.from_user.id}):
        users_col.insert_one({"user_id": message.from_user.id, "name": message.from_user.first_name})
    if not await ensure_fsub(client, message): raise StopPropagation

    text = f"👋 **Hᴇʏ, {message.from_user.first_name}**\n\n🎬 **Mᴀɪɴ Eᴋ Mᴏᴠɪᴇ Bᴏᴛ HᴏᴏN!**\n🔎 Koi bhi movie/series download karne ke liye bas uska naam bhejein.\n\n📌 Watchlist: `/watchlist`"
    try: await message.reply_photo(photo=START_PIC, caption=text)
    except: await message.reply_text(text)
    raise StopPropagation

@app.on_message(filters.command("request") & filters.private)
async def request_movie(client, message):
    if not await ensure_fsub(client, message): raise StopPropagation
    if len(message.command) < 2: return await message.reply_text("✍️ **Format:** `/request <movie name>`")
        
    req_movie = message.text.split(" ", 1)[1][:50]
    btn = [[InlineKeyboardButton("✅ Mark as Uploaded", callback_data=f"reqdone_{message.from_user.id}")]]
    admin_text = f"📩 **NEW REQUEST**\n👤 {message.from_user.first_name} (`{message.from_user.id}`)\n🎬 `{req_movie}`"
    try:
        await client.send_message(ADMIN_ID, admin_text, reply_markup=InlineKeyboardMarkup(btn))
        await message.reply_text("✅ Aapki request admin ko bhej di gayi hai!")
    except: pass
    raise StopPropagation

@app.on_message(filters.command("watchlist") & filters.private)
async def show_watchlist(client, message):
    wl = watchlist_col.find_one({"user_id": message.from_user.id})
    if not wl or not wl.get("movies"): return await message.reply_text("📌 Aapki Watchlist khali hai!")
    text = "📌 **MY WATCHLIST**\n\n"
    for i, mid in enumerate(wl["movies"][:20], 1):
        movie = movies_col.find_one({"_id": ObjectId(mid)})
        if movie: text += f"**{i}.** `{movie['movie_name'].title()}`\n"
    await message.reply_text(text)
    raise StopPropagation

# ==========================================
# 👑 ADMIN COMMANDS
# ==========================================
@app.on_message(filters.command("stats") & filters.private & filters.user(ADMIN_ID))
async def admin_stats(client, message):
    await message.reply_text(f"📊 **STATS**\n👥 Users: `{users_col.count_documents({})}`\n🎬 Files: `{movies_col.count_documents({})}`")
    raise StopPropagation

@app.on_message(filters.command("broadcast") & filters.private & filters.user(ADMIN_ID) & filters.reply)
async def admin_broadcast(client, message):
    users = list(users_col.find({}))
    await message.reply_text(f"🚀 Broadcasting to {len(users)} users...")
    for user in users:
        try: await message.reply_to_message.copy(user["user_id"])
        except: pass
    await message.reply_text("✅ Broadcast Complete!")
    raise StopPropagation

# ==========================================
# 📁 SAVE MOVIE (SMART TAGGING & CLEAN CAPTION)
# ==========================================
@app.on_message((filters.document | filters.video) & filters.private & filters.user(ADMIN_ID))
async def save_movie_to_db(client, message):
    media = message.document or message.video
    if not media: return
    exact_file_name = getattr(media, "file_name", None) or "movie_file.mp4"
    
    clean_movie_name = re.sub(r'\s+', ' ', exact_file_name.lower().replace("_", " ").replace(".", " ")).strip()
    
    q_tags, l_tags, s_tags, e_tags = [], [], [], []
    for q in ["480p", "720p", "1080p", "4k"]: 
        if q in clean_movie_name: q_tags.append(q)
    
    # 🗣️ Language Smart Match (Hindi, HIN, DUAL, Multi etc.)
    if any(x in clean_movie_name for x in ["hindi", "hin"]):
        l_tags.append("hindi")
    if any(x in clean_movie_name for x in ["english", "eng"]):
        l_tags.append("english")
    if any(x in clean_movie_name for x in ["dual", "hin-tel", "hin-tam", "multi"]):
        l_tags.append("dual audio")
    
    # 🎬 Smart Season Match (S01, S1, Season 1 etc.)
    season_matches = re.findall(r'\b(?:s|season)\s*0*(\d+)\b', clean_movie_name)
    for s_num in season_matches:
        s_tags.append(f"S{s_num.zfill(2)}")
        
    for match in re.findall(r'\be(\d+)\b|\bepisode\s*(\d+)\b', clean_movie_name):
        e_tags.append(f"E{str(match[0] or match[1]).zfill(2)}")

    try:
        clean_caption = f"`{exact_file_name}`"
        if message.document: copied_msg = await client.send_document(DB_CHANNEL_ID, media.file_id, caption=clean_caption)
        else: copied_msg = await client.send_video(DB_CHANNEL_ID, media.file_id, caption=clean_caption)
    except: return await message.reply_text("❌ Error in DB Channel.")

    movies_col.insert_one({
        "movie_name": clean_movie_name, "file_name": exact_file_name, "message_id": copied_msg.id,
        "quality": q_tags, "language": l_tags, "season": list(set(s_tags)), "episode": list(set(e_tags))
    })
    await message.reply_text(f"✅ **Saved!**\n📁 `{exact_file_name}`")
    raise StopPropagation

# ==========================================
# 🔍 USER SEARCH (DYNAMIC BUTTONS)
# ==========================================
@app.on_message(filters.text & filters.private & ~filters.bot & ~filters.command(["start", "stats", "broadcast", "watchlist", "request", "setmenu"]))
async def search_movie(client, message):
    if not await ensure_fsub(client, message): raise StopPropagation
    
    sq = re.escape(message.text.lower().strip())
    movies = list(movies_col.find({"movie_name": {"$regex": sq, "$options": "i"}}).limit(30))
    
    if not movies:
        all_names = movies_col.distinct("movie_name")
        close = difflib.get_close_matches(message.text.lower(), all_names, n=2, cutoff=0.5)
        sugg = "\n".join([f"👉 `{m.title()}`" for m in close]) if close else "No similar movies."
        return await message.reply_text(f"❌ **Nahi mila.**\n{sugg}\nRequest: `/request {message.text[:20]}`")

    cb_sq = message.text.lower().strip()[:15] 
    has_season = any(m.get("season") for m in movies)
    has_episode = any(m.get("episode") for m in movies)

    btns = [[InlineKeyboardButton("✨ PIXEL", callback_data=f"flt_q_{cb_sq}"), InlineKeyboardButton("🗣 LANGUAGE", callback_data=f"flt_l_{cb_sq}")]]
    
    if has_season or has_episode:
        row = []
        if has_season: row.append(InlineKeyboardButton("🎬 SEASON", callback_data=f"flt_s_{cb_sq}"))
        if has_episode: row.append(InlineKeyboardButton("📺 EPISODE", callback_data=f"flt_e_{cb_sq}"))
        btns.append(row)

    btns.append([InlineKeyboardButton("📥 SEND ALL", callback_data=f"sendall_{cb_sq}")])
    for m in movies:
        mid = str(m["_id"])
        btns.append([InlineKeyboardButton(f"📁 {m.get('file_name', 'File')}", callback_data=f"get_{mid}")])
        btns.append([InlineKeyboardButton("📌 Add Watchlist", callback_data=f"wladd_{mid}")])
        
    await message.reply_text(f"📁 **Files for:** `{message.text}`", reply_markup=InlineKeyboardMarkup(btns))
    raise StopPropagation

async def auto_del(client, chat_id, ids):
    await asyncio.sleep(600)
    try: await client.delete_messages(chat_id, ids)
    except: pass

@app.on_callback_query()
async def callbacks(client, query):
    data = query.data
    
    if data.startswith("reqdone_"):
        if query.from_user.id != ADMIN_ID: return
        try:
            await client.send_message(int(data.split("_")[1]), "🎉 **Movie Uploaded!** Bot me search karein.")
            await query.message.edit_text("✅ Notified user!")
        except: await query.answer("Failed", show_alert=True)
        
    elif data == "verify_fsub":
        if await check_fsub(client, query.from_user.id):
            await query.answer("✅ Verified!", show_alert=True)
            await query.message.delete()
        else: await query.answer("❌ Pehle join karein!", show_alert=True)
        
    elif data.startswith("wladd_"):
        watchlist_col.update_one({"user_id": query.from_user.id}, {"$addToSet": {"movies": data.split("_")[1]}}, upsert=True)
        await query.answer("📌 Saved to Watchlist!")

    # 📥 GET SINGLE FILE (WITH 10-MIN AUTO DELETE)
    elif data.startswith("get_"):
        movie = movies_col.find_one({"_id": ObjectId(data.split("_")[1])})
        if movie and "message_id" in movie:
            msg = await client.copy_message(query.message.chat.id, DB_CHANNEL_ID, movie["message_id"])
            if query.from_user.id != ADMIN_ID:
                w_msg = await query.message.reply_text("⚠️ **Yeh file 10 minute mein auto-delete ho jayegi!**")
                asyncio.create_task(auto_del(client, query.message.chat.id, [msg.id, w_msg.id]))
        await query.answer()

    # 📥 GET ALL FILES (WITH 10-MIN AUTO DELETE)
    elif data.startswith("sendall_"):
        sq = re.escape(data.split("_", 1)[1])
        movies = list(movies_col.find({"movie_name": {"$regex": sq, "$options": "i"}}).limit(30))
        sent = []
        for m in movies:
            if "message_id" in m:
                msg = await client.copy_message(query.message.chat.id, DB_CHANNEL_ID, m["message_id"])
                sent.append(msg.id)
                await asyncio.sleep(0.3)
        if sent and query.from_user.id != ADMIN_ID:
            w_msg = await query.message.reply_text("⚠️ **Yeh sabhi files 10 minute mein auto-delete ho jayengi!**")
            sent.append(w_msg.id)
            asyncio.create_task(auto_del(client, query.message.chat.id, sent))
        await query.answer()

    # 🛠️ FILTERS LOGIC
    elif data.startswith("flt_"):
        ftype = data.split("_")[1]
        sq = data.split("_", 2)[2]
        btns = []
        
        if ftype == "q": 
            btns = [[InlineKeyboardButton(q, callback_data=f"app_quality_{q}_{sq}")] for q in ["480p", "720p", "1080p", "4k"]]
        elif ftype == "l": 
            btns = [[InlineKeyboardButton(l.title(), callback_data=f"app_language_{l}_{sq}")] for l in ["hindi", "english", "dual audio"]]
        elif ftype == "s":
            movies = list(movies_col.find({"movie_name": {"$regex": re.escape(sq), "$options": "i"}}).limit(50))
            seasons = sorted(list({s for m in movies for s in m.get("season", [])}))
            if not seasons: return await query.answer("❌ Season nahi mila!", show_alert=True)
            
            row = []
            for s in seasons:
                s_label = f"Season {int(s.replace('S', ''))}"
                row.append(InlineKeyboardButton(s_label, callback_data=f"app_season_{s}_{sq}"))
                if len(row) == 2:
                    btns.append(row)
                    row = []
            if row: btns.append(row)
        else:
            movies = list(movies_col.find({"movie_name": {"$regex": re.escape(sq), "$options": "i"}}).limit(50))
            items = sorted(list({i for m in movies for i in m.get("episode", [])}))
            if not items: return await query.answer("❌ Episode nahi mila!", show_alert=True)
            btns = [[InlineKeyboardButton(i, callback_data=f"app_episode_{i}_{sq}")] for i in items]

        btns.append([InlineKeyboardButton("🔙 Back", callback_data=f"back_{sq}")])
        try: await query.message.edit_reply_markup(InlineKeyboardMarkup(btns))
        except MessageNotModified: pass

    # 🎯 APPLY FILTER & DISPLAY FILES
    elif data.startswith("app_"):
        parts = data.split("_", 3)
        field, val, sq = parts[1], parts[2], parts[3]
        
        if field == "language":
            movies = list(movies_col.find({"movie_name": {"$regex": re.escape(sq), "$options": "i"}, field: {"$regex": f"^{val}$", "$options": "i"}}).limit(30))
        else:
            movies = list(movies_col.find({"movie_name": {"$regex": re.escape(sq), "$options": "i"}, field: val}).limit(30))
            
        if not movies: return await query.answer("❌ File nahi mili!", show_alert=True)
        
        btns = [[InlineKeyboardButton("🔙 Back", callback_data=f"back_{sq}")]]
        for m in movies:
            mid = str(m["_id"])
            btns.append([InlineKeyboardButton(f"📁 {m.get('file_name', 'File')}", callback_data=f"get_{mid}")])
        try: await query.message.edit_reply_markup(InlineKeyboardMarkup(btns))
        except MessageNotModified: pass

    elif data.startswith("back_"):
        sq = data.split("_", 1)[1]
        movies = list(movies_col.find({"movie_name": {"$regex": re.escape(sq), "$options": "i"}}).limit(30))
        has_season = any(m.get("season") for m in movies)
        has_episode = any(m.get("episode") for m in movies)

        btns = [[InlineKeyboardButton("✨ PIXEL", callback_data=f"flt_q_{sq}"), InlineKeyboardButton("🗣 LANGUAGE", callback_data=f"flt_l_{sq}")]]
        if has_season or has_episode:
            row = []
            if has_season: row.append(InlineKeyboardButton("🎬 SEASON", callback_data=f"flt_s_{sq}"))
            if has_episode: row.append(InlineKeyboardButton("📺 EPISODE", callback_data=f"flt_e_{sq}"))
            btns.append(row)

        btns.append([InlineKeyboardButton("📥 SEND ALL", callback_data=f"sendall_{sq}")])
        for m in movies:
            mid = str(m["_id"])
            btns.append([InlineKeyboardButton(f"📁 {m.get('file_name', 'File')}", callback_data=f"get_{mid}")])
            btns.append([InlineKeyboardButton("📌 Add Watchlist", callback_data=f"wladd_{mid}")])
        try: await query.message.edit_reply_markup(InlineKeyboardMarkup(btns))
        except MessageNotModified: pass

# ==========================================
# 🚀 SERVER
# ==========================================
def run_port_server():
    with socketserver.TCPServer(("0.0.0.0", int(os.environ.get("PORT", 10000))), http.server.SimpleHTTPRequestHandler) as httpd:
        httpd.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_port_server, daemon=True).start()
    app.run()
    
