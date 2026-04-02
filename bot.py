#!/usr/bin/env python3
# ============================================================
#   SMM BOT - Yangilangan versiya
#   O'zgarishlar:
#     1. Ijtimoiy tarmoqlar 2x2 grid (Telegram, Instagram, Youtube, Tiktok)
#     2. Har bir platforma uchun alohida bo'limlar
#     3. Buyruqlar 15 sekundda o'chib ketadi
#     4. Narx to'g'ri ko'rsatiladi
#     5. Admin: bo'lim qo'shishda platforma tanlash
#   Ishlatish: pip install aiogram aiohttp
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
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
#  ⚙️  SOZLAMALAR
# ============================================================
BOT_TOKEN = "8648355597:AAF_eM_GHY3SmBpHB4VSuK93O-o_pUXdgFg"
ADMIN_IDS = [8537782289]

# Platformalar
PLATFORMS = {
    "telegram":  "Telegram",
    "instagram": "Instagram",
    "youtube":   "Youtube",
    "tiktok":    "Tik tok",
}

DB = "smm_bot.db"

# ─────────────────────────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────────────────────────
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

    # platform ustuni qo'shilgan (telegram/instagram/youtube/tiktok)
    c.execute("""CREATE TABLE IF NOT EXISTS categories (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        name      TEXT NOT NULL,
        platform  TEXT NOT NULL DEFAULT 'telegram',
        is_active INTEGER DEFAULT 1
    )""")

    # Mavjud jadvalga platform ustuni qo'shish (migration)
    try:
        c.execute("ALTER TABLE categories ADD COLUMN platform TEXT NOT NULL DEFAULT 'telegram'")
    except Exception:
        pass

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

    c.execute("""CREATE TABLE IF NOT EXISTS manual_payments (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        name        TEXT NOT NULL,
        card_number TEXT NOT NULL,
        card_expiry TEXT NOT NULL,
        card_holder TEXT NOT NULL,
        is_active   INTEGER DEFAULT 1
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
    ]
    for k, v in defaults:
        c.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (k, v))

    c.execute("INSERT OR IGNORE INTO guides(id,title,content) VALUES(1,?,?)", (
        "Botdan foydalanish qo'llanmasi",
        "1. Buyurtma berish uchun 'Buyurtma berish' tugmasini bosing\n"
        "2. Ijtimoiy tarmoqni tanlang (Telegram, Instagram va h.k)\n"
        "3. Bo'limni tanlang → Xizmatni tanlang\n"
        "4. Link va miqdorni kiriting\n"
        "5. Tasdiqlang – pul hisobingizdan yechiladi"
    ))

    conn.commit()
    conn.close()

# ─── Yordamchi funksiyalar ───────────────────────────────────
def get_setting(key, default=""):
    conn = db(); c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = c.fetchone(); conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = db(); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings VALUES(?,?)", (key, str(value)))
    conn.commit(); conn.close()

def cur(): return get_setting("currency", "Sum")

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

async def auto_delete(message: types.Message, delay: int = 15):
    """Xabarni delay sekunddan keyin o'chiradi"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────
#  STATES
# ─────────────────────────────────────────────────────────────
class US(StatesGroup):
    select_platform  = State()
    select_category  = State()
    select_service   = State()
    enter_link       = State()
    enter_quantity   = State()
    topup_amount     = State()
    support_msg      = State()

class AS(StatesGroup):
    add_cat_platform   = State()
    add_category       = State()
    api_name           = State()
    api_url            = State()
    api_key            = State()
    api_price          = State()
    svc_api_id         = State()
    svc_name           = State()
    svc_min            = State()
    svc_max            = State()
    svc_price          = State()
    set_referral       = State()
    set_currency       = State()
    broadcast_msg      = State()
    broadcast_uid      = State()
    broadcast_uid_msg  = State()
    user_id_input      = State()
    balance_amount     = State()
    mpay_name          = State()
    mpay_card          = State()
    mpay_expiry        = State()
    mpay_holder        = State()
    bot_api_token      = State()
    bot_api_url        = State()
    add_channel        = State()
    guide_title        = State()
    guide_content      = State()

# ─────────────────────────────────────────────────────────────
#  KEYBOARDS
# ─────────────────────────────────────────────────────────────
def main_kb(is_admin=False):
    rows = [
        [KeyboardButton(text="Buyurtma berish")],
        [KeyboardButton(text="Buyurtmalar"),    KeyboardButton(text="Hisobim")],
        [KeyboardButton(text="Pul ishlash"),    KeyboardButton(text="Hisob to'ldirish")],
        [KeyboardButton(text="Murojaat"),        KeyboardButton(text="Qo'llanma")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="🗄 Boshqaruv")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⚙️ Asosiy sozlamalar")],
        [KeyboardButton(text="📊 Statistika"),         KeyboardButton(text="📨 Xabar yuborish")],
        [KeyboardButton(text="🔒 Majbur obuna kanallar")],
        [KeyboardButton(text="💳 To'lov tizimlar"),   KeyboardButton(text="🔑 API")],
        [KeyboardButton(text="👩‍💻 Foydalanuvchini boshqarish")],
        [KeyboardButton(text="📚 Qo'llanmalar"),       KeyboardButton(text="📈 Buyurtmalar")],
        [KeyboardButton(text="📁 Xizmatlar")],
        [KeyboardButton(text="◀️ Orqaga")],
    ], resize_keyboard=True)

def back_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="◀️ Orqaga")]], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor qilish")]], resize_keyboard=True)

def platforms_inline_kb():
    """2x2 grid: Telegram, Instagram, Youtube, Tik tok"""
    b = InlineKeyboardBuilder()
    b.button(text="Telegram",  callback_data="plat_telegram")
    b.button(text="Instagram", callback_data="plat_instagram")
    b.button(text="Youtube",   callback_data="plat_youtube")
    b.button(text="Tik tok",   callback_data="plat_tiktok")
    b.button(text="◀️ Orqaga", callback_data="order_back_main")
    b.adjust(2, 2, 1)
    return b.as_markup()

# ─────────────────────────────────────────────────────────────
#  API HELPERS
# ─────────────────────────────────────────────────────────────
async def api_services(url, key):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, data={"key": key, "action": "services"},
                              timeout=aiohttp.ClientTimeout(total=10)) as r:
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

async def api_balance(url, key):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, data={"key": key, "action": "balance"},
                              timeout=aiohttp.ClientTimeout(total=10)) as r:
                data = await r.json(content_type=None)
                if isinstance(data, dict):
                    bal = data.get("balance", data.get("funds", data.get("Balance", None)))
                    cur_val = data.get("currency", data.get("Currency", "USD"))
                    if bal is not None:
                        return float(bal), str(cur_val)
        return None, None
    except Exception as e:
        logger.error(f"api_balance error: {e}")
        return None, None

# ─────────────────────────────────────────────────────────────
#  BOT & DISPATCHER
# ─────────────────────────────────────────────────────────────
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# ── Obunani tekshirish ──────────────────────────────────────
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
        b.button(text=f"📢 {cname}", url=clink)
    b.button(text="✅ Tekshirish", callback_data="check_sub")
    b.adjust(1)
    return b.as_markup()

# ═══════════════════════════════════════════════════════════
#  /start — buyruq 15 sekundda o'chadi
# ═══════════════════════════════════════════════════════════
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

    # /start buyrug'ini 15 sekundda o'chir
    asyncio.create_task(auto_delete(msg, 15))

    if not await check_sub(uid):
        await msg.answer("⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
                         reply_markup=await sub_kb())
        return

    await msg.answer("🖥 Asosiy menyudasiz!", reply_markup=main_kb(uid in ADMIN_IDS))

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(cb: types.CallbackQuery):
    if await check_sub(cb.from_user.id):
        await cb.message.answer("✅ Tasdiqlandi!\n🖥 Asosiy menyudasiz!",
                                 reply_markup=main_kb(cb.from_user.id in ADMIN_IDS))
        await cb.answer("✅ Tasdiqlandi!")
    else:
        await cb.answer("❌ Siz hali obuna bo'lmadingiz!", show_alert=True)

# ═══════════════════════════════════════════════════════════
#  USER — Hisobim
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "Hisobim")
async def my_account(msg: types.Message):
    u = get_user(msg.from_user.id)
    if not u: return
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="Hisobni to'ldirish")],
        [KeyboardButton(text="◀️ Orqaga")]
    ], resize_keyboard=True)
    await msg.answer(
        f"👤 Sizning ID raqamingiz: {u[0]}\n\n"
        f"💵 Balansingiz: {u[3]:.2f} {cur()}\n"
        f"📊 Buyurtmalaringiz: {orders_count(u[0])} ta\n"
        f"👥 Referallaringiz: {u[5]} ta\n"
        f"💰 Kiritgan pullaringiz: {u[6]:.2f} {cur()}",
        reply_markup=kb
    )

# ═══════════════════════════════════════════════════════════
#  USER — Pul ishlash
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "Pul ishlash")
async def earn(msg: types.Message):
    u = get_user(msg.from_user.id)
    if not u: return
    bonus = get_setting("referral_bonus", "2500")
    bi    = await bot.get_me()
    link  = f"https://t.me/{bi.username}?start={u[0]}"
    await msg.answer(
        f"🔗 Sizning referal havolangiz:\n\n{link}\n\n"
        f"1 ta referal uchun {bonus} {cur()} beriladi\n\n"
        f"👥 Referallaringiz: {u[5]} ta",
        reply_markup=back_kb()
    )

# ═══════════════════════════════════════════════════════════
#  USER — Hisob to'ldirish
# ═══════════════════════════════════════════════════════════
@dp.message(F.text.in_(["Hisob to'ldirish", "Hisobni to'ldirish"]))
async def topup(msg: types.Message):
    b = InlineKeyboardBuilder()
    if get_setting("payme_active") == "1" or get_setting("click_active") == "1":
        b.button(text="💠 Avto-to'lov (Payme, Click)", callback_data="pay_auto")
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name FROM manual_payments WHERE is_active=1")
    mpays = c.fetchall(); conn.close()
    for pid, pname in mpays:
        b.button(text=f"💳 {pname}", callback_data=f"pay_manual_{pid}")
    b.adjust(1)
    kb = b.as_markup()
    if not kb.inline_keyboard:
        await msg.answer("❌ Hozirda to'lov tizimlari faol emas."); return
    await msg.answer("💳 Quyidagilardan birini tanlang:", reply_markup=kb)

@dp.callback_query(F.data.startswith("pay_manual_"))
async def pay_manual_show(cb: types.CallbackQuery):
    pid = int(cb.data.replace("pay_manual_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT name,card_number,card_expiry,card_holder FROM manual_payments WHERE id=?", (pid,))
    pay = c.fetchone(); conn.close()
    if not pay:
        await cb.answer("❌ Topilmadi", show_alert=True); return
    pname, pcard, pexpiry, pholder = pay
    await cb.message.answer(
        f"💳 <b>{pname}</b>\n\n"
        f"🔢 Karta raqami: <code>{pcard}</code>\n"
        f"📅 Amal qilish muddati: {pexpiry}\n"
        f"👤 Karta egasi: {pholder}\n\n"
        f"Ushbu kartaga pul o'tkazing va admin bilan bog'laning.",
        parse_mode="HTML"
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("pay_") & ~F.data.startswith("pay_manual_"))
async def pay_method(cb: types.CallbackQuery, state: FSMContext):
    await state.update_data(pay_method=cb.data)
    await state.set_state(US.topup_amount)
    await cb.message.answer(f"💰 Qancha {cur()} kiritmoqchisiz?", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(US.topup_amount)
async def do_topup(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)); return
    try:
        amount = float(msg.text)
        if amount < 1000: raise ValueError
    except:
        await msg.answer("❌ Minimal miqdor 1000 Sum"); return

    b = InlineKeyboardBuilder()
    b.button(text="✅ To'lovni tasdiqlash (test)", callback_data=f"confirm_pay_{amount}")
    await msg.answer(
        f"💰 To'lov miqdori: {amount:.0f} {cur()}\n"
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
    await cb.message.answer(f"✅ {amount:.0f} {cur()} hisobingizga qo'shildi!")
    await cb.answer()

# ═══════════════════════════════════════════════════════════
#  USER — Buyurtmalar
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "Buyurtmalar")
async def my_orders(msg: types.Message):
    uid  = msg.from_user.id
    conn = db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM orders WHERE user_id=?", (uid,))
    total = c.fetchone()[0]
    if total == 0:
        await msg.answer("❌ Sizda buyurtmalar mavjud emas."); return
    st = {}
    for s in ("completed", "cancelled", "pending", "processing", "partial"):
        c.execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND status=?", (uid, s))
        st[s] = c.fetchone()[0]
    conn.close()
    await msg.answer(
        f"📈 Buyurtmalar: {total} ta\n\n"
        f"✅ Bajarilganlar: {st['completed']} ta\n"
        f"🚫 Bekor qilinganlar: {st['cancelled']} ta\n"
        f"⏳ Kutilayotganlar: {st['pending']} ta\n"
        f"🔄 Jarayondagilar: {st['processing']} ta\n"
        f"♻️ Qisman: {st['partial']} ta"
    )

# ═══════════════════════════════════════════════════════════
#  USER — Buyurtma berish → Platforma tanlash (2x2 grid)
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "Buyurtma berish")
async def place_order(msg: types.Message, state: FSMContext):
    await state.set_state(US.select_platform)
    await msg.answer(
        "Quyidagi ijtimoiy tarmoqlardan birini tanlang.",
        reply_markup=platforms_inline_kb()
    )

@dp.callback_query(F.data == "order_back_main")
async def order_back_main(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await cb.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await cb.message.answer("🖥 Asosiy menyudasiz!", reply_markup=main_kb(cb.from_user.id in ADMIN_IDS))
    await cb.answer()

# ─── Platforma tanlandi → bo'limlar ────────────────────────
@dp.callback_query(F.data.startswith("plat_"))
async def platform_selected(cb: types.CallbackQuery, state: FSMContext):
    platform = cb.data.replace("plat_", "")
    plat_name = PLATFORMS.get(platform, platform.capitalize())

    conn = db(); c = conn.cursor()
    c.execute("SELECT id, name FROM categories WHERE is_active=1 AND platform=?", (platform,))
    cats = c.fetchall()
    conn.close()

    if not cats:
        await cb.answer(f"❌ {plat_name} uchun bo'limlar yo'q!", show_alert=True)
        return

    b = InlineKeyboardBuilder()
    for cid, cname in cats:
        b.button(text=cname, callback_data=f"order_cat_{cid}")
    b.button(text="◀️ Orqaga", callback_data="back_to_platforms")
    b.adjust(1)

    await state.update_data(platform=platform, plat_name=plat_name)
    await state.set_state(US.select_category)

    try:
        await cb.message.edit_text(
            f"Quyidagi bo'limlardan birini tanlang.",
            reply_markup=b.as_markup()
        )
    except Exception:
        await cb.message.answer(
            f"Quyidagi bo'limlardan birini tanlang.",
            reply_markup=b.as_markup()
        )
    await cb.answer()

@dp.callback_query(F.data == "back_to_platforms")
async def back_to_platforms(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(US.select_platform)
    try:
        await cb.message.edit_text(
            "Quyidagi ijtimoiy tarmoqlardan birini tanlang.",
            reply_markup=platforms_inline_kb()
        )
    except Exception:
        await cb.message.answer(
            "Quyidagi ijtimoiy tarmoqlardan birini tanlang.",
            reply_markup=platforms_inline_kb()
        )
    await cb.answer()

# ─── Bo'lim tanlandi → xizmatlar ───────────────────────────
@dp.callback_query(F.data.startswith("order_cat_"))
async def order_cat_selected(cb: types.CallbackQuery, state: FSMContext):
    cat_id = int(cb.data.replace("order_cat_", ""))
    conn = db(); c = conn.cursor()
    c.execute(
        "SELECT id, name, price_per1000, min_qty, max_qty FROM services "
        "WHERE category_id=? AND is_active=1", (cat_id,)
    )
    svcs = c.fetchall()
    c.execute("SELECT name, platform FROM categories WHERE id=?", (cat_id,))
    cat_row = c.fetchone()
    conn.close()

    if not svcs:
        await cb.answer("❌ Bu bo'limda xizmatlar yo'q.", show_alert=True)
        return

    cat_name = cat_row[0] if cat_row else "Bo'lim"
    platform = cat_row[1] if cat_row else "telegram"
    plat_name = PLATFORMS.get(platform, platform.capitalize())

    b = InlineKeyboardBuilder()
    for sid, sname, price, mn, mx in svcs:
        btn_text = f"{sname} - {price:.2f} {cur()}"
        b.button(text=btn_text, callback_data=f"sel_svc_{sid}")
    b.button(text="◀️ Orqaga", callback_data=f"plat_{platform}")
    b.adjust(1)

    await state.update_data(
        svcs={str(sid): (sid, sname, price, mn, mx) for sid, sname, price, mn, mx in svcs},
        last_cat_id=cat_id,
        cat_name=cat_name,
        platform=platform,
        plat_name=plat_name,
    )
    await state.set_state(US.select_service)

    text = f"Quyidagi xizmatlardan birini tanlang:\nNarxlar 1000 tasi uchun berilgan"
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup())
    await cb.answer()

# ─── Xizmat kartochkasi ─────────────────────────────────────
@dp.callback_query(F.data.startswith("sel_svc_"))
async def sel_svc(cb: types.CallbackQuery, state: FSMContext):
    svc_id = int(cb.data.replace("sel_svc_", ""))
    conn = db(); c = conn.cursor()
    c.execute(
        "SELECT s.id, s.category_id, s.api_id, s.api_service_id, s.name, "
        "s.min_qty, s.max_qty, s.price_per1000, s.is_active, cat.name, cat.platform "
        "FROM services s LEFT JOIN categories cat ON s.category_id=cat.id "
        "WHERE s.id=?", (svc_id,)
    )
    row = c.fetchone(); conn.close()
    if not row:
        await cb.answer("❌ Xizmat topilmadi", show_alert=True); return

    svc      = row[:9]
    cat_name = row[9] or ""
    platform = row[10] or "telegram"
    plat_name = PLATFORMS.get(platform, platform.capitalize())

    await state.update_data(svc=svc, svc_cat_name=cat_name, platform=platform, plat_name=plat_name)
    await state.set_state(US.enter_quantity)

    b = InlineKeyboardBuilder()
    b.button(text="✅ Buyurtma berish", callback_data=f"start_order_{svc_id}")
    b.button(text="◀️ Orqaga",          callback_data=f"order_cat_{svc[1]}")
    b.adjust(1)

    text = (
        f"{plat_name} - {svc[4]}\n\n"
        f"💰 Narxi (1000x): {svc[7]:.2f} {cur()}\n"
        f"⬇️ Minimal: {svc[5]} ta\n"
        f"⬆️ Maksimal: {svc[6]} ta"
    )
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup())
    await cb.answer()

# ─── Buyurtma berish → miqdor so'rash ──────────────────────
@dp.callback_query(F.data.startswith("start_order_"))
async def start_order(cb: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    svc  = data.get("svc")
    if not svc:
        await cb.answer("❌ Xizmat topilmadi", show_alert=True); return

    plat_name = data.get("plat_name", "")
    await state.set_state(US.enter_quantity)

    b = InlineKeyboardBuilder()
    b.button(text="◀️ Orqaga", callback_data=f"sel_svc_{svc[0]}")

    text = (
        f"{plat_name} - {svc[4]}\n\n"
        f"🔢 Buyurtma miqdorini kiriting:\n\n"
        f"⬇️ Minimal: {svc[5]} ta\n"
        f"⬆️ Maksimal: {svc[6]} ta"
    )
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(text)
    await cb.answer()

# ─── Miqdor kiritildi → link so'rash ───────────────────────
@dp.message(US.enter_quantity)
async def enter_qty(msg: types.Message, state: FSMContext):
    if msg.text in ("❌ Bekor qilish", "◀️ Orqaga"):
        await state.clear()
        await msg.answer("Bekor qilindi", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS))
        return
    data = await state.get_data()
    svc  = data.get("svc")
    if not svc:
        await state.clear()
        await msg.answer("❌ Xatolik, qaytadan boshlang.", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS))
        return
    try:
        qty = int(msg.text)
        if not (svc[5] <= qty <= svc[6]):
            raise ValueError
    except (ValueError, TypeError):
        await msg.answer(f"❌ Miqdor {svc[5]} – {svc[6]} orasida bo'lishi kerak")
        return

    await state.update_data(qty=qty)
    await state.set_state(US.enter_link)

    plat_name = data.get("plat_name", "")
    amount    = (qty / 1000) * svc[7]

    await msg.answer(
        f"{plat_name} - {svc[4]}\n\n"
        f"📊 Miqdor: {qty} ta\n"
        f"💰 Narx: {amount:.2f} {cur()}\n\n"
        f"🔗 Linkni yuboring:\n(Masalan: https://t.me/username)",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="◀️ Orqaga")]],
            resize_keyboard=True
        )
    )

# ─── Link kiritildi → tasdiqlash ────────────────────────────
@dp.message(US.enter_link)
async def enter_link(msg: types.Message, state: FSMContext):
    if msg.text in ("❌ Bekor qilish", "◀️ Orqaga"):
        data = await state.get_data()
        svc  = data.get("svc")
        await state.set_state(US.enter_quantity)
        if svc:
            plat_name = data.get("plat_name", "")
            b = InlineKeyboardBuilder()
            b.button(text="◀️ Orqaga", callback_data=f"sel_svc_{svc[0]}")
            await msg.answer(
                f"{plat_name} - {svc[4]}\n\n"
                f"🔢 Buyurtma miqdorini kiriting:\n\n"
                f"⬇️ Minimal: {svc[5]} ta\n"
                f"⬆️ Maksimal: {svc[6]} ta",
                reply_markup=b.as_markup()
            )
        else:
            await msg.answer("Bekor qilindi", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS))
        return

    if not msg.text.startswith("http"):
        await msg.answer("❌ Link https:// yoki http:// bilan boshlanishi kerak"); return

    data     = await state.get_data()
    svc      = data["svc"]
    qty      = data["qty"]
    amount   = (qty / 1000) * svc[7]
    u        = get_user(msg.from_user.id)
    plat_name = data.get("plat_name", "")

    await state.update_data(link=msg.text, amount=amount)

    if u[3] < amount:
        await msg.answer(
            f"❌ Balansingiz yetarli emas!\n\n"
            f"💵 Balans: {u[3]:.2f} {cur()}\n"
            f"💰 Kerak: {amount:.2f} {cur()}\n"
            f"➖ Yetishmaydi: {amount - u[3]:.2f} {cur()}\n\n"
            f"Hisob to'ldirish uchun asosiy menyudan foydalaning.",
            reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)
        )
        await state.clear(); return

    b = InlineKeyboardBuilder()
    b.button(text="✅ Yuborish",     callback_data="order_yes")
    b.button(text="❌ Bekor qilish", callback_data="order_no")
    b.adjust(1)

    await msg.answer(
        f"📋 Buyurtma ma'lumotlari:\n\n"
        f"📌 Xizmat: {plat_name} - {svc[4]}\n"
        f"🔗 Link: {msg.text}\n"
        f"📊 Miqdor: {qty} ta\n"
        f"💰 To'lash: {amount:.2f} {cur()}\n"
        f"💵 Balans: {u[3]:.2f} {cur()}\n\n"
        f"Tasdiqlaysizmi?",
        reply_markup=b.as_markup()
    )

# ─── Tasdiqlash → API yuborish ──────────────────────────────
@dp.callback_query(F.data == "order_yes")
async def order_confirm(cb: types.CallbackQuery, state: FSMContext):
    data   = await state.get_data()
    svc    = data["svc"]
    link   = data["link"]
    qty    = data["qty"]
    amount = data["amount"]
    uid    = cb.from_user.id
    plat_name = data.get("plat_name", "")

    conn = db(); c = conn.cursor()
    c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, uid))

    api_order_id = None
    api_error    = None
    if svc[2]:
        c.execute("SELECT url,api_key FROM apis WHERE id=?", (svc[2],))
        api = c.fetchone()
        if api:
            res = await api_order(api[0], api[1], svc[3], link, qty)
            if res and "order" in res:
                api_order_id = str(res["order"])
            elif res and "error" in res:
                api_error = str(res["error"])

    c.execute(
        "INSERT INTO orders(user_id,service_id,api_order_id,link,quantity,amount,status) "
        "VALUES(?,?,?,?,?,?,?)",
        (uid, svc[0], api_order_id, link, qty, amount, "pending")
    )
    order_id = c.lastrowid
    c.execute(
        "INSERT INTO transactions(user_id,amount,type,description) VALUES(?,?,?,?)",
        (uid, -amount, "order", f"Buyurtma #{order_id}")
    )
    conn.commit(); conn.close()

    u = get_user(uid)
    new_balance = u[3] if u else 0

    lines = [
        "✅ Buyurtma muvaffaqiyatli yuborildi!\n",
        f"🆔 Buyurtma: #{order_id}",
        f"📌 Xizmat: {plat_name} - {svc[4]}",
        f"🔗 Link: {link}",
        f"📊 Miqdor: {qty} ta",
        f"💰 Yechildi: {amount:.2f} {cur()}",
        f"💵 Qolgan balans: {new_balance:.2f} {cur()}",
    ]
    if api_order_id:
        lines.append(f"📡 API order ID: {api_order_id}")
    if api_error:
        lines.append(f"⚠️ API xato: {api_error}")
    lines.append("\n⏳ Xizmat bajarilmoqda...")

    await state.clear()
    try:
        await cb.message.edit_text("\n".join(lines), reply_markup=None)
    except Exception:
        await cb.message.answer("\n".join(lines))
    await cb.message.answer("🖥 Asosiy menyudasiz!", reply_markup=main_kb(uid in ADMIN_IDS))
    await cb.answer()

@dp.callback_query(F.data == "order_no")
async def order_cancel(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await cb.message.edit_text("❌ Buyurtma bekor qilindi.", reply_markup=None)
    except Exception:
        pass
    await cb.message.answer("🖥 Asosiy menyudasiz!", reply_markup=main_kb(cb.from_user.id in ADMIN_IDS))
    await cb.answer()

# ═══════════════════════════════════════════════════════════
#  USER — Murojaat
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "Murojaat")
async def support(msg: types.Message, state: FSMContext):
    await state.set_state(US.support_msg)
    await msg.answer("📝 Murojaat matnini yozib yuboring.", reply_markup=cancel_kb())

@dp.message(US.support_msg)
async def do_support(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)); return
    for admin in ADMIN_IDS:
        try:
            await bot.send_message(admin,
                f"📩 Yangi murojaat!\n👤 {msg.from_user.full_name}\n🆔 {msg.from_user.id}\n📝 {msg.text}")
        except:
            pass
    await state.clear()
    await msg.answer("✅ Murojaatingiz qabul qilindi!", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS))

# ═══════════════════════════════════════════════════════════
#  USER — Qo'llanma
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "Qo'llanma")
async def guides(msg: types.Message):
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,title FROM guides")
    gs = c.fetchall(); conn.close()
    if not gs:
        await msg.answer("📚 Qo'llanmalar yo'q"); return
    b = InlineKeyboardBuilder()
    for gid, gtitle in gs:
        b.button(text=f"📖 {gtitle}", callback_data=f"guide_{gid}")
    b.adjust(1)
    await msg.answer(f"📚 Qo'llanmalar ro'yhati: {len(gs)} ta", reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("guide_"))
async def show_guide(cb: types.CallbackQuery):
    gid  = int(cb.data.replace("guide_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT title,content FROM guides WHERE id=?", (gid,))
    g = c.fetchone(); conn.close()
    if g: await cb.message.answer(f"📖 {g[0]}\n\n{g[1]}")
    await cb.answer()

# ═══════════════════════════════════════════════════════════
#  ORQAGA
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "◀️ Orqaga")
async def go_back(msg: types.Message, state: FSMContext):
    await state.clear()
    is_admin = msg.from_user.id in ADMIN_IDS
    await msg.answer("🖥 Asosiy menyudasiz!", reply_markup=main_kb(is_admin))

# ═══════════════════════════════════════════════════════════
#  ADMIN — Boshqaruv
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "🗄 Boshqaruv")
async def admin_panel(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS:
        await msg.answer("❌ Siz admin emassiz!"); return
    await state.clear()
    await msg.answer("Admin paneliga xush kelibsiz!", reply_markup=admin_kb())

# ── Asosiy sozlamalar ─────────────────────────────────────
@dp.message(F.text == "⚙️ Asosiy sozlamalar")
async def admin_settings(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    rb   = get_setting("referral_bonus", "2500")
    cv   = get_setting("currency", "Sum")
    st_s = "✅ Faol" if get_setting("service_time", "1") == "1" else "❌ Nofaol"
    st_p = "✅ Faol" if get_setting("premium_emoji", "1") == "1" else "❌ Nofaol"
    b = InlineKeyboardBuilder()
    b.button(text="💰 Referal o'zgartirish",  callback_data="set_ref")
    b.button(text="💱 Valyuta o'zgartirish",   callback_data="set_cur")
    b.button(text=f"🕐 Xizmat vaqti: {st_s}", callback_data="tog_svctime")
    b.button(text=f"✨ Premium emoji: {st_p}", callback_data="tog_premium")
    b.adjust(1)
    await msg.answer(
        f"⚙️ <b>Asosiy sozlamalar:</b>\n\n"
        f"♦️ Referal: {rb} {cv}\n"
        f"♦️ Valyuta: {cv}\n"
        f"♦️ Xizmat bajarilish vaqti: {st_s}\n"
        f"♦️ Premium emoji: {st_p}",
        parse_mode="HTML", reply_markup=b.as_markup()
    )

@dp.callback_query(F.data == "set_ref")
async def cb_set_ref(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.set_referral)
    await cb.message.answer(f"💰 Yangi referal miqdorini kiriting ({cur()}):", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.set_referral)
async def do_chg_ref(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    try:
        v = float(msg.text); set_setting("referral_bonus", v)
        await state.clear()
        await msg.answer(f"✅ Referal <b>{v:.0f}</b> {cur()} ga o'zgartirildi!", parse_mode="HTML",
                         reply_markup=admin_kb())
    except:
        await msg.answer("❌ Noto'g'ri miqdor, raqam kiriting:")

@dp.callback_query(F.data == "set_cur")
async def cb_set_cur(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    b = InlineKeyboardBuilder()
    b.button(text="🇺🇿 So'm (UZS)", callback_data="cur_Sum")
    b.button(text="🇺🇸 Dollar (USD)", callback_data="cur_USD")
    b.button(text="🇷🇺 Rubl (RUB)", callback_data="cur_RUB")
    b.adjust(1)
    await cb.message.answer("💱 Valyutani tanlang:", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("cur_"))
async def cb_cur_select(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    val = cb.data.replace("cur_", "")
    set_setting("currency", val)
    await cb.answer(f"✅ Valyuta: {val}")
    await cb.message.answer(f"✅ Valyuta <b>{val}</b> ga o'zgartirildi!", parse_mode="HTML",
                             reply_markup=admin_kb())

@dp.callback_query(F.data == "tog_svctime")
async def cb_tog_svctime(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    v = "0" if get_setting("service_time", "1") == "1" else "1"
    set_setting("service_time", v)
    await cb.answer("✅ O'zgartirildi!")

@dp.callback_query(F.data == "tog_premium")
async def cb_tog_premium(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    v = "0" if get_setting("premium_emoji", "1") == "1" else "1"
    set_setting("premium_emoji", v)
    await cb.answer("✅ O'zgartirildi!")

# ── Statistika ─────────────────────────────────────────────
@dp.message(F.text == "📊 Statistika")
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
    b.button(text="💵 TOP-50 Balans",  callback_data="top_bal")
    b.button(text="👥 TOP-50 Referal", callback_data="top_ref")
    b.adjust(2)
    await msg.answer(
        f"📊 Statistika\n\n"
        f"👥 Jami foydalanuvchilar: {total} ta\n"
        f"📈 Oxirgi 24 soat: +{h24}\n"
        f"📈 Oxirgi 7 kun: +{d7}\n"
        f"📈 Oxirgi 30 kun: +{d30}\n\n"
        f"💵 Puli borlar: {wb} ta\n"
        f"💰 Jami pullar: {tm:.2f} {cur()}\n\n"
        f"🤖 @{bi.username}",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data == "top_bal")
async def top_balance(cb: types.CallbackQuery):
    conn = db(); c = conn.cursor()
    c.execute("SELECT user_id,full_name,balance FROM users ORDER BY balance DESC LIMIT 50")
    rows = c.fetchall(); conn.close()
    text = "💵 TOP-50 Balans:\n\n"
    for i, (uid, name, bal) in enumerate(rows, 1):
        text += f"{i}. {name or uid} — {bal:.2f} {cur()}\n"
    await cb.message.answer(text[:4096]); await cb.answer()

@dp.callback_query(F.data == "top_ref")
async def top_ref(cb: types.CallbackQuery):
    conn = db(); c = conn.cursor()
    c.execute("SELECT user_id,full_name,referral_count FROM users ORDER BY referral_count DESC LIMIT 50")
    rows = c.fetchall(); conn.close()
    text = "👥 TOP-50 Referal:\n\n"
    for i, (uid, name, rc) in enumerate(rows, 1):
        text += f"{i}. {name or uid} — {rc} ta\n"
    await cb.message.answer(text[:4096]); await cb.answer()

# ── Xabar yuborish ─────────────────────────────────────────
@dp.message(F.text == "📨 Xabar yuborish")
async def broadcast_menu(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    b = InlineKeyboardBuilder()
    b.button(text="💬 1 foydalanuvchiga xabar",   callback_data="bc_single")
    b.button(text="📨 Barchaga xabar (forward)", callback_data="bc_forward_all")
    b.adjust(1)
    await msg.answer("Xabar yuborish turini tanlang:", reply_markup=b.as_markup())

@dp.callback_query(F.data == "bc_forward_all")
async def bc_forward_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.update_data(bc_type="forward")
    await state.set_state(AS.broadcast_msg)
    await cb.message.answer("📨 Forward qilinadigan xabarni yuboring:", reply_markup=cancel_kb())
    await cb.answer()

@dp.callback_query(F.data == "bc_single")
async def bc_single_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.broadcast_uid)
    await cb.message.answer("👤 Foydalanuvchi ID sini kiriting:", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.broadcast_uid)
async def bc_uid(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    try:
        uid = int(msg.text)
        await state.update_data(single_uid=uid)
        await state.set_state(AS.broadcast_uid_msg)
        await msg.answer(f"📝 {uid} ga xabar matnini kiriting:")
    except:
        await msg.answer("❌ Noto'g'ri ID")

@dp.message(AS.broadcast_uid_msg)
async def bc_uid_msg(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    data = await state.get_data()
    uid  = data["single_uid"]
    try:
        await bot.send_message(uid, msg.text)
        await msg.answer(f"✅ Xabar {uid} ga yuborildi!", reply_markup=admin_kb())
    except Exception as e:
        await msg.answer(f"❌ Xato: {e}", reply_markup=admin_kb())
    await state.clear()

@dp.message(AS.broadcast_msg)
async def do_broadcast(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    conn = db(); c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = c.fetchall(); conn.close()
    sent = fail = 0
    for (uid,) in users:
        try:
            await bot.forward_message(uid, msg.chat.id, msg.message_id)
            sent += 1
        except:
            fail += 1
        await asyncio.sleep(0.05)
    await state.clear()
    await msg.answer(f"✅ Xabar yuborildi!\n✔️ Muvaffaqiyatli: {sent}\n❌ Xato: {fail}",
                     reply_markup=admin_kb())

# ── Foydalanuvchini boshqarish ────────────────────────────
@dp.message(F.text == "👩‍💻 Foydalanuvchini boshqarish")
async def admin_users(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.user_id_input)
    await msg.answer("👤 Foydalanuvchi ID sini kiriting:", reply_markup=cancel_kb())

@dp.message(AS.user_id_input)
async def do_user_manage(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    try:
        uid = int(msg.text)
    except:
        await msg.answer("❌ Noto'g'ri ID"); return
    u = get_user(uid)
    if not u:
        await msg.answer("❌ Foydalanuvchi topilmadi"); await state.clear(); return
    await state.clear()
    b = InlineKeyboardBuilder()
    b.button(text="➕ Balans qo'shish", callback_data=f"uadd_{uid}")
    b.button(text="➖ Balans ayirish",  callback_data=f"usub_{uid}")
    b.button(text="📩 Xabar yuborish",  callback_data=f"umsg_{uid}")
    b.adjust(2)
    await msg.answer(
        f"👤 {u[2] or 'Nomsiz'}\n"
        f"🆔 ID: {u[0]}\n"
        f"💵 Balans: {u[3]:.2f} {cur()}\n"
        f"📊 Buyurtmalar: {orders_count(uid)} ta\n"
        f"👥 Referallar: {u[5]} ta",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data.startswith("uadd_"))
async def u_add(cb: types.CallbackQuery, state: FSMContext):
    uid = int(cb.data.replace("uadd_", ""))
    await state.update_data(target_uid=uid, bal_action="add")
    await state.set_state(AS.balance_amount)
    await cb.message.answer("💰 Qo'shmoqchi bo'lgan miqdor:", reply_markup=cancel_kb())
    await cb.answer()

@dp.callback_query(F.data.startswith("usub_"))
async def u_sub(cb: types.CallbackQuery, state: FSMContext):
    uid = int(cb.data.replace("usub_", ""))
    await state.update_data(target_uid=uid, bal_action="sub")
    await state.set_state(AS.balance_amount)
    await cb.message.answer("💰 Ayirmoqchi bo'lgan miqdor:", reply_markup=cancel_kb())
    await cb.answer()

@dp.callback_query(F.data.startswith("umsg_"))
async def u_msg(cb: types.CallbackQuery, state: FSMContext):
    uid = int(cb.data.replace("umsg_", ""))
    await state.update_data(single_uid=uid)
    await state.set_state(AS.broadcast_uid_msg)
    await cb.message.answer(f"📝 {uid} ga xabar matnini kiriting:", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.balance_amount)
async def do_balance(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    try: amount = float(msg.text)
    except: await msg.answer("❌ Noto'g'ri miqdor"); return
    data   = await state.get_data()
    uid    = data["target_uid"]
    action = data["bal_action"]
    conn   = db(); c = conn.cursor()
    if action == "add":
        c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid))
        c.execute("INSERT INTO transactions(user_id,amount,type,description) VALUES(?,?,?,?)",
                  (uid, amount, "admin_add", "Admin tomonidan qo'shildi"))
        try: await bot.send_message(uid, f"✅ Hisobingizga {amount:.2f} {cur()} qo'shildi!")
        except: pass
    else:
        c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, uid))
        c.execute("INSERT INTO transactions(user_id,amount,type,description) VALUES(?,?,?,?)",
                  (uid, -amount, "admin_sub", "Admin tomonidan ayirildi"))
        try: await bot.send_message(uid, f"⚠️ Hisobingizdan {amount:.2f} {cur()} ayirildi!")
        except: pass
    conn.commit(); conn.close()
    act_text = "qo'shildi" if action == "add" else "ayirildi"
    await state.clear()
    await msg.answer(f"✅ {uid} ga {amount:.2f} {cur()} {act_text}!", reply_markup=admin_kb())

# ── Majbur obuna ──────────────────────────────────────────
@dp.message(F.text == "🔒 Majbur obuna kanallar")
async def forced_channels(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,channel_name,channel_id FROM channels")
    chs = c.fetchall(); conn.close()
    b = InlineKeyboardBuilder()
    for cid, cname, ch_id in chs:
        b.button(text=f"🗑 {cname}", callback_data=f"del_ch_{cid}")
    b.button(text="➕ Kanal qo'shish", callback_data="add_channel")
    b.adjust(1)
    await msg.answer(f"📢 Kanallar: {len(chs)} ta", reply_markup=b.as_markup())

@dp.callback_query(F.data == "add_channel")
async def start_add_channel(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.add_channel)
    await cb.message.answer(
        "📢 Kanal ma'lumotlarini quyidagi formatda yuboring:\n\n"
        "<code>@kanal_username | Kanal Nomi | https://t.me/kanal_link</code>",
        parse_mode="HTML", reply_markup=cancel_kb()
    )
    await cb.answer()

@dp.message(AS.add_channel)
async def do_add_channel(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    parts = [p.strip() for p in msg.text.split("|")]
    if len(parts) != 3:
        await msg.answer("❌ Format noto'g'ri. Qayta kiriting:"); return
    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO channels(channel_id,channel_name,channel_link) VALUES(?,?,?)",
              (parts[0], parts[1], parts[2]))
    conn.commit(); conn.close()
    await state.clear()
    await msg.answer(f"✅ Kanal qo'shildi: {parts[1]}", reply_markup=admin_kb())

@dp.callback_query(F.data.startswith("del_ch_"))
async def del_ch(cb: types.CallbackQuery):
    cid = int(cb.data.replace("del_ch_", ""))
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM channels WHERE id=?", (cid,))
    conn.commit(); conn.close()
    await cb.message.answer("✅ Kanal o'chirildi!"); await cb.answer()

# ── To'lov tizimlari ──────────────────────────────────────
@dp.message(F.text == "💳 To'lov tizimlar")
async def payment_methods(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,card_number,is_active FROM manual_payments")
    pays = c.fetchall(); conn.close()
    b = InlineKeyboardBuilder()
    for pid, pname, pcard, pact in pays:
        st = "✅" if pact else "❌"
        b.button(text=f"{st} {pname} — {pcard[:8]}...", callback_data=f"pay_tog_{pid}")
    b.button(text="➕ To'lov qo'shish", callback_data="add_mpay")
    b.adjust(1)
    await msg.answer(f"💳 To'lov tizimlari: {len(pays)} ta", reply_markup=b.as_markup())

@dp.callback_query(F.data == "add_mpay")
async def add_mpay(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.mpay_name)
    await cb.message.answer("💳 To'lov nomi (masalan: Click, Payme):", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.mpay_name)
async def mpay_name(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    await state.update_data(mpay_name=msg.text)
    await state.set_state(AS.mpay_card)
    await msg.answer("🔢 Karta raqami:")

@dp.message(AS.mpay_card)
async def mpay_card(msg: types.Message, state: FSMContext):
    await state.update_data(mpay_card=msg.text)
    await state.set_state(AS.mpay_expiry)
    await msg.answer("📅 Amal qilish muddati (masalan: 12/26):")

@dp.message(AS.mpay_expiry)
async def mpay_expiry(msg: types.Message, state: FSMContext):
    await state.update_data(mpay_expiry=msg.text)
    await state.set_state(AS.mpay_holder)
    await msg.answer("👤 Karta egasi (to'liq ismi):")

@dp.message(AS.mpay_holder)
async def mpay_holder(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO manual_payments(name,card_number,card_expiry,card_holder) VALUES(?,?,?,?)",
              (data["mpay_name"], data["mpay_card"], data["mpay_expiry"], msg.text))
    conn.commit(); conn.close()
    await state.clear()
    await msg.answer(f"✅ To'lov tizimi qo'shildi: {data['mpay_name']}", reply_markup=admin_kb())

@dp.callback_query(F.data.startswith("pay_tog_"))
async def pay_toggle(cb: types.CallbackQuery):
    pid = int(cb.data.replace("pay_tog_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT is_active FROM manual_payments WHERE id=?", (pid,))
    v = c.fetchone()[0]
    c.execute("UPDATE manual_payments SET is_active=? WHERE id=?", (0 if v else 1, pid))
    conn.commit(); conn.close()
    await cb.answer("✅ O'zgartirildi!")

# ── API boshqaruvi ────────────────────────────────────────
@dp.message(F.text == "🔑 API")
async def api_menu(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,url FROM apis")
    apis = c.fetchall(); conn.close()
    b = InlineKeyboardBuilder()
    for aid, aname, aurl in apis:
        b.button(text=f"🔑 {aname}", callback_data=f"api_{aid}")
    b.button(text="➕ API qo'shish", callback_data="api_add")
    b.adjust(1)
    await msg.answer(f"🔑 API lar: {len(apis)} ta", reply_markup=b.as_markup())

@dp.callback_query(F.data == "api_add")
async def api_add(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.api_name)
    await cb.message.answer("🔑 API nomi:", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.api_name)
async def api_name_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    await state.update_data(api_name=msg.text)
    await state.set_state(AS.api_url)
    await msg.answer("🌐 API URL (masalan: https://panel.uz/api/v2):")

@dp.message(AS.api_url)
async def api_url_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    await state.update_data(api_url=msg.text)
    await state.set_state(AS.api_key)
    await msg.answer("🔐 API kaliti (key):")

@dp.message(AS.api_key)
async def api_key_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    data = await state.get_data()
    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO apis(name,url,api_key) VALUES(?,?,?)",
              (data["api_name"], data["api_url"], msg.text))
    aid = c.lastrowid
    conn.commit(); conn.close()
    await state.clear()
    await msg.answer(f"✅ API qo'shildi: {data['api_name']}\n🆔 ID: {aid}", reply_markup=admin_kb())

@dp.callback_query(F.data.startswith("api_") & ~F.data.startswith("api_add") & ~F.data.startswith("api_del_"))
async def api_detail(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    try:
        aid = int(cb.data.replace("api_", ""))
    except:
        await cb.answer(); return
    conn = db(); c = conn.cursor()
    c.execute("SELECT * FROM apis WHERE id=?", (aid,))
    api = c.fetchone(); conn.close()
    if not api: await cb.answer("❌ Topilmadi"); return
    b = InlineKeyboardBuilder()
    b.button(text="💰 Balansni ko'rish", callback_data=f"api_bal_{aid}")
    b.button(text="🗑 O'chirish",         callback_data=f"api_del_{aid}")
    b.adjust(2)
    await cb.message.answer(
        f"🔑 {api[1]}\n🌐 {api[2]}\n🔐 {api[3][:15]}...",
        reply_markup=b.as_markup()
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("api_bal_"))
async def api_bal(cb: types.CallbackQuery):
    aid  = int(cb.data.replace("api_bal_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT url,api_key FROM apis WHERE id=?", (aid,))
    api = c.fetchone(); conn.close()
    if not api: await cb.answer("❌ Topilmadi"); return
    bal, cur_val = await api_balance(api[0], api[1])
    if bal is None:
        await cb.answer("❌ API ga ulanib bo'lmadi", show_alert=True)
    else:
        await cb.message.answer(f"💰 API balansi: {bal:.2f} {cur_val}")
    await cb.answer()

@dp.callback_query(F.data.startswith("api_del_"))
async def api_del(cb: types.CallbackQuery):
    aid  = int(cb.data.replace("api_del_", ""))
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM apis WHERE id=?", (aid,))
    conn.commit(); conn.close()
    await cb.message.answer("✅ API o'chirildi!")
    await cb.answer()

# ── Qo'llanmalar (Admin) ─────────────────────────────────
@dp.message(F.text == "📚 Qo'llanmalar")
async def admin_guides(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,title FROM guides")
    gs = c.fetchall(); conn.close()
    b = InlineKeyboardBuilder()
    for gid, gtitle in gs:
        b.button(text=f"🗑 {gtitle}", callback_data=f"del_guide_{gid}")
    b.button(text="➕ Qo'llanma qo'shish", callback_data="add_guide")
    b.adjust(1)
    await msg.answer(f"📚 Qo'llanmalar: {len(gs)} ta", reply_markup=b.as_markup())

@dp.callback_query(F.data == "add_guide")
async def start_guide(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.guide_title)
    await cb.message.answer("📖 Qo'llanma nomini kiriting:", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.guide_title)
async def guide_title_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await admin_guides(msg); return
    await state.update_data(gtitle=msg.text)
    await state.set_state(AS.guide_content)
    await msg.answer("📝 Qo'llanma matnini kiriting:")

@dp.message(AS.guide_content)
async def guide_content_h(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO guides(title,content) VALUES(?,?)", (data["gtitle"], msg.text))
    conn.commit(); conn.close()
    await state.clear()
    await msg.answer("✅ Qo'llanma qo'shildi!", reply_markup=admin_kb())

@dp.callback_query(F.data.startswith("del_guide_"))
async def del_guide(cb: types.CallbackQuery):
    gid = int(cb.data.replace("del_guide_", ""))
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM guides WHERE id=?", (gid,))
    conn.commit(); conn.close()
    await cb.message.answer("✅ Qo'llanma o'chirildi!"); await cb.answer()

# ── Buyurtmalar (Admin) ──────────────────────────────────
@dp.message(F.text == "📈 Buyurtmalar")
async def admin_orders(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM orders"); total = c.fetchone()[0]
    st = {}
    for s in ("completed", "cancelled", "pending", "processing", "partial"):
        c.execute("SELECT COUNT(*) FROM orders WHERE status=?", (s,))
        st[s] = c.fetchone()[0]
    conn.close()
    b = InlineKeyboardBuilder()
    b.button(text="🔍 So'nggi buyurtmalar", callback_data="search_orders")
    await msg.answer(
        f"📈 Buyurtmalar: {total} ta\n\n"
        f"✅ Bajarilganlar: {st['completed']} ta\n"
        f"🚫 Bekor qilinganlar: {st['cancelled']} ta\n"
        f"⏳ Kutilayotganlar: {st['pending']} ta\n"
        f"🔄 Jarayondagilar: {st['processing']} ta\n"
        f"♻️ Qisman: {st['partial']} ta",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data == "search_orders")
async def search_orders(cb: types.CallbackQuery):
    conn = db(); c = conn.cursor()
    c.execute("""SELECT o.id,o.user_id,s.name,o.quantity,o.amount,o.status,o.created_at
                 FROM orders o LEFT JOIN services s ON o.service_id=s.id
                 ORDER BY o.id DESC LIMIT 20""")
    rows = c.fetchall(); conn.close()
    if not rows:
        await cb.message.answer("❌ Buyurtmalar yo'q"); await cb.answer(); return
    text = "📋 So'nggi 20 buyurtma:\n\n"
    for r in rows:
        text += f"#{r[0]} | {r[2] or '?'} | {r[3]} ta | {r[4]:.2f} {cur()} | {r[5]}\n"
    await cb.message.answer(text[:4096]); await cb.answer()

# ═══════════════════════════════════════════════════════════
#  ADMIN — 📁 Xizmatlar
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "📁 Xizmatlar")
async def svc_home(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM categories"); nc = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM services");   ns = c.fetchone()[0]
    conn.close()
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📂 Bo'limlar")],
        [KeyboardButton(text="🛠 Barcha xizmatlar")],
        [KeyboardButton(text="◀️ Orqaga")],
    ], resize_keyboard=True)
    await msg.answer(
        f"📁 Xizmatlar boshqaruvi\n\n"
        f"📂 Bo'limlar: {nc} ta\n"
        f"🛠 Xizmatlar: {ns} ta\n\n"
        f"Bo'lim qo'shishda platforma (Telegram, Instagram...) tanlanadi.",
        reply_markup=kb
    )

# ── Bo'limlar boshqaruvi ──────────────────────────────────
@dp.message(F.text == "📂 Bo'limlar")
async def cat_menu(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,platform,is_active FROM categories ORDER BY platform,name")
    cats = c.fetchall(); conn.close()
    b = InlineKeyboardBuilder()
    for cid, cname, cplat, cact in cats:
        status = "✅" if cact else "❌"
        plat_icon = {"telegram": "✈️", "instagram": "📸", "youtube": "▶️", "tiktok": "🎵"}.get(cplat, "📁")
        b.button(text=f"{status} {plat_icon} {cname}", callback_data=f"cat_{cid}")
    b.button(text="➕ Bo'lim qo'shish", callback_data="cat_add")
    b.adjust(2)
    await msg.answer(f"📂 Bo'limlar: {len(cats)} ta", reply_markup=b.as_markup())

# ─── Bo'lim qo'shish: 1-platforma tanlash ──────────────────
@dp.callback_query(F.data == "cat_add")
async def cat_add(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    b = InlineKeyboardBuilder()
    b.button(text="✈️ Telegram",  callback_data="newcat_plat_telegram")
    b.button(text="📸 Instagram", callback_data="newcat_plat_instagram")
    b.button(text="▶️ Youtube",   callback_data="newcat_plat_youtube")
    b.button(text="🎵 Tik tok",   callback_data="newcat_plat_tiktok")
    b.adjust(2)
    try:
        await cb.message.edit_text("📂 Qaysi platforma uchun bo'lim qo'shmoqchisiz?",
                                   reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer("📂 Qaysi platforma uchun bo'lim qo'shmoqchisiz?",
                                reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("newcat_plat_"))
async def cat_add_platform(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    platform = cb.data.replace("newcat_plat_", "")
    plat_name = PLATFORMS.get(platform, platform)
    await state.update_data(new_cat_platform=platform)
    await state.set_state(AS.add_category)
    await cb.message.answer(
        f"✅ Platforma: {plat_name}\n\n📂 Bo'lim nomini kiriting:",
        reply_markup=cancel_kb()
    )
    await cb.answer()

@dp.message(AS.add_category)
async def do_cat_add(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await cat_menu(msg); return
    data     = await state.get_data()
    platform = data.get("new_cat_platform", "telegram")
    plat_name = PLATFORMS.get(platform, platform)
    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO categories(name,platform) VALUES(?,?)", (msg.text, platform))
    conn.commit(); conn.close()
    await state.clear()
    await msg.answer(f"✅ '{msg.text}' bo'limi {plat_name} uchun qo'shildi!")
    await cat_menu(msg)

# ─── Bo'lim detali ──────────────────────────────────────────
@dp.callback_query(
    F.data.startswith("cat_") &
    ~F.data.startswith("cat_add") &
    ~F.data.startswith("cat_tog_") &
    ~F.data.startswith("cat_del_") &
    ~F.data.startswith("cat_svc_add_") &
    ~F.data.startswith("cat_svcs_")
)
async def cat_detail(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    try:
        cid = int(cb.data.replace("cat_", ""))
    except ValueError:
        await cb.answer(); return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,platform,is_active FROM categories WHERE id=?", (cid,))
    cat  = c.fetchone()
    c.execute("SELECT COUNT(*) FROM services WHERE category_id=?", (cid,))
    ns   = c.fetchone()[0]
    conn.close()
    if not cat: await cb.answer("❌ Topilmadi"); return
    status = "✅ Faol" if cat[3] else "❌ Nofaol"
    plat_name = PLATFORMS.get(cat[2], cat[2])
    b = InlineKeyboardBuilder()
    toggle = "❌ O'chirish" if cat[3] else "✅ Faollashtirish"
    b.button(text=toggle,                  callback_data=f"cat_tog_{cid}")
    b.button(text="➕ Xizmat qo'shish",    callback_data=f"cat_svc_add_{cid}")
    b.button(text="📋 Xizmatlar ro'yhati", callback_data=f"cat_svcs_{cid}")
    b.button(text="🗑 Bo'limni o'chirish",  callback_data=f"cat_del_{cid}")
    b.adjust(2)
    text = (
        f"📂 {cat[1]}\n"
        f"📱 Platforma: {plat_name}\n"
        f"Holat: {status}\n"
        f"Xizmatlar: {ns} ta"
    )
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("cat_tog_"))
async def cat_toggle(cb: types.CallbackQuery):
    cid  = int(cb.data.replace("cat_tog_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT is_active FROM categories WHERE id=?", (cid,))
    cur_val = c.fetchone()[0]
    new_val = 0 if cur_val else 1
    c.execute("UPDATE categories SET is_active=? WHERE id=?", (new_val, cid))
    c.execute("SELECT name,platform FROM categories WHERE id=?", (cid,))
    cat_row = c.fetchone()
    c.execute("SELECT COUNT(*) FROM services WHERE category_id=?", (cid,))
    ns = c.fetchone()[0]
    conn.commit(); conn.close()
    status = "✅ Faol" if new_val else "❌ Nofaol"
    plat_name = PLATFORMS.get(cat_row[1], cat_row[1])
    b = InlineKeyboardBuilder()
    toggle = "❌ O'chirish" if new_val else "✅ Faollashtirish"
    b.button(text=toggle,                  callback_data=f"cat_tog_{cid}")
    b.button(text="➕ Xizmat qo'shish",    callback_data=f"cat_svc_add_{cid}")
    b.button(text="📋 Xizmatlar ro'yhati", callback_data=f"cat_svcs_{cid}")
    b.button(text="🗑 Bo'limni o'chirish",  callback_data=f"cat_del_{cid}")
    b.adjust(2)
    try:
        await cb.message.edit_text(
            f"📂 {cat_row[0]}\n📱 Platforma: {plat_name}\nHolat: {status}\nXizmatlar: {ns} ta",
            reply_markup=b.as_markup()
        )
    except Exception:
        pass
    await cb.answer("✅ O'zgartirildi!")

@dp.callback_query(F.data.startswith("cat_del_"))
async def cat_del(cb: types.CallbackQuery):
    cid  = int(cb.data.replace("cat_del_", ""))
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM categories WHERE id=?", (cid,))
    c.execute("DELETE FROM services WHERE category_id=?", (cid,))
    conn.commit(); conn.close()
    try:
        await cb.message.edit_text("✅ Bo'lim o'chirildi!", reply_markup=None)
    except Exception:
        await cb.message.answer("✅ Bo'lim o'chirildi!")
    await cb.answer()

# ── Xizmat qo'shish ──────────────────────────────────────
@dp.callback_query(F.data.startswith("cat_svc_add_"))
async def svc_add_step1(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    cat_id = int(cb.data.replace("cat_svc_add_", ""))
    conn   = db(); c = conn.cursor()
    c.execute("SELECT id,name FROM apis")
    apis   = c.fetchall(); conn.close()
    if not apis:
        await cb.answer("❌ Avval API qo'shing!", show_alert=True); return
    await state.update_data(new_svc_cat=cat_id)
    b = InlineKeyboardBuilder()
    for aid, aname in apis:
        b.button(text=f"🔑 {aname}", callback_data=f"svc_api_{aid}")
    b.adjust(1)
    try:
        await cb.message.edit_text("🔑 API tanlang:", reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer("🔑 API tanlang:", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("svc_api_"))
async def svc_add_step2(cb: types.CallbackQuery, state: FSMContext):
    api_id = int(cb.data.replace("svc_api_", ""))
    await state.update_data(new_svc_api=api_id)
    await state.set_state(AS.svc_api_id)
    text = (
        "🔢 API xizmat ID sini kiriting:\n\n"
        "💡 Misol: 268, 15, 1024 ...\n"
        "📋 ID ni bilish uchun API panelidan xizmatlar ro'yxatiga qarang."
    )
    try:
        await cb.message.edit_text(text, reply_markup=None)
    except Exception:
        await cb.message.answer(text, reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.svc_api_id)
async def svc_add_step3(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return

    api_service_id = msg.text.strip()
    data = await state.get_data()
    api_id = data["new_svc_api"]

    # API dan xizmat ma'lumotlarini olish
    conn = db(); c = conn.cursor()
    c.execute("SELECT url,api_key FROM apis WHERE id=?", (api_id,))
    api_row = c.fetchone(); conn.close()

    prefill = {"name": f"Xizmat #{api_service_id}", "min": 100, "max": 10000, "price": 0}

    if api_row:
        svcs = await api_services(api_row[0], api_row[1])
        if svcs and isinstance(svcs, list):
            for s in svcs:
                sid = str(s.get("service", s.get("id", "")))
                if sid == str(api_service_id):
                    prefill["name"]  = s.get("name", prefill["name"])
                    prefill["min"]   = int(float(s.get("min", 100)))
                    prefill["max"]   = int(float(s.get("max", 10000)))
                    prefill["price"] = float(s.get("rate", s.get("price", 0)))
                    break

    await state.update_data(new_svc_api_id=api_service_id, prefill=prefill)

    # Oldindan to'ldirilgan ma'lumotlar bilan tasdiqlash
    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash va saqlash", callback_data="svc_confirm_save")
    b.button(text="✏️ Nomni o'zgartirish",   callback_data="svc_edit_name")
    b.adjust(1)

    await msg.answer(
        f"📋 Xizmat ma'lumotlari:\n\n"
        f"🔢 API ID: {api_service_id}\n"
        f"📌 Nomi: {prefill['name']}\n"
        f"💰 Narx (1000x): {prefill['price']:.2f} {cur()}\n"
        f"⬇️ Minimal: {prefill['min']} ta\n"
        f"⬆️ Maksimal: {prefill['max']} ta\n\n"
        f"Saqlaymizmi?",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data == "svc_confirm_save")
async def svc_confirm_save(cb: types.CallbackQuery, state: FSMContext):
    data    = await state.get_data()
    prefill = data.get("prefill", {})
    cat_id  = data["new_svc_cat"]

    conn = db(); c = conn.cursor()
    c.execute("""INSERT INTO services(category_id,api_id,api_service_id,name,min_qty,max_qty,price_per1000)
                 VALUES(?,?,?,?,?,?,?)""",
              (cat_id, data["new_svc_api"], data["new_svc_api_id"],
               prefill.get("name",""), prefill.get("min",100),
               prefill.get("max",10000), prefill.get("price",0)))
    c.execute("SELECT COUNT(*) FROM services WHERE category_id=?", (cat_id,))
    svc_count = c.fetchone()[0]
    c.execute("SELECT name FROM categories WHERE id=?", (cat_id,))
    cat_row = c.fetchone()
    conn.commit(); conn.close()
    cat_name = cat_row[0] if cat_row else "Bo'lim"

    b = InlineKeyboardBuilder()
    b.button(text="➕ Yana xizmat qo'shish", callback_data=f"cat_svc_add_{cat_id}")
    b.button(text="📋 Xizmatlar ro'yhati",   callback_data=f"cat_svcs_{cat_id}")
    b.adjust(2)

    await state.clear()
    try:
        await cb.message.edit_text(
            f"✅ Xizmat saqlandi!\n\n"
            f"📌 {prefill['name']}\n"
            f"💰 {prefill['price']:.2f} {cur()}/1000\n"
            f"📁 {cat_name}  ({svc_count} ta xizmat)",
            reply_markup=b.as_markup()
        )
    except Exception:
        await cb.message.answer(
            f"✅ Xizmat saqlandi!\n\n"
            f"📌 {prefill['name']}\n"
            f"💰 {prefill['price']:.2f} {cur()}/1000\n"
            f"📁 {cat_name}  ({svc_count} ta xizmat)",
            reply_markup=b.as_markup()
        )
    await cb.answer()

@dp.callback_query(F.data == "svc_edit_name")
async def svc_edit_name(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(AS.svc_name)
    try:
        await cb.message.edit_text("📌 Yangi nom kiriting:", reply_markup=None)
    except Exception:
        await cb.message.answer("📌 Yangi nom kiriting:", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.svc_name)
async def svc_add_name(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    data    = await state.get_data()
    prefill = data.get("prefill", {})
    name    = prefill.get("name", "") if msg.text == "/skip" else msg.text
    prefill["name"] = name
    await state.update_data(prefill=prefill)

    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash va saqlash", callback_data="svc_confirm_save")
    b.button(text="✏️ Nomni o'zgartirish",   callback_data="svc_edit_name")
    b.adjust(1)

    cat_id = data.get("new_svc_cat", 0)
    await msg.answer(
        f"📋 Yangilangan ma'lumotlar:\n\n"
        f"📌 Nomi: {prefill['name']}\n"
        f"💰 Narx (1000x): {prefill.get('price',0):.2f} {cur()}\n"
        f"⬇️ Minimal: {prefill.get('min',100)} ta\n"
        f"⬆️ Maksimal: {prefill.get('max',10000)} ta\n\n"
        f"Saqlaymizmi?",
        reply_markup=b.as_markup()
    )

# ── Bo'limdagi xizmatlar ro'yhati ────────────────────────
@dp.callback_query(F.data.startswith("cat_svcs_"))
async def cat_svcs(cb: types.CallbackQuery):
    cid  = int(cb.data.replace("cat_svcs_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,price_per1000,is_active FROM services WHERE category_id=?", (cid,))
    svcs = c.fetchall()
    c.execute("SELECT name FROM categories WHERE id=?", (cid,))
    cat_row = c.fetchone()
    conn.close()
    cat_name = cat_row[0] if cat_row else "Bo'lim"
    if not svcs:
        await cb.answer("❌ Xizmatlar yo'q", show_alert=True); return
    b = InlineKeyboardBuilder()
    for sid, sname, sprice, sact in svcs:
        st = "✅" if sact else "❌"
        b.button(text=f"{st} {sname} — {sprice:.2f} {cur()}", callback_data=f"admin_svc_{sid}")
    b.button(text="➕ Xizmat qo'shish", callback_data=f"cat_svc_add_{cid}")
    b.adjust(1)
    try:
        await cb.message.edit_text(
            f"📋 {cat_name} — xizmatlar ({len(svcs)} ta):",
            reply_markup=b.as_markup()
        )
    except Exception:
        await cb.message.answer(
            f"📋 {cat_name} — xizmatlar ({len(svcs)} ta):",
            reply_markup=b.as_markup()
        )
    await cb.answer()

# ── Barcha xizmatlar ─────────────────────────────────────
@dp.message(F.text == "🛠 Barcha xizmatlar")
async def all_svcs(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("""SELECT s.id,s.name,s.price_per1000,s.is_active,cat.name,cat.platform
                 FROM services s LEFT JOIN categories cat ON s.category_id=cat.id
                 ORDER BY cat.platform, cat.name""")
    svcs = c.fetchall(); conn.close()
    if not svcs: await msg.answer("❌ Xizmatlar yo'q"); return
    b = InlineKeyboardBuilder()
    for sid, sname, sprice, sact, cname, cplat in svcs:
        st = "✅" if sact else "❌"
        plat_icon = {"telegram": "✈️", "instagram": "📸", "youtube": "▶️", "tiktok": "🎵"}.get(cplat, "📁")
        b.button(text=f"{st} {plat_icon} {sname} — {sprice:.2f} {cur()}", callback_data=f"admin_svc_{sid}")
    b.adjust(1)
    await msg.answer(f"📋 Barcha xizmatlar ({len(svcs)} ta):", reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("admin_svc_"))
async def admin_svc_detail(cb: types.CallbackQuery):
    sid  = int(cb.data.replace("admin_svc_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT * FROM services WHERE id=?", (sid,))
    svc  = c.fetchone(); conn.close()
    if not svc: await cb.answer("❌ Topilmadi"); return
    status = "✅ Faol" if svc[8] else "❌ Nofaol"
    b = InlineKeyboardBuilder()
    b.button(text="❌ O'chirish" if svc[8] else "✅ Faollashtirish", callback_data=f"svc_tog_{sid}")
    b.button(text="🗑 O'chirish", callback_data=f"svc_del_{sid}")
    b.adjust(2)
    text = (
        f"🛠 {svc[4]}\n"
        f"Holat: {status}\n"
        f"💰 {svc[7]:.2f} {cur()}/1000\n"
        f"⬇️ Min: {svc[5]} ta  |  ⬆️ Max: {svc[6]} ta\n"
        f"🔢 API Xizmat ID: {svc[3]}"
    )
    try:
        await cb.message.edit_text(text, reply_markup=b.as_markup())
    except Exception:
        await cb.message.answer(text, reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("svc_tog_"))
async def svc_toggle(cb: types.CallbackQuery):
    sid  = int(cb.data.replace("svc_tog_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT is_active FROM services WHERE id=?", (sid,))
    v    = c.fetchone()[0]
    new_v = 0 if v else 1
    c.execute("UPDATE services SET is_active=? WHERE id=?", (new_v, sid))
    c.execute("SELECT * FROM services WHERE id=?", (sid,))
    svc = c.fetchone()
    conn.commit(); conn.close()
    status = "✅ Faol" if new_v else "❌ Nofaol"
    b = InlineKeyboardBuilder()
    b.button(text="❌ O'chirish" if new_v else "✅ Faollashtirish", callback_data=f"svc_tog_{sid}")
    b.button(text="🗑 O'chirish", callback_data=f"svc_del_{sid}")
    b.adjust(2)
    try:
        await cb.message.edit_text(
            f"🛠 {svc[4]}\nHolat: {status}\n"
            f"💰 {svc[7]:.2f} {cur()}/1000\n"
            f"⬇️ Min: {svc[5]} ta  |  ⬆️ Max: {svc[6]} ta\n"
            f"🔢 API Xizmat ID: {svc[3]}",
            reply_markup=b.as_markup()
        )
    except Exception:
        pass
    await cb.answer("✅ O'zgartirildi!")

@dp.callback_query(F.data.startswith("svc_del_"))
async def svc_del(cb: types.CallbackQuery):
    sid  = int(cb.data.replace("svc_del_", ""))
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM services WHERE id=?", (sid,))
    conn.commit(); conn.close()
    try:
        await cb.message.edit_text("✅ Xizmat o'chirildi!", reply_markup=None)
    except Exception:
        await cb.message.answer("✅ Xizmat o'chirildi!")
    await cb.answer()

# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════
async def main():
    init_db()
    logger.info("✅ SMM Bot ishga tushdi!")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
