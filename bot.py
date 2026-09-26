Import re
import time
import asyncio
import threading
import os
import http.server
import socketserver
import difflib  
import google.generativeai as genai 
from pyrogram import Client, filters, enums, StopPropagation
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    BotCommand, 
    BotCommandScopeDefault, 
    BotCommandScopeChat
)
from pymongo import MongoClient
from bson.objectid import ObjectId

# ==========================================
# 1. 🚀 CREDENTIALS & SETUP 
# ==========================================
BOT_TOKEN = "8600027374:AAEIW_jS0yL1O4WfNswL-7PAwqp5C7z2wj8" 
ADMIN_ID = 6855375693
API_ID = 33056032
API_HASH = "4b04c50c2004752cee284a3f533a8dd3"
MONGO_URL = "mongodb+srv://Movie123:Yash123@cluster0.bi61te2.mongodb.net/?appName=Cluster0&compressors=zlib"
DB_CHANNEL_ID = -1004448866853 

FSUB_CHANNEL_ID = -1004442475534 
FSUB_CHANNEL_LINK = "https://t.me/+KAQT3ciLAfExMTY1" 
START_PIC = "https://telegra.ph/file/a7cc9bb4cf0d6c8e3cc50.jpg" 
GEMINI_API_KEY = "AQ.Ab8RN6JREi500rTtVQHd0EHnxEdMZ6CedGiOB-O-XNtOn8tpAw" 

# Safe MongoDB Connection with Auto-Ping for Stability
mongo_client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=5000)
db = mongo_client["MovieBot"]
movies_col = db["Movies"]
users_col = db["Users"] 
banned_col = db["BannedUsers"]
trending_col = db["Trending"] 
vip_col = db["VIPUsers"]      
watchlist_col = db["Watchlist"] 

app = Client("ProMovieBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
SPAM_TRACKER = {}

try:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print("AI Setup Error:", e)

# ==========================================
# ⚡ STRICT FORCE SUB (FSUB) LOGIC
# ==========================================
@app.on_chat_join_request(filters.chat(FSUB_CHANNEL_ID))
async def approve_join_req(client, message):
    try:
        await client.approve_chat_join_request(chat_id=message.chat.id, user_id=message.from_user.id)
        await client.send_message(message.from_user.id, "✅ **Aapki join request accept ho gayi hai! Ab aap bot me movie search kar sakte hain.**")
    except: pass

async def check_fsub(client, user_id):
    if not FSUB_CHANNEL_ID or FSUB_CHANNEL_ID == -1000000000000: return True 
    try:
        member = await client.get_chat_member(FSUB_CHANNEL_ID, user_id)
        if member.status in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]: return False
        return True
    except:
        return False

async def ensure_fsub(client, message):
    user_id = message.from_user.id
    if await check_fsub(client, user_id): return True
    
    btn = [
        [InlineKeyboardButton("📢 Join Our Channel", url=FSUB_CHANNEL_LINK)],
        [InlineKeyboardButton("✅ Verify", callback_data="verify_fsub")]
    ]
    await message.reply_text("⚠️ **Aapne channel join nahi kiya hai, ya join karke left kar diya hai!**\n\nPehle hamara official channel join karein, fir 'Verify' dabayein tabhi bot aage kaam karega.", reply_markup=InlineKeyboardMarkup(btn))
    return False

def save_user(user_id, name):
    try:
        if not users_col.find_one({"user_id": user_id}):
            users_col.insert_one({"user_id": user_id, "name": name, "searches": 0})
    except: pass

# ==========================================
# 👤 USER PROFILE DASHBOARD
# ==========================================
@app.on_message(filters.command("profile") & filters.private)
async def user_profile(client, message):
    if not await ensure_fsub(client, message): raise StopPropagation
    user_id = message.from_user.id
    user_doc = users_col.find_one({"user_id": user_id}) or {}
    searches = user_doc.get("searches", 0)
    
    vip_status = "👑 VIP Member" if vip_col.find_one({"user_id": user_id}) else "👤 Normal User"
    wl = watchlist_col.find_one({"user_id": user_id})
    wl_count = len(wl.get("movies", [])) if wl else 0
    
    text = (
        f"👤 **YOUR DASHBOARD** 👤\n\n"
        f"📛 **Name:** {message.from_user.first_name}\n"
        f"🆔 **ID:** `{user_id}`\n"
        f"🏷️ **Status:** {vip_status}\n"
        f"🔍 **Total Searches:** `{searches}`\n"
        f"📌 **Movies in Watchlist:** `{wl_count}`\n"
    )
    await message.reply_text(text)
    raise StopPropagation

# ==========================================
# 📩 IN-BOT SMART REQUEST SYSTEM
# ==========================================
@app.on_message(filters.command("request") & filters.private)
async def request_movie(client, message):
    if not await ensure_fsub(client, message): raise StopPropagation
    
    if len(message.command) < 2:
        await message.reply_text("✍️ **Sahi format:** `/request <movie name>`\n_Example: /request The Boys Season 4_")
        raise StopPropagation
        
    req_movie = message.text.split(" ", 1)[1][:50]
    user_id = message.from_user.id
    user_name = message.from_user.first_name

    btn = [[InlineKeyboardButton("✅ Mark as Uploaded", callback_data=f"reqdone_{user_id}")]]
    admin_text = f"📩 **NEW MOVIE REQUEST**\n\n👤 **User:** {user_name} (`{user_id}`)\n🎬 **Movie:** `{req_movie}`"
    
    try:
        await client.send_message(ADMIN_ID, admin_text, reply_markup=InlineKeyboardMarkup(btn))
        await message.reply_text(f"✅ **Aapki request admin ko bhej di gayi hai!**\nMovie upload hote hi bot aapko notify kar dega.")
    except:
        await message.reply_text("❌ Error: Admin tak request nahi pahunchi.")
    raise StopPropagation

@app.on_message(filters.command("watchlist") & filters.private)
async def show_watchlist(client, message):
    if not await ensure_fsub(client, message): raise StopPropagation
    user_data = watchlist_col.find_one({"user_id": message.from_user.id})
    if not user_data or not user_data.get("movies"):
        await message.reply_text("📌 Aapki Watchlist khali hai! Kisi bhi movie ke aage '📌 Add Watchlist' dabayein.")
        raise StopPropagation
        
    text = "📌 **MY WATCHLIST** 📌\n\n"
    for idx, mid in enumerate(user_data["movies"][:20], 1):
        try:
            movie = movies_col.find_one({"_id": ObjectId(mid)})
            if movie: text += f"**{idx}.** `{movie['movie_name'].title()}`\n"
        except: pass
    await message.reply_text(text)
    raise StopPropagation

@app.on_message(filters.command("trending") & filters.private)
async def trending_movies(client, message):
    if not await ensure_fsub(client, message): raise StopPropagation
    top_movies = list(trending_col.find().sort("count", -1).limit(10))
    if not top_movies:
        await message.reply_text("📉 Abhi tak koi trending data nahi hai!")
        raise StopPropagation
    text = "📈 **TOP 10 TRENDING SEARCHES** 📈\n\n"
    for i, m in enumerate(top_movies, 1): text += f"**{i}.** `{m['query'].title()}` (🔥 {m['count']} Searches)\n"
    await message.reply_text(text)
    raise StopPropagation

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    if banned_col.find_one({"user_id": user_id}): return 
    save_user(user_id, message.from_user.first_name)
    if not await ensure_fsub(client, message): raise StopPropagation

    welcome_text = (
        f"👋 **Hᴇʏ, {message.from_user.first_name or 'User'}** ❞\n\n"
        f"🎬 **Mᴀɪɴ Eᴋ Aᴅᴠᴀɴᴄᴇ Mᴏᴠɪᴇ Bᴏᴛ HᴏᴏN!**\n\n"
        f"🔎 Kᴏɪ ʙʜɪ ᴍᴏᴠɪᴇ ʏᴀ ᴡᴇʙ sᴇʀɪᴇs ᴅᴏᴡɴʟᴏᴀᴅ ᴋᴀʀɴᴇ ᴋᴇ ʟɪʏᴇ ʙᴀs ᴜsᴋᴀ ɴᴀᴀᴍ ʟɪᴋʜ ᴋᴀʀ ʙʜᴇᴊᴇɪɴ.\n\n"
        f"👤 Profile check: `/profile`"
    )
    try: await message.reply_photo(photo=START_PIC, caption=welcome_text)
    except: await message.reply_text(welcome_text) 
    raise StopPropagation

# ==========================================
# 👑 ADMIN COMMANDS
# ==========================================
@app.on_message(filters.command("addvip") & filters.private & filters.user(ADMIN_ID))
async def add_vip(client, message):
    if len(message.command) > 1:
        try:
            uid = int(message.command[1])
            vip_col.update_one({"user_id": uid}, {"$set": {"user_id": uid}}, upsert=True)
            await message.reply_text(f"👑 ✅ User `{uid}` ab VIP ban gaya hai!")
        except: pass
    raise StopPropagation

@app.on_message(filters.command("rmvip") & filters.private & filters.user(ADMIN_ID))
async def remove_vip(client, message):
    if len(message.command) > 1:
        try:
            uid = int(message.command[1])
            vip_col.delete_one({"user_id": uid})
            await message.reply_text(f"❌ User `{uid}` ab VIP nahi raha.")
        except: pass
    raise StopPropagation

@app.on_message(filters.command("stats") & filters.private & filters.user(ADMIN_ID))
async def admin_stats(client, message):
    total_users = users_col.count_documents({})
    total_movies = movies_col.count_documents({})
    total_banned = banned_col.count_documents({})
    total_vip = vip_col.count_documents({})
    text = f"📊 **ADMIN DASHBOARD** 📊\n\n👥 **Total Users:** `{total_users}`\n🎬 **Total Files:** `{total_movies}`\n👑 **VIP Users:** `{total_vip}`\n🚫 **Spammers:** `{total_banned}`"
    await message.reply_text(text)
    raise StopPropagation

# ==========================================
# 3. 📁 AUTO-SAVE (Admin Lock)
# ==========================================
@app.on_message((filters.document | filters.video) & filters.private & filters.user(ADMIN_ID))
async def save_movie_to_db(client, message):
    try: copied_msg = await message.copy(DB_CHANNEL_ID)
    except:
        await message.reply_text("❌ Error: Bot ko Database channel mein admin banayein.")
        raise StopPropagation

    media = message.document or message.video
    exact_file_name = getattr(media, "file_name", None) or "movie_file.mp4"
    search_keyword = exact_file_name.lower()
    
    quality_tags, lang_tags, season_tags, episode_tags = [], [], [], []
    if "480p" in search_keyword: quality_tags.append("480p")
    if "720p" in search_keyword: quality_tags.append("720p")
    if "1080p" in search_keyword: quality_tags.append("1080p")
    if "4k" in search_keyword or "2160p" in search_keyword: quality_tags.append("4k")
    if "hindi" in search_keyword or "hin" in search_keyword: lang_tags.append("hindi")
    if "english" in search_keyword or "eng" in search_keyword: lang_tags.append("english")
    if "dual" in search_keyword: lang_tags.append("dual audio")
        
    for match in re.findall(r'\bs(\d+)|\bseason\s*(\d+)', search_keyword):
        season_tags.append(f"S{(match[0] or match[1]).zfill(2)}") 
    for ep in re.findall(r'\[?[eE]p?(?:isode)?\s*(\d+(?:\s*-\s*\d+)?)\]?', search_keyword):
        ep_clean = ep.replace(" ", "")
        episode_tags.append(f"E{ep_clean}" if '-' in ep_clean else f"E{ep_clean.zfill(2)}") 
    
    movies_col.insert_one({
        "movie_name": search_keyword, "file_name": exact_file_name, "message_id": copied_msg.id,
        "quality": quality_tags, "language": lang_tags, "season": list(set(season_tags)), "episode": list(set(episode_tags))
    })
    await message.reply_text(f"✅ **Save ho gayi!**\n📁 `{exact_file_name}`")
    raise StopPropagation

# ==========================================
# 4. 🔍 USER SEARCH
# ==========================================
@app.on_message(filters.text & filters.private & ~filters.bot & ~filters.command(["start", "stats", "broadcast", "trending", "addvip", "rmvip", "ai", "watchlist", "profile", "request"]))
async def search_movie(client, message):
    user_id = message.from_user.id
    
    if message.forward_date or message.forward_from: return
    if len(message.text) > 40: 
        await message.reply_text("❌ Kripya sirf movie ka chhota naam likhein (Max 40 letters).")
        return
        
    if banned_col.find_one({"user_id": user_id}): return 
    save_user(user_id, message.from_user.first_name)
    
    if not await ensure_fsub(client, message): raise StopPropagation

    search_query = message.text.lower().strip()
    safe_query = re.escape(search_query)
    
    users_col.update_one({"user_id": user_id}, {"$inc": {"searches": 1}})
    movies = list(movies_col.find({"movie_name": {"$regex": safe_query}}).limit(50))
    
    if not movies:
        all_names = movies_col.distinct("movie_name")
        close_matches = difflib.get_close_matches(search_query, all_names, n=3, cutoff=0.5)
        
        if close_matches:
            sugg = "\n".join([f"👉 `{m.title()}`" for m in close_matches])
            await message.reply_text(f"❌ **Nahi mila.**\n💡 **Kya aapka matlab inse tha?**\n{sugg}")
        else:
            await message.reply_text(f"❌ **Sorry, '{search_query[:20]}...' abhi available nahi hai.**")
        raise StopPropagation
        
    trending_col.update_one({"query": search_query}, {"$inc": {"count": 1}}, upsert=True)
    
    text = f"👋 **Hᴇʏ, {message.from_user.first_name}** ❞\n\n📁 **Files Found For -** `{message.text}`."
    
    buttons = []
    for movie in movies:
        mid = str(movie["_id"])
        buttons.append([InlineKeyboardButton(f"📁 {movie.get('file_name', 'File')}", callback_data=f"get_{mid}")])
        buttons.append([InlineKeyboardButton("📌 Add Watchlist", callback_data=f"wladd_{mid}")])
        
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    raise StopPropagation

async def auto_delete_task(client, chat_id, message_ids):
    await asyncio.sleep(600) 
    try: await client.delete_messages(chat_id, message_ids)
    except: pass

@app.on_callback_query()
async def button_click(client, query):
    data = query.data

    if data.startswith("reqdone_"):
        if query.from_user.id != ADMIN_ID: return
        target_user = int(data.split("_")[1])
        msg_text = query.message.text
        movie_name = "Requested Movie"
        for line in msg_text.split('\n'):
            if line.startswith("🎬 **Movie:**"):
                movie_name = line.split("`")[1]

        try:
            await client.send_message(target_user, f"🎉 **GOOD NEWS!**\nAapki request ki gayi movie **'{movie_name}'** upload ho chuki hai.\n\nAb aap aaram se bot me naam likhkar search kar sakte hain!")
            await query.message.edit_text(f"✅ **Request Fulfilled!**\nUser ko notification bhej diya gaya hai.\n\n{msg_text}")
        except:
            await query.answer("❌ User ne bot block kar diya hai.", show_alert=True)
            await query.message.edit_text(f"❌ **User Blocked Bot**\n\n{msg_text}")
        return

    if data == "verify_fsub":
        is_joined = await check_fsub(client, query.from_user.id)
        if is_joined:
            await query.answer("✅ Verification Successful! Ab aap movie search kar sakte hain.", show_alert=True)
            try: await query.message.delete()
            except: pass
        else:
            await query.answer("❌ Aapne abhi tak channel join nahi kiya hai. Pehle join karein!", show_alert=True)
        return

    if data.startswith("wladd_"):
        mid = data.split("_")[1]
        watchlist_col.update_one({"user_id": query.from_user.id}, {"$addToSet": {"movies": mid}}, upsert=True)
        await query.answer("📌 Watchlist me save ho gayi!", show_alert=True)
        return

    if data.startswith("get_"):
        mid = data.split("_")[1]
        movie = movies_col.find_one({"_id": ObjectId(mid)})
        if movie and "message_id" in movie:
            await query.answer("Sending File... 📤", show_alert=False)
            try:
                msg = await client.copy_message(chat_id=query.message.chat.id, from_chat_id=DB_CHANNEL_ID, message_id=movie["message_id"])
                if not vip_col.find_one({"user_id": query.from_user.id}) and query.from_user.id != ADMIN_ID:
                    w_msg = await query.message.reply_text("⚠️ **Note:** Yeh file 10 minute mein auto-delete ho jayegi!")
                    asyncio.create_task(auto_delete_task(client, query.message.chat.id, [msg.id, w_msg.id]))
            except Exception: 
                await query.message.reply_text("❌ Error: Channel se file fetch nahi ho payi.")
        else: await query.answer("Yeh purani file hai!", show_alert=True)

# ==========================================
# 🚀 RENDER PORT KEEPER + STABLE BOT RUNNER
# ==========================================
def run_port_server():
    port = int(os.environ.get("PORT", 10000))
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("0.0.0.0", port), handler) as httpd:
        print(f"Serving port keeper on port {port}")
        httpd.serve_forever()

if __name__ == "__main__":
    port_thread = threading.Thread(target=run_port_server, daemon=True)
    port_thread.start()
    
    print("🚀 CLASSIC STABLE MOVIE BOT IS RUNNING...")
    app.run()
