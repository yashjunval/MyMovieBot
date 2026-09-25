from pyrogram import Client, filters, enums
from pyrogram.exceptions import StopPropagation
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from bson.objectid import ObjectId

# ==========================================
# 1. CREDENTIALS & SETUP
# ==========================================
BOT_TOKEN = "8600027374:AAGmMjISNfFqpSofW9piZtHuoLB0ij5E3qI" 
ADMIN_ID = 6855375693 # 🔒 Yash bhai ki Admin ID Set Ho Gayi Hai
API_ID = 33056032
API_HASH = "4b04c50c2004752cee284a3f533a8dd3"
MONGO_URL = "mongodb+srv://Movie123:Yash123@cluster0.bi61te2.mongodb.net/?appName=Cluster0&compressors=zlib"
DB_CHANNEL_ID = -1004448866853 

mongo_client = MongoClient(MONGO_URL)
db = mongo_client["MovieBot"]
movies_col = db["Movies"]

app = Client("ProMovieBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

# ==========================================
# 2. START COMMAND
# ==========================================
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_name = message.from_user.first_name if message.from_user else "User"
    welcome_text = (
        f"👋 **Hᴇʏ, {user_name}** ❞\n\n"
        f"🎬 **Mᴀɪɴ Eᴋ Aᴅᴠᴀɴᴄᴇ Mᴏᴠɪᴇ Bᴏᴛ Hᴏᴏɴ!**\n\n"
        f"🔎 Kᴏɪ ʙʜɪ ᴍᴏᴠɪᴇ ʏᴀ ᴡᴇʙ sᴇʀɪᴇs ᴅᴏᴡɴʟᴏᴀᴅ ᴋᴀʀɴᴇ ᴋᴇ ʟɪʏᴇ ʙᴀs ᴜsᴋᴀ ɴᴀᴀᴍ ʟɪᴋʜ ᴋᴀʀ ʙʜᴇᴊᴇɪɴ."
    )
    await message.reply_text(welcome_text)
    raise StopPropagation

# ==========================================
# 3. AUTO-SAVE (Sirf Admin Ke Liye Lock 🔒)
# ==========================================
@app.on_message((filters.document | filters.video) & filters.private & filters.user(ADMIN_ID))
async def save_movie_to_db(client, message):
    try:
        copied_msg = await message.copy(DB_CHANNEL_ID)
    except Exception:
        await message.reply_text("❌ Error: Bot ko channel mein admin banayein.")
        raise StopPropagation

    media = message.document or message.video
    exact_file_name = getattr(media, "file_name", "movie_file.mp4")
    search_keyword = exact_file_name.lower()
    
    quality_tags = []
    if "480p" in search_keyword: quality_tags.append("480p")
    if "720p" in search_keyword: quality_tags.append("720p")
    if "1080p" in search_keyword: quality_tags.append("1080p")
    if "4k" in search_keyword or "2160p" in search_keyword: quality_tags.append("4k")
    
    lang_tags = []
    if "hindi" in search_keyword or "hin" in search_keyword: lang_tags.append("hindi")
    if "english" in search_keyword or "eng" in search_keyword: lang_tags.append("english")
    if "dual" in search_keyword: lang_tags.append("dual audio")
    
    movies_col.insert_one({
        "movie_name": search_keyword, 
        "file_name": exact_file_name,
        "message_id": copied_msg.id,
        "quality": quality_tags,
        "language": lang_tags
    })
    
    await message.reply_text(f"✅ **Movie DataBase Channel mein Save ho gayi!**\n📁 `{exact_file_name}`")
    raise StopPropagation

# ==========================================
# 4. USER SEARCH (Spam Loop Killer System)
# ==========================================
@app.on_message(filters.text & filters.private & ~filters.command("start"))
async def search_movie(client, message):
    if message.from_user and message.from_user.is_bot:
        return
        
    search_query = message.text.lower().strip()
    
    if "sorry" in search_query:
        return

    movies = list(movies_col.find({"movie_name": {"$regex": search_query}}))
    
    if not movies:
        await message.reply_text("❌ **Sorry, yeh movie abhi available nahi hai. Spelling check karein.**")
        raise StopPropagation
        
    user_name = message.from_user.first_name if message.from_user else "User"
    text = f"👋 **Hᴇʏ, {user_name}** ❞\n\n📁 **Hᴇʀᴇ I Fᴏᴜɴᴅ Fᴏʀ Yᴏᴜʀ Sᴇᴀʀᴄʜ -** `{message.text}`."
    
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
        
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    raise StopPropagation

# ==========================================
# 5. BUTTON CLICKS & FILE DELIVERY (From Channel)
# ==========================================
@app.on_callback_query()
async def button_click(client, query):
    data = query.data
    
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

    elif data.startswith("get_"):
        movie_id = data.split("_")[1]
        movie = movies_col.find_one({"_id": ObjectId(movie_id)})
        
        if movie and "message_id" in movie:
            await query.answer("Sending File... 📤", show_alert=False)
            await client.send_chat_action(query.message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
            try:
                await client.copy_message(chat_id=query.message.chat.id, from_chat_id=DB_CHANNEL_ID, message_id=movie["message_id"])
            except Exception as e:
                await query.message.reply_text("❌ Error: Channel se file fetch nahi ho payi.")
        else:
            await query.answer("Yeh purani file hai, isey wapas upload karein!", show_alert=True)
            
    elif data.startswith("sendall_"):
        search_query = data.split("_", 1)[1]
        movies = list(movies_col.find({"movie_name": {"$regex": search_query}}))
        await query.answer(f"Sending {len(movies)} files... 📤", show_alert=False)
        for movie in movies:
            if "message_id" in movie:
                try:
                    await client.copy_message(chat_id=query.message.chat.id, from_chat_id=DB_CHANNEL_ID, message_id=movie["message_id"])
                except:
                    continue

if __name__ == "__main__":
    print("🚀 Ultimate Pro Bot is Alive (Admin Locked + Anti-Spam)...")
    app.run()
