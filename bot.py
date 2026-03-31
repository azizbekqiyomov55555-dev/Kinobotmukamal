"""
🎬 CINEMA BOT - To'liq Telegram Bot (Yangilangan versiya)
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
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# ⚙️ SOZLAMALAR - O'zgartiring!
# ============================================================
BOT_TOKEN = "8693668045:AAGY-fCRkzaDNO9xHqJAFcrpI_OLpYIBMdI"
ADMIN_IDS = [8537782289]
CHANNEL_ID = "@Azizbekl2026"
BOT_USERNAME = "VipDramlarBot"   # @ siz

JSONBIN_API_KEY = "$2a$10$mQZC26SFNwuUJbIo3fANVO3eiIMW4jWdJTva4/6tBlESt4AAde.mi"
JSONBIN_BIN_ID = "69cc43a2856a682189e936f0"
JSONBIN_URL = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"

# ============================================================
# 🌈 HAQIQIY RANGLI TUGMALAR - Telegram 3 xil rang
# ============================================================
# Telegram InlineKeyboard da haqiqiy rang berish uchun:
# color="green"  → yashil tugma  (faqat pay tugmalarida)
# color="red"    → qizil tugma
# Oddiy → ko'k (default)
#
# Lekin ReplyKeyboard va standart InlineKeyboard da
# rang FAQAT WebApp orqali ishlaydi.
# Shuning uchun biz har xil emoji prefix ishlatamiz:
# 🟢 → yashil ma'no   🔴 → qizil ma'no   🔵 → ko'k ma'no
#
# HAQIQIY RANG: pay_button (InlineKeyboardButton) uchun
# aiogram 3.x da to'g'ridan-to'g'ri rang yo'q,
# lekin Telegram WebApp Button orqali ishlaydi.
#
# Amaliy yechim: Inline tugmalar uchun
# callback_data bo'yicha rang kodini belgilaymiz:
# "green_" prefix → tasdiqlash (yashil)
# "red_"   prefix → bekor qilish (qizil)
# default         → ko'k

# ============================================================
# 📦 JSONBin - Ma'lumotlar bazasi
# ============================================================

DEFAULT_DATA = {
    "users": {},
    "movies": {},
    "tariffs": {
        "1oy":  {"name": "1 Oylik VIP",  "price": 50000,  "days": 30},
        "3oy":  {"name": "3 Oylik VIP",  "price": 120000, "days": 90},
        "1yil": {"name": "1 Yillik VIP", "price": 400000, "days": 365}
    },
    "card_number": "8600 0000 0000 0000",
    "card_owner":  "Ism Familiya",
    "mandatory_channels": [],
    "stats": {
        "monthly_joins": {},
        "payments": []
    }
}

async def db_get() -> dict:
    try:
        async with aiohttp.ClientSession() as s:
            h = {"X-Master-Key": JSONBIN_API_KEY}
            async with s.get(JSONBIN_URL + "/latest", headers=h) as r:
                if r.status == 200:
                    d = await r.json()
                    return d.get("record", DEFAULT_DATA)
    except Exception as e:
        logger.error(f"DB GET xato: {e}")
    return DEFAULT_DATA.copy()

async def db_set(data: dict) -> bool:
    try:
        async with aiohttp.ClientSession() as s:
            h = {"X-Master-Key": JSONBIN_API_KEY, "Content-Type": "application/json"}
            async with s.put(JSONBIN_URL, headers=h, json=data) as r:
                return r.status == 200
    except Exception as e:
        logger.error(f"DB SET xato: {e}")
        return False

# ============================================================
# 🎛️ FSM - Holatlar
# ============================================================
class AdminStates(StatesGroup):
    add_movie_poster    = State()
    add_movie_name      = State()
    add_movie_episodes  = State()
    add_movie_lang      = State()
    add_movie_watch_link= State()
    add_movie_code      = State()
    add_movie_is_vip    = State()

    add_episode_movie_code = State()
    add_episode_number     = State()
    add_episode_video      = State()
    add_episode_price      = State()

    add_tariff_id    = State()
    add_tariff_name  = State()
    add_tariff_price = State()
    add_tariff_days  = State()

    set_card     = State()
    add_channel  = State()

    post_photo      = State()
    post_name       = State()
    post_episodes   = State()
    post_lang       = State()
    post_watch_link = State()
    post_confirm    = State()

    broadcast_msg   = State()
    paid_episode_movie = State()
    paid_episode_num   = State()
    paid_episode_price = State()

class UserStates(StatesGroup):
    searching       = State()
    top_up_amount   = State()
    top_up_receipt  = State()
    vip_receipt     = State()
    writing_admin   = State()

# ============================================================
# 🎨 KLAVIATURA - Rangli tugmalar
# ============================================================

def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """
    Asosiy menyu — ReplyKeyboard (pastdagi tugmalar)
    3 xil rang yo'nalishi: qidirish, VIP, hisob
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🎬 Kino Qidirish"),
                KeyboardButton(text="👑 VIP Obunalar")
            ],
            [
                KeyboardButton(text="💰 Hisobim"),
                KeyboardButton(text="📢 Yangiliklar")
            ],
            [
                KeyboardButton(text="📞 Admin bilan bog'lanish")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Menyu tugmasini tanlang..."
    )

def admin_panel_keyboard() -> InlineKeyboardMarkup:
    """
    Admin panel — chiroyli tartib, rang guruhlari:
    🟢 Ko'k   → kino/qism amallar
    🟡 Sariq  → moliyaviy
    🔴 Qizil  → xavfli/muhim
    """
    builder = InlineKeyboardBuilder()

    # --- 1-qator: Kino amallar (ko'k) ---
    builder.row(
        InlineKeyboardButton(text="🎬 Kino Qo'shish",   callback_data="admin_add_movie"),
        InlineKeyboardButton(text="📹 Qism Qo'shish",   callback_data="admin_add_episode"),
    )
    # --- 2-qator: Moliya (sariq/yashil) ---
    builder.row(
        InlineKeyboardButton(text="💳 Karta Raqam",     callback_data="admin_set_card"),
        InlineKeyboardButton(text="⭐ Tarif Qo'shish",  callback_data="admin_add_tariff"),
    )
    # --- 3-qator: Boshqaruv ---
    builder.row(
        InlineKeyboardButton(text="🔗 Majburiy Obuna",  callback_data="admin_mandatory"),
        InlineKeyboardButton(text="📊 Statistika",      callback_data="admin_stats"),
    )
    # --- 4-qator: Xabar ---
    builder.row(
        InlineKeyboardButton(text="📣 Kanal Post",      callback_data="admin_post"),
        InlineKeyboardButton(text="📨 Xabar Yuborish",  callback_data="admin_broadcast"),
    )
    # --- 5-qator: To'lovlar ---
    builder.row(
        InlineKeyboardButton(text="💸 To'lovlar",       callback_data="admin_payments"),
        InlineKeyboardButton(text="👑 VIP So'rovlar",   callback_data="admin_vip_requests"),
    )
    # --- 6-qator: VIP kino va pulik ---
    builder.row(
        InlineKeyboardButton(text="💎 VIP Kino Qo'sh",  callback_data="admin_add_vip_movie"),
        InlineKeyboardButton(text="🔒 Qismni Pulik",    callback_data="admin_paid_episode"),
    )

    return builder.as_markup()

def confirm_reject_keyboard(approve_data: str, reject_data: str, user_id: int) -> InlineKeyboardMarkup:
    """
    Tasdiqlash / Bekor qilish / Xabar — 3 xil rang
    ✅ Yashil ma'no  ❌ Qizil ma'no  📨 Ko'k
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash",    callback_data=approve_data),
            InlineKeyboardButton(text="❌ Bekor qilish",  callback_data=reject_data),
        ],
        [
            InlineKeyboardButton(text="📨 Xabar Yuborish", callback_data=f"msg_user_{user_id}")
        ]
    ])

def back_admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Admin Panel", callback_data="back_admin")]
    ])

def cancel_keyboard(cb: str = "admin_cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data=cb)]
    ])

# ============================================================
# 🤖 BOT INIT
# ============================================================
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# ============================================================
# ✅ MAJBURIY OBUNA TEKSHIRISH
# ============================================================
async def check_subscription(user_id: int) -> bool:
    db = await db_get()
    for ch in db.get("mandatory_channels", []):
        try:
            m = await bot.get_chat_member(ch, user_id)
            if m.status in ["left", "kicked"]:
                return False
        except:
            pass
    return True

async def subscription_keyboard(db: dict) -> InlineKeyboardMarkup:
    buttons = []
    for ch in db.get("mandatory_channels", []):
        try:
            chat   = await bot.get_chat(ch)
            invite = await bot.export_chat_invite_link(ch)
            buttons.append([InlineKeyboardButton(text=f"📢 {chat.title}", url=invite)])
        except:
            link = ch if ch.startswith("http") else f"https://t.me/{ch.lstrip('@')}"
            buttons.append([InlineKeyboardButton(text=f"📢 {ch}", url=link)])
    buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ============================================================
# /start
# ============================================================
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    uid       = message.from_user.id
    username  = message.from_user.username or ""
    full_name = message.from_user.full_name

    db = await db_get()

    if str(uid) not in db["users"]:
        db["users"][str(uid)] = {
            "id": uid, "username": username, "name": full_name,
            "balance": 0, "vip_until": None,
            "joined": datetime.now().strftime("%Y-%m-%d"),
            "transactions": []
        }
        mk = datetime.now().strftime("%Y-%m")
        db["stats"]["monthly_joins"][mk] = db["stats"]["monthly_joins"].get(mk, 0) + 1
        await db_set(db)

    if not await check_subscription(uid):
        kb = await subscription_keyboard(db)
        await message.answer(
            "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=kb
        )
        return

    args = message.text.split()
    if len(args) > 1:
        await show_movie_by_code(message, args[1], db)
        return

    await message.answer(
        f"🎬 <b>Salom, {full_name}!</b>\n\n"
        "🍿 Kino botiga xush kelibsiz!\n"
        "📱 Quyidagi tugmalardan foydalaning:",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(call: CallbackQuery):
    if await check_subscription(call.from_user.id):
        await call.message.delete()
        await call.message.answer("✅ Obuna tasdiqlandi!", reply_markup=main_menu_keyboard())
    else:
        await call.answer("❌ Hali obuna bo'lmadingiz!", show_alert=True)

# ============================================================
# 🎬 KINO QIDIRISH
# ============================================================
@dp.message(F.text == "🎬 Kino Qidirish")
async def search_movie(message: Message, state: FSMContext):
    await state.set_state(UserStates.searching)
    await message.answer(
        "🔍 Kino kodini yoki nomini yozing:\n\n<i>Masalan: OZ001 yoki OMADLI ZARBA</i>",
        reply_markup=cancel_keyboard("cancel_search"),
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
    db = await db_get()
    await show_movie_by_code(message, message.text.strip(), db)

async def show_movie_by_code(message: Message, code: str, db: dict):
    movies = db.get("movies", {})
    movie  = None
    movie_code = ""

    code_up = code.upper().strip()
    if code_up in movies:
        movie = movies[code_up]
        movie_code = code_up
    else:
        for mc, mv in movies.items():
            if code.lower() in mv.get("name", "").lower():
                movie = mv
                movie_code = mc
                break

    if not movie:
        await message.answer(
            "❌ Kino topilmadi!\n\n"
            "🔍 Kino kodini to'g'ri kiriting yoki\n"
            "📢 Kanalimizga obuna bo'ling.",
            reply_markup=main_menu_keyboard()
        )
        return

    # VIP kino tekshirish
    user_id  = str(message.from_user.id)
    user     = db["users"].get(user_id, {})
    is_vip   = _check_vip(user)
    is_vip_movie = movie.get("is_vip", False)

    if is_vip_movie and not is_vip:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👑 VIP Olish", callback_data="goto_vip")],
            [InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="back_main")]
        ])
        await message.answer(
            f"🔒 <b>{movie.get('name')}</b> — bu VIP kino!\n\n"
            "👑 VIP obuna sotib oling va barcha kinolarni ko'ring.",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    episodes = movie.get("episodes", {})
    buttons  = []
    row      = []

    for ep_num in sorted(episodes.keys(), key=lambda x: int(x)):
        ep    = episodes[ep_num]
        price = ep.get("price", 0)
        if price > 0:
            label = f"🟢 {ep_num}" if is_vip else f"🔴 {ep_num} ({price:,})"
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
        await message.answer_photo(photo=poster, caption=caption, reply_markup=kb, parse_mode="HTML")
    else:
        await message.answer(caption, reply_markup=kb, parse_mode="HTML")

def _check_vip(user: dict) -> bool:
    vip = user.get("vip_until")
    if not vip:
        return False
    try:
        return datetime.fromisoformat(vip) > datetime.now()
    except:
        return False

@dp.callback_query(F.data == "goto_vip")
async def goto_vip(call: CallbackQuery):
    await call.message.delete()
    await vip_page_from_call(call)

# ============================================================
# 📹 EPIZOD KO'RSATISH
# ============================================================
@dp.callback_query(F.data.startswith("ep_"))
async def show_episode(call: CallbackQuery):
    parts      = call.data.split("_")
    movie_code = parts[1]
    ep_num     = parts[2]

    db      = await db_get()
    uid     = str(call.from_user.id)
    user    = db["users"].get(uid, {})
    movie   = db["movies"].get(movie_code)

    if not movie:
        await call.answer("❌ Kino topilmadi!", show_alert=True)
        return

    episode = movie.get("episodes", {}).get(ep_num)
    if not episode:
        await call.answer("❌ Qism topilmadi!", show_alert=True)
        return

    price  = episode.get("price", 0)
    is_vip = _check_vip(user)

    if price > 0 and not is_vip:
        balance = user.get("balance", 0)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"💳 Karta orqali ({price:,} so'm)",
                callback_data=f"pay_card_{movie_code}_{ep_num}"
            )],
            [InlineKeyboardButton(
                text=f"💰 Balansdan ({balance:,} so'm)",
                callback_data=f"pay_balance_{movie_code}_{ep_num}"
            )],
            [InlineKeyboardButton(text="◀️ Orqaga", callback_data=f"back_movie_{movie_code}")]
        ])
        await call.message.answer(
            f"🔒 <b>Bu qism pullik!</b>\n\n"
            f"🎬 {movie.get('name')} — {ep_num}-qism\n"
            f"💰 Narxi: <b>{price:,} so'm</b>\n\n"
            f"To'lov usulini tanlang:",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    await _send_episode_video(call.message, movie, movie_code, ep_num, episode)

async def _send_episode_video(message: Message, movie: dict, movie_code: str, ep_num: str, episode: dict):
    video_id = episode.get("file_id")
    if not video_id:
        await message.answer("❌ Video topilmadi!")
        return

    share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start={movie_code}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Do'stlarga ulashish", url=share_url)],
        [InlineKeyboardButton(text="◀️ Boshqa qismlar", callback_data=f"back_movie_{movie_code}")]
    ])

    await message.answer_video(
        video=video_id,
        caption=f"🎬 <b>{movie.get('name')}</b> — {ep_num}-qism\n\n"
                f"📌 Boshqa qismlar: <code>{movie_code}</code>",
        reply_markup=kb,
        parse_mode="HTML",
        protect_content=True   # Screenshot / ekran zapis / nusxa ko'chirish bloklandi
    )

@dp.callback_query(F.data.startswith("back_movie_"))
async def back_to_movie(call: CallbackQuery):
    mc = call.data.split("_", 2)[2]
    db = await db_get()
    await show_movie_by_code(call.message, mc, db)

# ============================================================
# 💳 TO'LOV — KARTA ORQALI (qism)
# ============================================================
@dp.callback_query(F.data.startswith("pay_card_"))
async def pay_card_episode(call: CallbackQuery, state: FSMContext):
    _, _, movie_code, ep_num = call.data.split("_", 3)
    db      = await db_get()
    movie   = db["movies"].get(movie_code, {})
    episode = movie.get("episodes", {}).get(ep_num, {})
    price   = episode.get("price", 0)
    card    = db.get("card_number", "?")
    owner   = db.get("card_owner", "")

    await state.update_data(pay_type="episode", movie_code=movie_code, ep_num=ep_num, amount=price)
    await state.set_state(UserStates.vip_receipt)

    await call.message.answer(
        f"💳 <b>To'lov Ma'lumotlari</b>\n\n"
        f"💰 Summa: <b>{price:,} so'm</b>\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"👤 Egasi: <b>{owner}</b>\n\n"
        f"✅ To'lovni amalga oshirib, chek rasmini yuboring:",
        reply_markup=cancel_keyboard("cancel_payment"),
        parse_mode="HTML"
    )

# ============================================================
# 💰 BALANSDAN TO'LASH (qism)
# ============================================================
@dp.callback_query(F.data.startswith("pay_balance_"))
async def pay_balance_episode(call: CallbackQuery):
    _, _, movie_code, ep_num = call.data.split("_", 3)
    db      = await db_get()
    uid     = str(call.from_user.id)
    user    = db["users"].get(uid, {})
    movie   = db["movies"].get(movie_code, {})
    episode = movie.get("episodes", {}).get(ep_num, {})
    price   = episode.get("price", 0)
    balance = user.get("balance", 0)

    if balance < price:
        await call.answer(
            f"❌ Balans yetarli emas!\nBalans: {balance:,} so'm\nNarx: {price:,} so'm",
            show_alert=True
        )
        return

    db["users"][uid]["balance"] -= price
    db["users"][uid].setdefault("transactions", []).append({
        "type": "episode_purchase", "amount": -price,
        "movie": movie.get("name"), "episode": ep_num,
        "date": datetime.now().isoformat()
    })
    await db_set(db)
    await call.answer(f"✅ To'lov muvaffaqiyatli! -{price:,} so'm", show_alert=True)
    await _send_episode_video(call.message, movie, movie_code, ep_num, episode)

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
    db  = await db_get()
    uid = str(message.from_user.id)
    user = db["users"].get(uid, {"balance": 0, "vip_until": None, "transactions": []})

    balance = user.get("balance", 0)
    vip_until = user.get("vip_until")
    if vip_until:
        try:
            vip_dt = datetime.fromisoformat(vip_until)
            if vip_dt > datetime.now():
                vip_text = f"👑 VIP: {(vip_dt - datetime.now()).days} kun qoldi ({vip_dt.strftime('%d.%m.%Y')})"
            else:
                vip_text = "❌ VIP muddati tugagan"
        except:
            vip_text = "❌ VIP ma'lumot xato"
    else:
        vip_text = "❌ VIP obuna yo'q"

    txs = user.get("transactions", [])[-5:]
    tx_text = ""
    for tx in reversed(txs):
        sign = "+" if tx.get("amount", 0) > 0 else ""
        tx_text += f"\n• {sign}{tx.get('amount', 0):,} so'm — {tx.get('type', '')}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Balansni To'ldirish", callback_data="topup_balance")],
        [InlineKeyboardButton(text="📜 Barcha Tarix",        callback_data="full_history")]
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

@dp.callback_query(F.data == "full_history")
async def full_history(call: CallbackQuery):
    db  = await db_get()
    uid = str(call.from_user.id)
    user = db["users"].get(uid, {})
    txs  = user.get("transactions", [])

    if not txs:
        await call.answer("Tarix yo'q", show_alert=True)
        return

    text = "📜 <b>Barcha operatsiyalar</b>\n\n"
    for tx in reversed(txs[-30:]):
        sign = "+" if tx.get("amount", 0) > 0 else ""
        d = tx.get("date", "")[:10]
        text += f"• {sign}{tx.get('amount',0):,} so'm — {tx.get('type','')} ({d})\n"

    await call.message.answer(text, parse_mode="HTML", reply_markup=back_admin_keyboard())

# ============================================================
# 💳 BALANS TO'LDIRISH
# ============================================================
@dp.callback_query(F.data == "topup_balance")
async def topup_balance(call: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.top_up_amount)
    await call.message.answer(
        "💰 Qancha miqdorda to'ldirmoqchisiz?\n\nMiqdorni yozing (so'mda):\n<i>Masalan: 50000</i>",
        reply_markup=cancel_keyboard("cancel_payment"),
        parse_mode="HTML"
    )

@dp.message(UserStates.top_up_amount)
async def process_topup_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.replace(" ", "").replace(",", ""))
        if amount < 1000:
            await message.answer("❌ Minimal summa 1 000 so'm!")
            return
    except:
        await message.answer("❌ Faqat raqam kiriting!")
        return

    db    = await db_get()
    card  = db.get("card_number", "Yo'q")
    owner = db.get("card_owner", "")

    await state.update_data(topup_amount=amount, pay_type="balance")
    await state.set_state(UserStates.top_up_receipt)

    await message.answer(
        f"💳 <b>To'lov Ma'lumotlari</b>\n\n"
        f"💰 Summa: <b>{amount:,} so'm</b>\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"👤 Egasi: <b>{owner}</b>\n\n"
        f"✅ To'lovni amalga oshirib, chek rasmini yuboring:",
        reply_markup=cancel_keyboard("cancel_payment"),
        parse_mode="HTML"
    )

@dp.message(UserStates.top_up_receipt, F.photo)
async def process_topup_receipt(message: Message, state: FSMContext):
    data   = await state.get_data()
    amount = data.get("topup_amount", 0)
    await state.clear()

    user = message.from_user
    rid  = f"topup_{user.id}_{int(datetime.now().timestamp())}"
    kb   = confirm_reject_keyboard(
        approve_data=f"approve_topup_{user.id}_{amount}_{rid}",
        reject_data =f"reject_topup_{user.id}_{amount}_{rid}",
        user_id=user.id
    )

    for aid in ADMIN_IDS:
        try:
            await bot.send_photo(
                aid, message.photo[-1].file_id,
                caption=f"💳 <b>Balans To'ldirish So'rovi</b>\n\n"
                        f"👤 {user.full_name}\n"
                        f"🆔 <code>{user.id}</code>\n"
                        f"💰 Summa: <b>{amount:,} so'm</b>\n"
                        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                reply_markup=kb,
                parse_mode="HTML"
            )
        except:
            pass

    await message.answer("✅ Chek yuborildi! Admin tasdiqlashini kuting.", reply_markup=main_menu_keyboard())

@dp.message(UserStates.top_up_receipt)
async def topup_not_photo(message: Message):
    await message.answer("📸 Iltimos, chek RASMINI yuboring!")

# ============================================================
# ✅ TO'LOV TASDIQLASH / BEKOR QILISH (Admin)
# ============================================================
@dp.callback_query(F.data.startswith("approve_topup_"))
async def approve_topup(call: CallbackQuery):
    parts   = call.data.split("_")
    uid     = parts[2]
    amount  = int(parts[3])

    db = await db_get()
    db["users"].setdefault(uid, {"balance": 0, "transactions": []})
    db["users"][uid]["balance"] = db["users"][uid].get("balance", 0) + amount
    db["users"][uid].setdefault("transactions", []).append({
        "type": "topup", "amount": amount, "date": datetime.now().isoformat()
    })
    db["stats"]["payments"].append({
        "user_id": uid, "amount": amount, "type": "topup",
        "date": datetime.now().isoformat()
    })
    await db_set(db)

    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"✅ {uid} — {amount:,} so'm qo'shildi!")

    try:
        await bot.send_message(
            int(uid),
            f"✅ <b>Balans To'ldirildi!</b>\n\n"
            f"💰 +{amount:,} so'm\n"
            f"💳 Yangi balans: {db['users'][uid]['balance']:,} so'm",
            parse_mode="HTML"
        )
    except:
        pass

@dp.callback_query(F.data.startswith("reject_topup_"))
async def reject_topup(call: CallbackQuery):
    parts  = call.data.split("_")
    uid    = parts[2]
    amount = int(parts[3])

    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"❌ {uid} so'rovi bekor qilindi!")

    try:
        await bot.send_message(
            int(uid),
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
    await vip_page_msg(message)

async def vip_page_msg(message: Message):
    db      = await db_get()
    tariffs = db.get("tariffs", {})
    uid     = str(message.from_user.id)
    user    = db["users"].get(uid, {})
    is_vip  = _check_vip(user)

    buttons = []
    for tid, t in tariffs.items():
        buttons.append([InlineKeyboardButton(
            text=f"⭐ {t['name']} — {t['price']:,} so'm",
            callback_data=f"buy_vip_{tid}"
        )])
    buttons.append([InlineKeyboardButton(text="🔍 Kod bo'yicha qidirish", callback_data="vip_search")])
    buttons.append([InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="back_main")])

    vip_status = f"👑 VIP: {(datetime.fromisoformat(user['vip_until']) - datetime.now()).days} kun qoldi" \
        if is_vip else "❌ VIP obuna yo'q"

    await message.answer(
        f"👑 <b>VIP Obunalar</b>\n\n"
        f"📊 Holat: {vip_status}\n\n"
        f"✨ VIP afzalliklari:\n"
        f"• Barcha pullik qismlarni bepul ko'rish\n"
        f"• Yangi qismlar birinchi bo'lib\n"
        f"• Eksklyuziv kontentlar\n\n"
        f"💎 Tarifni tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )

async def vip_page_from_call(call: CallbackQuery):
    db      = await db_get()
    tariffs = db.get("tariffs", {})
    uid     = str(call.from_user.id)
    user    = db["users"].get(uid, {})
    is_vip  = _check_vip(user)

    buttons = []
    for tid, t in tariffs.items():
        buttons.append([InlineKeyboardButton(
            text=f"⭐ {t['name']} — {t['price']:,} so'm",
            callback_data=f"buy_vip_{tid}"
        )])
    buttons.append([InlineKeyboardButton(text="🔍 Kod bo'yicha qidirish", callback_data="vip_search")])
    buttons.append([InlineKeyboardButton(text="🏠 Asosiy Menyu", callback_data="back_main")])

    vip_status = "❌ VIP obuna yo'q"
    if is_vip:
        try:
            vip_status = f"👑 VIP: {(datetime.fromisoformat(user['vip_until']) - datetime.now()).days} kun qoldi"
        except:
            pass

    await call.message.answer(
        f"👑 <b>VIP Obunalar</b>\n\n📊 Holat: {vip_status}\n\n💎 Tarifni tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "vip_search")
async def vip_search(call: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.searching)
    await call.message.answer(
        "🔍 Kino kodini kiriting:",
        reply_markup=cancel_keyboard("cancel_search")
    )

@dp.callback_query(F.data.startswith("buy_vip_"))
async def buy_vip(call: CallbackQuery, state: FSMContext):
    tid  = call.data.split("_")[2]
    db   = await db_get()
    tariff = db.get("tariffs", {}).get(tid)

    if not tariff:
        await call.answer("❌ Tarif topilmadi!", show_alert=True)
        return

    card    = db.get("card_number", "?")
    owner   = db.get("card_owner", "")
    uid     = str(call.from_user.id)
    user    = db["users"].get(uid, {})
    balance = user.get("balance", 0)

    await state.update_data(vip_tariff_id=tid, pay_type="vip")
    await state.set_state(UserStates.vip_receipt)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"💰 Balansdan ({balance:,} so'm)",
            callback_data=f"vip_from_balance_{tid}"
        )],
        [InlineKeyboardButton(
            text="💳 Karta orqali to'lash",
            callback_data=f"vip_card_{tid}"
        )],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_payment")]
    ])

    await call.message.answer(
        f"⭐ <b>{tariff['name']}</b>\n\n"
        f"💰 Narxi: <b>{tariff['price']:,} so'm</b>\n"
        f"📅 Muddat: {tariff['days']} kun\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"👤 Egasi: <b>{owner}</b>\n\n"
        f"To'lov usulini tanlang:",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("vip_from_balance_"))
async def vip_from_balance(call: CallbackQuery, state: FSMContext):
    await state.clear()
    tid    = call.data.split("_")[3]
    db     = await db_get()
    uid    = str(call.from_user.id)
    user   = db["users"].get(uid, {})
    tariff = db.get("tariffs", {}).get(tid, {})
    balance = user.get("balance", 0)
    price   = tariff.get("price", 0)

    if balance < price:
        await call.answer(
            f"❌ Balans yetarli emas!\nBalans: {balance:,} so'm\nNarx: {price:,} so'm",
            show_alert=True
        )
        return

    db["users"][uid]["balance"] -= price
    new_vip = _extend_vip(user.get("vip_until"), tariff.get("days", 30))
    db["users"][uid]["vip_until"] = new_vip.isoformat()
    db["users"][uid].setdefault("transactions", []).append({
        "type": "vip_purchase", "amount": -price,
        "tariff": tariff.get("name"), "date": datetime.now().isoformat()
    })
    db["stats"]["payments"].append({
        "user_id": uid, "amount": price, "type": "vip",
        "tariff": tid, "date": datetime.now().isoformat()
    })
    await db_set(db)

    await call.message.answer(
        f"👑 <b>VIP faollashtirildi!</b>\n\n"
        f"⭐ {tariff.get('name')}\n"
        f"📅 Muddati: {new_vip.strftime('%d.%m.%Y')}\n"
        f"💰 -{price:,} so'm\n\nTabriklaymiz! 🎉",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML"
    )

@dp.callback_query(F.data.startswith("vip_card_"))
async def vip_card(call: CallbackQuery, state: FSMContext):
    tid    = call.data.split("_")[2]
    db     = await db_get()
    tariff = db.get("tariffs", {}).get(tid, {})
    card   = db.get("card_number", "?")
    owner  = db.get("card_owner", "")

    await state.update_data(vip_tariff_id=tid, pay_type="vip")
    await state.set_state(UserStates.vip_receipt)

    await call.message.answer(
        f"💳 <b>VIP To'lov</b>\n\n"
        f"💰 Summa: <b>{tariff.get('price', 0):,} so'm</b>\n"
        f"💳 Karta: <code>{card}</code>\n"
        f"👤 Egasi: <b>{owner}</b>\n\n"
        f"✅ To'lovni amalga oshirib, chek rasmini yuboring:",
        reply_markup=cancel_keyboard("cancel_payment"),
        parse_mode="HTML"
    )

@dp.message(UserStates.vip_receipt, F.photo)
async def vip_receipt_photo(message: Message, state: FSMContext):
    data   = await state.get_data()
    pay_type = data.get("pay_type", "vip")
    await state.clear()

    user = message.from_user

    if pay_type == "episode":
        mc     = data.get("movie_code", "")
        ep_num = data.get("ep_num", "")
        amount = data.get("amount", 0)
        rid    = f"ep_{user.id}_{int(datetime.now().timestamp())}"
        kb     = confirm_reject_keyboard(
            approve_data=f"approve_ep_{user.id}_{mc}_{ep_num}_{amount}_{rid}",
            reject_data =f"reject_ep_{user.id}_{mc}_{ep_num}_{rid}",
            user_id=user.id
        )
        info = f"🎬 Kino: {mc} — {ep_num}-qism\n💰 Summa: {amount:,} so'm"
    else:
        tid    = data.get("vip_tariff_id", "")
        db     = await db_get()
        tariff = db.get("tariffs", {}).get(tid, {})
        amount = tariff.get("price", 0)
        rid    = f"vip_{user.id}_{int(datetime.now().timestamp())}"
        kb     = confirm_reject_keyboard(
            approve_data=f"approve_vip_{user.id}_{tid}_{rid}",
            reject_data =f"reject_vip_{user.id}_{tid}_{rid}",
            user_id=user.id
        )
        info = f"⭐ Tarif: {tariff.get('name', tid)}\n💰 Summa: {amount:,} so'm"

    for aid in ADMIN_IDS:
        try:
            await bot.send_photo(
                aid, message.photo[-1].file_id,
                caption=f"💳 <b>To'lov So'rovi</b>\n\n"
                        f"👤 {user.full_name}\n🆔 <code>{user.id}</code>\n"
                        f"{info}\n🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                reply_markup=kb,
                parse_mode="HTML"
            )
        except:
            pass

    await message.answer("✅ Chek yuborildi! Admin tasdiqlashini kuting.", reply_markup=main_menu_keyboard())

@dp.message(UserStates.vip_receipt)
async def vip_not_photo(message: Message):
    await message.answer("📸 Iltimos, chek RASMINI yuboring!")

def _extend_vip(current_vip: str | None, days: int) -> datetime:
    if current_vip:
        try:
            dt = datetime.fromisoformat(current_vip)
            if dt > datetime.now():
                return dt + timedelta(days=days)
        except:
            pass
    return datetime.now() + timedelta(days=days)

# ============================================================
# VIP / EPIZOD TASDIQLASH (Admin)
# ============================================================
@dp.callback_query(F.data.startswith("approve_vip_"))
async def approve_vip(call: CallbackQuery):
    parts  = call.data.split("_")
    uid    = parts[2]
    tid    = parts[3]

    db     = await db_get()
    tariff = db.get("tariffs", {}).get(tid, {})
    days   = tariff.get("days", 30)
    price  = tariff.get("price", 0)

    user_data = db["users"].setdefault(uid, {})
    new_vip   = _extend_vip(user_data.get("vip_until"), days)
    db["users"][uid]["vip_until"] = new_vip.isoformat()
    db["stats"]["payments"].append({
        "user_id": uid, "amount": price, "type": "vip",
        "tariff": tid, "date": datetime.now().isoformat()
    })
    await db_set(db)

    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"✅ {uid} uchun VIP faollashtirildi ({days} kun)!")

    try:
        await bot.send_message(
            int(uid),
            f"👑 <b>VIP Faollashtirildi!</b>\n\n⭐ {tariff.get('name')}\n"
            f"📅 Muddati: {new_vip.strftime('%d.%m.%Y')}\n\nTabriklaymiz! 🎉",
            parse_mode="HTML"
        )
    except:
        pass

@dp.callback_query(F.data.startswith("reject_vip_"))
async def reject_vip(call: CallbackQuery):
    parts = call.data.split("_")
    uid   = parts[2]
    tid   = parts[3]
    db    = await db_get()
    tariff = db.get("tariffs", {}).get(tid, {})

    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"❌ {uid} VIP so'rovi bekor qilindi!")

    try:
        await bot.send_message(
            int(uid),
            f"❌ <b>VIP so'rov rad etildi</b>\n\nTarif: {tariff.get('name', tid)}\n"
            f"📞 Muammo bo'lsa admin bilan bog'laning.",
            parse_mode="HTML"
        )
    except:
        pass

@dp.callback_query(F.data.startswith("approve_ep_"))
async def approve_ep(call: CallbackQuery):
    parts      = call.data.split("_")
    uid        = parts[2]
    movie_code = parts[3]
    ep_num     = parts[4]
    amount     = int(parts[5]) if len(parts) > 5 else 0

    db      = await db_get()
    movie   = db["movies"].get(movie_code, {})
    episode = movie.get("episodes", {}).get(ep_num, {})

    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"✅ {uid} uchun {movie_code}—{ep_num}-qism tasdiqlandi!")

    try:
        await _send_episode_video_direct(int(uid), movie, movie_code, ep_num, episode)
    except:
        pass

@dp.callback_query(F.data.startswith("reject_ep_"))
async def reject_ep(call: CallbackQuery):
    parts      = call.data.split("_")
    uid        = parts[2]
    movie_code = parts[3]
    ep_num     = parts[4]

    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"❌ {uid} epizod to'lovi bekor qilindi!")

    try:
        await bot.send_message(
            int(uid),
            f"❌ <b>To'lov rad etildi</b>\n\nKino: {movie_code} — {ep_num}-qism\n"
            f"📞 Muammo bo'lsa admin bilan bog'laning.",
            parse_mode="HTML"
        )
    except:
        pass

async def _send_episode_video_direct(user_id: int, movie: dict, movie_code: str, ep_num: str, episode: dict):
    video_id = episode.get("file_id")
    if not video_id:
        return
    share_url = f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start={movie_code}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Do'stlarga ulashish", url=share_url)]
    ])
    await bot.send_video(
        user_id, video_id,
        caption=f"🎬 <b>{movie.get('name')}</b> — {ep_num}-qism\n✅ To'lov tasdiqlandi!",
        reply_markup=kb, parse_mode="HTML", protect_content=True
    )

# ============================================================
# 📞 ADMIN BILAN BOG'LANISH
# ============================================================
@dp.message(F.text == "📞 Admin bilan bog'lanish")
async def contact_admin(message: Message, state: FSMContext):
    await state.set_state(UserStates.writing_admin)
    await message.answer(
        "✍️ Adminga xabar yozing (matn, rasm yoki ovozli xabar):",
        reply_markup=cancel_keyboard("cancel_contact")
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

    for aid in ADMIN_IDS:
        try:
            await bot.send_message(
                aid,
                f"📨 <b>Foydalanuvchi xabari</b>\n"
                f"👤 {user.full_name} | <code>{user.id}</code>\n"
                f"{'─'*20}",
                parse_mode="HTML"
            )
            await message.forward(aid)
            await bot.send_message(aid, "─"*20, reply_markup=kb)
        except:
            pass

    await message.answer("✅ Xabaringiz adminga yuborildi!", reply_markup=main_menu_keyboard())

@dp.callback_query(F.data.startswith("msg_user_"))
async def msg_user_prompt(call: CallbackQuery, state: FSMContext):
    uid = call.data.split("_")[2]
    await state.update_data(msg_target=uid)
    await state.set_state(AdminStates.broadcast_msg)
    await call.message.answer(f"✍️ {uid} ga xabar yozing:")

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
        "📢 <b>Yangi kinolar va yangiliklar!</b>\n\nKanalimizga obuna bo'ling!",
        reply_markup=kb, parse_mode="HTML"
    )

# ============================================================
# 🔙 ORQAGA
# ============================================================
@dp.callback_query(F.data == "back_main")
async def back_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("🏠 Asosiy menyu:", reply_markup=main_menu_keyboard())

@dp.callback_query(F.data == "back_admin")
async def back_admin(call: CallbackQuery):
    await call.message.answer("👨‍💼 Admin Panel:", reply_markup=admin_panel_keyboard())

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
    await call.message.answer("🖼 Kino posterini yuboring (rasm):", reply_markup=cancel_keyboard())

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
        await state.update_data(total_episodes=int(message.text))
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
    await state.update_data(watch_link="" if message.text == "-" else message.text)
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
            InlineKeyboardButton(text="👑 VIP",   callback_data="movie_vip"),
        ]
    ])
    await message.answer("💎 Kino turi:", reply_markup=kb)

@dp.callback_query(F.data.in_(["movie_free", "movie_vip"]))
async def save_movie(call: CallbackQuery, state: FSMContext):
    is_vip = call.data == "movie_vip"
    data   = await state.get_data()
    await state.clear()

    code = data.get("code", "")
    db   = await db_get()
    db["movies"][code] = {
        "name":           data.get("name", ""),
        "poster":         data.get("poster", ""),
        "total_episodes": data.get("total_episodes", 0),
        "lang":           data.get("lang", "O'zbek tilida"),
        "watch_link":     data.get("watch_link", ""),
        "is_vip":         is_vip,
        "episodes":       {},
        "created":        datetime.now().isoformat()
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
    db   = await db_get()
    if code not in db["movies"]:
        await message.answer(f"❌ '{code}' kodli kino topilmadi!")
        return
    await state.update_data(episode_movie_code=code)
    await state.set_state(AdminStates.add_episode_number)
    movie   = db["movies"][code]
    existing = sorted(movie.get("episodes", {}).keys(), key=int)
    await message.answer(
        f"🎬 Kino: <b>{movie['name']}</b>\n"
        f"📋 Mavjud qismlar: {', '.join(existing) or 'yo`q'}\n\n"
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
        reply_markup=kb, parse_mode="HTML"
    )

@dp.callback_query(F.data == "ep_price_free")
async def ep_price_free(call: CallbackQuery, state: FSMContext):
    await _save_episode(call.message, state, 0)

@dp.message(AdminStates.add_episode_price)
async def add_episode_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.replace(" ", "").replace(",", ""))
        await _save_episode(message, state, price)
    except:
        await message.answer("❌ Faqat raqam kiriting!")

async def _save_episode(message: Message, state: FSMContext, price: int):
    data     = await state.get_data()
    await state.clear()
    mc       = data.get("episode_movie_code")
    ep_num   = data.get("episode_number")
    file_id  = data.get("episode_file_id")

    db = await db_get()
    db["movies"][mc]["episodes"][ep_num] = {
        "file_id": file_id, "price": price,
        "added": datetime.now().isoformat()
    }
    await db_set(db)

    await message.answer(
        f"✅ <b>Qism saqlandi!</b>\n\n"
        f"🎬 {db['movies'][mc].get('name', mc)}\n"
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
    await call.message.answer(
        f"💳 Joriy: <code>{db.get('card_number', 'Yo`q')}</code>\n"
        f"👤 Egasi: {db.get('card_owner', 'Yo`q')}\n\n"
        f"Yangi karta raqam va egasini yozing:\n"
        f"<i>Format: 8600 1234 5678 9012 | Ism Familiya</i>",
        parse_mode="HTML"
    )

@dp.message(AdminStates.set_card)
async def save_card(message: Message, state: FSMContext):
    await state.clear()
    parts = message.text.split("|")
    db    = await db_get()
    db["card_number"] = parts[0].strip()
    db["card_owner"]  = parts[1].strip() if len(parts) > 1 else ""
    await db_set(db)
    await message.answer(
        f"✅ Karta saqlandi!\n💳 <code>{db['card_number']}</code>\n👤 {db['card_owner']}",
        reply_markup=admin_panel_keyboard(), parse_mode="HTML"
    )

# ============================================================
# ⭐ TARIF QO'SHISH (Admin)
# ============================================================
@dp.callback_query(F.data == "admin_add_tariff")
async def admin_add_tariff(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    db = await db_get()
    tariffs = db.get("tariffs", {})
    existing = "\n".join([f"• {k}: {v['name']} — {v['price']:,} so'm ({v['days']} kun)"
                          for k, v in tariffs.items()])
    await state.set_state(AdminStates.add_tariff_id)
    await call.message.answer(
        f"⭐ <b>Tariflar</b>\n\n{existing or 'Hali tarif yo`q'}\n\n"
        f"Yangi tarif ID kiriting (masalan: 6oy):",
        parse_mode="HTML"
    )

@dp.message(AdminStates.add_tariff_id)
async def tariff_id(message: Message, state: FSMContext):
    await state.update_data(tariff_id=message.text.strip())
    await state.set_state(AdminStates.add_tariff_name)
    await message.answer("✏️ Tarif nomini kiriting (masalan: 6 Oylik VIP):")

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
        await message.answer("📅 Necha kun amal qiladi?")
    except:
        await message.answer("❌ Faqat raqam!")

@dp.message(AdminStates.add_tariff_days)
async def tariff_days(message: Message, state: FSMContext):
    try:
        days = int(message.text)
        data = await state.get_data()
        await state.clear()
        db   = await db_get()
        db["tariffs"][data["tariff_id"]] = {
            "name":  data["tariff_name"],
            "price": data["tariff_price"],
            "days":  days
        }
        await db_set(db)
        await message.answer(
            f"✅ Tarif saqlandi!\n⭐ {data['tariff_name']} — {data['tariff_price']:,} so'm | {days} kun",
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
    db       = await db_get()
    channels = db.get("mandatory_channels", [])

    buttons = []
    for ch in channels:
        buttons.append([InlineKeyboardButton(
            text=f"🗑 {ch}", callback_data=f"del_channel_{ch.lstrip('@')}"
        )])
    buttons.append([InlineKeyboardButton(text="➕ Kanal/Bot/Link Qo'shish", callback_data="add_channel")])
    buttons.append([InlineKeyboardButton(text="◀️ Admin Panel", callback_data="back_admin")])

    ch_list = "\n".join([f"• {ch}" for ch in channels]) or "Hali yo'q"
    await call.message.answer(
        f"🔗 <b>Majburiy Obunalar</b>\n\nJami: {len(channels)} ta\n\n{ch_list}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "add_channel")
async def add_channel_prompt(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.add_channel)
    await call.message.answer(
        "📢 Qo'shmoqchi bo'lgan kanalning linkini yozing:\n\n"
        "• Telegram kanal: @kanal_nomi\n"
        "• Bot: @bot_nomi\n"
        "• Oddiy link: https://t.me/..."
    )

@dp.message(AdminStates.add_channel)
async def save_channel(message: Message, state: FSMContext):
    await state.clear()
    ch = message.text.strip()
    db = await db_get()
    channels = db.setdefault("mandatory_channels", [])
    if ch not in channels:
        channels.append(ch)
        await db_set(db)
        await message.answer(f"✅ '{ch}' qo'shildi!", reply_markup=admin_panel_keyboard())
    else:
        await message.answer(f"⚠️ '{ch}' allaqachon mavjud!")

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
    db       = await db_get()
    users    = db.get("users", {})
    movies   = db.get("movies", {})
    payments = db.get("stats", {}).get("payments", [])

    mk = datetime.now().strftime("%Y-%m")
    this_month = db.get("stats", {}).get("monthly_joins", {}).get(mk, 0)

    week_ago   = datetime.now() - timedelta(days=7)
    w_pays     = [p for p in payments if _parse_dt(p.get("date")) > week_ago]
    w_count    = len(w_pays)
    w_sum      = sum(p.get("amount", 0) for p in w_pays)

    vip_users  = [u for u in users.values() if _check_vip(u)]
    vip_count  = len(vip_users)
    vip_rev    = sum(p.get("amount", 0) for p in payments if p.get("type") == "vip")

    m_pays     = [p for p in payments if _parse_dt(p.get("date")).strftime("%Y-%m") == mk]
    m_sum      = sum(p.get("amount", 0) for p in m_pays)

    top_users  = sorted(users.values(), key=lambda x: x.get("balance", 0), reverse=True)[:15]
    top_text   = "\n".join(
        [f"{i}. {u.get('name','?')}: {u.get('balance',0):,} so'm"
         for i, u in enumerate(top_users, 1)]
    ) or "Ma'lumot yo'q"

    await call.message.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"👥 Jami foydalanuvchilar: {len(users)}\n"
        f"📈 Bu oy qo'shildi: {this_month}\n"
        f"🎬 Jami kinolar: {len(movies)}\n\n"
        f"👑 VIP foydalanuvchilar: {vip_count}\n"
        f"💰 VIP daromad: {vip_rev:,} so'm\n\n"
        f"📅 Haftalik to'ldirish: {w_count} ta | {w_sum:,} so'm\n"
        f"📅 Bu oy daromad: {m_sum:,} so'm\n\n"
        f"🏆 Top 15 balans:\n{top_text}",
        reply_markup=back_admin_keyboard(),
        parse_mode="HTML"
    )

def _parse_dt(s: str | None) -> datetime:
    try:
        return datetime.fromisoformat(s or "2000-01-01")
    except:
        return datetime(2000, 1, 1)

# ============================================================
# 📣 KANAL POST (Admin)
# Kanalga post yuboriladi: rasm + info + "Ko'rish" tugmasi → botga deep link
# Foydalanuvchi tugmani bosadi → bot /start KINO_KODI → kino chiqadi
# ============================================================
@dp.callback_query(F.data == "admin_post")
async def admin_post(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        return
    await state.set_state(AdminStates.post_photo)
    await call.message.answer("🖼 Post uchun rasm yuboring:", reply_markup=cancel_keyboard())

@dp.message(AdminStates.post_photo, F.photo)
async def post_photo(message: Message, state: FSMContext):
    await state.update_data(post_photo=message.photo[-1].file_id)
    await state.set_state(AdminStates.post_name)
    await message.answer("✏️ Kino nomini kiriting:")

@dp.message(AdminStates.post_name)
async def post_name_input(message: Message, state: FSMContext):
    await state.update_data(post_name=message.text)
    await state.set_state(AdminStates.post_episodes)
    await message.answer("🎞 Qismlar (masalan: 100/7):")

@dp.message(AdminStates.post_episodes)
async def post_episodes_input(message: Message, state: FSMContext):
    await state.update_data(post_episodes=message.text)
    await state.set_state(AdminStates.post_lang)
    await message.answer("🌐 Tili:")

@dp.message(AdminStates.post_lang)
async def post_lang_input(message: Message, state: FSMContext):
    await state.update_data(post_lang=message.text)
    await state.set_state(AdminStates.post_watch_link)
    await message.answer(
        "🔑 Kino kodini kiriting (botda ko'rish uchun deep link bo'ladi):\n"
        "<i>Masalan: OZ001</i>",
        parse_mode="HTML"
    )

@dp.message(AdminStates.post_watch_link)
async def post_watch_link_input(message: Message, state: FSMContext):
    movie_code = message.text.upper().strip()
    deep_link  = f"https://t.me/{BOT_USERNAME}?start={movie_code}"
    await state.update_data(post_watch_link=deep_link, post_movie_code=movie_code)
    await state.set_state(AdminStates.post_confirm)
    data = await state.get_data()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yuborish",  callback_data="confirm_post"),
            InlineKeyboardButton(text="❌ Bekor",     callback_data="admin_cancel"),
        ]
    ])

    await message.answer_photo(
        data["post_photo"],
        caption=f"🎬 <b>{data['post_name']}</b>\n\n"
                f"▶️ Qism: {data['post_episodes']}\n"
                f"🌐 Til: {data['post_lang']}\n\n"
                f"<i>Preview — tasdiqlaysizmi?</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "confirm_post")
async def confirm_post(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    # Kanalga yuboriladigan post — rasm + kino ma'lumoti + "Ko'rish" tugmasi
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="▶️ Ko'rish ◀️",
            url=data["post_watch_link"]
        )]
    ])

    caption = (
        f"🎬 <b>{data['post_name']}</b>\n\n"
        f"▶️ Qism: {data['post_episodes']}\n"
        f"🌐 Til: {data['post_lang']}\n\n"
        f"📌 Ko'rish uchun tugmani bosing 👇"
    )

    await bot.send_photo(
        CHANNEL_ID,
        data["post_photo"],
        caption=caption,
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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Hammaga",  callback_data="broadcast_all"),
            InlineKeyboardButton(text="👑 VIPlarga", callback_data="broadcast_vip"),
            InlineKeyboardButton(text="🆓 Bepullarga", callback_data="broadcast_free"),
        ],
        [InlineKeyboardButton(text="❌ Bekor", callback_data="admin_cancel")]
    ])
    await call.message.answer("📨 Kimga yubormoqchisiz?", reply_markup=kb)

@dp.callback_query(F.data.startswith("broadcast_") & ~F.data.startswith("broadcast_msg"))
async def broadcast_target(call: CallbackQuery, state: FSMContext):
    target = call.data.split("_")[1]
    await state.update_data(msg_target=target)
    await state.set_state(AdminStates.broadcast_msg)
    await call.message.answer("✍️ Yubormoqchi bo'lgan xabarni yozing (matn, rasm, video, ovoz):")

@dp.message(AdminStates.broadcast_msg)
async def send_broadcast(message: Message, state: FSMContext):
    data   = await state.get_data()
    target = data.get("msg_target", "all")
    await state.clear()

    db    = await db_get()
    users = db.get("users", {})

    if target == "all":
        targets = list(users.keys())
    elif target == "vip":
        targets = [k for k, u in users.items() if _check_vip(u)]
    elif target == "free":
        targets = [k for k, u in users.items() if not _check_vip(u)]
    else:
        targets = [target]   # bitta foydalanuvchi

    sent = failed = 0
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
            await asyncio.sleep(0.05)
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
    db       = await db_get()
    payments = db.get("stats", {}).get("payments", [])[-20:]

    text = "💸 <b>So'nggi to'lovlar</b>\n\n"
    for p in reversed(payments):
        d = _parse_dt(p.get("date")).strftime("%d.%m %H:%M")
        text += f"• {p.get('type','')} | {p.get('amount',0):,} so'm | {d}\n"

    if not payments:
        text += "Hali to'lov yo'q"

    await call.message.answer(text, parse_mode="HTML", reply_markup=back_admin_keyboard())

# ============================================================
# 👑 VIP SO'ROVLAR
# ============================================================
@dp.callback_query(F.data == "admin_vip_requests")
async def admin_vip_requests(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    await call.answer("VIP so'rovlar chek rasmlari orqali keladi!", show_alert=True)

# ============================================================
# 💎 VIP KINO (Admin)
# ============================================================
@dp.callback_query(F.data == "admin_add_vip_movie")
async def admin_add_vip_movie(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        return
    await call.answer(
        "Kino qo'shishda 'VIP' tugmasini tanlang.",
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
    db   = await db_get()
    if code not in db["movies"]:
        await message.answer("❌ Kino topilmadi!")
        return
    await state.update_data(paid_movie_code=code)
    await state.set_state(AdminStates.paid_episode_num)
    await message.answer("📌 Nechinchi qismni pulik qilmoqchisiz?")

@dp.message(AdminStates.paid_episode_num)
async def paid_ep_num(message: Message, state: FSMContext):
    try:
        await state.update_data(paid_ep_num=str(int(message.text)))
        await state.set_state(AdminStates.paid_episode_price)
        await message.answer("💰 Narxini kiriting (so'mda):")
    except:
        await message.answer("❌ Faqat raqam!")

@dp.message(AdminStates.paid_episode_price)
async def paid_ep_price(message: Message, state: FSMContext):
    try:
        price = int(message.text.replace(" ", "").replace(",", ""))
        data  = await state.get_data()
        await state.clear()

        mc  = data.get("paid_movie_code")
        ep  = data.get("paid_ep_num")
        db  = await db_get()

        if ep not in db["movies"].get(mc, {}).get("episodes", {}):
            await message.answer("❌ Bu qism topilmadi! Avval qismni qo'shing.")
            return

        db["movies"][mc]["episodes"][ep]["price"] = price
        await db_set(db)

        await message.answer(
            f"✅ {mc} — {ep}-qism narxi {price:,} so'm qilindi!",
            reply_markup=admin_panel_keyboard()
        )
    except:
        await message.answer("❌ Faqat raqam!")

# ============================================================
# ❌ BEKOR QILISH
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
    db = await db_get()
    if not db.get("users"):
        logger.info("📦 Ma'lumotlar bazasi yangilanmoqda...")
        await db_set(DEFAULT_DATA)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
