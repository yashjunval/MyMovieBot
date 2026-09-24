from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from bson.objectid import ObjectId  # Database se ID nikalne ke liye
import asyncio # Auto-delete timer ke liye

# --- 1. CREDENTIALS ---
BOT_TOKEN = "8600027374:AAFU9RWFfRFxrNHm6W9FZ_V9LI2WQSlMCKU" 
API_ID = 33056032 
API_HASH = "4b04c50c2004752cee284a3f533a8dd3"
MONGO_URL = "mongodb+srv://Movie123:Yash123@cluster0.bi61te2.mongodb.net/?appName=Cluster0&compressors=zlib"

ADMIN_ID = 6855375693  

# --- 2. DATABASE CONNECTION ---
mongo_client = MongoClient(MONGO_URL)
db = mongo_client["MovieBot_DB"]
movies_col = db["movies"] 

# --- 3. BOT SETUP ---
app = Client("my_movie_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
temp_data = {} 

@app.on_message(filters.command("start"))
def start(client, message):
    message.reply_text(f"Hello {message.from_user.first_name}! Main ek advance Movie Bot hoon 🎬\nMovies search karne ke liye bas naam likh kar bhejein.")

# --- STEP 1: ADMIN MOVIE UPLOAD SYSTEM ---
@app.on_message((filters.document | filters.video) & filters.user(ADMIN_ID))
def movie_received(client, message):
    file = message.document or message.video
    file_id = file.file_id
    file_name = getattr(file, "file_name", "Unknown_Movie.mp4")

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("480p", callback_data="qual_480p"),
         InlineKeyboardButton("720p", callback_data="qual_720p")],
        [InlineKeyboardButton("1080p", callback_data="qual_1080p")]
    ])
    
    reply_msg = message.reply_text(f"📁 Movie aagayi: **{file_name}**\n\nAb iski quality select karo:", reply_markup=buttons)
    temp_data[reply_msg.id] = {"file_id": file_id, "file_name": file_name}

# --- STEP 2: USER SEARCH SYSTEM ---
@app.on_message(filters.text & ~filters.command("start"))
def search_movie(client, message):
    search_query = message.text.lower()
    
    # Database mein movie ka naam dhundho (regex ka matlab milta-julta naam)
    movies = list(movies_col.find({"movie_name": {"$regex": search_query}}))
    
    if not movies:
        message.reply_text("❌ Sorry, yeh movie abhi available nahi hai. Spelling check karein ya Admin se request karein.")
        return

    # Agar movie mili, toh buttons banao
    buttons = []
    for movie in movies:
        movie_id = str(movie["_id"])
        # Button par quality aur movie ka thoda naam dikhega
        buttons.append([InlineKeyboardButton(f"📺 {movie['quality']} - Download Now", callback_data=f"get_{movie_id}")])
        
    reply_markup = InlineKeyboardMarkup(buttons)
    message.reply_text(f"🔍 Search Results for **{message.text}**:\nNiche apni quality select karein:", reply_markup=reply_markup)

# --- STEP 3: BUTTON CLICKS & AUTO-DELETE SYSTEM ---
@app.on_callback_query()
def button_click(client, query):
    data = query.data
    msg_id = query.message.id

    # 1. Admin Upload wala button
    if data.startswith("qual_"):
        quality = data.split("_")[1] 
        if msg_id in temp_data:
            movie_info = temp_data[msg_id]
            file_name = movie_info["file_name"]
            
            movies_col.insert_one({
                "movie_name": file_name.lower(), 
                "original_name": file_name,
                "file_id": movie_info["file_id"],
                "quality": quality
            })
            query.message.edit_text(f"✅ Movie Database mein save ho gayi!\n\n🎬 Naam: {file_name}\n📺 Quality: {quality}")
            del temp_data[msg_id] 
        else:
            query.answer("Error: Data purana ho gaya hai.", show_alert=True)

    # 2. User Download wala button
    elif data.startswith("get_"):
        movie_id = data.split("_")[1]
        movie = movies_col.find_one({"_id": ObjectId(movie_id)})
        
        if movie:
            query.answer("Movie bhej raha hoon... 🚀")
            
            # User ko file bhejo aur msg_id save karo auto-delete ke liye
            sent_msg = client.send_cached_media(
                chat_id=query.from_user.id,
                file_id=movie["file_id"],
                caption=f"🎬 **{movie['original_name']}**\n📺 Quality: {movie['quality']}\n\n⚠️ **Security Warning:** Yeh file 10 minute mein auto-delete ho jayegi. Kripya ise save/forward kar lein!"
            )
            
            # Delete timer chalu karo (600 seconds = 10 minutes)
            # Testing ke liye abhi sirf 1 minute (60 seconds) rakha hai taaki aap check kar sakein
            async def delete_timer():
                await asyncio.sleep(600) # Test hone ke baad isko 600 kar dena
                try:
                    await client.delete_messages(chat_id=query.from_user.id, message_ids=sent_msg.id)
                except Exception as e:
                    print("Delete error:", e)
            
            # Timer ko background mein chalu kar do
            client.loop.create_task(delete_timer())

        else:
            query.answer("❌ Movie database mein nahi mili.", show_alert=True)

print("Advanced Search & Auto-Delete Bot Chalu Ho Gaya Hai...")
app.run()