import re
import time
import asyncio
import aiohttp
import difflib  
import google.generativeai as genai 
from pyrogram import Client, filters, enums, StopPropagation
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
# 1. CREDENTIALS & SETUP
# ==========================================
BOT_TOKEN = "8600027374:AAFNGEkHzPKnCpRC-VRivArvRG3HtFrfiXc" 
ADMIN_ID = 6855375693
API_ID = 33056032
API_HASH = "4b04c50c2004752cee284a3f533a8dd3"
MONGO_URL = "mongodb+srv://Movie123:Yash123@cluster0.bi61te2.mongodb.net/?appName=Cluster0&compressors=zlib"
DB_CHANNEL_ID = -1004448866853 

FSUB_CHANNEL_ID = -1004442475534 
FSUB_CHANNEL_LINK = "https://t.me/+KAQT3ciLAfExMTY1" 
START_PIC = "https://telegra.ph/file/a7cc9bb4cf0d6c8e3cc50.jpg" 
OMDB_API_KEY = "ec736b29" 
GEMINI_API_KEY = "AQ.Ab8RN6J8twzki-2L29lpbYLWkzhj0SOMbwzZOZu1WahyewmKig" 

mongo_client = MongoClient(MONGO_URL)
db = mongo_client["MovieBot"]
movies_col = db["Movies"]
users_col = db["Users"] 
banned_col = db["BannedUsers"]
trending_col = db["Trending"] 
vip_col = db["VIPUsers"]      
watchlist_col = db["Watchlist"] 

app = Client("ProMovieBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
SPAM_TRACKER = {}

if GEMINI_API_KEY != "YOUR_GEMINI_API_KEY":
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')

# ==========================================
# ⚡ AUTO-APPROVE & HELPERS
# ==========================================
@app.on_chat_join_request(filters.chat(FSUB_CHANNEL_ID))
async def approve_join_req(client, message):
    try:
        await client.approve_chat_join_request(chat_id=message.chat.id, user_id=message.from_user.id)
        await client.send_message(message.from_user.id, "✅ **Aapki join request accept ho gayi hai! Ab aap bot me movie search kar sakte hain.**")
    except:
        pass

async def check_fsub(client, user_id):
    if not FSUB_CHANNEL_ID or FSUB_CHANNEL_ID == -1000000000000: return True 
    try:
        member = await client.get_chat_member(FSUB_CHANNEL_ID, user_id)
        if member.status in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED]: return False
        return True
    except:
        return False

def save_user(user_id, name):
    if not users_col.find_one({"user_id": user_id}):
        users_col.insert_one({"user_id": user_id, "name": name})

async def get_imdb_info(query):
    url = f"http://www.omdbapi.com/?t={query}&apikey={OMDB_API_KEY}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                if data.get("Response") == "True": return data
    except:
        return None

# ==========================================
# 🛠️ MENU SETUP COMMAND (Auto Menu Creation)
# ==========================================
@app.on_message(filters.command("setmenu") & filters.private & filters.user(ADMIN_ID))
async def set_bot_menus(client, message):
    user_commands = [
        BotCommand("start", "Bot ko restart karein"),
        BotCommand("ai", "🤖 AI Movie Buddy"),
        BotCommand("trending", "📈 Top 10 Searches"),
        BotCommand("watchlist", "📌 My Saved Movies")
    ]
    await client.set_bot_commands(user_commands, scope=BotCommandScopeDefault())
    
    admin_commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("stats", "📊 Bot Statistics"),
        BotCommand("broadcast", "📢 Send Message to All"),
        BotCommand("addvip", "👑 Add VIP User"),
        BotCommand("rmvip", "❌ Remove VIP User"),
        BotCommand("ai", "🤖 AI Movie Buddy"),
        BotCommand("trending", "📈 Top 10 Searches"),
        BotCommand("watchlist", "📌 My Saved Movies")
    ]
    await client.set_bot_commands(admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
    await message.reply_text("✅ **Menu Set Successfully!**\nAb aapko Admin wale commands dikhenge aur baaki users ko sirf unke commands.")
    raise StopPropagation

# ==========================================
# 🤖 AI & COMMANDS
# ==========================================
@app.on_message(filters.command("ai") & filters.private)
async def ai_recommender(client, message):
    if len(message.command) < 2:
        await message.reply_text("🤖 **AI Movie Buddy**\n\nMujhse kuch bhi recommend karne ko kahein!\n**Example:** `/ai Suggest some best mind-bending thriller movies of 2023`")
        raise StopPropagation
        
    query = message.text.split(" ", 1)[1]
    wait_msg = await message.reply_text("🤖 _Thinking... (Dhoondh raha hoon)_")
    try:
        prompt = f"Act as a movie recommender bot. Suggest 3 movies based on this request: '{query}'. Briefly explain why they fit. Keep it short and engaging."
        response = ai_model.generate_content(prompt)
        await wait_msg.edit_text(f"🤖 **AI Suggestions:**\n\n{response.text}\n\n_In movies ko download karne ke liye normal search karein!_")
    except:
        await wait_msg.edit_text("❌ AI server thoda busy hai, baad me try karein.")
    raise StopPropagation

@app.on_message(filters.command("watchlist") & filters.private)
async def show_watchlist(client, message):
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
    top_movies = list(trending_col.find().sort("count", -1).limit(10))
    if not top_movies:
        await message.reply_text("📉 Abhi tak koi trending data nahi hai!")
        raise StopPropagation
    text = "📈 **TOP 10 TRENDING SEARCHES** 📈\n\n"
    for i, m in enumerate(top_movies, 1): text += f"**{i}.** `{m['query'].title()}` (🔥 {m['count']} Searches)\n"
    await message.reply_text(text)
    raise StopPropagation

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

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    if banned_col.find_one({"user_id": user_id}): return 
    save_user(user_id, message.from_user.first_name)
    
    if not await check_fsub(client, user_id):
        btn = [
            [InlineKeyboardButton("📢 Join Our Channel", url=FSUB_CHANNEL_LINK)],
            [InlineKeyboardButton("✅ Verify", callback_data="verify_fsub")]
        ]
        await message.reply_text("⚠️ **Wait! Pehle hamara official channel join karein, uske baad 'Verify' dabayein!**", reply_markup=InlineKeyboardMarkup(btn))
        raise StopPropagation

    welcome_text = (
        f"👋 **Hᴇʏ, {message.from_user.first_name or 'User'}** ❞\n\n"
        f"🎬 **Mᴀɪɴ Eᴋ Aᴅᴠᴀɴᴄᴇ Mᴏᴠɪᴇ Bᴏᴛ Hᴏᴏɴ!**\n\n"
        f"🔎 Kᴏɪ ʙʜɪ ᴍᴏᴠɪᴇ ʏᴀ ᴡᴇʙ sᴇʀɪᴇs ᴅᴏᴡɴʟᴏᴀᴅ ᴋᴀʀɴᴇ ᴋᴇ ʟɪʏᴇ ʙᴀs ᴜsᴋᴀ ɴᴀᴀᴍ ʟɪᴋʜ ᴋᴀʀ ʙʜᴇᴊᴇɪɴ.\n\n"
        f"🤖 AI Recommendation: `/ai <movie>`\n📈 Trending: `/trending`"
    )
    try: await message.reply_photo(photo=START_PIC, caption=welcome_text)
    except: await message.reply_text(welcome_text) 
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

@app.on_message(filters.command("broadcast") & filters.private & filters.user(ADMIN_ID) & filters.reply)
async def admin_broadcast(client, message):
    users = list(users_col.find({}))
    await message.reply_text(f"🚀 Broadcast started for {len(users)} users...")
    success = 0
    for user in users:
        try:
            await message.reply_to_message.copy(user["user_id"])
            success += 1
            await asyncio.sleep(0.5) 
        except: pass
    await message.reply_text(f"✅ **Broadcast Complete!**\nSuccessfully sent to {success} out of {len(users)} users.")
    raise StopPropagation

# ==========================================
# 3. AUTO-SAVE (Admin Lock)
# ==========================================
@app.on_message((filters.document | filters.video) & filters.private & filters.user(ADMIN_ID))
async def save_movie_to_db(client, message):
    try: copied_msg = await message.copy(DB_CHANNEL_ID)
    except:
        await message.reply_text("❌ Error: Bot ko Database channel mein admin banayein.")
        raise StopPropagation

    exact_file_name = getattr(message.document or message.video, "file_name", "movie_file.mp4")
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
# 4. USER SEARCH
# ==========================================
@app.on_message(filters.text & filters.private & ~filters.bot & ~filters.command(["start", "stats", "broadcast", "trending", "addvip", "rmvip", "ai", "watchlist", "setmenu"]))
async def search_movie(client, message):
    user_id = message.from_user.id
    
    if message.forward_date or message.forward_from: return
    if len(message.text) > 40: 
        await message.reply_text("❌ Kripya sirf movie ka chhota naam likhein (Max 40 letters).")
        return
        
    is_vip = vip_col.find_one({"user_id": user_id})
    if banned_col.find_one({"user_id": user_id}): return 
        
    if user_id != ADMIN_ID and not is_vip:
        curr_time = time.time()
        if user_id in SPAM_TRACKER:
            SPAM_TRACKER[user_id] = [t for t in SPAM_TRACKER[user_id] if curr_time - t < 5]
            if len(SPAM_TRACKER[user_id]) >= 5:
                banned_col.insert_one({"user_id": user_id})
                await message.reply_text("🚫 **BANNED!** Aapne spam kiya hai.")
                raise StopPropagation
            elif len(SPAM_TRACKER[user_id]) >= 3:
                SPAM_TRACKER[user_id].append(curr_time)
                await message.reply_text("⚠️ **WARNING:** Dheere type karein!")
                raise StopPropagation
            else: SPAM_TRACKER[user_id].append(curr_time)
        else: SPAM_TRACKER[user_id] = [curr_time]

    save_user(user_id, message.from_user.first_name)
    if not await check_fsub(client, user_id):
        btn = [
            [InlineKeyboardButton("📢 Join Our Channel", url=FSUB_CHANNEL_LINK)],
            [InlineKeyboardButton("✅ Verify", callback_data="verify_fsub")]
        ]
        await message.reply_text("⚠️ **Pehle hamara official channel join karein, fir 'Verify' dabayein!**", reply_markup=InlineKeyboardMarkup(btn))
        raise StopPropagation

    search_query = message.text.lower().strip()
    safe_query = re.escape(search_query)
    movies = list(movies_col.find({"movie_name": {"$regex": safe_query}}).limit(50))
    
    if not movies:
        all_names = movies_col.distinct("movie_name")
        close_matches = difflib.get_close_matches(search_query, all_names, n=3, cutoff=0.5)
        req_btn = [[InlineKeyboardButton("📩 Request to Admin", url="https://t.me/JUNVALBOT")]]
        
        if close_matches:
            sugg = "\n".join([f"👉 `{m.title()}`" for m in close_matches])
            await message.reply_text(f"❌ **Nahi mila.**\n💡 **Kya aapka matlab inse tha?**\n{sugg}", reply_markup=InlineKeyboardMarkup(req_btn))
        else:
            await message.reply_text(f"❌ **Sorry, '{search_query[:20]}...' abhi available nahi hai.**", reply_markup=InlineKeyboardMarkup(req_btn))
        raise StopPropagation
        
    trending_col.update_one({"query": search_query}, {"$inc": {"count": 1}}, upsert=True)
    
    imdb_data = await get_imdb_info(search_query)
    if imdb_data:
        text = f"👋 **Hᴇʏ, {message.from_user.first_name}** ❞\n\n🎬 **{imdb_data.get('Title', '')} ({imdb_data.get('Year', '')})**\n⭐ IMDb: {imdb_data.get('imdbRating', 'N/A')}/10\n📖 {imdb_data.get('Plot', '')}\n\n📁 **Files Found:**"
    else:
        text = f"👋 **Hᴇʏ, {message.from_user.first_name}** ❞\n\n📁 **Files Found For -** `{message.text}`."
    
    buttons = [
        [InlineKeyboardButton("✨ PIXEL", callback_data=f"filter_pixel_{search_query}"), InlineKeyboardButton("🗣 LANGUAGE", callback_data=f"filter_lang_{search_query}")],
        [InlineKeyboardButton("🎬 SEASON", callback_data=f"filter_season_{search_query}"), InlineKeyboardButton("📺 EPISODE", callback_data=f"filter_episode_{search_query}")]
    ]
    if len(movies) > 1: buttons.append([InlineKeyboardButton("📥 Sᴇɴᴅ Aʟʟ Fɪʟᴇs 📥", callback_data=f"sendall_{search_query}")])
    
    for movie in movies:
        mid = str(movie["_id"])
        buttons.append([InlineKeyboardButton(f"📁 {movie.get('file_name', 'File')}", callback_data=f"get_{mid}")])
        buttons.append([InlineKeyboardButton("📌 Add to Watchlist", callback_data=f"wladd_{mid}")])
        
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    raise StopPropagation

async def auto_delete_task(client, chat_id, message_ids):
    await asyncio.sleep(600) 
    try: await client.delete_messages(chat_id, message_ids)
    except: pass

@app.on_callback_query()
async def button_click(client, query):
    data = query.data

    if data == "verify_fsub":
        is_joined = await check_fsub(client, query.from_user.id)
        if is_joined:
            await query.answer("✅ Verification Successful! Ab aap movie search kar sakte hain.", show_alert=True)
            welcome_text = (
                f"👋 **Hᴇʏ, {query.from_user.first_name or 'User'}** ❞\n\n"
                f"🎬 **Mᴀɪɴ Eᴋ Aᴅᴠᴀɴᴄᴇ Mᴏᴠɪᴇ Bᴏᴛ Hᴏᴏɴ!**\n\n"
                f"🔎 Kᴏɪ ʙʜɪ ᴍᴏᴠɪᴇ ʏᴀ ᴡᴇʙ sᴇʀɪᴇs ᴅᴏᴡɴʟᴏᴀᴅ ᴋᴀʀɴᴇ ᴋᴇ ʟɪʏᴇ ʙᴀs ᴜsᴋᴀ ɴᴀᴀᴍ ʟɪᴋʜ ᴋᴀʀ ʙʜᴇᴊᴇɪɴ.\n\n"
                f"🤖 AI Recommendation: `/ai <movie>`\n📈 Trending: `/trending`"
            )
            try: await query.message.reply_photo(photo=START_PIC, caption=welcome_text)
            except: await query.message.reply_text(welcome_text) 
            await query.message.delete()
        else:
            await query.answer("❌ Aapne abhi tak channel join nahi kiya hai. Pehle join karein!", show_alert=True)
        return

    if data.startswith("wladd_"):
        mid = data.split("_")[1]
        watchlist_col.update_one({"user_id": query.from_user.id}, {"$addToSet": {"movies": mid}}, upsert=True)
        await query.answer("📌 Watchlist me save ho gayi! Dekhne ke liye /watchlist bhejein.", show_alert=True)
        return

    if data.startswith("filter_pixel_"):
        sq = data.split("_", 2)[2]
        btns = [
            [InlineKeyboardButton("480p", callback_data=f"apply_pixel_480p_{sq}"), InlineKeyboardButton("720p", callback_data=f"apply_pixel_720p_{sq}")],
            [InlineKeyboardButton("1080p", callback_data=f"apply_pixel_1080p_{sq}"), InlineKeyboardButton("4K", callback_data=f"apply_pixel_4k_{sq}")],
            [InlineKeyboardButton("🔙 Back", callback_data=f"back_{sq}")]
        ]
        await query.message.edit_reply_markup(InlineKeyboardMarkup(btns))
        
    elif data.startswith("filter_lang_"):
        sq = data.split("_", 2)[2]
        btns = [
            [InlineKeyboardButton("Hindi", callback_data=f"apply_lang_hindi_{sq}"), InlineKeyboardButton("English", callback_data=f"apply_lang_english_{sq}")],
            [InlineKeyboardButton("Dual Audio", callback_data=f"apply_lang_dual audio_{sq}")],
            [InlineKeyboardButton("🔙 Back", callback_data=f"back_{sq}")]
        ]
        await query.message.edit_reply_markup(InlineKeyboardMarkup(btns))
        
    elif data.startswith("filter_season_"):
        sq = data.split("_", 2)[2]
        movies = list(movies_col.find({"movie_name": {"$regex": re.escape(sq)}}).limit(50))
        seasons = sorted(list({s for m in movies if "season" in m for s in m["season"]}))
        if not seasons: return await query.answer("❌ Season filter nahi mila!", show_alert=True)
        btns = [[InlineKeyboardButton(s, callback_data=f"apply_season_{s}_{sq}")] for s in seasons]
        btns.append([InlineKeyboardButton("🔙 Back", callback_data=f"back_{sq}")])
        await query.message.edit_reply_markup(InlineKeyboardMarkup(btns))
        
    elif data.startswith("filter_episode_"):
        sq = data.split("_", 2)[2]
        movies = list(movies_col.find({"movie_name": {"$regex": re.escape(sq)}}).limit(50))
        episodes = sorted(list({e for m in movies if "episode" in m for e in m["episode"]}))
        if not episodes: return await query.answer("❌ Episode filter nahi mila!", show_alert=True)
        btns = [[InlineKeyboardButton(e, callback_data=f"apply_episode_{e}_{sq}")] for e in episodes]
        btns.append([InlineKeyboardButton("🔙 Back", callback_data=f"back_{sq}")])
        await query.message.edit_reply_markup(InlineKeyboardMarkup(btns))
        
    elif data.startswith("apply_"):
        parts = data.split("_", 3)
        movies = list(movies_col.find({"movie_name": {"$regex": re.escape(parts[3])}, parts[1]: parts[2]}).limit(50))
        if not movies: return await query.answer("❌ File nahi mili!", show_alert=True)
        buttons = [[InlineKeyboardButton("🔙 Back", callback_data=f"back_{parts[3]}")]]
        for m in movies:
            mid = str(m["_id"])
            buttons.append([InlineKeyboardButton(f"📁 {m.get('file_name', 'File')}", callback_data=f"get_{mid}")])
            buttons.append([InlineKeyboardButton("📌 Add Watchlist", callback_data=f"wladd_{mid}")])
        await query.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
        
    elif data.startswith("back_"):
        sq = data.split("_", 1)[1]
        movies = list(movies_col.find({"movie_name": {"$regex": re.escape(sq)}}).limit(50))
        buttons = [
            [InlineKeyboardButton("✨ PIXEL", callback_data=f"filter_pixel_{sq}"), InlineKeyboardButton("🗣 LANGUAGE", callback_data=f"filter_lang_{sq}")],
            [InlineKeyboardButton("🎬 SEASON", callback_data=f"filter_season_{sq}"), InlineKeyboardButton("📺 EPISODE", callback_data=f"filter_episode_{sq}")]
        ]
        if len(movies) > 1: buttons.append([InlineKeyboardButton("📥 Sᴇɴᴅ Aʟʟ Fɪʟᴇs 📥", callback_data=f"sendall_{sq}")])
        for m in movies:
            mid = str(m["_id"])
            buttons.append([InlineKeyboardButton(f"📁 {m.get('file_name', 'File')}", callback_data=f"get_{mid}")])
            buttons.append([InlineKeyboardButton("📌 Add Watchlist", callback_data=f"wladd_{mid}")])
        await query.message.edit_reply_markup(InlineKeyboardMarkup(buttons))

    elif data.startswith("get_"):
        mid = data.split("_")[1]
        movie = movies_col.find_one({"_id": ObjectId(mid)})
        if movie and "message_id" in movie:
            await query.answer("Sending File... 📤", show_alert=False)
            await client.send_chat_action(query.message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
            try:
                msg = await client.copy_message(chat_id=query.message.chat.id, from_chat_id=DB_CHANNEL_ID, message_id=movie["message_id"])
                if not vip_col.find_one({"user_id": query.from_user.id}) and query.from_user.id != ADMIN_ID:
                    w_msg = await query.message.reply_text("⚠️ **Note:** Yeh file 10 minute mein auto-delete ho jayegi!")
                    asyncio.create_task(auto_delete_task(client, query.message.chat.id, [msg.id, w_msg.id]))
            except: await query.message.reply_text("❌ Error: Channel se file fetch nahi ho payi.")
        else: await query.answer("Yeh purani file hai!", show_alert=True)
            
    elif data.startswith("sendall_"):
        sq = data.split("_", 1)[1]
        movies = list(movies_col.find({"movie_name": {"$regex": re.escape(sq)}}).limit(50))
        await query.answer(f"Sending {len(movies)} files... 📤", show_alert=False)
        sent_ids = []
        for m in movies:
            if "message_id" in m:
                try:
                    msg = await client.copy_message(chat_id=query.message.chat.id, from_chat_id=DB_CHANNEL_ID, message_id=m["message_id"])
                    sent_ids.append(msg.id)
                    await asyncio.sleep(0.5) 
                except: continue
        if sent_ids and not vip_col.find_one({"user_id": query.from_user.id}) and query.from_user.id != ADMIN_ID:
            w_msg = await query.message.reply_text("⚠️ **Note:** Yeh sabhi files 10 minute mein auto-delete ho jayengi!")
            sent_ids.append(w_msg.id)
            asyncio.create_task(auto_delete_task(client, query.message.chat.id, sent_ids))

if __name__ == "__main__":
    print("🚀 Ultimate VIP Bot is Alive (Menu Auto-Setup Added)...")
    app.run()
