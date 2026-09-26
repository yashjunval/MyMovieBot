import re
import time
import asyncio
import aiohttp
import difflib  
import threading
import os
import google.generativeai as genai 
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import uvicorn

from pyrogram import Client, filters, enums, StopPropagation
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    WebAppInfo,
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
OMDB_API_KEY = "ec736b29" 
GEMINI_API_KEY = "AQ.Ab8RN6JREi500rTtVQHd0EHnxEdMZ6CedGiOB-O-XNtOn8tpAw" 

# ✅ Exact Live Render URL
WEBAPP_URL = "https://mymoviebot-1-u4v3.onrender.com"

mongo_client = MongoClient(MONGO_URL)
db = mongo_client["MovieBot"]
movies_col = db["Movies"]
users_col = db["Users"] 
banned_col = db["BannedUsers"]
trending_col = db["Trending"] 
vip_col = db["VIPUsers"]      
watchlist_col = db["Watchlist"] 

app = Client("ProMovieBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
web_app = FastAPI()
SPAM_TRACKER = {}

try:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    print("AI Setup Error:", e)

# ==========================================
# 🌐 TELEGRAM MINI APP (NETFLIX STYLE HTML)
# ==========================================
MINI_APP_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🎬 NetFlix Movie Hub</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #141414; color: #ffffff; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .netflix-red { background-color: #E50914; }
        .netflix-red:hover { background-color: #b20710; }
    </style>
</head>
<body class="pb-20">
    <header class="p-4 bg-black/80 sticky top-0 z-50 flex justify-between items-center border-b border-zinc-800">
        <h1 class="text-xl font-bold text-red-600 tracking-wider">NETFLIX MOVIES</h1>
        <div id="username" class="text-xs text-zinc-400">Loading...</div>
    </header>

    <div class="p-4">
        <input type="text" id="search" placeholder="Search movies, series..." 
            class="w-full p-3 rounded-lg bg-zinc-900 border border-zinc-700 text-white focus:outline-none focus:border-red-600"
            oninput="searchMovies()">
    </div>

    <main class="p-4 grid grid-cols-2 gap-4" id="movie-grid"></main>

    <nav class="fixed bottom-0 left-0 right-0 bg-black border-t border-zinc-800 flex justify-around p-3 z-50">
        <button onclick="loadHome()" class="text-red-600 font-semibold">🏠 Home</button>
        <button onclick="alert('Watchlist active in bot!')" class="text-zinc-400">📌 Watchlist</button>
        <button onclick="alert('VIP Dashboard')" class="text-zinc-400">👤 Profile</button>
    </nav>

    <script>
        let tg = window.Telegram.WebApp;
        tg.expand();
        if(tg.initDataUnsafe && tg.initDataUnsafe.user) {
            document.getElementById('username').innerText = "Hi, " + tg.initDataUnsafe.user.first_name;
        }

        async function loadHome() {
            let res = await fetch('/api/movies');
            let movies = await res.json();
            let grid = document.getElementById('movie-grid');
            grid.innerHTML = '';
            movies.forEach(m => {
                grid.innerHTML += `
                    <div class="bg-zinc-900 rounded-lg p-2 border border-zinc-800 flex flex-col justify-between">
                        <div>
                            <div class="h-32 bg-zinc-800 rounded mb-2 flex items-center justify-center text-zinc-500 font-bold">🎬 MOVIE</div>
                            <h3 class="text-sm font-bold truncate">${m.movie_name}</h3>
                        </div>
                        <button onclick="getMovie('${m._id}')" class="mt-2 w-full netflix-red text-white py-1.5 rounded text-xs font-semibold">Get File</button>
                    </div>
                `;
            });
        }

        async function searchMovies() {
            let query = document.getElementById('search').value;
            if(query.length < 2) { loadHome(); return; }
            let res = await fetch('/api/search?q=' + query);
            let movies = await res.json();
            let grid = document.getElementById('movie-grid');
            grid.innerHTML = '';
            movies.forEach(m => {
                grid.innerHTML += `
                    <div class="bg-zinc-900 rounded-lg p-2 border border-zinc-800 flex flex-col justify-between">
                        <div>
                            <div class="h-32 bg-zinc-800 rounded mb-2 flex items-center justify-center text-zinc-500 font-bold">🎬 MOVIE</div>
                            <h3 class="text-sm font-bold truncate">${m.movie_name}</h3>
                        </div>
                        <button onclick="getMovie('${m._id}')" class="mt-2 w-full netflix-red text-white py-1.5 rounded text-xs font-semibold">Get File</button>
                    </div>
                `;
            });
        }

        function getMovie(id) {
            tg.sendData(id);
            tg.close();
        }

        loadHome();
    </script>
</body>
</html>
"""

@web_app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return MINI_APP_HTML

@web_app.get("/api/movies")
async def api_movies():
    movies = list(movies_col.find().limit(20))
    for m in movies: m["_id"] = str(m["_id"])
    return movies

@web_app.get("/api/search")
async def api_search(q: str):
    movies = list(movies_col.find({"movie_name": {"$regex": re.escape(q), "$options": "i"}}).limit(20))
    for m in movies: m["_id"] = str(m["_id"])
    return movies

# ==========================================
# ⚡ FORCE SUB & HELPERS
# ==========================================
@app.on_chat_join_request(filters.chat(FSUB_CHANNEL_ID))
async def approve_join_req(client, message):
    try:
        await client.approve_chat_join_request(chat_id=message.chat.id, user_id=message.from_user.id)
        await client.send_message(message.from_user.id, "✅ **Aapki join request accept ho gayi hai!**")
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
        [InlineKeyboardButton("📢 Join Channel", url=FSUB_CHANNEL_LINK)],
        [InlineKeyboardButton("✅ Verify", callback_data="verify_fsub")]
    ]
    await message.reply_text("⚠️ **Pehle hamara official channel join karein, fir 'Verify' dabayein!**", reply_markup=InlineKeyboardMarkup(btn))
    return False

def save_user(user_id, name):
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({"user_id": user_id, "name": name, "searches": 0})

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    if banned_col.find_one({"user_id": user_id}): return 
    save_user(user_id, message.from_user.first_name)
    if not await ensure_fsub(client, message): raise StopPropagation

    btn = [
        [InlineKeyboardButton("🚀 Open Netflix Mini App", web_app=WebAppInfo(url=WEBAPP_URL))],
        [InlineKeyboardButton("📌 My Watchlist", callback_data="show_wl")]
    ]

    welcome_text = (
        f"👋 **Hᴇʏ, {message.from_user.first_name or 'User'}** ❞\n\n"
        f"🎬 **Mᴀɪɴ Eᴋ Aᴅᴠᴀɴᴄᴇ Mᴏᴠɪᴇ Bᴏᴛ Hᴏᴏɴ!**\n"
        f"Neeche diye gaye button se hamara **Mini App** kholkar seedhe Netflix style mein movies dekhein!\n\n"
        f"🔎 Ya koi bhi movie ka naam direct likhkar bhejein."
    )
    try: await message.reply_photo(photo=START_PIC, caption=welcome_text, reply_markup=InlineKeyboardMarkup(btn))
    except: await message.reply_text(welcome_text, reply_markup=InlineKeyboardMarkup(btn)) 
    raise StopPropagation

@app.on_message(filters.private)
async def receive_webapp_data(client, message):
    if not message.web_app_data:
        return
    mid = message.web_app_data.data
    try:
        movie = movies_col.find_one({"_id": ObjectId(mid)})
        if movie and "message_id" in movie:
            await client.send_chat_action(message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
            msg = await client.copy_message(chat_id=message.chat.id, from_chat_id=DB_CHANNEL_ID, message_id=movie["message_id"])
            if not vip_col.find_one({"user_id": message.from_user.id}) and message.from_user.id != ADMIN_ID:
                w_msg = await message.reply_text("⚠️ **Note:** Yeh file 10 minute mein auto-delete ho jayegi!")
                asyncio.create_task(auto_delete_task(client, message.chat.id, [msg.id, w_msg.id]))
        else:
            await message.reply_text("❌ Yeh movie nahi mili.")
    except:
        await message.reply_text("❌ Error fetching file.")
    raise StopPropagation

async def auto_delete_task(client, chat_id, message_ids):
    await asyncio.sleep(600) 
    try: await client.delete_messages(chat_id, message_ids)
    except: pass

@app.on_message(filters.text & filters.private & ~filters.bot)
async def search_movie(client, message):
    if message.text.startswith("/"): return
    user_id = message.from_user.id
    if not await ensure_fsub(client, message): raise StopPropagation

    search_query = message.text.lower().strip()
    movies = list(movies_col.find({"movie_name": {"$regex": re.escape(search_query)}}).limit(20))
    
    if not movies:
        await message.reply_text(f"❌ **Sorry, '{search_query[:20]}' available nahi hai.**\n\n📝 Request karne ke liye type karein:\n`/request {search_query}`")
        return
        
    text = f"📁 **Files Found For -** `{message.text}`:"
    buttons = []
    for movie in movies:
        mid = str(movie["_id"])
        buttons.append([InlineKeyboardButton(f"📁 {movie.get('file_name', 'File')}", callback_data=f"get_{mid}")])
        
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    raise StopPropagation

@app.on_callback_query()
async def button_click(client, query):
    data = query.data
    if data == "verify_fsub":
        if await check_fsub(client, query.from_user.id):
            await query.answer("✅ Verified Successfully!", show_alert=True)
            await query.message.delete()
        else:
            await query.answer("❌ Channel join nahi kiya!", show_alert=True)
        return
    
    if data.startswith("get_"):
        mid = data.split("_")[1]
        movie = movies_col.find_one({"_id": ObjectId(mid)})
        if movie and "message_id" in movie:
            await query.answer("Sending File...", show_alert=False)
            await client.copy_message(chat_id=query.message.chat.id, from_chat_id=DB_CHANNEL_ID, message_id=movie["message_id"])

# ==========================================
# 🚀 SAFE THREADED BOT & PORT RUNNER (FIXED)
# ==========================================
def run_telegram_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def main_bot():
        await app.start()
        print("🚀 Telegram Bot started successfully in background thread...")
        # Keep the bot running infinitely without using main thread signals
        while True:
            await asyncio.sleep(3600)

    loop.run_until_complete(main_bot())

if __name__ == "__main__":
    # Telegram Bot ko background thread me chalayein
    t = threading.Thread(target=run_telegram_bot, daemon=True)
    t.start()
    
    # FastAPI/Uvicorn ko main process me chalayein taaki Render port detect kar sake
    port = int(os.environ.get("PORT", 10000))
    print(f"🚀 Starting Netflix Mini App on port {port}...")
    uvicorn.run(web_app, host="0.0.0.0", port=port, log_level="warning")
