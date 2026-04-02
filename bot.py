#!/usr/bin/env python3
# ============================================================
#   SMM BOT - Telegram SMM Panel Bot
#   Ishlatish: pip install aiogram aiohttp
#   Keyin: python smm_bot.py
# ============================================================

import asyncio
import logging
import sqlite3
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
#  \u2699\ufe0f  SOZLAMALAR  \u2013  shu qatorlarni o'zgartiring
# ============================================================
BOT_TOKEN  = "8648355597:AAF_eM_GHY3SmBpHB4VSuK93O-o_pUXdgFg"       # @BotFather dan oling
ADMIN_IDS  = [8537782289]                 # O'z Telegram ID-ingizni yozing
# ============================================================

DB = "smm_bot.db"

# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  DATABASE
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def db():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    conn = db()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id        INTEGER PRIMARY KEY,
        username       TEXT,
        full_name      TEXT,
        balance        REAL    DEFAULT 0,
        referral_id    INTEGER DEFAULT 0,
        referral_count INTEGER DEFAULT 0,
        total_dep      REAL    DEFAULT 0,
        created_at     TEXT    DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS categories (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        name      TEXT NOT NULL,
        is_active INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS apis (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        name          TEXT NOT NULL,
        url           TEXT NOT NULL,
        api_key       TEXT NOT NULL,
        price_per1000 REAL DEFAULT 0
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS services (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id     INTEGER,
        api_id          INTEGER,
        api_service_id  TEXT,
        name            TEXT NOT NULL,
        min_qty         INTEGER DEFAULT 100,
        max_qty         INTEGER DEFAULT 10000,
        price_per1000   REAL    DEFAULT 0,
        is_active       INTEGER DEFAULT 1
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id      INTEGER,
        service_id   INTEGER,
        api_order_id TEXT,
        link         TEXT,
        quantity     INTEGER,
        amount       REAL,
        status       TEXT DEFAULT 'pending',
        created_at   TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        amount      REAL,
        type        TEXT,
        description TEXT,
        created_at  TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS channels (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        channel_id   TEXT,
        channel_name TEXT,
        channel_link TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS guides (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        title   TEXT,
        content TEXT
    )""")

    defaults = [
        ("referral_bonus", "2500"),
        ("currency",       "Sum"),
        ("service_time",   "1"),
        ("premium_emoji",  "1"),
        ("payme_active",   "0"),
        ("click_active",   "0"),
        ("uzcart_active",  "0"),
    ]
    for k, v in defaults:
        c.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (k, v))

    c.execute("INSERT OR IGNORE INTO guides(id,title,content) VALUES(1,?,?)", (
        "Botdan foydalanish qo'llanmasi",
        "1. Buyurtma berish uchun 'Buyurtma berish' tugmasini bosing\n"
        "2. Bo'limni tanlang \u2192 Xizmatni tanlang\n"
        "3. Link va miqdorni kiriting\n"
        "4. Tasdiqlang \u2013 pul hisobingizdan yechiladi"
    ))

    conn.commit()
    conn.close()

# helpers
def get_setting(key, default=""):
    conn = db(); c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone(); conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = db(); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, str(value)))
    conn.commit(); conn.close()

def cur():  return get_setting("currency", "Sum")

def get_user(uid):
    conn = db(); c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    row = c.fetchone(); conn.close()
    return row

def reg_user(uid, username, full_name, ref_id=0):
    conn = db(); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users(user_id,username,full_name,referral_id) VALUES(?,?,?,?)",
              (uid, username, full_name, ref_id))
    if ref_id and ref_id != uid:
        bonus = float(get_setting("referral_bonus", "2500"))
        c.execute("UPDATE users SET balance=balance+?, referral_count=referral_count+1 WHERE user_id=?",
                  (bonus, ref_id))
        c.execute("INSERT INTO transactions(user_id,amount,type,description) VALUES(?,?,?,?)",
                  (ref_id, bonus, "referral", f"Referal bonus: {uid}"))
    conn.commit(); conn.close()

def orders_count(uid):
    conn = db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,))
    n = c.fetchone()[0]; conn.close(); return n

# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  STATES
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
class US(StatesGroup):          # User States
    select_category  = State()
    select_service   = State()
    enter_link       = State()
    enter_quantity   = State()
    topup_amount     = State()
    support_msg      = State()

class AS(StatesGroup):          # Admin States
    add_category       = State()
    api_name           = State()
    api_url            = State()
    api_key            = State()
    api_price          = State()
    svc_api_id         = State()   # API service ID kiritish
    svc_name           = State()
    svc_min            = State()
    svc_max            = State()
    svc_price          = State()
    set_referral       = State()
    set_currency       = State()
    broadcast_msg      = State()
    user_id_input      = State()
    balance_amount     = State()
    add_channel        = State()
    guide_title        = State()
    guide_content      = State()

# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  KEYBOARDS
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
def main_kb(is_admin=False):
    rows = [
        [KeyboardButton(text="Buyurtma berish")],
        [KeyboardButton(text="Buyurtmalar"),    KeyboardButton(text="Hisobim")],
        [KeyboardButton(text="Pul ishlash"),    KeyboardButton(text="Hisob to'ldirish")],
        [KeyboardButton(text="Murojaat"),        KeyboardButton(text="Qo'llanma")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="\ud83d\uddc4 Boshqaruv")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="\u2699\ufe0f Asosiy sozlamalar")],
        [KeyboardButton(text="\ud83d\udcca Statistika"),         KeyboardButton(text="\ud83d\udce8 Xabar yuborish")],
        [KeyboardButton(text="\ud83d\udd12 Majbur obuna kanallar")],
        [KeyboardButton(text="\ud83d\udcb3 To'lov tizimlar"),   KeyboardButton(text="\ud83d\udd11 API")],
        [KeyboardButton(text="\ud83d\udc69\u200d\ud83d\udcbb Foydalanuvchini boshqarish")],
        [KeyboardButton(text="\ud83d\udcda Qo'llanmalar"),       KeyboardButton(text="\ud83d\udcc8 Buyurtmalar")],
        [KeyboardButton(text="\ud83d\udcc1 Xizmatlar")],
        [KeyboardButton(text="\u25c0\ufe0f Orqaga")],
    ], resize_keyboard=True)

def back_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="\u25c0\ufe0f Orqaga")]], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="\u274c Bekor qilish")]], resize_keyboard=True)

# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  API HELPERS
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
async def api_services(url, key):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, data={"key": key, "action": "services"}, timeout=aiohttp.ClientTimeout(total=10)) as r:
                return await r.json(content_type=None)
    except Exception as e:
        logger.error(f"api_services error: {e}")
        return None

async def api_order(url, key, service_id, link, qty):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, data={"key": key, "action": "add",
                                          "service": service_id, "link": link, "quantity": qty},
                              timeout=aiohttp.ClientTimeout(total=15)) as r:
                return await r.json(content_type=None)
    except Exception as e:
        logger.error(f"api_order error: {e}")
        return None

# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
#  BOT
# \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# \u2500\u2500 subscription check \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
async def check_sub(uid):
    conn = db(); c = conn.cursor()
    c.execute("SELECT channel_id FROM channels")
    chs = c.fetchall(); conn.close()
    for (ch,) in chs:
        try:
            m = await bot.get_chat_member(ch, uid)
            if m.status in ("left", "kicked", "banned"):
                return False
        except:
            pass
    return True

async def sub_kb():
    conn = db(); c = conn.cursor()
    c.execute("SELECT channel_id,channel_name,channel_link FROM channels")
    chs = c.fetchall(); conn.close()
    b = InlineKeyboardBuilder()
    for cid, cname, clink in chs:
        b.button(text=f"\ud83d\udce2 {cname}", url=clink)
    b.button(text="\u2705 Tekshirish", callback_data="check_sub")
    b.adjust(1)
    return b.as_markup()

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  /start
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
@dp.message(Command("start"))
async def cmd_start(msg: types.Message, state: FSMContext):
    await state.clear()
    uid  = msg.from_user.id
    args = msg.text.split()
    ref  = 0
    if len(args) > 1:
        try: ref = int(args[1])
        except: pass

    if not get_user(uid):
        reg_user(uid, msg.from_user.username or "", msg.from_user.full_name or "", ref)

    if not await check_sub(uid):
        await msg.answer("\u26a0\ufe0f Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=await sub_kb())
        return

    await msg.answer("\ud83d\udda5 Asosiy menyudasiz!", reply_markup=main_kb(uid in ADMIN_IDS))

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(cb: types.CallbackQuery):
    if await check_sub(cb.from_user.id):
        await cb.message.answer("\u2705 Tasdiqlandi!\n\ud83d\udda5 Asosiy menyudasiz!", reply_markup=main_kb(cb.from_user.id in ADMIN_IDS))
        await cb.answer("\u2705 Tasdiqlandi!")
    else:
        await cb.answer("\u274c Siz hali obuna bo'lmadingiz!", show_alert=True)

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  USER \u2014 Hisobim
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
@dp.message(F.text == "Hisobim")
async def my_account(msg: types.Message):
    u = get_user(msg.from_user.id)
    if not u: return
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Hisobni to'ldirish")],
        [KeyboardButton(text="\u25c0\ufe0f Orqaga")]
    ], resize_keyboard=True)
    await msg.answer(
        f"\ud83d\udc64 Sizning ID raqamingiz: {u[0]}\n\n"
        f"\ud83d\udcb5 Balansingiz: {u[3]:.0f} {cur()}\n"
        f"\ud83d\udcca Buyurtmalaringiz: {orders_count(u[0])} ta\n"
        f"\ud83d\udc65 Referallaringiz: {u[5]} ta\n"
        f"\ud83d\udcb0 Kiritgan pullaringiz: {u[6]:.0f} {cur()}",
        reply_markup=kb
    )

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  USER \u2014 Pul ishlash
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
@dp.message(F.text == "Pul ishlash")
async def earn(msg: types.Message):
    u = get_user(msg.from_user.id)
    if not u: return
    bonus = get_setting("referral_bonus", "2500")
    bi    = await bot.get_me()
    link  = f"https://t.me/{bi.username}?start={u[0]}"
    await msg.answer(
        f"\ud83d\udd17 Sizning referal havolangiz:\n\n{link}\n\n"
        f"1 ta referal uchun {bonus} {cur()} beriladi\n\n"
        f"\ud83d\udc65 Referallaringiz: {u[5]} ta",
        reply_markup=back_kb()
    )

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  USER \u2014 Hisob to'ldirish
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
@dp.message(F.text.in_(["Hisob to'ldirish", "Hisobni to'ldirish"]))
async def topup(msg: types.Message):
    b = InlineKeyboardBuilder()
    if get_setting("payme_active") == "1" or get_setting("click_active") == "1":
        b.button(text="\ud83d\udca0 Avto-to'lov (Payme, Click)", callback_data="pay_auto")
    if get_setting("uzcart_active") == "1":
        b.button(text="Uzcart", callback_data="pay_uzcart")
    b.adjust(1)
    kb = b.as_markup()
    if not kb.inline_keyboard:
        await msg.answer("\u274c Hozirda to'lov tizimlari faol emas."); return
    await msg.answer("\ud83d\udcb3 Quyidagilardan birini tanlang:", reply_markup=kb)

@dp.callback_query(F.data.startswith("pay_"))
async def pay_method(cb: types.CallbackQuery, state: FSMContext):
    await state.update_data(pay_method=cb.data)
    await state.set_state(US.topup_amount)
    await cb.message.answer(f"\ud83d\udcb0 Qancha {cur()} kiritmoqchisiz?", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(US.topup_amount)
async def do_topup(msg: types.Message, state: FSMContext):
    if msg.text == "\u274c Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)); return
    try:
        amount = float(msg.text)
        if amount < 1000: raise ValueError
    except:
        await msg.answer("\u274c Minimal miqdor 1000 Sum"); return

    # Real loyihada to'lov tizimi bilan integratsiya qilish kerak
    b = InlineKeyboardBuilder()
    b.button(text="\u2705 To'lovni tasdiqlash (test)", callback_data=f"confirm_pay_{amount}")
    await msg.answer(
        f"\ud83d\udcb0 To'lov miqdori: {amount:.0f} {cur()}\n"
        f"To'lovni amalga oshirib 'Tasdiqlash' ni bosing.",
        reply_markup=b.as_markup()
    )
    await state.clear()

@dp.callback_query(F.data.startswith("confirm_pay_"))
async def confirm_pay(cb: types.CallbackQuery):
    amount = float(cb.data.replace("confirm_pay_", ""))
    uid    = cb.from_user.id
    conn   = db(); c = conn.cursor()
    c.execute("UPDATE users SET balance=balance+?, total_dep=total_dep+? WHERE user_id=?", (amount, amount, uid))
    c.execute("INSERT INTO transactions(user_id,amount,type,description) VALUES(?,?,?,?)",
              (uid, amount, "deposit", "Hisob to'ldirish"))
    conn.commit(); conn.close()
    await cb.message.answer(f"\u2705 {amount:.0f} {cur()} hisobingizga qo'shildi!")
    await cb.answer()

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  USER \u2014 Buyurtmalar
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
@dp.message(F.text == "Buyurtmalar")
async def my_orders(msg: types.Message):
    uid  = msg.from_user.id
    conn = db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,))
    total = c.fetchone()[0]
    if total == 0:
        await msg.answer("\u274c Sizda buyurtmalar mavjud emas."); return
    st = {}
    for s in ("completed","cancelled","pending","processing","partial"):
        c.execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND status=?", (uid, s))
        st[s] = c.fetchone()[0]
    conn.close()
    await msg.answer(
        f"\ud83d\udcc8 Buyurtmalar: {total} ta\n\n"
        f"\u2705 Bajarilganlar: {st['completed']} ta\n"
        f"\ud83d\udeab Bekor qilinganlar: {st['cancelled']} ta\n"
        f"\u23f3 Bajarilayotganlar: {st['pending']} ta\n"
        f"\ud83d\udd04 Jarayondagilar: {st['processing']} ta\n"
        f"\u267b\ufe0f Qayta ishlanganlar: {st['partial']} ta"
    )

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  USER \u2014 Buyurtma berish
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
@dp.message(F.text == "Buyurtma berish")
async def place_order(msg: types.Message, state: FSMContext):
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name FROM categories WHERE is_active=1")
    cats = c.fetchall(); conn.close()
    if not cats:
        await msg.answer("\u274c Hozirda xizmatlar mavjud emas."); return
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=name)] for _,name in cats] + [[KeyboardButton(text="\u25c0\ufe0f Orqaga")]],
        resize_keyboard=True
    )
    await state.set_state(US.select_category)
    await state.update_data(cats={name: cid for cid, name in cats})
    await msg.answer("\ud83d\udcc1 Bo'limni tanlang:", reply_markup=kb)

@dp.message(US.select_category)
async def sel_cat(msg: types.Message, state: FSMContext):
    if msg.text == "\u25c0\ufe0f Orqaga":
        await state.clear()
        await msg.answer("\ud83d\udda5 Asosiy menyudasiz!", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)); return
    data = await state.get_data()
    cats = data.get("cats", {})
    if msg.text not in cats:
        await msg.answer("\u274c Noto'g'ri tanlov"); return
    cat_id = cats[msg.text]
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,price_per1000,min_qty,max_qty FROM services WHERE category_id=? AND is_active=1", (cat_id,))
    svcs = c.fetchall(); conn.close()
    if not svcs:
        await msg.answer("\u274c Bu bo'limda xizmatlar yo'q."); return
    lines = f"\ud83d\udccb {msg.text}:\n\n"
    for sid, sname, price, mn, mx in svcs:
        lines += f"\u2022 {sname}\n  \ud83d\udcb0 {price:.0f} {cur()}/1000 | Min:{mn} Max:{mx}\n\n"
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=sname)] for _,sname,*_ in svcs] + [[KeyboardButton(text="\u25c0\ufe0f Orqaga")]],
        resize_keyboard=True
    )
    await state.update_data(svcs={sname: sid for sid, sname, *_ in svcs})
    await state.set_state(US.select_service)
    await msg.answer(lines, reply_markup=kb)

@dp.message(US.select_service)
async def sel_svc(msg: types.Message, state: FSMContext):
    if msg.text == "\u25c0\ufe0f Orqaga":
        await place_order(msg, state); return
    data = await state.get_data()
    svcs = data.get("svcs", {})
    if msg.text not in svcs:
        await msg.answer("\u274c Noto'g'ri tanlov"); return
    svc_id = svcs[msg.text]
    conn = db(); c = conn.cursor()
    c.execute("SELECT * FROM services WHERE id=?", (svc_id,))
    svc = c.fetchone(); conn.close()
    await state.update_data(svc=svc)
    await state.set_state(US.enter_link)
    await msg.answer(
        f"\ud83d\udccc {svc[4]}\n\ud83d\udcb0 {svc[7]:.0f} {cur()}/1000\nMin:{svc[5]} Max:{svc[6]}\n\n\ud83d\udd17 Linkni kiriting:",
        reply_markup=cancel_kb()
    )

@dp.message(US.enter_link)
async def enter_link(msg: types.Message, state: FSMContext):
    if msg.text == "\u274c Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)); return
    if not msg.text.startswith("http"):
        await msg.answer("\u274c Link https:// bilan boshlanishi kerak"); return
    await state.update_data(link=msg.text)
    data = await state.get_data()
    svc = data["svc"]
    await state.set_state(US.enter_quantity)
    await msg.answer(f"\ud83d\udcca Miqdorni kiriting (Min:{svc[5]}, Max:{svc[6]}):")

@dp.message(US.enter_quantity)
async def enter_qty(msg: types.Message, state: FSMContext):
    if msg.text == "\u274c Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)); return
    data = await state.get_data()
    svc  = data["svc"]
    try:
        qty = int(msg.text)
        assert svc[5] <= qty <= svc[6]
    except:
        await msg.answer(f"\u274c Miqdor {svc[5]}\u2013{svc[6]} orasida bo'lishi kerak"); return
    amount = (qty / 1000) * svc[7]
    u      = get_user(msg.from_user.id)
    text   = (
        f"\ud83d\udccb Buyurtma:\n\ud83d\udccc {svc[4]}\n\ud83d\udd17 {data['link']}\n"
        f"\ud83d\udcca Miqdor: {qty}\n\ud83d\udcb0 {amount:.0f} {cur()}\n"
        f"\ud83d\udcb5 Balans: {u[3]:.0f} {cur()}\n\n"
    )
    if u[3] < amount:
        text += f"\u274c Balans yetarli emas! Yetishmaydi: {amount-u[3]:.0f} {cur()}"
        await msg.answer(text, reply_markup=main_kb(msg.from_user.id in ADMIN_IDS))
        await state.clear(); return
    text += "\u2705 Tasdiqlaysizmi?"
    b = InlineKeyboardBuilder()
    b.button(text="\u2705 Tasdiqlash",   callback_data="order_yes")
    b.button(text="\u274c Bekor qilish", callback_data="order_no")
    await state.update_data(qty=qty, amount=amount)
    await msg.answer(text, reply_markup=b.as_markup())

@dp.callback_query(F.data == "order_yes")
async def order_confirm(cb: types.CallbackQuery, state: FSMContext):
    data   = await state.get_data()
    svc    = data["svc"]
    link   = data["link"]
    qty    = data["qty"]
    amount = data["amount"]
    uid    = cb.from_user.id

    conn = db(); c = conn.cursor()
    c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, uid))

    api_order_id = None
    if svc[2]:  # api_id
        c.execute("SELECT url,api_key FROM apis WHERE id=?", (svc[2],))
        api = c.fetchone()
        if api:
            res = await api_order(api[0], api[1], svc[3], link, qty)
            if res and "order" in res:
                api_order_id = str(res["order"])

    c.execute("INSERT INTO orders(user_id,service_id,api_order_id,link,quantity,amount,status) VALUES(?,?,?,?,?,?,?)",
              (uid, svc[0], api_order_id, link, qty, amount, "pending"))
    order_id = c.lastrowid
    c.execute("INSERT INTO transactions(user_id,amount,type,description) VALUES(?,?,?,?)",
              (uid, -amount, "order", f"Buyurtma #{order_id}"))
    conn.commit(); conn.close()

    await state.clear()
    await cb.message.answer(
        f"\u2705 Buyurtma qabul qilindi! #{order_id}\n\ud83d\udcb0 {amount:.0f} {cur()} yechildi.",
        reply_markup=main_kb(uid in ADMIN_IDS)
    )
    await cb.answer()

@dp.callback_query(F.data == "order_no")
async def order_cancel(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.answer("\u274c Bekor qilindi.", reply_markup=main_kb(cb.from_user.id in ADMIN_IDS))
    await cb.answer()

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  USER \u2014 Murojaat
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
@dp.message(F.text == "Murojaat")
async def support(msg: types.Message, state: FSMContext):
    await state.set_state(US.support_msg)
    await msg.answer("\ud83d\udcdd Murojaat matnini yozib yuboring.", reply_markup=cancel_kb())

@dp.message(US.support_msg)
async def do_support(msg: types.Message, state: FSMContext):
    if msg.text == "\u274c Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)); return
    for admin in ADMIN_IDS:
        try:
            await bot.send_message(admin,
                f"\ud83d\udce9 Yangi murojaat!\n\ud83d\udc64 {msg.from_user.full_name}\n\ud83c\udd94 {msg.from_user.id}\n\ud83d\udcdd {msg.text}")
        except: pass
    await state.clear()
    await msg.answer("\u2705 Murojaatingiz qabul qilindi!", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS))

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  USER \u2014 Qo'llanma
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
@dp.message(F.text == "Qo'llanma")
async def guides(msg: types.Message):
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,title FROM guides")
    gs = c.fetchall(); conn.close()
    if not gs:
        await msg.answer("\ud83d\udcda Qo'llanmalar yo'q"); return
    b = InlineKeyboardBuilder()
    for gid, gtitle in gs:
        b.button(text=f"\ud83d\udcd6 {gtitle}", callback_data=f"guide_{gid}")
    b.adjust(1)
    await msg.answer(f"\ud83d\udcda Qo'llanmalar ro'yhati: {len(gs)} ta", reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("guide_"))
async def show_guide(cb: types.CallbackQuery):
    gid  = int(cb.data.replace("guide_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT title,content FROM guides WHERE id=?", (gid,))
    g = c.fetchone(); conn.close()
    if g: await cb.message.answer(f"\ud83d\udcd6 {g[0]}\n\n{g[1]}")
    await cb.answer()

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  BACK / orqaga
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
@dp.message(F.text == "\u25c0\ufe0f Orqaga")
async def go_back(msg: types.Message, state: FSMContext):
    await state.clear()
    is_admin = msg.from_user.id in ADMIN_IDS
    await msg.answer("\ud83d\udda5 Asosiy menyudasiz!", reply_markup=main_kb(is_admin))

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
#  ADMIN \u2014 Boshqaruv
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
@dp.message(F.text == "\ud83d\uddc4 Boshqaruv")
async def admin_panel(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("\u274c Siz admin emassiz!"); return
    await state.clear()
    await msg.answer("Admin paneliga hush kelibsiz !", reply_markup=admin_kb())

# \u2500\u2500 Asosiy sozlamalar \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
@dp.message(F.text == "\u2699\ufe0f Asosiy sozlamalar")
async def admin_settings(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    rb   = get_setting("referral_bonus","2500")
    cv   = get_setting("currency","Sum")
    st_s = "\u2705 Faol" if get_setting("service_time","1")=="1" else "\u274c Nofaol"
    st_p = "\u2705 Faol" if get_setting("premium_emoji","1")=="1" else "\u274c Nofaol"
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="\ud83d\udcb0 Referal o'zgartirish")],
        [KeyboardButton(text="\ud83d\udcb2 Valyuta o'zgartirish")],
        [KeyboardButton(text=f"\ud83d\udd50 Xizmat vaqti: {st_s}")],
        [KeyboardButton(text=f"\u2728 Premium emoji: {st_p}")],
        [KeyboardButton(text="\u25c0\ufe0f Orqaga")],
    ], resize_keyboard=True)
    await msg.answer(
        f"\u2699\ufe0f Asosiy sozlamalar:\n\n"
        f"\u2666\ufe0f Referal: {rb} {cv}\n\u2666\ufe0f Valyuta: {cv}\n"
        f"\u2666\ufe0f Xizmat bajarilish vaqti: {st_s}\n\u2666\ufe0f Premium emoji: {st_p}\n\n"
        f"_Premium emoji faqat Telegram Premium foydalanuvchilari botlarida ishlaydi._",
        reply_markup=kb
    )

@dp.message(F.text == "\ud83d\udcb0 Referal o'zgartirish")
async def chg_ref(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.set_referral)
    await msg.answer(f"\ud83d\udcb0 Yangi referal miqdorini kiriting ({cur()}):", reply_markup=cancel_kb())

@dp.message(AS.set_referral)
async def do_chg_ref(msg: types.Message, state: FSMContext):
    if msg.text == "\u274c Bekor qilish":
        await state.clear(); await admin_settings(msg); return
    try:
        v = float(msg.text); set_setting("referral_bonus", v)
        await state.clear(); await msg.answer(f"\u2705 Referal {v:.0f} ga o'zgartirildi!")
        await admin_settings(msg)
    except: await msg.answer("\u274c Noto'g'ri miqdor")

@dp.message(F.text == "\ud83d\udcb2 Valyuta o'zgartirish")
async def chg_cur(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.set_currency)
    await msg.answer("\ud83d\udcb2 Yangi valyutani kiriting (Sum, USD, UZS ...):", reply_markup=cancel_kb())

@dp.message(AS.set_currency)
async def do_chg_cur(msg: types.Message, state: FSMContext):
    if msg.text == "\u274c Bekor qilish":
        await state.clear(); await admin_settings(msg); return
    set_setting("currency", msg.text)
    await state.clear(); await msg.answer(f"\u2705 Valyuta: {msg.text}")
    await admin_settings(msg)

@dp.message(F.text.startswith("\ud83d\udd50 Xizmat vaqti"))
async def toggle_svc_time(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    v = "0" if get_setting("service_time","1")=="1" else "1"
    set_setting("service_time", v)
    await msg.answer("\u2705 O'zgartirildi!"); await admin_settings(msg)

@dp.message(F.text.startswith("\u2728 Premium emoji"))
async def toggle_premium(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    v = "0" if get_setting("premium_emoji","1")=="1" else "1"
    set_setting("premium_emoji", v)
    await msg.answer("\u2705 O'zgartirildi!"); await admin_settings(msg)

# \u2500\u2500 Statistika \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
@dp.message(F.text == "\ud83d\udcca Statistika")
async def stat(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users"); total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE created_at>=datetime('now','-1 day')"); h24 = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE created_at>=datetime('now','-7 days')"); d7  = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE created_at>=datetime('now','-30 days')"); d30 = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE balance>0"); wb = c.fetchone()[0]
    c.execute("SELECT IFNULL(SUM(balance),0) FROM users"); tm = c.fetchone()[0]
    conn.close()
    bi = await bot.get_me()
    b  = InlineKeyboardBuilder()
    b.button(text="\ud83d\udcb5 TOP-50 Balans",  callback_data="top_bal")
    b.button(text="\ud83d\udc65 TOP-50 Referal", callback_data="top_ref")
    b.adjust(2)
    await msg.answer(
        f"\ud83d\udcca Statistika\n\u2022 Obunachilar soni: {total} ta\n\u2022 Faol obunachilar: {total} ta\n\u2022 Tark etganlar: 0 ta\n\n"
        f"\ud83d\udcc8 Qo'shilish\n\u2022 Oxirgi 24 soat: +{h24}\n\u2022 Oxirgi 7 kun: +{d7}\n\u2022 Oxirgi 30 kun: +{d30}\n\n"
        f"\ud83d\udcca Faollik\n\u2022 24 soatda faol: {h24} ta\n\u2022 7 kun faol: {d7} ta\n\u2022 30 kun faol: {d30} ta\n\n"
        f"\ud83d\udcb5 Pullar Statistikasi\n\u2022 Puli borlar: {wb} ta\n\u2022 Jami pullar: {tm:.0f} {cur()}\n\n"
        f"\ud83e\udd16 @{bi.username}",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data == "top_bal")
async def top_balance(cb: types.CallbackQuery):
    conn = db(); c = conn.cursor()
    c.execute("SELECT user
