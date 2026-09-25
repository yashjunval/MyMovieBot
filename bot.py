from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from bson.objectid import ObjectId

# ==========================================
# 1. BOT CREDENTIALS & SETUP
# ==========================================
BOT_TOKEN = "YAHAN_APNA_NAYA_BOT_TOKEN_DALEIN" 
API_ID = 33056032
API_HASH = "4b04c50c2004752cee284a3f533a8dd3"
MONGO_URL = "mongodb+srv://Movie123:Yash123@cluster0.bi61te2.mongodb.net/?appName=Cluster0&compressors=zlib"

# Database Connection
mongo_client = MongoClient(MONGO_URL)
db = mongo_client["MovieBot"]
movies_col = db["Movies"]

# Initialize Bot
app = Client("ProMovieBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ==========================================
# 2. START COMMAND (WELCOME MESSAGE)
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

# ==========================================
# 3. AUTO-SAVE SYSTEM (ADMIN UPLOAD)
# ==========================================
@app.on_message((filters.document | filters.video) & filters.private)
async def save_movie_to_db(client, message):
    # Caption zaroori hai (Search keyword ke liye)
    if not message.caption:
        await message.reply_text("❌ **Upload Failed!**\nKripya file bhejte waqt Caption mein movie ka chhota naam zaroor likhein.")
        return
        
    search_keyword = message.caption.lower().strip()
    media = message.document or message.video
    file_id = media.file_id
    
    # Telegram se asli lamba file name nikalna
    exact_file_name = getattr(media, "file_name", f"{search_keyword}_premium_file.mp4")
    
    # Database mein save karna
    movies_col.insert_one({
        "movie_name": search_keyword,
        "file_name": exact_file_name,
        "file_id": file_id
    })
    
    success_msg = (
        f"✅ **File DataBase mein Save ho gayi!**\n\n"
        f"🔎 **Search Keyword:** `{search_keyword}`\n"
        f"📁 **File Name:** `{exact_file_name}`"
    )
    await message.reply_text(success_msg)

# ==========================================
# 4. PREMIUM SEARCH SYSTEM (USER UI)
# ==========================================
@app.on_message(filters.text & filters.private & ~filters.command("start"))
async def search_movie(client, message):
    search_query = message.text.lower().strip()
    
    # Regex search: thoda milta-julta naam bhi pakad lega
    movies = list(movies_col.find({"movie_name": {"$regex": search_query}}))
    
    if not movies:
        await message.reply_text("❌ **Sorry, yeh movie abhi available nahi hai. Spelling check karein.**")
        return
        
    user_name = message.from_user.first_name
    text = f"👋 **Hᴇʏ, {user_name}** ❞\n\n📁 **Hᴇʀᴇ I Fᴏᴜɴᴅ Fᴏʀ Yᴏᴜʀ Sᴇᴀʀᴄʜ -** `{message.text}`."
    
    buttons = []
    
    # Top 3 Premium Filters (Design Look)
    buttons.append([
        InlineKeyboardButton("✨ PIXEL", callback_data="dummy"),
        InlineKeyboardButton("🗣 LANGUAGE", callback_data="dummy"),
        InlineKeyboardButton("🎬 SEASON", callback_data="dummy")
    ])
    
    # Send All Button (Agar 1 se zyada files hain)
    if len(movies) > 1:
        buttons.append([
            InlineKeyboardButton("📥 Sᴇɴᴅ Aʟʟ Fɪʟᴇs 📥", callback_data=f"sendall_{search_query}")
        ])
    
    # Har movie file ke liye ek lamba button
    for movie in movies:
        movie_id = str(movie["_id"])
        exact_file_name = movie.get("file_name", "Movie File")
        
        buttons.append([
            InlineKeyboardButton(f"📁 {exact_file_name}", callback_data=f"get_{movie_id}")
        ])
        
    reply_markup = InlineKeyboardMarkup(buttons)
    await message.reply_text(text, reply_markup=reply_markup)

# ==========================================
# 5. BUTTON CLICKS & FILE DELIVERY
# ==========================================
@app.on_callback_query()
async def button_click(client, query):
    data = query.data
    
    # Dummy buttons
    if data == "dummy":
        await query.answer("Yeh sirf premium design ke liye hai! 🚀", show_alert=False)
        
    # Single Movie Send
    elif data.startswith("get_"):
        movie_id = data.split("_")[1]
        movie = movies_col.find_one({"_id": ObjectId(movie_id)})
        
        if movie:
            await query.answer("Sending File... 📤", show_alert=False)
            await client.send_chat_action(query.message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
            
            exact_file_name = movie.get("file_name", "Movie File")
            try:
                await client.send_document(
                    chat_id=query.message.chat.id, 
                    document=movie["file_id"], 
                    caption=f"🍿 **Enjoy your movie!**\n📁 `{exact_file_name}`"
                )
            except Exception as e:
                await query.message.reply_text("❌ Error: File Telegram server se delete ho chuki hai.")
        else:
            await query.answer("File missing in Database!", show_alert=True)
            
    # Send All feature
    elif data.startswith("sendall_"):
        search_query = data.split("_", 1)[1]
        movies = list(movies_col.find({"movie_name": {"$regex": search_query}}))
        
        await query.answer(f"Sending {len(movies)} files... 📤", show_alert=False)
        await client.send_chat_action(query.message.chat.id, enums.ChatAction.UPLOAD_DOCUMENT)
        
        for movie in movies:
            exact_file_name = movie.get("file_name", "Movie File")
            try:
                await client.send_document(
                    chat_id=query.message.chat.id, 
                    document=movie["file_id"], 
                    caption=f"📁 `{exact_file_name}`"
                )
            except:
                continue # Agar ek file corrupt hai, toh baaki bhejta rahega

if __name__ == "__main__":
    print("🚀 Pro Bot is Alive and Running on Render...")
    app.run()
