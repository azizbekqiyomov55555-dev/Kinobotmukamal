import logging
import sqlite3
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- SOZLAMALAR ---
API_TOKEN = 'BOT_TOKENINGIZNI_SHU_YERGA_YOZING'
ADMIN_ID = 12345678  # O'zingizning Telegram ID-ingizni yozing

# Loglarni sozlash
logging.basicConfig(level=logging.INFO)

# Bot va Dispatcher
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- MA'LUMOTLAR BAZASI ---
conn = sqlite3.connect('dorama_bot.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS movies 
                (id INTEGER PRIMARY KEY, code TEXT, name TEXT, photo TEXT, lang TEXT, parts INTEGER)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS videos 
                (movie_id INTEGER, part_num INTEGER, file_id TEXT)''')
conn.commit()

# --- STATES (HOLATLAR) ---
class AddMovie(StatesGroup):
    code = State()
    name = State()
    photo = State()
    lang = State()
    parts_count = State()
    uploading_videos = State()

# --- ADMIN PANEL ---
@dp.message_handler(commands=['admin'], user_id=ADMIN_ID)
async def admin_start(message: types.Message):
    await message.answer("Xush kelibsiz Admin! Yangi kino qo'shish uchun /add buyrug'ini bering.")

@dp.message_handler(commands=['add'], user_id=ADMIN_ID)
async def start_add(message: types.Message):
    await AddMovie.code.set()
    await message.answer("Kino uchun maxsus kodni kiriting:")

@dp.message_handler(state=AddMovie.code)
async def set_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text)
    await AddMovie.name.set()
    await message.answer("Kino nomini kiriting:")

@dp.message_handler(state=AddMovie.name)
async def set_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await AddMovie.photo.set()
    await message.answer("Kino uchun rasm (poster) yuboring:")

@dp.message_handler(content_types=['photo'], state=AddMovie.photo)
async def set_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo=photo_id)
    await AddMovie.lang.set()
    await message.answer("Kino tilini kiriting (masalan: O'zbek tili):")

@dp.message_handler(state=AddMovie.lang)
async def set_lang(message: types.Message, state: FSMContext):
    await state.update_data(lang=message.text)
    await AddMovie.parts_count.set()
    await message.answer("Kino necha qismdan iborat? (son kiriting):")

@dp.message_handler(state=AddMovie.parts_count)
async def set_parts(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Iltimos faqat son kiriting!")
    
    parts = int(message.text)
    data = await state.get_data()
    
    cursor.execute("INSERT INTO movies (code, name, photo, lang, parts) VALUES (?, ?, ?, ?, ?)",
                   (data['code'], data['name'], data['photo'], data['lang'], parts))
    movie_id = cursor.lastrowid
    conn.commit()
    
    await state.update_data(movie_id=movie_id, current_part=1, total_parts=parts)
    await AddMovie.uploading_videos.set()
    await message.answer(f"1-qism videosini yuboring:")

@dp.message_handler(content_types=['video'], state=AddMovie.uploading_videos)
async def upload_videos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    m_id = data['movie_id']
    curr = data['current_part']
    total = data['total_parts']
    
    cursor.execute("INSERT INTO videos (movie_id, part_num, file_id) VALUES (?, ?, ?)",
                   (m_id, curr, message.video.file_id))
    conn.commit()
    
    if curr < total:
        new_part = curr + 1
        await state.update_data(current_part=new_part)
        await message.answer(f"{new_part}-qism videosini yuboring:")
    else:
        await state.finish()
        await message.answer("Kino va barcha qismlar muvaffaqiyatli saqlandi! ✅")

# --- FOYDALANUVCHI QISMI ---

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    args = message.get_args()
    if args:
        # Agar start bilan kod kelsa (masalan: t.me/bot?start=kod)
        await process_code(message, args)
    else:
        await message.answer("Assalomu alaykum! Kino ko'rish uchun kodni yuboring.")

@dp.message_handler()
async def check_code(message: types.Message):
    await process_code(message, message.text)

async def process_code(message, code):
    cursor.execute("SELECT * FROM movies WHERE code=?", (code,))
    movie = cursor.fetchone()
    
    if movie:
        m_id, m_code, m_name, m_photo, m_lang, m_parts = movie
        
        text = (f"🎬 **Nomi:** {m_name}\n"
                f"🌍 **Davlat:** Xitoy\n"
                f"🇺🇿 **Tili:** {m_lang}\n"
                f"🎞 **Qismlar soni:** {m_parts}\n"
                f"🎭 **Janri:** Mini drama")
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        # Qismlarni tanlash tugmalari
        buttons = []
        for i in range(1, m_parts + 1):
            buttons.append(InlineKeyboardButton(f"{i}-qism", callback_data=f"part_{m_id}_{i}"))
        keyboard.add(*buttons)
        
        # protect_content=True - Forward qilish va saqlashni taqiqlaydi
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=m_photo,
            caption=text,
            reply_markup=keyboard,
            protect_content=True 
        )
    else:
        await message.answer("Xato kod kiritdingiz yoki bunday kino mavjud emas. ❌")

@dp.callback_query_handler(lambda c: c.data.startswith('part_'))
async def show_part(callback_query: types.CallbackQuery):
    _, m_id, part_num = callback_query.data.split('_')
    
    cursor.execute("SELECT file_id FROM videos WHERE movie_id=? AND part_num=?", (m_id, part_num))
    video = cursor.fetchone()
    
    if video:
        # MUHIM: protect_content=True videoni yuklab olishni va forwardni yopadi
        # Bu funksiya Telegramning o'zida skrinshot va zapisni ham cheklaydi (Android/iOS)
        await bot.send_video(
            chat_id=callback_query.from_user.id,
            video=video[0],
            caption=f"🎬 {part_num}-qism\n\nMarhamat, tomosha qiling!",
            protect_content=True
        )
        await callback_query.answer()
    else:
        await callback_query.answer("Video topilmadi.", show_alert=True)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
