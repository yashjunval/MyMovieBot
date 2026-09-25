from pyrogram import Client, filters, enums, StopPropagation
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from bson.objectid import ObjectId

# ==========================================
# 1. BOT CREDENTIALS & SETUP
# ==========================================
BOT_TOKEN = "8600027374:AAEWjWAV5xghoaC-elK0zSyTILLvVjvst0k" 
API_ID = 33056032
API_HASH = "4b04c50c2004752cee284a3f533a8dd3"
MONGO_URL = "mongodb+srv://Movie123:Yash123@cluster0.bi61te2.mongodb.net/?appName=Cluster0&compressors=zlib"

mongo_client = MongoClient(MONGO_URL)
db = mongo_client["MovieBot"]
movies_col = db["Movies"]

app = Client("ProMovieBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# ==========================================
# 2. START COMMAND (Spam Blocker Added)
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_name = message.from_user.first_name
    welcome_text = (
        f"👋 **Hᴇʏ, {user_name}** ❞\n\n"
        f"🎬 **Mᴀɪɴ Eᴋ Aᴅᴠᴀɴᴄᴇ Mᴏᴠɪᴇ Bᴏᴛ Hᴏᴏɴ!**\n\n"
        f"🔎 Kᴏɪ ʙʜɪ ᴍᴏᴠɪᴇ ʏᴀ ᴡᴇʙ sᴇʀɪᴇs ᴅᴏᴡɴʟᴏᴀᴅ ᴋᴀʀɴᴇ ᴋᴇ ʟɪʏᴇ ʙᴀs ᴜsᴋᴀ ɴᴀᴀᴍ ʟɪᴋʜ ᴋᴀʀ ʙʜᴇᴊᴇɪɴ."
    )
    await message.reply_text(welcome_text)
    raise StopPropagation # Spam rokne ke liye

# ==========================================
# 3. AUTO-SAVE & SMART TAG SCANNER
# ==========================================
@app.on_message((filters.document | filters.video) & filters.private)
async def save_movie_to_db(client, message):
    if not message.caption:
        await message.reply_text("❌ Kripya caption mein chhota search keyword likhein (eg: spiderman)")
        return
        
    search_keyword = message.caption.lower().strip()
    media = message.document or message.video
    exact_file_name = getattr(media, "file_name", f"{search_keyword}_file.mp4")
    
    # Auto-detect Quality and Language from File Name
    name_lower = exact_file_name.lower()
    quality_tags = []
    if "480p" in name_lower: quality_tags.append("480p")
    if "720p" in name_lower: quality_tags.append("720p")
    if "1080p" in name_lower: quality_tags.append("1080p")
    if "4k" in name_lower or "2160p" in name_lower: quality_tags.append("4k")
    
    lang_tags = []
    if "hindi" in name_lower or "hin" in name_lower: lang_tags.append("hindi")
    if "english" in name_lower or "eng" in name_lower: lang_tags.append("english")
    if "dual" in name_lower: lang_tags.append("dual audio")
    
    movies_col.insert_one({
        "movie_name": search_keyword,
        "file_name": exact_file_name,
        "file_id": media.file_id,
        "quality": quality_tags,
        "language": lang_tags
    })
    
    await message.reply_text(f"✅ **Movie Saved & Scanned!**\n🔎 `{search_keyword}`\n📁 `{exact_file_name}`")
    raise StopPropagation

# ==========================================
# 4. USER SEARCH & DYNAMIC FILTER UI
# ==========================================
@app.on_message(filters.text & filters.private & ~filters.command("start"))
async def search_movie(client, message):
    search_query = message.text.lower().strip()
    movies = list(movies_col.find({"movie_name": {"$regex": search_query}}))
    
    if not movies:
        await message.reply_text("❌ **Sorry, yeh movie abhi available nahi hai. Spelling check karein.**")
        raise StopPropagation
        
    user_name = message.from_user.first_name
    text = f"👋 **Hᴇʏ, {user_name}** ❞\n\n📁 **Hᴇʀᴇ I Fᴏᴜɴᴅ Fᴏʀ Yᴏᴜʀ Sᴇᴀʀᴄʜ -** `{message.text}`."
    
    buttons = []
    buttons.append([
        InlineKeyboardButton("✨ PIXEL", callback_data=f"filter_pixel_{search_query}"),
        InlineKeyboardButton("🗣 LANGUAGE", callback_data=f"filter_lang_{search_query}"),
        InlineKeyboardButton("🎬 SEASON", callback_data="dummy_season")
    ])
    
    if len(movies) > 1:
        buttons.append([
            InlineKeyboardButton("📥 Sᴇɴᴅ Aʟʟ Fɪʟᴇs 📥", callback_data=f"sendall_{search_query}")
        ])
    
    for movie in movies:
        movie_id = str(movie["_id"])
        exact_file_name = movie.get("file_name", "Movie File")
        buttons.append([
            InlineKeyboardButton(f"📁 {exact_file_name}", callback_data=f"get_{movie_id}")
        ])
        
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    raise StopPropagation

# ==========================================
# 5. BUTTON CLICKS & LIVE FILTER LOGIC
# ==========================================
@app.on_callback_query()
async def button_click(client, query):
    data = query.data
    
    # FILTER MENUS (Pixel & Language)
    if data.startswith("filter_pixel_"):
        search_query = data.split("_", 2)[2]
        btns = [
            [InlineKeyboardButton("480p", callback_data=f"apply_pixel_480p_{search_query}"),
             InlineKeyboardButton("720p", callback_data=f"apply_pixel_720p_{search_query}")],
            [InlineKeyboardButton("1080p", callback_data=f"apply_pixel_1080p_{search_query}"),
             InlineKeyboardButton("4K", callback_data=f"apply_pixel_4k_{search_query}")],
            [InlineKeyboardButton("🔙 Back", callback_data=f"back_{search_query}")]
        ]
        await query.message.edit_reply_markup(InlineKeyboardMarkup(btns))
        
    elif data.startswith("filter_lang_"):
        search_query = data.split("_", 2)[2]
        btns = [
            [InlineKeyboardButton("Hindi", callback_data=f"apply_lang_hindi_{search_query}"),
             InlineKeyboardButton("English", callback_data=f"apply_lang_english_{search_query}")],
            [InlineKeyboardButton("Dual Audio", callback_data=f"apply_lang_dual audio_{search_query}")],
            [InlineKeyboardButton("🔙 Back", callback_data=f"back_{search_query}")]
        ]
        await query.message.edit_reply_markup(InlineKeyboardMarkup(btns))
        
    elif data == "dummy_season":
        await query.answer("Season filter abhi process mein hai! 🚀", show_alert=True)
        
    # APPLY FILTERS
    elif data.startswith("apply_"):
        parts = data.split("_", 3)
        filter_type = parts[1] 
        filter_value = parts[2]
        search_query = parts[3]
        
        if filter_type == "pixel":
            movies = list(movies_col.find({"movie_name": {"$regex": search_query}, "quality": filter_value}))
        else:
            movies = list(movies_col.find({"movie_name": {"$regex": search_query}, "language": filter_value}))
            
        if not movies:
            await query.answer(f"❌ Is movie ki '{filter_value}' file abhi upload nahi hui hai!", show_alert=True)
            return
            
        buttons = [[InlineKeyboardButton("🔙 Back to All Files", callback_data=f"back_{search_query}")]]
        for movie in movies:
            movie_id = str(movie["_id"])
            exact_file_name = movie.get("file_name", "Movie File")
            buttons.append([InlineKeyboardButton(f"📁 {exact_file_name}", callback_data=f"get_{movie_id}")])
            
        await query.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
        
    # BACK BUTTON
    elif data.startswith("back_"):
        search_query = data.split("_", 1)[1]
        movies = list(movies_col.find({"movie_name": {"$regex": search_query}}))
        
        buttons = []
        buttons.append([
            InlineKeyboardButton("✨ PIXEL", callback_data=f"filter_pixel_{search_query}"),
            InlineKeyboardButton("🗣 LANGUAGE", callback_data=f"filter_lang_{search_query}"),
            InlineKeyboardButton("🎬 SEASON", callback_data="dummy_season")
        ])
        if len(movies) > 1:
            buttons.append([InlineKeyboardButton("📥 Sᴇɴᴅ Aʟʟ Fɪʟᴇs 📥", callback_data=f"sendall_{search_query}")])
        for movie in movies:
            movie_id = str(movie["_id"])
            exact_file_name = movie.get("file_name", "Movie File")
            buttons.append([InlineKeyboardButton(f"📁 {exact_file_name}", callback_data=f"get_{movie_id}")])
            
        await query.message.edit_reply_markup(InlineKeyboardMarkup(buttons))

    # SEND SINGLE FILE
    elif data.startswith("get_"):
        movie_id = data.split("_")[1]
        movie = movies_col.find_one({"_id": ObjectId(movie_id)})
        if movie:
            await query.answer("Sending File... 📤", show_alert=False)
            await client.send_chat_action(query.message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
            exact_file_name = movie.get("file_name", "Movie File")
            try:
                await client.send_document(chat_id=query.message.chat.id, document=movie["file_id"], caption=f"🍿 **Enjoy your movie!**\n📁 `{exact_file_name}`")
            except Exception:
                await query.message.reply_text("❌ Error: File Telegram server se delete ho chuki hai.")
        else:
            await query.answer("File missing in Database!", show_alert=True)
            
    # SEND ALL FILES
    elif data.startswith("sendall_"):
        search_query = data.split("_", 1)[1]
        movies = list(movies_col.find({"movie_name": {"$regex": search_query}}))
        await query.answer(f"Sending {len(movies)} files... 📤", show_alert=False)
        for movie in movies:
            try:
                await client.send_document(chat_id=query.message.chat.id, document=movie["file_id"], caption=f"📁 `{movie.get('file_name', '')}`")
            except:
                continue

if __name__ == "__main__":
    print("🚀 Pro Bot is Alive (With Live Filters & Spam Blocker)...")
    app.run()
