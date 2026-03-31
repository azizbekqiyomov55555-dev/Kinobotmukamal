"""
🎬 CINEMA BOT - To'liq Telegram Bot
Kutubxonalar: pip install aiogram aiohttp python-dotenv
"""

import asyncio
import json
import logging
import aiohttp
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, InputMediaVideo, ReplyKeyboardRemove
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# ⚙️ SOZLAMALAR - O'zgartiring!
# ============================================================
BOT_TOKEN = "YOUR_BOT_TOKEN"          # @BotFather dan oling
ADMIN_IDS = [123456789]               # Admin Telegram ID
CHANNEL_ID = "@your_channel"          # Kanal username
BOT_USERNAME = "your_bot"             # Bot username (@ siz)

# JSONBin.io sozlamalari
JSONBIN_API_KEY = "$2a$10$mQZC26SFNwuUJbIo3fANVO3eiIMW4jWdJTva4/6tBlESt4AAde.mi"
JSONBIN_BIN_ID = "YOUR_BIN_ID"        # jsonbin.io dan yarating
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

# ============================================================
# 🌈 RANGLI TUGMALAR - Telegram InlineKeyboard rang turlari
# ============================================================
# Telegram 3 xil tugma rangini qo'llab-quvvatlaydi:
# "" - Ko'k (default)    - primary
# "✅" - Yashil (callback) - boshqa rang uchun emoji qo'shing
# Haqiqiy rangli tugmalar faqat WebApp orqali ishlaydi.
# Biz emoji bilan rangli ko'rinish beramiz:
# 🟢 Yashil | 🔵 Ko'k | 🔴 Qizil

# ============================================================
# 📦 JSONBin - Ma'lumotlar bazasi
# ============================================================

DEFAULT_DATA = {
    "users": {},
    "movies": {},
    "tariffs": {
        "1oy": {"name": "1 Oylik VIP", "price": 50000, "days": 30},
        "3oy": {"name": "3 Oylik VIP", "price": 120000, "days": 90},
        "1yil": {"name": "1 Yillik VIP", "price": 400000, "days": 365}
    },
    "card_number": "8600 0000 0000 0000",
    "card_owner": "Ism Familiya",
    "mandatory_channels": [],
    "stats": {
        "monthly_joins": {},
        "payments": []
    }
}

async def db_get():
    """JSONBin'dan ma'lumot olish"""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"X-Master-Key": JSONBIN_API_KEY}
            async with session.get(JSONBIN_URL + "/latest", headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("record", DEFAULT_DATA)
    except Exception as e:
        logger.error(f"DB GET xato: {e}")
    return DEFAULT_DATA

async def db_set(data: dict):
    """JSONBin'ga ma'lumot saqlash"""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "X-Master-Key": JSONBIN_API_KEY,
                "Content-Type": "application/json"
            }
            async with session.put(JSONBIN_URL, headers=headers, json=data) as resp:
                return resp.status == 200
    except Exception as e:
        logger.error(f"DB SET xato: {e}")
        return False

# ============================================================
# 🎛️ FSM - Holatlar
# ============================================================
class AdminStates(StatesGroup):
    # Kino qo'shish
    add_movie_poster = State()
    add_movie_name = State()
    add_movie_episodes = State()
    add_movie_lang = State()
    add_movie_watch_link = State()
    add_movie_code = State()
    add_movie_is_vip = State()
    # Epizod qo'shish
    add_episode_movie_code = State()
    add_episode_number = State()
    add_episode_video = State()
    add_episode_price = State()
    # Tarif qo'shish
    add_tariff_id = State()
    add_tariff_name = State()
    add_tariff_price = State()
    add_tariff_days = State()
    # Karta qo'shish
    set_card = State()
    # Majburiy obuna
    add_channel = State()
    # Statistika
    # Kanal post
    post_photo = State()
    post_name = State()
    post_episodes = State()
    post_lang = State()
    post_watch_link = State()
    post_confirm = State()
    # Xabar yuborish
    broadcast_msg = State()
    # Balans tasdiqlash
    confirm_payment_id = State()
    # VIP tasdiqlash
    vip_confirm_id = State()
    # Pulik qism
    paid_episode_movie = State()
    paid_episode_num = State()
    paid_episode_price = State()

class UserStates(StatesGroup):
    searching = State()
    top_up_amount = State()
    top_up_receipt = State()
    vip_receipt = State()
    vip_tariff = State()
    writing_admin = State()

# ============================================================
# 🎨 KLAVIATURA - Tugmalar
# ============================================================

def main_menu_keyboard():
    """Asosiy menyu - rangli tugmalar"""
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🎬 Kino Qidirish"), KeyboardButton(text="👑 VIP Obunalar")],
        [KeyboardButton(text="💰 Hisobim"), KeyboardButton(text="📢 Yangiliklar")],
        [KeyboardButton(text="📞 Admin bilan bog'lanish")]
    ], resize_keyboard=True)
    return kb

def admin_panel_keyboard():
    """Admin panel tugmalari"""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎬 Kino Qo'shish", callback_data="admin_add_movie"),
            InlineKeyboardButton(text="📹 Qism Qo'shish", callback_data="admin_add_episode")
        ],
        [
            InlineKeyboardButton(text="💳 Karta Raqam", callback_data="admin_set_card"),
            InlineKeyboardButton(text="⭐ Tarif Qo'shish", callback_data="admin_add_tariff")
        ],
        [
            InlineKeyboardButton(text="🔗 Majburiy Obuna", callback_data="admin_mandatory"),
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")
        ],
        [
            InlineKeyboardButton(text="📣 Kanal Post", callback_data="admin_post"),
            InlineKeyboardButton(text="📨 Xabar Yuborish", callback_data="admin_broadcast")
        ],
        [
            InlineKeyboardButton(text="💸 To'lovlar", callback_data="admin_payments"),
            InlineKeyboardButton(text="👑 VIP So'rovlar", callback_data="admin_vip_requests")
        ],
        [
            InlineKeyboardButton(text="💎 VIP Kino Qo'shish", callback_data="admin_add_vip_movie"),
            InlineKeyboardButton(text="🔒 Qismni Pulik", callback_data="admin_paid_episode")
        ]
    ])
    return kb

def back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_main")]
    ])

# ============================================================
# 🤖 BOT - Asosiy ishlovchilar
# ============================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ============================================================
# ✅ MAJBURIY OBUNA TEKSHIRISH
# ============================================================

async def check_subscription(user_id: int) -> bool:
    """Majburiy kanallarga obunani tekshirish"""
    db = await db_get()
    channels = db.get("mandatory_channels", [])
    for ch in channels:
        try:
            member = await bot.get_chat_member(ch, user_id)
            if member.status in ["left", "kicked", "restricted"]:
                return False
        except:
            pass
    return True

async def subscription_keyboard(db: dict) -> InlineKeyboardMarkup:
    """Obuna tugmalari"""
    buttons = []
    for ch in db.get("mandatory_channels", []):
        try:
            chat = await bot.get_chat(ch)
            invite = await bot.export_chat_invite_link(ch)
            buttons.append([InlineKeyboardButton(text=f"📢 {chat.title}", url=invite)])
        except:
            buttons.append([InlineKeyboardButton(text=f"📢 {ch}", url=f"https://t.me/{ch.lstrip('@')}")])
    buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ============================================================
# /start - BOSHLASH
# ============================================================

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name

    db = await db_get()

    # Foydalanuvchi ro'yxatdan o'tkazish
    if str(user_id) not in db["users"]:
        db["users"][str(user_id)] = {
            "id": user_id,
            "username": username,
            "name": full_name,
            "balance": 0,
            "vip_until": None,
            "joined": datetime.now().strftime("%Y-%m-%d"),
            "transactions": []
        }
        # Oylik statistika
        month_key = datetime.now().strftime("%Y-%m")
        db["stats"]["monthly_joins"][month_key] = db["stats"]["monthly_joins"].get(month_key, 0) + 1
        await db_set(db)

    # Majburiy obuna tekshirish
    if not await check_subscription(user_id):
        kb = await subscription_keyboard(db)
        await message.answer(
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=kb
        )
        return

    # Deep link - kino kodi
    args = message.text.split()
    if len(args) > 1:
        code = args[1]
        await show_movie_by_code(message, code, db)
        return

    await message.answer(
        f"🎬 <b>Salom, {full_name}!</b>\n\n"
        "🍿 Xush kelibsiz! Kino botiga xush kelibsiz!\n"
        "📱 Quyidagi tugmalardan foydalaning:",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(call: CallbackQuery):
    if await check_subscription(call.from_user.id):
        await call.message.delete()
        await call.message.answer(
            "✅ Obuna tasdiqlandi! Botdan foydalanishingiz mumkin.",
            reply_markup=main_menu_keyboard()
        )
    else:
        await call.answer("❌ Hali obuna bo'lmadingiz!", show_alert=True)

# ============================================================
# 🎬 KINO QIDIRISH
# ============================================================

@dp.message(F.text == "🎬 Kino Qidirish")
async def search_movie(message: Message, state: FSMContext):
    await state.set_state(UserStates.searching)
    await message.answer(
        "🔍 Kino kodini yoki nomini yozing:\n\n"
        "<i>Masalan: 001 yoki OMADLI ZARBA</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_search")]
        ]),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "cancel_search")
async def cancel_search(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("🏠 Asosiy menyu:", reply_markup=main_menu_keyboard())

@dp.message(UserStates.searching)
async def process_search(message: Message, state: FSMContext):
    await state.clear()
    query = message.text.strip()
    db = await db_get()
    await show_movie_by_code(message, query, db)

async def show_movie_by_code(message: Message, code: str, db: dict):
    """Kino kodiga qarab ko'rsatish"""
    movies = db.get("movies", {})
    movie = None

    # Kod bo'yicha qidirish
    if code.upper() in movies:
        movie = movies[code.upper()]
        movie_code = code.upper()
    else:
        # Nom bo'yicha qidirish
        for mc, mv in movies.items():
            if query_match(code, mv.get("name", "")):
                movie = mv
                movie_code = mc
                break

    if not movie:
        await message.answer(
            "❌ Kino topilmadi!\n\n"
            "🔍 Kino kodini to'g'ri kiriting yoki\n"
            "📢 Kanalimizda yangi kinolar e'lon qilinishini kuting.",
            reply_markup=main_menu_keyboard()
        )
        return

    # Epizodlar tugmalari
    episodes = movie.get("episodes", {})
    user_id = str(message.from_user.id)
    user = db["users"].get(user_id, {})

    buttons = []
    row = []
    for ep_num in sorted(episodes.keys(), key=lambda x: int(x)):
        ep = episodes[ep_num]
        price = ep.get("price", 0)

        if price > 0:
            # VIP tekshirish
            vip_until = user.get("vip_until")
            is_vip = vip_until and datetime.fromisoformat(vip_until) > datetime.now()
            if is_vip:
                label = f"🟢 {ep_num}-qism"
            else:
                label = f"🔴 {ep_num}-qism ({price:,}so'm)"
        else:
            label = f"🔵 {ep_num}-qism"

        row.append(InlineKeyboardButton(
            text=label,
            callback_data=f"ep_{movie_code}_{ep_num}"
        ))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="back_main")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    caption = (
        f"🎬 <b>{movie.get('name', '')}</b>\n\n"
        f"🎞 Qismlar: {len(episodes)}/{movie.get('total_episodes', '?')}\n"
        f"🌐 Til: {movie.get('lang', 'O\'zbek tilida')}\n"
        f"🔑 Kod: <code>{movie_code}</code>\n\n"
        f"📌 Qismni tanlang:"
    )

    poster = movie.get("poster")
    if poster:
        await message.answer_photo(
            photo=poster,
            caption=caption,
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        await message.answer(caption, reply_markup=kb, parse_mode="HTML")

def query_match(query: str, text: str) -> bool:
    return query.lower() in text.lower()

# ============================================================
# 📹 EPIZOD KO'RSATISH
# ============================================================

@dp.callback_query(F.data.startswith("ep_"))
async def show_episode(call: CallbackQuery):
    parts = call.data.split("_")
    movie_code = parts[1]
    ep_num = parts[2]

    db = await db_get()
    user_id = str(call.from_user.id)
    user = db["users"].get(user_id, {})
    movie = db["movies"].get(movie_code)

    if not movie:
        await call.answer("❌ Kino topilmadi!", show_alert=True)
        return

    episode = movie.get("episodes", {}).get(ep_num)
    if not episode:
        await call.answer("❌ Qism topilmadi!", show_alert=True)
        return

    price = episode.get("price", 0)

    if price > 0:
        # VIP tekshirish
        vip_until = user.get("vip_until")
        is_vip = vip_until and datetime.fromisoformat(vip_until) > datetime.now()

        if not is_vip:
            balance = user.get("balance", 0)
            # To'lov talab qilish
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"💳 Karta orqali ({price:,}so'm)", callback_data=f"pay_card_{movie_code}_{ep_num}")],
                [InlineKeyboardButton(text=f"💰 Balansdan to'lash ({balance:,}so'm)", callback_data=f"pay_balance_{movie_code}_{ep_num}")],
                [InlineKeyboardButton(text="◀️ Orqaga", callback_data=f"back_movie_{movie_code}")]
            ])
            await call.message.answer(
                f"🔒 <b>Bu qism pullik!</b>\n\n"
                f"💵 Narxi: <b>{price:,} so'm</b>\n"
                f"💰 Balansingiz: <b>{balance:,} so'm</b>\n\n"
                f"To'lov usulini tanlang:",
                reply_markup=kb,
                parse_mode="HTML"
            )
            return

    # Video yuborish - screenshot va yozib olishni bloklash
    video_file_id = episode.get("file_id")
    if not video_file_id:
        await call.answer("❌ Video topilmadi!", show_alert=True)
        return

    # Do'stlarga ulashish tugmasi (faqat kino kodi, video emas)
    share_text = f"🎬 {movie.get('name')} - {ep_num}-qismni ko'rdim!\n\n🔗 @{BOT_USERNAME} botiga /start {movie_code} yozing"
    share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start={movie_code}&text={share_text}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Do'stlarga ulashish", url=share_url)],
        [InlineKeyboardButton(text="◀️ Boshqa qismlar", callback_data=f"back_movie_{movie_code}")]
    ])

    await call.message.answer_video(
        video=video_file_id,
        caption=f"🎬 <b>{movie.get('name')}</b> — {ep_num}-qism\n\n"
                f"📌 Boshqa qismlar uchun: <code>{movie_code}</code>",
        reply_markup=kb,
        parse_mode="HTML",
        protect_content=True  # Screenshot va yozib olishni bloklaydi
    )

@dp.callback_query(F.data.startswith("back_movie_"))
async def back_to_movie(call: CallbackQuery):
    movie_code = call.data.split("_", 2)[2]
    db = await db_get()
    await show_movie_by_code(call.message, movie_code, db)

# ============================================================
# 💳 TO'LOV - KARTA ORQALI (qism)
# ============================================================

@dp.callback_query(F.data.startswith("pay_card_"))
async def pay_card_episode(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    movie_code = parts[2]
    ep_num = parts[3]

    db = await db_get()
    movie = db["movies"].get(movie_code, {})
    episode = movie.get("episodes", {}).get(ep_num, {})
    price = episode.get("price", 0)
    card = db.get("card_number", "Karta raqami yo'q")
    card_owner = db.get("card_owner", "")

    await state.update_data(
        pay_type="episode",
        movie_code=movie_code,
        ep_num=ep_num,
        amount=price
    )
    await state.set_state(UserStates.vip_receipt)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_payment")]
    ])

    await call.message.answer(
        f"💳 <b>To'lov Ma'lumotlari</b>\n\n"
        f"💰 Summa: <b>{price:,} so'm</b>\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"👤 Ism: <b>{card_owner}</b>\n\n"
        f"✅ To'lovni amalga oshirib, chek rasmini yuboring:",
        reply_markup=kb,
        parse_mode="HTML"
    )

# ============================================================
# 💰 BALANSDAN TO'LASH (qism)
# ============================================================

@dp.callback_query(F.data.startswith("pay_balance_"))
async def pay_balance_episode(call: CallbackQuery):
    parts = call.data.split("_")
    movie_code = parts[2]
    ep_num = parts[3]

    db = await db_get()
    user_id = str(call.from_user.id)
    user = db["users"].get(user_id, {})
    movie = db["movies"].get(movie_code, {})
    episode = movie.get("episodes", {}).get(ep_num, {})
    price = episode.get("price", 0)
    balance = user.get("balance", 0)

    if balance < price:
        await call.answer(
            f"❌ Balans yetarli emas!\nBalans: {balance:,} so'm\nNarx: {price:,} so'm",
            show_alert=True
        )
        return

    # To'lov
    db["users"][user_id]["balance"] -= price
    db["users"][user_id]["transactions"].append({
        "type": "episode_purchase",
        "amount": -price,
        "movie": movie.get("name"),
        "episode": ep_num,
        "date": datetime.now().isoformat()
    })
    await db_set(db)

    await call.answer(f"✅ To'lov muvaffaqiyatli! -{price:,} so'm", show_alert=True)

    # Videoni yuborish
    video_file_id = episode.get("file_id")
    share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start={movie_code}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Do'stlarga ulashish", url=share_url)],
        [InlineKeyboardButton(text="◀️ Boshqa qismlar", callback_data=f"back_movie_{movie_code}")]
    ])

    await call.message.answer_video(
        video=video_file_id,
        caption=f"🎬 <b>{movie.get('name')}</b> — {ep_num}-qism",
        reply_markup=kb,
        parse_mode="HTML",
        protect_content=True
    )

@dp.callback_query(F.data == "cancel_payment")
async def cancel_payment(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("❌ Bekor qilindi.", reply_markup=main_menu_keyboard())

# ============================================================
# 💰 HISOBIM
# ============================================================

@dp.message(F.text == "💰 Hisobim")
async def my_account(message: Message):
    db = await db_get()
    user_id = str(message.from_user.id)
    user = db["users"].get(user_id, {
        "balance": 0, "vip_until": None, "transactions": []
    })

    balance = user.get("balance", 0)
    vip_until = user.get("vip_until")
    vip_text = "❌ VIP obuna yo'q"
    if vip_until:
        vip_dt = datetime.fromisoformat(vip_until)
        if vip_dt > datetime.now():
            days_left = (vip_dt - datetime.now()).days
            vip_text = f"👑 VIP: {days_left} kun qoldi ({vip_dt.strftime('%d.%m.%Y')})"
        else:
            vip_text = "❌ VIP muddati tugagan"

    transactions = user.get("transactions", [])[-5:]
    tx_text = ""
    for tx in reversed(transactions):
        sign = "+" if tx.get("amount", 0) > 0 else ""
        tx_text += f"\n• {sign}{tx.get('amount', 0):,} so'm — {tx.get('type', '')}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Balansni To'ldirish", callback_data="topup_balance")],
        [InlineKeyboardButton(text="📜 Barcha Tarix", callback_data="full_history")]
    ])

    await message.answer(
        f"👤 <b>Hisobim</b>\n\n"
        f"🆔 ID: <code>{message.from_user.id}</code>\n"
        f"💰 Balans: <b>{balance:,} so'm</b>\n"
        f"{vip_text}\n\n"
        f"📊 So'nggi operatsiyalar:{tx_text or chr(10) + '• Tarix yo`q'}",
        reply_markup=kb,
        parse_mode="HTML"
    )

# ============================================================
# 💳 BALANS TO'LDIRISH
# ============================================================

@dp.callback_query(F.data == "topup_balance")
async def topup_balance(call: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.top_up_amount)
    await call.message.answer(
        "💰 Qancha miqdorda to'ldirmoqchisiz?\n\n"
        "Miqdorni yozing (so'mda):\n"
        "<i>Masalan: 50000</i>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_payment")]
        ]),
        parse_mode="HTML"
    )

@dp.message(UserStates.top_up_amount)
async def process_topup_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.replace(" ", "").replace(",", ""))
        if amount < 1000:
            await message.answer("❌ Minimal summa 1000 so'm!")
            return
    except:
        await message.answer("❌ Faqat raqam kiriting!")
        return

    db = await db_get()
    card = db.get("card_number", "Karta yo'q")
    card_owner = db.get("card_owner", "")

    await state.update_data(topup_amount=amount, pay_type="balance")
    await state.set_state(UserStates.top_up_receipt)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_payment")]
    ])

    await message.answer(
        f"💳 <b>To'lov Ma'lumotlari</b>\n\n"
        f"💰 Summa: <b>{amount:,} so'm</b>\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"👤 Egasi: <b>{card_owner}</b>\n\n"
        f"✅ To'lovni amalga oshirib, chek rasmini yuboring:",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.message(UserStates.top_up_receipt, F.photo)
async def process_topup_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("topup_amount", 0)
    await state.clear()

    # Adminlarga yuborish
    user = message.from_user
    request_id = f"topup_{user.id}_{int(datetime.now().timestamp())}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_topup_{user.id}_{amount}_{request_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"reject_topup_{user.id}_{amount}_{request_id}")
        ],
        [InlineKeyboardButton(text="📨 Xabar Yuborish", callback_data=f"msg_user_{user.id}")]
    ])

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                admin_id,
                message.photo[-1].file_id,
                caption=f"💳 <b>Balans To'ldirish So'rovi</b>\n\n"
                        f"👤 Foydalanuvchi: {user.full_name}\n"
                        f"🆔 ID: <code>{user.id}</code>\n"
                        f"💰 Summa: <b>{amount:,} so'm</b>\n"
                        f"🕐 Vaqt: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                reply_markup=kb,
                parse_mode="HTML"
            )
        except:
            pass

    await message.answer(
        "✅ Chek yuborildi! Admin tasdiqlashini kuting.",
        reply_markup=main_menu_keyboard()
    )

@dp.message(UserStates.top_up_receipt)
async def topup_receipt_not_photo(message: Message):
    await message.answer("📸 Iltimos, chek RASMINI yuboring!")

# ============================================================
# ✅ TO'LOV TASDIQLASH (Admin)
# ============================================================

@dp.callback_query(F.data.startswith("approve_topup_"))
async def approve_topup(call: CallbackQuery):
    parts = call.data.split("_")
    user_id = parts[2]
    amount = int(parts[3])

    db = await db_get()
    if user_id not in db["users"]:
        db["users"][user_id] = {"balance": 0, "transactions": []}

    db["users"][user_id]["balance"] = db["users"][user_id].get("balance", 0) + amount
    db["users"][user_id].setdefault("transactions", []).append({
        "type": "topup",
        "amount": amount,
        "date": datetime.now().isoformat()
    })
    db["stats"]["payments"].append({
        "user_id": user_id,
        "amount": amount,
        "type": "topup",
        "date": datetime.now().isoformat()
    })
    await db_set(db)

    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"✅ {user_id} foydalanuvchiga {amount:,} so'm qo'shildi!")

    try:
        await bot.send_message(
            int(user_id),
            f"✅ <b>Balans To'ldirildi!</b>\n\n"
            f"💰 +{amount:,} so'm\n"
            f"💳 Yangi balans: {db['users'][user_id]['balance']:,} so'm",
            parse_mode="HTML"
        )
    except:
        pass

@dp.callback_query(F.data.startswith("reject_topup_"))
async def reject_topup(call: CallbackQuery):
    parts = call.data.split("_")
    user_id = parts[2]
    amount = int(parts[3])

    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"❌ {user_id} so'rovi bekor qilindi!")

    try:
        await bot.send_message(
            int(user_id),
            f"❌ <b>Balans to'ldirish bekor qilindi!</b>\n\n"
            f"💰 So'ralgan summa: {amount:,} so'm\n"
            f"📞 Muammo bo'lsa admin bilan bog'laning.",
            parse_mode="HTML"
        )
    except:
        pass

# ============================================================
# 👑 VIP OBUNALAR
# ============================================================

@dp.message(F.text == "👑 VIP Obunalar")
async def vip_page(message: Message):
    db = await db_get()
    tariffs = db.get("tariffs", {})

    buttons = []
    for tariff_id, tariff in tariffs.items():
        buttons.append([InlineKeyboardButton(
            text=f"⭐ {tariff['name']} — {tariff['price']:,} so'm",
            callback_data=f"buy_vip_{tariff_id}"
        )])

    buttons.append([InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="back_main")])

    user_id = str(message.from_user.id)
    user = db["users"].get(user_id, {})
    vip_until = user.get("vip_until")
    vip_status = "❌ VIP obuna yo'q"
    if vip_until:
        vip_dt = datetime.fromisoformat(vip_until)
        if vip_dt > datetime.now():
            days_left = (vip_dt - datetime.now()).days
            vip_status = f"👑 VIP: {days_left} kun qoldi"

    await message.answer(
        f"👑 <b>VIP Obunalar</b>\n\n"
        f"📊 Holat: {vip_status}\n\n"
        f"✨ VIP obuna afzalliklari:\n"
        f"• Barcha pullik qismlarni bepul ko'rish\n"
        f"• Yangi qismlar birinchi bo'lib\n"
        f"• Reklama yo'q\n\n"
        f"💎 Tarifni tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("buy_vip_"))
async def buy_vip(call: CallbackQuery, state: FSMContext):
    tariff_id = call.data.split("_")[2]
    db = await db_get()
    tariff = db.get("tariffs", {}).get(tariff_id)

    if not tariff:
        await call.answer("❌ Tarif topilmadi!", show_alert=True)
        return

    card = db.get("card_number", "Karta yo'q")
    card_owner = db.get("card_owner", "")
    user = db["users"].get(str(call.from_user.id), {})
    balance = user.get("balance", 0)

    await state.update_data(vip_tariff_id=tariff_id, pay_type="vip")
    await state.set_state(UserStates.vip_receipt)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"💰 Balansdan ({balance:,} so'm)", callback_data=f"vip_from_balance_{tariff_id}")],
        [InlineKeyboardButton(text="💳 Karta orqali to'lash", callback_data=f"vip_card_{tariff_id}")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_payment")]
    ])

    await call.message.answer(
        f"⭐ <b>{tariff['name']}</b>\n\n"
        f"💰 Narxi: <b>{tariff['price']:,} so'm</b>\n"
        f"📅 Muddat: {tariff['days']} kun\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"👤 Egasi: <b>{card_owner}</b>\n\n"
        f"To'lov usulini tanlang:",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("vip_from_balance_"))
async def vip_from_balance(call: CallbackQuery, state: FSMContext):
    await state.clear()
    tariff_id = call.data.split("_")[3]
    db = await db_get()
    user_id = str(call.from_user.id)
    user = db["users"].get(user_id, {})
    tariff = db.get("tariffs", {}).get(tariff_id, {})

    balance = user.get("balance", 0)
    price = tariff.get("price", 0)

    if balance < price:
        await call.answer(
            f"❌ Balans yetarli emas!\nBalans: {balance:,} so'm\nNarx: {price:,} so'm",
            show_alert=True
        )
        return

    # VIP berish
    db["users"][user_id]["balance"] -= price
    days = tariff.get("days", 30)
    current_vip = user.get("vip_until")
    if current_vip and datetime.fromisoformat(current_vip) > datetime.now():
        new_vip = datetime.fromisoformat(current_vip) + timedelta(days=days)
    else:
        new_vip = datetime.now() + timedelta(days=days)

    db["users"][user_id]["vip_until"] = new_vip.isoformat()
    db["users"][user_id].setdefault("transactions", []).append({
        "type": "vip_purchase",
        "amount": -price,
        "tariff": tariff.get("name"),
        "date": datetime.now().isoformat()
    })
    await db_set(db)

    await call.message.answer(
        f"👑 <b>VIP obuna faollashtirildi!</b>\n\n"
        f"⭐ Tarif: {tariff.get('name')}\n"
        f"📅 Muddat: {new_vip.strftime('%d.%m.%Y')}\n"
        f"💰 -{price:,} so'm\n\n"
        f"Barcha VIP kontentdan bahramand bo'ling!",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("vip_card_"))
async def vip_card(call: CallbackQuery, state: FSMContext):
    tariff_id = call.data.split("_")[2]
    db = await db_get()
    tariff = db.get("tariffs", {}).get(tariff_id, {})
    card = db.get("card_number", "Karta yo'q")
    card_owner = db.get("card_owner", "")

    await state.update_data(vip_tariff_id=tariff_id, pay_type="vip")
    await state.set_state(UserStates.vip_receipt)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_payment")]
    ])

    await call.message.answer(
        f"💳 <b>VIP To'lov</b>\n\n"
        f"💰 Summa: <b>{tariff.get('price', 0):,} so'm</b>\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"👤 Egasi: <b>{card_owner}</b>\n\n"
        f"✅ To'lovni amalga oshirib, chek rasmini yuboring:",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.message(UserStates.vip_receipt, F.photo)
async def process_vip_receipt(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    pay_type = data.get("pay_type", "vip")
    tariff_id = data.get("vip_tariff_id", "")
    movie_code = data.get("movie_code", "")
    ep_num = data.get("ep_num", "")
    amount = data.get("amount", 0)

    db = await db_get()
    user = message.from_user
    request_id = f"{pay_type}_{user.id}_{int(datetime.now().timestamp())}"

    if pay_type == "vip":
        tariff = db.get("tariffs", {}).get(tariff_id, {})
        amount = tariff.get("price", 0)
        info = f"👑 VIP: {tariff.get('name', tariff_id)}\n💰 Summa: {amount:,} so'm"
        approve_cb = f"approve_vip_{user.id}_{tariff_id}_{request_id}"
        reject_cb = f"reject_vip_{user.id}_{tariff_id}_{request_id}"
    else:
        info = f"🎬 Kino: {movie_code} — {ep_num}-qism\n💰 Summa: {amount:,} so'm"
        approve_cb = f"approve_ep_{user.id}_{movie_code}_{ep_num}_{amount}"
        reject_cb = f"reject_ep_{user.id}_{movie_code}_{ep_num}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=approve_cb),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=reject_cb)
        ],
        [InlineKeyboardButton(text="📨 Xabar Yuborish", callback_data=f"msg_user_{user.id}")]
    ])

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                admin_id,
                message.photo[-1].file_id,
                caption=f"💳 <b>To'lov So'rovi</b>\n\n"
                        f"👤 {user.full_name} | <code>{user.id}</code>\n"
                        f"{info}\n"
                        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                reply_markup=kb,
                parse_mode="HTML"
            )
        except:
            pass

    await message.answer("✅ Chek yuborildi! Admin tasdiqlashini kuting.", reply_markup=main_menu_keyboard())

@dp.message(UserStates.vip_receipt)
async def vip_receipt_not_photo(message: Message):
    await message.answer("📸 Iltimos, chek RASMINI yuboring!")

# VIP Tasdiqlash
@dp.callback_query(F.data.startswith("approve_vip_"))
async def approve_vip(call: CallbackQuery):
    parts = call.data.split("_")
    user_id = parts[2]
    tariff_id = parts[3]

    db = await db_get()
    tariff = db.get("tariffs", {}).get(tariff_id, {})
    days = tariff.get("days", 30)
    price = tariff.get("price", 0)

    user_data = db["users"].setdefault(user_id, {})
    current_vip = user_data.get("vip_until")
    if current_vip and datetime.fromisoformat(current_vip) > datetime.now():
        new_vip = datetime.fromisoformat(current_vip) + timedelta(days=days)
    else:
        new_vip = datetime.now() + timedelta(days=days)

    db["users"][user_id]["vip_until"] = new_vip.isoformat()
    db["stats"]["payments"].append({
        "user_id": user_id, "amount": price, "type": "vip",
        "tariff": tariff_id, "date": datetime.now().isoformat()
    })
    await db_set(db)

    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"✅ {user_id} uchun VIP faollashtirildi! ({days} kun)")

    try:
        await bot.send_message(
            int(user_id),
            f"👑 <b>VIP Obuna Faollashtirildi!</b>\n\n"
            f"⭐ {tariff.get('name')}\n"
            f"📅 Amal qilish muddati: {new_vip.strftime('%d.%m.%Y')}\n\n"
            f"Tabriklaymiz! 🎉",
            parse_mode="HTML"
        )
    except:
        pass

@dp.callback_query(F.data.startswith("reject_vip_"))
async def reject_vip(call: CallbackQuery):
    parts = call.data.split("_")
    user_id = parts[2]
    tariff_id = parts[3]
    db = await db_get()
    tariff = db.get("tariffs", {}).get(tariff_id, {})

    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"❌ {user_id} VIP so'rovi bekor qilindi!")

    try:
        await bot.send_message(
            int(user_id),
            f"❌ <b>VIP so'rov rad etildi</b>\n\n"
            f"Tarif: {tariff.get('name', tariff_id)}\n"
            f"📞 Muammo bo'lsa admin bilan bog'laning.",
            parse_mode="HTML"
        )
    except:
        pass

# Epizod to'lovini tasdiqlash
@dp.callback_query(F.data.startswith("approve_ep_"))
async def approve_episode_payment(call: CallbackQuery):
    parts = call.data.split("_")
    user_id = parts[2]
    movie_code = parts[3]
    ep_num = parts[4]
    amount = int(parts[5])

    db = await db_get()
    movie = db["movies"].get(movie_code, {})
    episode = movie.get("episodes", {}).get(ep_num, {})

    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"✅ {user_id} uchun {movie_code} — {ep_num}-qism tasdiqlandi!")

    video_file_id = episode.get("file_id")
    if video_file_id:
        share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start={movie_code}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Do'stlarga ulashish", url=share_url)],
        ])
        try:
            await bot.send_video(
                int(user_id),
                video_file_id,
                caption=f"🎬 <b>{movie.get('name')}</b> — {ep_num}-qism\n✅ To'lov tasdiqlandi!",
                reply_markup=kb,
                parse_mode="HTML",
                protect_content=True
            )
        except:
            pass

@dp.callback_query(F.data.startswith("reject_ep_"))
async def reject_episode_payment(call: CallbackQuery):
    parts = call.data.split("_")
    user_id = parts[2]
    movie_code = parts[3]
    ep_num = parts[4]

    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"❌ {user_id} epizod to'lovi bekor qilindi!")

    try:
        await bot.send_message(
            int(user_id),
            f"❌ <b>To'lov rad etildi</b>\n\n"
            f"Kino: {movie_code} — {ep_num}-qism\n"
            f"📞 Muammo bo'lsa admin bilan bog'laning.",
            parse_mode="HTML"
        )
    except:
        pass

# ============================================================
# 📞 ADMIN BILAN BOG'LANISH
# ============================================================

@dp.message(F.text == "📞 Admin bilan bog'lanish")
async def contact_admin(message: Message, state: FSMContext):
    await state.set_state(UserStates.writing_admin)
    await message.answer(
        "✍️ Adminга xabar yozing (matn, rasm yoki ovozli xabar):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_contact")]
        ])
    )

@dp.callback_query(F.data == "cancel_contact")
async def cancel_contact(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.message.answer("❌ Bekor qilindi.", reply_markup=main_menu_keyboard())

@dp.message(UserStates.writing_admin)
async def forward_to_admin(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Javob berish", callback_data=f"msg_user_{user.id}")]
    ])

    header = (
        f"📨 <b>Foydalanuvchi xabari</b>\n"
        f"👤 {user.full_name} | <code>{user.id}</code>\n"
        f"━━━━━━━━━━━━━━━\n"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, header, parse_mode="HTML")
            await message.forward(admin_id)
            await bot.send_message(admin_id, "━━━━━━━━━━━━━━━", reply_markup=kb)
        except:
            pass

    await message.answer("✅ Xabaringiz adminga yuborildi!", reply_markup=main_menu_keyboard())

# Admin - foydalanuvchiga xabar yuborish
@dp.callback_query(F.data.startswith("msg_user_"))
async def msg_user_prompt(call: CallbackQuery, state: FSMContext):
    user_id = call.data.split("_")[2]
    await state.update_data(msg_target=user_id)
    await state.set_state(AdminStates.broadcast_msg)
    await call.message.answer(
        f"✍️ {user_id} foydalanuvchiga xabar yozing:"
    )

# ============================================================
# 📢 YANGILIKLAR
# ============================================================

@dp.message(F.text == "📢 Yangiliklar")
async def news(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga o'tish", url=f"https://t.me/{CHANNEL_ID.lstrip('@')}")],
        [InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="back_main")]
    ])
    await message.answer(
        "📢 <b>Yangi kinolar va yangiliklar!</b>\n\n"
        "Kanalimizga obuna bo'ling va birinchilardan bo'ling!",
        reply_markup=kb,
        parse_mode="HTML"
    )

# ============================================================
# 🔙 ORQAGA
# ============================================================

@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("🏠 Asosiy menyu:", reply_markup=main_menu_keyboard())

# ============================================================
# 👨‍💼 ADMIN PANEL
# ============================================================

@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer(
        "👨‍💼 <b>Admin Panel</b>\n\nNimani qilmoqchisiz?",
        reply_markup=admin_panel_keyboard(),
        parse_mode="HTML"
    )

# ============================================================
# 🎬 KINO QO'SHISH (Admin)
# ============================================================

@dp.callback_query(F.data == "admin_add_movie")
async def admin_add_movie(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminStates.add_movie_poster)
    await call.message.answer(
        "🖼 Kino posterini yuboring (rasm):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")]
        ])
    )

@dp.message(AdminStates.add_movie_poster, F.photo)
async def add_movie_poster(message: Message, state: FSMContext):
    await state.update_data(poster=message.photo[-1].file_id)
    await state.set_state(AdminStates.add_movie_name)
    await message.answer("✏️ Kino nomini kiriting:")

@dp.message(AdminStates.add_movie_name)
async def add_movie_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AdminStates.add_movie_episodes)
    await message.answer("🎞 Jami qismlar sonini kiriting (masalan: 100):")

@dp.message(AdminStates.add_movie_episodes)
async def add_movie_episodes(message: Message, state: FSMContext):
    try:
        total = int(message.text)
        await state.update_data(total_episodes=total)
        await state.set_state(AdminStates.add_movie_lang)
        await message.answer("🌐 Tilini kiriting (masalan: O'zbek tilida):")
    except:
        await message.answer("❌ Faqat raqam kiriting!")

@dp.message(AdminStates.add_movie_lang)
async def add_movie_lang(message: Message, state: FSMContext):
    await state.update_data(lang=message.text)
    await state.set_state(AdminStates.add_movie_watch_link)
    await message.answer("🔗 Ko'rish linkini kiriting (yoki - yozing):")

@dp.message(AdminStates.add_movie_watch_link)
async def add_movie_watch_link(message: Message, state: FSMContext):
    await state.update_data(watch_link=message.text if message.text != "-" else "")
    await state.set_state(AdminStates.add_movie_code)
    await message.answer("🔑 Kino kodini kiriting (masalan: OZ001):")

@dp.message(AdminStates.add_movie_code)
async def add_movie_code_input(message: Message, state: FSMContext):
    code = message.text.upper().strip()
    await state.update_data(code=code)
    await state.set_state(AdminStates.add_movie_is_vip)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🆓 Bepul", callback_data="movie_free"),
            InlineKeyboardButton(text="👑 VIP", callback_data="movie_vip")
        ]
    ])
    await message.answer("💎 Kino turi:", reply_markup=kb)

@dp.callback_query(F.data.in_(["movie_free", "movie_vip"]))
async def save_movie(call: CallbackQuery, state: FSMContext):
    is_vip = call.data == "movie_vip"
    data = await state.get_data()
    await state.clear()

    code = data.get("code", "")
    db = await db_get()

    db["movies"][code] = {
        "name": data.get("name", ""),
        "poster": data.get("poster", ""),
        "total_episodes": data.get("total_episodes", 0),
        "lang": data.get("lang", "O'zbek tilida"),
        "watch_link": data.get("watch_link", ""),
        "is_vip": is_vip,
        "episodes": {},
        "created": datetime.now().isoformat()
    }
    await db_set(db)

    await call.message.answer(
        f"✅ <b>Kino saqlandi!</b>\n\n"
        f"🎬 Nom: {data.get('name')}\n"
        f"🔑 Kod: <code>{code}</code>\n"
        f"{'👑 VIP' if is_vip else '🆓 Bepul'}",
        reply_markup=admin_panel_keyboard(),
        parse_mode="HTML"
    )

# ============================================================
# 📹 QISM QO'SHISH (Admin)
# ============================================================

@dp.callback_query(F.data == "admin_add_episode")
async def admin_add_episode(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminStates.add_episode_movie_code)
    await call.message.answer("🔑 Kino kodini kiriting:")

@dp.message(AdminStates.add_episode_movie_code)
async def add_episode_movie_code(message: Message, state: FSMContext):
    code = message.text.upper().strip()
    db = await db_get()
    if code not in db["movies"]:
        await message.answer(f"❌ '{code}' kodli kino topilmadi!")
        return
    await state.update_data(episode_movie_code=code)
    await state.set_state(AdminStates.add_episode_number)
    movie = db["movies"][code]
    existing = list(movie.get("episodes", {}).keys())
    await message.answer(
        f"🎬 Kino: <b>{movie['name']}</b>\n"
        f"📋 Mavjud qismlar: {', '.join(sorted(existing, key=int)) if existing else 'yo`q'}\n\n"
        f"📌 Yangi qism raqamini kiriting:",
        parse_mode="HTML"
    )

@dp.message(AdminStates.add_episode_number)
async def add_episode_number(message: Message, state: FSMContext):
    try:
        num = int(message.text)
        await state.update_data(episode_number=str(num))
        await state.set_state(AdminStates.add_episode_video)
        await message.answer(f"🎥 {num}-qism videosini yuboring:")
    except:
        await message.answer("❌ Faqat raqam kiriting!")

@dp.message(AdminStates.add_episode_video, F.video)
async def add_episode_video(message: Message, state: FSMContext):
    await state.update_data(episode_file_id=message.video.file_id)
    await state.set_state(AdminStates.add_episode_price)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆓 Bepul", callback_data="ep_price_free")]
    ])
    await message.answer(
        "💰 Qism narxini kiriting (so'mda) yoki bepul tanlang:\n<i>Masalan: 5000</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "ep_price_free")
async def ep_price_free(call: CallbackQuery, state: FSMContext):
    await save_episode(call.message, state, 0)

@dp.message(AdminStates.add_episode_price)
async def add_episode_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.replace(" ", "").replace(",", ""))
        await save_episode(message, state, price)
    except:
        await message.answer("❌ Faqat raqam kiriting!")

async def save_episode(message: Message, state: FSMContext, price: int):
    data = await state.get_data()
    await state.clear()

    movie_code = data.get("episode_movie_code")
    ep_num = data.get("episode_number")
    file_id = data.get("episode_file_id")

    db = await db_get()
    db["movies"][movie_code]["episodes"][ep_num] = {
        "file_id": file_id,
        "price": price,
        "added": datetime.now().isoformat()
    }
    await db_set(db)

    movie_name = db["movies"][movie_code].get("name", movie_code)
    await message.answer(
        f"✅ <b>Qism saqlandi!</b>\n\n"
        f"🎬 {movie_name}\n"
        f"📌 {ep_num}-qism\n"
        f"💰 Narx: {'Bepul' if price == 0 else f'{price:,} so`m'}",
        reply_markup=admin_panel_keyboard(),
        parse_mode="HTML"
    )

# ============================================================
# 💳 KARTA RAQAM (Admin)
# ============================================================

@dp.callback_query(F.data == "admin_set_card")
async def admin_set_card(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminStates.set_card)
    db = await db_get()
    current = db.get("card_number", "Yo'q")
    owner = db.get("card_owner", "Yo'q")
    await call.message.answer(
        f"💳 Joriy karta: <code>{current}</code>\n"
        f"👤 Egasi: {owner}\n\n"
        f"Yangi karta raqam va egasini yozing:\n"
        f"<i>Format: 8600 1234 5678 9012 | Ism Familiya</i>",
        parse_mode="HTML"
    )

@dp.message(AdminStates.set_card)
async def save_card(message: Message, state: FSMContext):
    await state.clear()
    parts = message.text.split("|")
    card = parts[0].strip()
    owner = parts[1].strip() if len(parts) > 1 else ""

    db = await db_get()
    db["card_number"] = card
    db["card_owner"] = owner
    await db_set(db)

    await message.answer(
        f"✅ Karta yangilandi!\n💳 {card}\n👤 {owner}",
        reply_markup=admin_panel_keyboard()
    )

# ============================================================
# ⭐ TARIF QO'SHISH (Admin)
# ============================================================

@dp.callback_query(F.data == "admin_add_tariff")
async def admin_add_tariff(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminStates.add_tariff_id)
    await call.message.answer("🔑 Tarif ID kiriting (masalan: 1oy):")

@dp.message(AdminStates.add_tariff_id)
async def tariff_id(message: Message, state: FSMContext):
    await state.update_data(tariff_id=message.text.strip())
    await state.set_state(AdminStates.add_tariff_name)
    await message.answer("✏️ Tarif nomini kiriting (masalan: 1 Oylik VIP):")

@dp.message(AdminStates.add_tariff_name)
async def tariff_name(message: Message, state: FSMContext):
    await state.update_data(tariff_name=message.text)
    await state.set_state(AdminStates.add_tariff_price)
    await message.answer("💰 Narxini kiriting (so'mda):")

@dp.message(AdminStates.add_tariff_price)
async def tariff_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.replace(" ", "").replace(",", ""))
        await state.update_data(tariff_price=price)
        await state.set_state(AdminStates.add_tariff_days)
        await message.answer("📅 Necha kunlik (masalan: 30):")
    except:
        await message.answer("❌ Faqat raqam!")

@dp.message(AdminStates.add_tariff_days)
async def tariff_days(message: Message, state: FSMContext):
    try:
        days = int(message.text)
        data = await state.get_data()
        await state.clear()

        db = await db_get()
        tariff_id = data.get("tariff_id")
        db["tariffs"][tariff_id] = {
            "name": data.get("tariff_name"),
            "price": data.get("tariff_price"),
            "days": days
        }
        await db_set(db)

        await message.answer(
            f"✅ Tarif qo'shildi!\n"
            f"⭐ {data.get('tariff_name')}\n"
            f"💰 {data.get('tariff_price'):,} so'm | {days} kun",
            reply_markup=admin_panel_keyboard()
        )
    except:
        await message.answer("❌ Faqat raqam!")

# ============================================================
# 🔗 MAJBURIY OBUNA (Admin)
# ============================================================

@dp.callback_query(F.data == "admin_mandatory")
async def admin_mandatory(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    db = await db_get()
    channels = db.get("mandatory_channels", [])

    buttons = []
    for ch in channels:
        buttons.append([
            InlineKeyboardButton(text=f"🗑 {ch}", callback_data=f"del_channel_{ch.lstrip('@')}")
        ])
    buttons.append([InlineKeyboardButton(text="➕ Kanal Qo'shish", callback_data="add_channel")])
    buttons.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="back_admin")])

    await call.message.answer(
        f"🔗 <b>Majburiy Obunalar</b>\n\n"
        f"Jami: {len(channels)} ta kanal\n\n"
        f"{''.join([f'• {ch}' + chr(10) for ch in channels]) or 'Hali kanal yo`q'}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "add_channel")
async def add_channel_prompt(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.add_channel)
    await call.message.answer(
        "📢 Kanal/bot/link qo'shing:\n\n"
        "• Telegram kanal: @kanal_nomi\n"
        "• Bot: @bot_nomi\n"
        "• Oddiy link: https://t.me/...\n\n"
        "Linkni yozing:"
    )

@dp.message(AdminStates.add_channel)
async def save_channel(message: Message, state: FSMContext):
    await state.clear()
    channel = message.text.strip()
    db = await db_get()
    channels = db.setdefault("mandatory_channels", [])
    if channel not in channels:
        channels.append(channel)
        await db_set(db)
        await message.answer(f"✅ '{channel}' qo'shildi!", reply_markup=admin_panel_keyboard())
    else:
        await message.answer(f"⚠️ '{channel}' allaqachon mavjud!")

@dp.callback_query(F.data.startswith("del_channel_"))
async def del_channel(call: CallbackQuery):
    ch = "@" + call.data.split("_", 2)[2]
    db = await db_get()
    if ch in db.get("mandatory_channels", []):
        db["mandatory_channels"].remove(ch)
        await db_set(db)
    await call.answer(f"✅ {ch} o'chirildi!", show_alert=True)
    await admin_mandatory(call, None)

# ============================================================
# 📊 STATISTIKA (Admin)
# ============================================================

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    db = await db_get()

    users = db.get("users", {})
    movies = db.get("movies", {})
    payments = db.get("stats", {}).get("payments", [])

    # Oylik qo'shilganlar
    month_key = datetime.now().strftime("%Y-%m")
    monthly_joins = db.get("stats", {}).get("monthly_joins", {})
    this_month = monthly_joins.get(month_key, 0)

    # Haftalik hisob to'ldirishlar
    week_ago = datetime.now() - timedelta(days=7)
    weekly_topups = [p for p in payments
                     if datetime.fromisoformat(p.get("date", "2000-01-01")) > week_ago]
    weekly_topup_count = len(weekly_topups)
    weekly_topup_sum = sum(p.get("amount", 0) for p in weekly_topups)

    # VIP foydalanuvchilar
    vip_users = [u for u in users.values()
                 if u.get("vip_until") and
                 datetime.fromisoformat(u.get("vip_until", "2000-01-01")) > datetime.now()]
    vip_count = len(vip_users)
    vip_revenue = sum(p.get("amount", 0) for p in payments if p.get("type") == "vip")

    # Top 15 balans
    top_users = sorted(users.values(), key=lambda x: x.get("balance", 0), reverse=True)[:15]
    top_text = ""
    for i, u in enumerate(top_users, 1):
        top_text += f"{i}. {u.get('name', 'Noma`lum')}: {u.get('balance', 0):,} so'm\n"

    # Oylik payments
    monthly_payments = [p for p in payments
                        if datetime.fromisoformat(p.get("date", "2000-01-01")).strftime("%Y-%m") == month_key]
    monthly_sum = sum(p.get("amount", 0) for p in monthly_payments)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Admin Panel", callback_data="back_admin")]
    ])

    await call.message.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: {len(users)}\n"
        f"📈 Bu oy qo'shildi: {this_month}\n"
        f"🎬 Jami kinolar: {len(movies)}\n\n"
        f"👑 VIP foydalanuvchilar: {vip_count}\n"
        f"💰 VIP daromad: {vip_revenue:,} so'm\n\n"
        f"📅 Haftalik hisob to'ldirish:\n"
        f"  • {weekly_topup_count} ta | {weekly_topup_sum:,} so'm\n\n"
        f"📅 Bu oy daromad: {monthly_sum:,} so'm\n\n"
        f"🏆 Top 15 balans:\n{top_text or 'Ma`lumot yo`q'}",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "back_admin")
async def back_admin(call: CallbackQuery):
    await call.message.answer("👨‍💼 Admin Panel:", reply_markup=admin_panel_keyboard())

# ============================================================
# 📣 KANAL POST (Admin)
# ============================================================

@dp.callback_query(F.data == "admin_post")
async def admin_post(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminStates.post_photo)
    await call.message.answer(
        "🖼 Post uchun rasm yuboring:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")]
        ])
    )

@dp.message(AdminStates.post_photo, F.photo)
async def post_photo(message: Message, state: FSMContext):
    await state.update_data(post_photo=message.photo[-1].file_id)
    await state.set_state(AdminStates.post_name)
    await message.answer("✏️ Kino nomini kiriting:")

@dp.message(AdminStates.post_name)
async def post_name(message: Message, state: FSMContext):
    await state.update_data(post_name=message.text)
    await state.set_state(AdminStates.post_episodes)
    await message.answer("🎞 Qismlar (masalan: 100/7):")

@dp.message(AdminStates.post_episodes)
async def post_episodes(message: Message, state: FSMContext):
    await state.update_data(post_episodes=message.text)
    await state.set_state(AdminStates.post_lang)
    await message.answer("🌐 Tili:")

@dp.message(AdminStates.post_lang)
async def post_lang(message: Message, state: FSMContext):
    await state.update_data(post_lang=message.text)
    await state.set_state(AdminStates.post_watch_link)
    await message.answer("🔗 Ko'rish linki (botga deep link yoki kanal linki):")

@dp.message(AdminStates.post_watch_link)
async def post_watch_link_input(message: Message, state: FSMContext):
    await state.update_data(post_watch_link=message.text)
    await state.set_state(AdminStates.post_confirm)
    data = await state.get_data()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yuborish", callback_data="confirm_post"),
            InlineKeyboardButton(text="❌ Bekor", callback_data="admin_cancel")
        ]
    ])

    await message.answer_photo(
        data["post_photo"],
        caption=f"🎬 <b>{data['post_name']}</b>\n\n"
                f"▶️ Qism: {data['post_episodes']}\n"
                f"🌐 Til: {data['post_lang']}\n"
                f"🔗 Ko'rish: {data['post_watch_link']}\n\n"
                f"<i>Preview — tasdiqlaysizmi?</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "confirm_post")
async def confirm_post(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="▶️ Tomosha qilish ◀️", url=data["post_watch_link"])]
    ])

    await bot.send_photo(
        CHANNEL_ID,
        data["post_photo"],
        caption=f"🎬 <b>{data['post_name']}</b>\n\n"
                f"▶️ Qism: {data['post_episodes']}\n"
                f"🌐 Til: {data['post_lang']}",
        reply_markup=kb,
        parse_mode="HTML"
    )

    await call.message.answer("✅ Post kanalga yuborildi!", reply_markup=admin_panel_keyboard())

# ============================================================
# 📨 XABAR YUBORISH (Admin)
# ============================================================

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.update_data(msg_target="all")
    await state.set_state(AdminStates.broadcast_msg)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Hammaga", callback_data="broadcast_all"),
            InlineKeyboardButton(text="👑 VIP larga", callback_data="broadcast_vip"),
            InlineKeyboardButton(text="🆓 Bepullarga", callback_data="broadcast_free")
        ],
        [InlineKeyboardButton(text="❌ Bekor", callback_data="admin_cancel")]
    ])
    await call.message.answer("📨 Kimga yubormoqchisiz?", reply_markup=kb)

@dp.callback_query(F.data.startswith("broadcast_"))
async def broadcast_target(call: CallbackQuery, state: FSMContext):
    target = call.data.split("_")[1]
    await state.update_data(msg_target=target)
    await state.set_state(AdminStates.broadcast_msg)
    await call.message.answer("✍️ Yubormoqchi bo'lgan xabarni yozing (matn, rasm, video, ovoz):")

@dp.message(AdminStates.broadcast_msg)
async def send_broadcast(message: Message, state: FSMContext):
    data = await state.get_data()
    target = data.get("msg_target", "all")
    await state.clear()

    db = await db_get()
    users = db.get("users", {})

    # Maqsadli foydalanuvchilar
    if target == "all":
        targets = list(users.keys())
    elif target == "vip":
        targets = [uid for uid, u in users.items()
                   if u.get("vip_until") and
                   datetime.fromisoformat(u.get("vip_until", "2000-01-01")) > datetime.now()]
    elif target == "free":
        targets = [uid for uid, u in users.items()
                   if not u.get("vip_until") or
                   datetime.fromisoformat(u.get("vip_until", "2000-01-01")) <= datetime.now()]
    else:
        # Bitta foydalanuvchi
        targets = [target]

    sent = 0
    failed = 0

    for uid in targets:
        try:
            if message.photo:
                await bot.send_photo(int(uid), message.photo[-1].file_id, caption=message.caption or "")
            elif message.video:
                await bot.send_video(int(uid), message.video.file_id, caption=message.caption or "")
            elif message.voice:
                await bot.send_voice(int(uid), message.voice.file_id)
            elif message.audio:
                await bot.send_audio(int(uid), message.audio.file_id)
            else:
                await bot.send_message(int(uid), message.text or "")
            sent += 1
            await asyncio.sleep(0.05)  # Flood limitdan qochish
        except:
            failed += 1

    await message.answer(
        f"📨 Xabar yuborildi!\n✅ Muvaffaqiyatli: {sent}\n❌ Xato: {failed}",
        reply_markup=admin_panel_keyboard()
    )

# ============================================================
# 💸 TO'LOVLAR (Admin)
# ============================================================

@dp.callback_query(F.data == "admin_payments")
async def admin_payments(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    db = await db_get()
    payments = db.get("stats", {}).get("payments", [])[-20:]

    text = "💸 <b>So'nggi to'lovlar</b>\n\n"
    for p in reversed(payments):
        date = datetime.fromisoformat(p.get("date", "2000-01-01")).strftime("%d.%m %H:%M")
        text += f"• {p.get('type', '')} | {p.get('amount', 0):,} so'm | {date}\n"

    if not payments:
        text += "Hali to'lov yo'q"

    await call.message.answer(text, parse_mode="HTML", reply_markup=admin_panel_keyboard())

# ============================================================
# 👑 VIP SO'ROVLAR (Admin)
# ============================================================

@dp.callback_query(F.data == "admin_vip_requests")
async def admin_vip_requests(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    await call.answer("VIP so'rovlar chek rasmlari orqali keladi!", show_alert=True)

# ============================================================
# 💎 VIP KINO QO'SHISH (Admin)
# ============================================================

@dp.callback_query(F.data == "admin_add_vip_movie")
async def admin_add_vip_movie(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    await call.answer(
        "Kino qo'shishda 'VIP' tugmasini tanlang. Bepul kinolar botda hammaga ko'rinadi, VIP kinolar faqat VIP egalari uchun!",
        show_alert=True
    )

# ============================================================
# 🔒 QISMNI PULIK QILISH (Admin)
# ============================================================

@dp.callback_query(F.data == "admin_paid_episode")
async def admin_paid_episode(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminStates.paid_episode_movie)
    await call.message.answer("🔑 Kino kodini kiriting:")

@dp.message(AdminStates.paid_episode_movie)
async def paid_ep_movie(message: Message, state: FSMContext):
    code = message.text.upper().strip()
    db = await db_get()
    if code not in db["movies"]:
        await message.answer("❌ Kino topilmadi!")
        return
    await state.update_data(paid_movie_code=code)
    await state.set_state(AdminStates.paid_episode_num)
    await message.answer("📌 Nechinchi qismni pulik qilmoqchisiz?")

@dp.message(AdminStates.paid_episode_num)
async def paid_ep_num(message: Message, state: FSMContext):
    try:
        num = int(message.text)
        await state.update_data(paid_ep_num=str(num))
        await state.set_state(AdminStates.paid_episode_price)
        await message.answer("💰 Narxini kiriting (so'mda):")
    except:
        await message.answer("❌ Faqat raqam!")

@dp.message(AdminStates.paid_episode_price)
async def paid_ep_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.replace(" ", "").replace(",", ""))
        data = await state.get_data()
        await state.clear()

        movie_code = data.get("paid_movie_code")
        ep_num = data.get("paid_ep_num")

        db = await db_get()
        if ep_num not in db["movies"].get(movie_code, {}).get("episodes", {}):
            await message.answer("❌ Bu qism topilmadi! Avval qismni qo'shing.")
            return

        db["movies"][movie_code]["episodes"][ep_num]["price"] = price
        await db_set(db)

        await message.answer(
            f"✅ {movie_code} — {ep_num}-qism narxi {price:,} so'm qilindi!",
            reply_markup=admin_panel_keyboard()
        )
    except:
        await message.answer("❌ Faqat raqam!")

# ============================================================
# ❌ BEKOR QILISH (Admin)
# ============================================================

@dp.callback_query(F.data == "admin_cancel")
async def admin_cancel(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("❌ Bekor qilindi.", reply_markup=admin_panel_keyboard())

# ============================================================
# 🚀 BOT ISHGA TUSHIRISH
# ============================================================

async def main():
    logger.info("🤖 Bot ishga tushmoqda...")

    # JSONBin tekshirish
    db = await db_get()
    if not db.get("users"):
        logger.info("📦 Ma'lumotlar bazasi yangi yaratilmoqda...")
        await db_set(DEFAULT_DATA)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
