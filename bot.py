import os
import re
import time
import asyncio
import logging
import difflib
import aiohttp

from pyrogram import Client, filters, enums, StopPropagation
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
)
from pymongo import MongoClient
from bson.objectid import ObjectId
from google import genai


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")

ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

MONGO_URL = os.getenv("MONGO_URL")

DB_CHANNEL_ID = int(os.getenv("DB_CHANNEL_ID", "0"))
FSUB_CHANNEL_ID = int(os.getenv("FSUB_CHANNEL_ID", "0"))

FSUB_CHANNEL_LINK = os.getenv("FSUB_CHANNEL_LINK", "")
START_PIC = os.getenv("START_PIC", "")

OMDB_API_KEY = os.getenv("OMDB_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Change from environment if required
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

AUTO_DELETE_SECONDS = 600
MAX_RESULTS = 30


# =========================================================
# LOGGING
# =========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger("MovieBot")


# =========================================================
# VALIDATE CONFIG
# =========================================================

required = {
    "BOT_TOKEN": BOT_TOKEN,
    "API_ID": API_ID,
    "API_HASH": API_HASH,
    "ADMIN_ID": ADMIN_ID,
    "MONGO_URL": MONGO_URL,
    "DB_CHANNEL_ID": DB_CHANNEL_ID,
}

missing = [key for key, value in required.items() if not value]

if missing:
    raise RuntimeError(
        f"Missing environment variables: {', '.join(missing)}"
    )


# =========================================================
# DATABASE
# =========================================================

mongo_client = MongoClient(MONGO_URL)

db = mongo_client["MovieBot"]

movies_col = db["Movies"]
users_col = db["Users"]
banned_col = db["BannedUsers"]
trending_col = db["Trending"]
vip_col = db["VIPUsers"]
watchlist_col = db["Watchlist"]


# Useful indexes
try:
    users_col.create_index("user_id", unique=True)
    banned_col.create_index("user_id", unique=True)
    vip_col.create_index("user_id", unique=True)
    watchlist_col.create_index("user_id", unique=True)

    movies_col.create_index("message_id")
    movies_col.create_index("movie_name")
except Exception as e:
    logger.warning("Index creation error: %s", e)


# =========================================================
# CLIENTS
# =========================================================

app = Client(
    "ProMovieBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)

ai_client = None

if GEMINI_API_KEY:
    try:
        ai_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.error("Gemini init error: %s", e)


# =========================================================
# MEMORY DATA
# =========================================================

SPAM_TRACKER = {}

# Callback-data me long search query store karne ke bajay
# short token use hoga.
SEARCH_CACHE = {}

SEARCH_CACHE_TTL = 1800


# =========================================================
# HELPERS
# =========================================================

def save_user(user_id, name):
    try:
        users_col.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "name": name or "User"
                }
            },
            upsert=True
        )
    except Exception as e:
        logger.error("save_user error: %s", e)


def is_vip(user_id):
    return vip_col.find_one({"user_id": user_id}) is not None


def is_banned(user_id):
    return banned_col.find_one({"user_id": user_id}) is not None


def create_search_token(query):
    """
    Telegram callback_data max size issue avoid karne ke liye
    short token generate karta hai.
    """
    token = ObjectId().binary.hex()[:12]

    SEARCH_CACHE[token] = {
        "query": query,
        "created": time.time()
    }

    # Occasionally cleanup old tokens
    if len(SEARCH_CACHE) > 1000:
        now = time.time()

        expired = [
            key
            for key, value in SEARCH_CACHE.items()
            if now - value["created"] > SEARCH_CACHE_TTL
        ]

        for key in expired:
            SEARCH_CACHE.pop(key, None)

    return token


def get_search_from_token(token):
    item = SEARCH_CACHE.get(token)

    if not item:
        return None

    if time.time() - item["created"] > SEARCH_CACHE_TTL:
        SEARCH_CACHE.pop(token, None)
        return None

    return item["query"]


def movie_query(search_query):
    return {
        "movie_name": {
            "$regex": re.escape(search_query),
            "$options": "i"
        }
    }


def get_movies(search_query, limit=MAX_RESULTS):
    return list(
        movies_col.find(
            movie_query(search_query)
        ).limit(limit)
    )


def make_main_buttons(movies, token):
    buttons = [
        [
            InlineKeyboardButton(
                "✨ PIXEL",
                callback_data=f"fp:{token}"
            ),
            InlineKeyboardButton(
                "🗣 LANGUAGE",
                callback_data=f"fl:{token}"
            ),
        ],
        [
            InlineKeyboardButton(
                "🎬 SEASON",
                callback_data=f"fs:{token}"
            ),
            InlineKeyboardButton(
                "📺 EPISODE",
                callback_data=f"fe:{token}"
            ),
        ]
    ]

    if len(movies) > 1:
        buttons.append([
            InlineKeyboardButton(
                "📥 Sᴇɴᴅ Aʟʟ Fɪʟᴇs 📥",
                callback_data=f"sa:{token}"
            )
        ])

    for movie in movies:
        mid = str(movie["_id"])

        file_name = movie.get(
            "file_name",
            "File"
        )

        # Button text ko manageable rakho
        if len(file_name) > 50:
            file_name = file_name[:47] + "..."

        buttons.append([
            InlineKeyboardButton(
                f"📁 {file_name}",
                callback_data=f"g:{mid}"
            )
        ])

        buttons.append([
            InlineKeyboardButton(
                "📌 Add to Watchlist",
                callback_data=f"w:{mid}"
            )
        ])

    return buttons


async def check_fsub(client, user_id):
    if not FSUB_CHANNEL_ID:
        return True

    try:
        member = await client.get_chat_member(
            FSUB_CHANNEL_ID,
            user_id
        )

        if member.status in [
            enums.ChatMemberStatus.LEFT,
            enums.ChatMemberStatus.BANNED
        ]:
            return False

        return True

    except Exception as e:
        logger.warning(
            "Force-sub check failed for %s: %s",
            user_id,
            e
        )

        return False


def force_sub_buttons():
    buttons = []

    if FSUB_CHANNEL_LINK:
        buttons.append([
            InlineKeyboardButton(
                "📢 Join Our Channel",
                url=FSUB_CHANNEL_LINK
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "✅ Verify",
            callback_data="verify"
        )
    ])

    return InlineKeyboardMarkup(buttons)


async def send_welcome(message):
    first_name = message.from_user.first_name or "User"

    text = (
        f"👋 **Hᴇʏ, {first_name}** ❞\n\n"
        "🎬 **Mᴀɪɴ Eᴋ Aᴅᴠᴀɴᴄᴇ Mᴏᴠɪᴇ Bᴏᴛ Hᴏᴏɴ!**\n\n"
        "🔎 Movie ya web series search karne ke liye "
        "sirf uska naam bhejein.\n\n"
        "🤖 AI Recommendation: `/ai <request>`\n"
        "📈 Trending: `/trending`\n"
        "📌 Watchlist: `/watchlist`"
    )

    if START_PIC:
        try:
            await message.reply_photo(
                photo=START_PIC,
                caption=text
            )
            return

        except Exception as e:
            logger.warning("Welcome photo error: %s", e)

    await message.reply_text(text)


async def get_imdb_info(query):
    if not OMDB_API_KEY:
        return None

    url = "https://www.omdbapi.com/"

    params = {
        "t": query,
        "apikey": OMDB_API_KEY
    }

    try:
        timeout = aiohttp.ClientTimeout(total=8)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.get(
                url,
                params=params
            ) as response:

                data = await response.json()

                if data.get("Response") == "True":
                    return data

    except Exception as e:
        logger.warning("OMDb error: %s", e)

    return None


async def auto_delete_task(
    client,
    chat_id,
    message_ids
):
    await asyncio.sleep(AUTO_DELETE_SECONDS)

    try:
        await client.delete_messages(
            chat_id,
            message_ids
        )

    except Exception as e:
        logger.warning(
            "Auto delete error: %s",
            e
        )


def extract_tags(file_name):
    name = file_name.lower()

    qualities = []
    languages = []
    seasons = []
    episodes = []

    # Quality
    if re.search(r"\b480p\b", name):
        qualities.append("480p")

    if re.search(r"\b720p\b", name):
        qualities.append("720p")

    if re.search(r"\b1080p\b", name):
        qualities.append("1080p")

    if (
        re.search(r"\b2160p\b", name)
        or re.search(r"\b4k\b", name)
    ):
        qualities.append("4k")

    # Languages
    if re.search(r"\bhindi\b|\bhin\b", name):
        languages.append("hindi")

    if re.search(r"\benglish\b|\beng\b", name):
        languages.append("english")

    if "dual audio" in name or re.search(r"\bdual\b", name):
        languages.append("dual audio")

    # Seasons
    season_matches = re.findall(
        r"(?:\bs(?:eason)?[\s._-]*)(\d{1,2})",
        name,
        flags=re.IGNORECASE
    )

    for season in season_matches:
        seasons.append(
            f"S{season.zfill(2)}"
        )

    # Episodes:
    # E01
    # EP01
    # Episode 01
    # E01-E05
    episode_matches = re.findall(
        r"\b(?:e|ep|episode)[\s._-]*(\d{1,3})"
        r"(?:[\s._-]*(?:-|to)[\s._-]*"
        r"(?:e|ep|episode)?[\s._-]*(\d{1,3}))?",
        name,
        flags=re.IGNORECASE
    )

    for start, end in episode_matches:

        if end:
            episodes.append(
                f"E{start.zfill(2)}-E{end.zfill(2)}"
            )
        else:
            episodes.append(
                f"E{start.zfill(2)}"
            )

    return (
        list(set(qualities)),
        list(set(languages)),
        list(set(seasons)),
        list(set(episodes))
    )


# =========================================================
# JOIN REQUEST AUTO APPROVE
# =========================================================

@app.on_chat_join_request(
    filters.chat(FSUB_CHANNEL_ID)
)
async def approve_join_req(client, request):
    try:
        await client.approve_chat_join_request(
            chat_id=request.chat.id,
            user_id=request.from_user.id
        )

        try:
            await client.send_message(
                request.from_user.id,
                "✅ **Aapki join request accept ho gayi!**\n\n"
                "Ab bot me movie search kar sakte hain."
            )
        except Exception:
            pass

    except Exception as e:
        logger.error(
            "Join approve error: %s",
            e
        )


# =========================================================
# SET MENU
# =========================================================

@app.on_message(
    filters.command("setmenu")
    & filters.private
    & filters.user(ADMIN_ID)
)
async def set_bot_menus(client, message):

    user_commands = [
        BotCommand(
            "start",
            "Bot ko restart karein"
        ),
        BotCommand(
            "ai",
            "🤖 AI Movie Buddy"
        ),
        BotCommand(
            "trending",
            "📈 Top 10 Searches"
        ),
        BotCommand(
            "watchlist",
            "📌 My Saved Movies"
        ),
    ]

    admin_commands = [
        BotCommand(
            "start",
            "Start the bot"
        ),
        BotCommand(
            "stats",
            "📊 Bot Statistics"
        ),
        BotCommand(
            "broadcast",
            "📢 Send Message to All"
        ),
        BotCommand(
            "addvip",
            "👑 Add VIP User"
        ),
        BotCommand(
            "rmvip",
            "❌ Remove VIP User"
        ),
        BotCommand(
            "unban",
            "🔓 Unban User"
        ),
        BotCommand(
            "ai",
            "🤖 AI Movie Buddy"
        ),
        BotCommand(
            "trending",
            "📈 Top 10 Searches"
        ),
        BotCommand(
            "watchlist",
            "📌 My Saved Movies"
        ),
    ]

    try:
        await client.set_bot_commands(
            user_commands,
            scope=BotCommandScopeDefault()
        )

        await client.set_bot_commands(
            admin_commands,
            scope=BotCommandScopeChat(
                chat_id=ADMIN_ID
            )
        )

        await message.reply_text(
            "✅ **Menu Set Successfully!**"
        )

    except Exception as e:
        logger.exception("Set menu error")

        await message.reply_text(
            f"❌ Menu set nahi hua:\n`{e}`"
        )

    raise StopPropagation


# =========================================================
# START
# =========================================================

@app.on_message(
    filters.command("start")
    & filters.private
)
async def start_command(client, message):

    user_id = message.from_user.id

    if is_banned(user_id):
        return

    save_user(
        user_id,
        message.from_user.first_name
    )

    if not await check_fsub(
        client,
        user_id
    ):
        await message.reply_text(
            "⚠️ **Pehle hamara official channel join karein.**\n\n"
            "Join karne ke baad **Verify** button dabayein.",
            reply_markup=force_sub_buttons()
        )

        raise StopPropagation

    await send_welcome(message)

    raise StopPropagation


# =========================================================
# AI
# =========================================================

@app.on_message(
    filters.command("ai")
    & filters.private
)
async def ai_recommender(client, message):

    if len(message.command) < 2:
        await message.reply_text(
            "🤖 **AI Movie Buddy**\n\n"
            "Example:\n"
            "`/ai best mind bending thriller movies`"
        )

        raise StopPropagation

    if ai_client is None:
        await message.reply_text(
            "❌ AI service configure nahi hai."
        )

        raise StopPropagation

    query = message.text.split(
        " ",
        1
    )[1].strip()

    wait_msg = await message.reply_text(
        "🤖 _Thinking..._"
    )

    try:
        prompt = (
            "Act as a concise movie recommendation assistant. "
            "Recommend exactly 3 movies based on the user's request. "
            "For each movie give its title, year and one short reason. "
            "Do not include download links.\n\n"
            f"User request: {query}"
        )

        response = await ai_client.aio.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        answer = getattr(
            response,
            "text",
            None
        )

        if not answer:
            raise ValueError(
                "Empty Gemini response"
            )

        await wait_msg.edit_text(
            "🤖 **AI Suggestions:**\n\n"
            f"{answer}\n\n"
            "🔎 Movie available hai ya nahi dekhne ke liye "
            "uska naam bot me search karein."
        )

    except Exception as e:
        logger.exception(
            "Gemini error"
        )

        await wait_msg.edit_text(
            "❌ AI service me abhi problem aa rahi hai.\n"
            "Thodi der baad try karein."
        )

    raise StopPropagation


# =========================================================
# WATCHLIST
# =========================================================

@app.on_message(
    filters.command("watchlist")
    & filters.private
)
async def show_watchlist(client, message):

    user_data = watchlist_col.find_one({
        "user_id": message.from_user.id
    })

    if (
        not user_data
        or not user_data.get("movies")
    ):
        await message.reply_text(
            "📌 **Aapki Watchlist khali hai!**"
        )

        raise StopPropagation

    buttons = []

    count = 0

    for mid in user_data["movies"][:20]:

        try:
            movie = movies_col.find_one({
                "_id": ObjectId(mid)
            })

        except Exception:
            movie = None

        if not movie:
            continue

        count += 1

        name = movie.get(
            "file_name",
            movie.get(
                "movie_name",
                "Movie"
            )
        )

        if len(name) > 45:
            name = name[:42] + "..."

        buttons.append([
            InlineKeyboardButton(
                f"📁 {name}",
                callback_data=f"g:{mid}"
            )
        ])

        buttons.append([
            InlineKeyboardButton(
                "❌ Remove",
                callback_data=f"wr:{mid}"
            )
        ])

    if not buttons:
        await message.reply_text(
            "📌 Watchlist me valid movies nahi mili."
        )

        raise StopPropagation

    await message.reply_text(
        f"📌 **MY WATCHLIST**\n\n"
        f"🎬 Total: `{count}`",
        reply_markup=InlineKeyboardMarkup(
            buttons
        )
    )

    raise StopPropagation


# =========================================================
# TRENDING
# =========================================================

@app.on_message(
    filters.command("trending")
    & filters.private
)
async def trending_movies(client, message):

    top_movies = list(
        trending_col.find()
        .sort("count", -1)
        .limit(10)
    )

    if not top_movies:
        await message.reply_text(
            "📉 Abhi tak trending data nahi hai!"
        )

        raise StopPropagation

    text = (
        "📈 **TOP 10 TRENDING SEARCHES** 📈\n\n"
    )

    for i, movie in enumerate(
        top_movies,
        1
    ):
        text += (
            f"**{i}.** "
            f"`{movie.get('query', 'Unknown').title()}` "
            f"(🔥 {movie.get('count', 0)})\n"
        )

    await message.reply_text(text)

    raise StopPropagation


# =========================================================
# ADMIN: VIP
# =========================================================

@app.on_message(
    filters.command("addvip")
    & filters.private
    & filters.user(ADMIN_ID)
)
async def add_vip(client, message):

    if len(message.command) != 2:
        await message.reply_text(
            "Usage:\n`/addvip USER_ID`"
        )

        raise StopPropagation

    try:
        uid = int(message.command[1])

        vip_col.update_one(
            {"user_id": uid},
            {"$set": {"user_id": uid}},
            upsert=True
        )

        await message.reply_text(
            f"👑 User `{uid}` ab VIP hai."
        )

    except ValueError:
        await message.reply_text(
            "❌ Invalid User ID."
        )

    except Exception as e:
        logger.exception("Add VIP error")

        await message.reply_text(
            "❌ VIP add nahi h
