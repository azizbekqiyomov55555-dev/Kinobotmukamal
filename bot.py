import asyncio
import logging

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# ───────────────────────────────────────────────
#  SOZLAMALAR  –  O'ZINGIZNIKIGA ALMASHTIRING
# ───────────────────────────────────────────────
BOT_TOKEN       = "8693668045:AAGY-fCRkzaDNO9xHqJAFcrpI_OLpYIBMdI"
CHANNEL_ID      = "@Azizbekl2026"         # Masalan: @mening_kanalim
ADMIN_IDS       = [8537782289]             # Masalan: [123456789]
CLAUDE_KEY      = "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"
JSONBIN_API_KEY = "$2a$10$mQZC26SFNwuUJbIo3fANVO3eiIMW4jWdJTva4/6tBlESt4AAde.mi"
JSONBIN_BIN_ID  = "69cc43a2856a682189e936f0"

JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ───────────────────────────────────────────────
#  JSONBIN DATABASE
# ───────────────────────────────────────────────

async def load_db() -> dict:
    headers = {"X-Master-Key": JSONBIN_API_KEY, "X-Bin-Meta": "false"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(JSONBIN_URL, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, dict) and "movies" in data:
                        return data
    except Exception as e:
        logger.error(f"DB yuklashda xato: {e}")
    return {"movies": {}, "counter": 0}


async def save_db(db: dict) -> None:
    headers = {"Content-Type": "application/json", "X-Master-Key": JSONBIN_API_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(JSONBIN_URL, headers=headers, json=db, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.error(f"DB saqlashda xato: {resp.status}")
    except Exception as e:
        logger.error(f"DB saqlashda xato: {e}")


def next_movie_id(db: dict) -> str:
    db["counter"] = db.get("counter", 0) + 1
    return str(db["counter"])


def find_movie_by_id(db: dict, mid: str) -> dict | None:
    return db["movies"].get(mid)


def find_movie_by_name(db: dict, name: str) -> dict | None:
    nl = name.lower()
    for movie in db["movies"].values():
        if nl in movie["name"].lower():
            return movie
    return None

# ───────────────────────────────────────────────
#  CLAUDE AI
# ───────────────────────────────────────────────

async def ask_claude(user_text: str) -> str:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": CLAUDE_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1024,
        "system": (
            "Siz kinolar haqida bilimli, do'stona Telegram bot assistantsiz. "
            "Foydalanuvchilarga O'zbek tilida qisqa va aniq javob bering."
        ),
        "messages": [{"role": "user", "content": user_text}],
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                data = await resp.json()
                return data["content"][0]["text"]
    except Exception as e:
        logger.error(f"Claude API xato: {e}")
        return "Kechirasiz, hozir javob bera olmayapman. Keyinroq urinib ko'ring."

# ───────────────────────────────────────────────
#  YORDAMCHI FUNKSIYALAR
# ───────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def movie_deep_link(bot_username: str, movie_id: str) -> str:
    return f"https://t.me/{bot_username}?start=movie_{movie_id}"


def movie_inline_kb(bot_username: str, movie_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎬 Tomosha qilish", url=movie_deep_link(bot_username, movie_id))
    ]])


async def send_movie_to_user(message: Message, movie: dict) -> None:
    caption = f"🎬 <b>{movie['name']}</b>"
    try:
        if movie.get("poster_file_id"):
            await message.answer_photo(photo=movie["poster_file_id"], caption=caption, parse_mode=ParseMode.HTML)
        await message.answer_video(video=movie["video_file_id"], caption=caption, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Kino yuborishda xato: {e}")
        await message.answer("⚠️ Kinoni yuborishda xato yuz berdi.")


async def post_movie_to_channel(bot: Bot, movie: dict, bot_username: str) -> None:
    caption = f"🎬 <b>{movie['name']}</b>\n\n👇 Tomosha qilish uchun tugmani bosing"
    kb = movie_inline_kb(bot_username, movie["id"])
    try:
        if movie.get("poster_file_id"):
            await bot.send_photo(chat_id=CHANNEL_ID, photo=movie["poster_file_id"], caption=caption, reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            await bot.send_video(chat_id=CHANNEL_ID, video=movie["video_file_id"], caption=caption, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Kanalga post qilishda xato: {e}")
        raise

# ───────────────────────────────────────────────
#  FSM HOLATLARI
# ───────────────────────────────────────────────

class AddMovieState(StatesGroup):
    waiting_name   = State()
    waiting_video  = State()
    waiting_poster = State()

# ───────────────────────────────────────────────
#  HANDLERLAR
# ───────────────────────────────────────────────

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    db = await load_db()
    args = message.text.split(maxsplit=1)
    param = args[1] if len(args) > 1 else ""

    if param.startswith("movie_"):
        movie = find_movie_by_id(db, param[len("movie_"):])
        if movie:
            await send_movie_to_user(message, movie)
        else:
            await message.answer("❌ Kino topilmadi yoki o'chirilgan.")
        return

    admin_text = "\n\n🔑 <b>Admin panel:</b> /add – yangi kino qo'shish" if is_admin(message.from_user.id) else ""
    await message.answer(
        f"👋 Salom, <b>{message.from_user.full_name}</b>!\n\n"
        "🎬 <b>Kino Botga xush kelibsiz!</b>\n\n"
        "• Kino nomini yozing – topib beraman\n"
        "• Har qanday savol yozing – AI javob beradi"
        f"{admin_text}",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("❌ Sizda bu buyruqqa ruxsat yo'q.")
        return
    await state.set_state(AddMovieState.waiting_name)
    await message.answer("🎬 Kino nomini kiriting:")


@router.message(AddMovieState.waiting_name)
async def add_movie_name(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Iltimos, kino nomini matn ko'rinishida kiriting.")
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(AddMovieState.waiting_video)
    await message.answer("🎥 Kino videosini yuboring:")


@router.message(AddMovieState.waiting_video, F.video)
async def add_movie_video(message: Message, state: FSMContext) -> None:
    await state.update_data(video_file_id=message.video.file_id)
    await state.set_state(AddMovieState.waiting_poster)
    await message.answer("🖼 Poster (rasm) yuboring yoki /skip bosing (ixtiyoriy):")


@router.message(AddMovieState.waiting_video)
async def add_movie_video_invalid(message: Message) -> None:
    await message.answer("⚠️ Iltimos, video fayl yuboring.")


@router.message(AddMovieState.waiting_poster, F.photo)
async def add_movie_poster(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.update_data(poster_file_id=message.photo[-1].file_id)
    await _finalize_add(message, state, bot)


@router.message(AddMovieState.waiting_poster, Command("skip"))
async def add_movie_skip_poster(message: Message, state: FSMContext, bot: Bot) -> None:
    await _finalize_add(message, state, bot)


@router.message(AddMovieState.waiting_poster)
async def add_movie_poster_invalid(message: Message) -> None:
    await message.answer("⚠️ Rasm yuboring yoki /skip bosing.")


async def _finalize_add(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    await state.clear()

    db = await load_db()
    mid = next_movie_id(db)
    db["movies"][mid] = {
        "id": mid,
        "name": data["name"],
        "video_file_id": data["video_file_id"],
        "poster_file_id": data.get("poster_file_id"),
    }
    await save_db(db)

    me = await bot.get_me()
    try:
        await post_movie_to_channel(bot, db["movies"][mid], me.username)
        channel_status = "✅ Kanalga muvaffaqiyatli post qilindi!"
    except Exception:
        channel_status = "⚠️ Kanalga post qilishda xato yuz berdi."

    await message.answer(
        f"✅ <b>{data['name']}</b> qo'shildi!\n\n"
        f"🆔 ID: <code>{mid}</code>\n"
        f"🔗 {movie_deep_link(me.username, mid)}\n\n"
        f"{channel_status}",
        parse_mode=ParseMode.HTML,
    )


@router.message(F.text)
async def handle_text(message: Message) -> None:
    db = await load_db()
    movie = find_movie_by_name(db, message.text)
    if movie:
        await send_movie_to_user(message, movie)
        return
    await message.answer("🤔 Qidirilmoqda...")
    answer = await ask_claude(message.text)
    await message.answer(answer)


@router.callback_query()
async def handle_callback(callback: CallbackQuery) -> None:
    await callback.answer()

# ───────────────────────────────────────────────
#  MAIN
# ───────────────────────────────────────────────

async def main() -> None:
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    logger.info("Bot ishga tushmoqda...")
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
