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
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
#  ⚙️  SOZLAMALAR  –  shu qatorlarni o'zgartiring
# ============================================================
BOT_TOKEN  = "8648355597:AAF_eM_GHY3SmBpHB4VSuK93O-o_pUXdgFg"       # @BotFather dan oling
ADMIN_IDS  = [8537782289]                 # O'z Telegram ID-ingizni yozing
# ============================================================

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
        ("uzcart_active",  "0"),
    ]
    for k, v in defaults:
        c.execute("INSERT OR IGNORE INTO settings VALUES (?,?)", (k, v))

    c.execute("INSERT OR IGNORE INTO guides(id,title,content) VALUES(1,?,?)", (
        "Botdan foydalanish qo'llanmasi",
        "1. Buyurtma berish uchun 'Buyurtma berish' tugmasini bosing\n"
        "2. Bo'limni tanlang → Xizmatni tanlang\n"
        "3. Link va miqdorni kiriting\n"
        "4. Tasdiqlang – pul hisobingizdan yechiladi"
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

# ─────────────────────────────────────────────────────────────
#  STATES
# ─────────────────────────────────────────────────────────────
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
    # Manual payment
    mpay_name          = State()
    mpay_card          = State()
    mpay_expiry        = State()
    mpay_holder        = State()
    # Bot account
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

# ─────────────────────────────────────────────────────────────
#  API HELPERS
# ─────────────────────────────────────────────────────────────
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
#  BOT
# ─────────────────────────────────────────────────────────────
bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

# ── subscription check ──────────────────────────────────────
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
#  /start
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

    if not await check_sub(uid):
        await msg.answer("⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:", reply_markup=await sub_kb())
        return

    await msg.answer("🖥 Asosiy menyudasiz!", reply_markup=main_kb(uid in ADMIN_IDS))

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(cb: types.CallbackQuery):
    if await check_sub(cb.from_user.id):
        await cb.message.answer("✅ Tasdiqlandi!\n🖥 Asosiy menyudasiz!", reply_markup=main_kb(cb.from_user.id in ADMIN_IDS))
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
        f"💵 Balansingiz: {u[3]:.0f} {cur()}\n"
        f"📊 Buyurtmalaringiz: {orders_count(u[0])} ta\n"
        f"👥 Referallaringiz: {u[5]} ta\n"
        f"💰 Kiritgan pullaringiz: {u[6]:.0f} {cur()}",
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
    pid = int(cb.data.replace("pay_manual_",""))
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

@dp.callback_query(F.data.startswith("pay_"))
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
    for s in ("completed","cancelled","pending","processing","partial"):
        c.execute("SELECT COUNT(*) FROM orders WHERE user_id=? AND status=?", (uid, s))
        st[s] = c.fetchone()[0]
    conn.close()
    await msg.answer(
        f"📈 Buyurtmalar: {total} ta\n\n"
        f"✅ Bajarilganlar: {st['completed']} ta\n"
        f"🚫 Bekor qilinganlar: {st['cancelled']} ta\n"
        f"⏳ Bajarilayotganlar: {st['pending']} ta\n"
        f"🔄 Jarayondagilar: {st['processing']} ta\n"
        f"♻️ Qayta ishlanganlar: {st['partial']} ta"
    )

# ═══════════════════════════════════════════════════════════
#  USER — Buyurtma berish  ← TUZATILGAN QISM
# ═══════════════════════════════════════════════════════════
@dp.message(F.text == "Buyurtma berish")
async def place_order(msg: types.Message, state: FSMContext):
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name FROM categories WHERE is_active=1")
    cats = c.fetchall(); conn.close()
    if not cats:
        await msg.answer("❌ Hozirda xizmatlar mavjud emas."); return

    # Bo'limlarni 2 ta qatorda, emojisiz ko'rsatish
    b = InlineKeyboardBuilder()
    for cid, name in cats:
        b.button(text=name, callback_data=f"order_cat_{cid}")
    b.button(text="◀️ Orqaga", callback_data="order_back_main")
    b.adjust(2)

    await state.set_state(US.select_category)
    await state.update_data(cats={str(cid): name for cid, name in cats})

    # Reply keyboard olib tashlash va inline ko'rsatish
    await msg.answer(".", reply_markup=ReplyKeyboardRemove())
    await msg.answer("📁 Bo'limni tanlang:", reply_markup=b.as_markup())

@dp.callback_query(F.data == "order_back_main")
async def order_back_main(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.answer("🖥 Asosiy menyudasiz!", reply_markup=main_kb(cb.from_user.id in ADMIN_IDS))
    await cb.answer()

@dp.callback_query(F.data.startswith("order_cat_"))
async def order_cat_selected(cb: types.CallbackQuery, state: FSMContext):
    cat_id = int(cb.data.replace("order_cat_", ""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,price_per1000,min_qty,max_qty FROM services WHERE category_id=? AND is_active=1", (cat_id,))
    svcs = c.fetchall()
    c.execute("SELECT name FROM categories WHERE id=?", (cat_id,))
    cat_name_row = c.fetchone()
    conn.close()

    cat_name = cat_name_row[0] if cat_name_row else "Bo'lim"

    if not svcs:
        await cb.answer("❌ Bu bo'limda xizmatlar yo'q.", show_alert=True); return

    lines = f"📋 {cat_name} — xizmatlarni tanlang:\n\n"
    for sid, sname, price, mn, mx in svcs:
        lines += f"• {sname}\n  💰 {price:.0f} {cur()}/1000 | Min:{mn}–{mx}\n\n"

    b = InlineKeyboardBuilder()
    for sid, sname, price, mn, mx in svcs:
        b.button(text=sname, callback_data=f"sel_svc_{sid}")
    b.button(text="◀️ Orqaga", callback_data="back_to_cats")
    b.adjust(2)

    await state.update_data(
        svcs={sid: (sid, sname, price, mn, mx) for sid, sname, price, mn, mx in svcs},
        last_cat_id=cat_id
    )
    await state.set_state(US.select_service)
    await cb.message.answer(lines, reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data == "back_to_cats")
async def back_to_cats(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name FROM categories WHERE is_active=1")
    cats = c.fetchall(); conn.close()
    if not cats:
        await cb.message.answer("❌ Hozirda xizmatlar mavjud emas."); return

    b = InlineKeyboardBuilder()
    for cid, name in cats:
        b.button(text=name, callback_data=f"order_cat_{cid}")
    b.button(text="◀️ Orqaga", callback_data="order_back_main")
    b.adjust(2)

    await state.set_state(US.select_category)
    await state.update_data(cats={str(cid): name for cid, name in cats})
    await cb.message.answer("📁 Bo'limni tanlang:", reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("sel_svc_"))
async def sel_svc(cb: types.CallbackQuery, state: FSMContext):
    svc_id = int(cb.data.replace("sel_svc_",""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT * FROM services WHERE id=?", (svc_id,))
    svc = c.fetchone(); conn.close()
    if not svc:
        await cb.answer("❌ Xizmat topilmadi", show_alert=True); return
    await state.update_data(svc=svc)
    await state.set_state(US.enter_link)
    await cb.message.answer(
        f"📌 {svc[4]}\n💰 {svc[7]:.0f} {cur()}/1000\nMin:{svc[5]} Max:{svc[6]}\n\n🔗 Linkni kiriting:",
        reply_markup=cancel_kb()
    )
    await cb.answer()

@dp.message(US.enter_link)
async def enter_link(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)); return
    if not msg.text.startswith("http"):
        await msg.answer("❌ Link https:// bilan boshlanishi kerak"); return
    await state.update_data(link=msg.text)
    data = await state.get_data()
    svc = data["svc"]
    await state.set_state(US.enter_quantity)
    await msg.answer(f"📊 Miqdorni kiriting (Min:{svc[5]}, Max:{svc[6]}):")

@dp.message(US.enter_quantity)
async def enter_qty(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("Bekor qilindi", reply_markup=main_kb(msg.from_user.id in ADMIN_IDS)); return
    data = await state.get_data()
    svc  = data["svc"]
    try:
        qty = int(msg.text)
        assert svc[5] <= qty <= svc[6]
    except:
        await msg.answer(f"❌ Miqdor {svc[5]}–{svc[6]} orasida bo'lishi kerak"); return
    amount = (qty / 1000) * svc[7]
    u      = get_user(msg.from_user.id)
    text   = (
        f"📋 Buyurtma:\n📌 {svc[4]}\n🔗 {data['link']}\n"
        f"📊 Miqdor: {qty}\n💰 {amount:.0f} {cur()}\n"
        f"💵 Balans: {u[3]:.0f} {cur()}\n\n"
    )
    if u[3] < amount:
        text += f"❌ Balans yetarli emas! Yetishmaydi: {amount-u[3]:.0f} {cur()}"
        await msg.answer(text, reply_markup=main_kb(msg.from_user.id in ADMIN_IDS))
        await state.clear(); return
    text += "✅ Tasdiqlaysizmi?"
    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash",   callback_data="order_yes")
    b.button(text="❌ Bekor qilish", callback_data="order_no")
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
    api_error    = None
    if svc[2]:
        c.execute("SELECT url,api_key FROM apis WHERE id=?", (svc[2],))
        api = c.fetchone()
        if api:
            res = await api_order(api[0], api[1], svc[3], link, qty)
            if res and "order" in res:
                api_order_id = str(res["order"])
            elif res and "error" in res:
                api_error = res["error"]

    c.execute("INSERT INTO orders(user_id,service_id,api_order_id,link,quantity,amount,status) VALUES(?,?,?,?,?,?,?)",
              (uid, svc[0], api_order_id, link, qty, amount, "pending"))
    order_id = c.lastrowid
    c.execute("INSERT INTO transactions(user_id,amount,type,description) VALUES(?,?,?,?)",
              (uid, -amount, "order", f"Buyurtma #{order_id}"))
    conn.commit(); conn.close()

    # Yangi balansni olish
    u = get_user(uid)
    new_balance = u[3] if u else 0

    result_text = (
        f"✅ Buyurtma muvaffaqiyatli yuborildi!\n\n"
        f"🆔 Buyurtma raqami: #{order_id}\n"
        f"📌 Xizmat: {svc[4]}\n"
        f"🔢 Xizmat ID: {svc[3]}\n"
        f"📊 Miqdor: {qty}\n"
        f"🔗 Link: {link}\n"
        f"💰 Yechildi: {amount:.0f} {cur()}\n"
        f"💵 Qolgan balans: {new_balance:.0f} {cur()}\n"
    )
    if api_order_id:
        result_text += f"📡 API buyurtma ID: {api_order_id}\n"
    if api_error:
        result_text += f"⚠️ API xato: {api_error}\n"
    result_text += f"\n⏳ Xizmat bajarilmoqda..."

    await state.clear()
    await cb.message.answer(result_text, reply_markup=main_kb(uid in ADMIN_IDS))
    await cb.answer()

@dp.callback_query(F.data == "order_no")
async def order_cancel(cb: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.answer("❌ Bekor qilindi.", reply_markup=main_kb(cb.from_user.id in ADMIN_IDS))
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
        except: pass
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
#  BACK / orqaga
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
    await msg.answer("Admin paneliga hush kelibsiz !", reply_markup=admin_kb())

# ── Asosiy sozlamalar ─────────────────────────────────────
@dp.message(F.text == "⚙️ Asosiy sozlamalar")
async def admin_settings(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    rb   = get_setting("referral_bonus","2500")
    cv   = get_setting("currency","Sum")
    st_s = "✅ Faol" if get_setting("service_time","1")=="1" else "❌ Nofaol"
    st_p = "✅ Faol" if get_setting("premium_emoji","1")=="1" else "❌ Nofaol"
    b = InlineKeyboardBuilder()
    b.button(text="💰 Referal o'zgartirish",        callback_data="set_ref")
    b.button(text="💱 Valyuta o'zgartirish",         callback_data="set_cur")
    b.button(text=f"🕐 Xizmat vaqti: {st_s}",       callback_data="tog_svctime")
    b.button(text=f"✨ Premium emoji: {st_p}",       callback_data="tog_premium")
    b.adjust(1)
    await msg.answer(
        f"⚙️ <b>Asosiy sozlamalar:</b>\n\n"
        f"♦️ Referal: {rb} {cv}\n"
        f"♦️ Valyuta: {cv}\n"
        f"♦️ Xizmat bajarilish vaqti: {st_s}\n"
        f"♦️ Premium emoji: {st_p}\n\n"
        f"<i>Premium emoji faqat Telegramda premium obunasi bor foydalanuvchi botlarida ishlaydi.</i>",
        parse_mode="HTML",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data == "set_ref")
async def cb_set_ref(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.set_referral)
    await cb.message.answer(f"💰 Yangi referal miqdorini kiriting ({cur()}):", reply_markup=cancel_kb())
    await cb.answer()

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
    v = "0" if get_setting("service_time","1")=="1" else "1"
    set_setting("service_time", v)
    await cb.answer("✅ O'zgartirildi!")
    rb   = get_setting("referral_bonus","2500")
    cv   = get_setting("currency","Sum")
    st_s = "✅ Faol" if v=="1" else "❌ Nofaol"
    st_p = "✅ Faol" if get_setting("premium_emoji","1")=="1" else "❌ Nofaol"
    b = InlineKeyboardBuilder()
    b.button(text="💰 Referal o'zgartirish",        callback_data="set_ref")
    b.button(text="💱 Valyuta o'zgartirish",         callback_data="set_cur")
    b.button(text=f"🕐 Xizmat vaqti: {st_s}",       callback_data="tog_svctime")
    b.button(text=f"✨ Premium emoji: {st_p}",       callback_data="tog_premium")
    b.adjust(1)
    try:
        await cb.message.edit_text(
            f"⚙️ <b>Asosiy sozlamalar:</b>\n\n"
            f"♦️ Referal: {rb} {cv}\n♦️ Valyuta: {cv}\n"
            f"♦️ Xizmat bajarilish vaqti: {st_s}\n♦️ Premium emoji: {st_p}\n\n"
            f"<i>Premium emoji faqat Telegramda premium obunasi bor foydalanuvchi botlarida ishlaydi.</i>",
            parse_mode="HTML", reply_markup=b.as_markup()
        )
    except: pass

@dp.callback_query(F.data == "tog_premium")
async def cb_tog_premium(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    v = "0" if get_setting("premium_emoji","1")=="1" else "1"
    set_setting("premium_emoji", v)
    await cb.answer("✅ O'zgartirildi!")
    rb   = get_setting("referral_bonus","2500")
    cv   = get_setting("currency","Sum")
    st_s = "✅ Faol" if get_setting("service_time","1")=="1" else "❌ Nofaol"
    st_p = "✅ Faol" if v=="1" else "❌ Nofaol"
    b = InlineKeyboardBuilder()
    b.button(text="💰 Referal o'zgartirish",        callback_data="set_ref")
    b.button(text="💱 Valyuta o'zgartirish",         callback_data="set_cur")
    b.button(text=f"🕐 Xizmat vaqti: {st_s}",       callback_data="tog_svctime")
    b.button(text=f"✨ Premium emoji: {st_p}",       callback_data="tog_premium")
    b.adjust(1)
    try:
        await cb.message.edit_text(
            f"⚙️ <b>Asosiy sozlamalar:</b>\n\n"
            f"♦️ Referal: {rb} {cv}\n♦️ Valyuta: {cv}\n"
            f"♦️ Xizmat bajarilish vaqti: {st_s}\n♦️ Premium emoji: {st_p}\n\n"
            f"<i>Premium emoji faqat Telegramda premium obunasi bor foydalanuvchi botlarida ishlaydi.</i>",
            parse_mode="HTML", reply_markup=b.as_markup()
        )
    except: pass

# ── Bot hisobi ────────────────────────────────────────────
@dp.message(AS.set_referral)
async def do_chg_ref(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    try:
        v = float(msg.text); set_setting("referral_bonus", v)
        await state.clear()
        await msg.answer(f"✅ Referal <b>{v:.0f}</b> {cur()} ga o'zgartirildi!", parse_mode="HTML",
                         reply_markup=admin_kb())
    except: await msg.answer("❌ Noto'g'ri miqdor, raqam kiriting:")

@dp.message(F.text == "🤖 Bot hisobi")
async def bot_account_menu(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS: return
    saved_token = get_setting("ext_bot_token", "")
    saved_url   = get_setting("ext_bot_url",   "")
    b = InlineKeyboardBuilder()
    if saved_token:
        b.button(text="🔄 Yangilash",       callback_data="bot_acc_update")
        b.button(text="💰 Balansni ko'rish", callback_data="bot_acc_balance")
        b.button(text="🗑 O'chirish",        callback_data="bot_acc_delete")
        b.adjust(2)
        await msg.answer(
            f"🤖 Bot hisobi:\n\n"
            f"🔑 Token: {saved_token[:20]}...\n"
            f"🌐 URL: {saved_url or 'Kiritilmagan'}",
            reply_markup=b.as_markup()
        )
    else:
        b.button(text="➕ Bot API qo'shish", callback_data="bot_acc_add")
        b.adjust(1)
        await msg.answer("🤖 Bot hisobi ulangan emas.\nBoshqa botni API tokenini ulashing:", reply_markup=b.as_markup())

@dp.callback_query(F.data.in_({"bot_acc_add", "bot_acc_update"}))
async def bot_acc_add(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.bot_api_token)
    await cb.message.answer("🔑 Botning API tokenini kiriting\n(masalan: 123456:ABCdef...)", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.bot_api_token)
async def bot_acc_token(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    await state.update_data(ext_token=msg.text.strip())
    await state.set_state(AS.bot_api_url)
    await msg.answer("🌐 SMM panel API URL ni kiriting\n(masalan: https://saleseen.uz/api/v2)\n\nAgar yo'q bo'lsa /skip yozing:")

@dp.message(AS.bot_api_url)
async def bot_acc_url(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    data = await state.get_data()
    token = data["ext_token"]
    url   = "" if msg.text.strip() == "/skip" else msg.text.strip()

    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.telegram.org/bot{token}/getMe", timeout=aiohttp.ClientTimeout(total=8)) as r:
                res = await r.json()
        if not res.get("ok"):
            await msg.answer(f"❌ Token noto'g'ri yoki bot topilmadi!\nXato: {res.get('description','')}"); await state.clear(); return
        bot_info = res["result"]
    except Exception as e:
        await msg.answer(f"❌ Ulanib bo'lmadi: {e}"); await state.clear(); return

    set_setting("ext_bot_token", token)
    set_setting("ext_bot_url",   url)
    await state.clear()
    await msg.answer(
        f"✅ Bot ulandi!\n\n"
        f"🤖 @{bot_info.get('username','?')} — {bot_info.get('first_name','')}\n"
        f"🆔 ID: {bot_info.get('id','?')}\n"
        f"🌐 URL: {url or 'Kiritilmagan'}",
        reply_markup=admin_kb()
    )

@dp.callback_query(F.data == "bot_acc_balance")
async def bot_acc_balance(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    token = get_setting("ext_bot_token","")
    url   = get_setting("ext_bot_url","")
    if not token:
        await cb.answer("❌ Bot ulanmagan!", show_alert=True); return
    await cb.answer("⏳ Tekshirilmoqda...")

    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.telegram.org/bot{token}/getMe", timeout=aiohttp.ClientTimeout(total=8)) as r:
                bot_res = await r.json()
        bot_name = bot_res.get("result",{}).get("username","?") if bot_res.get("ok") else "Noma'lum"
    except:
        bot_name = "Noma'lum"

    balance_text = "—"
    if url:
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(url, data={"key": token, "action": "balance"}, timeout=aiohttp.ClientTimeout(total=10)) as r:
                    bal_res = await r.json(content_type=None)
            balance_text = f"{bal_res.get('balance','?')} {bal_res.get('currency','')}"
        except Exception as e:
            balance_text = f"Xato: {e}"

    await cb.message.answer(
        f"🤖 @{bot_name}\n"
        f"💰 Panel balansi: {balance_text}\n"
        f"🌐 URL: {url or 'Kiritilmagan'}"
    )

@dp.callback_query(F.data == "bot_acc_delete")
async def bot_acc_delete(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    set_setting("ext_bot_token", "")
    set_setting("ext_bot_url",   "")
    await cb.message.answer("✅ Bot hisobi o'chirildi!")
    await cb.answer()

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
        f"📊 Statistika\n• Obunachilar soni: {total} ta\n• Faol obunachilar: {total} ta\n• Tark etganlar: 0 ta\n\n"
        f"📈 Qo'shilish\n• Oxirgi 24 soat: +{h24}\n• Oxirgi 7 kun: +{d7}\n• Oxirgi 30 kun: +{d30}\n\n"
        f"📊 Faollik\n• 24 soatda faol: {h24} ta\n• 7 kun faol: {d7} ta\n• 30 kun faol: {d30} ta\n\n"
        f"💵 Pullar Statistikasi\n• Puli borlar: {wb} ta\n• Jami pullar: {tm:.0f} {cur()}\n\n"
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
        text += f"{i}. {name or uid} — {bal:.0f} {cur()}\n"
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
    b.button(text="💬 Oddiy xabar (1 foydalanuvchi)", callback_data="bc_single")
    b.button(text="📨 Forward (barchaga)",            callback_data="bc_forward_all")
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
    await cb.message.answer("🆔 Foydalanuvchi ID sini kiriting:", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.broadcast_uid)
async def bc_single_uid(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    try:
        uid = int(msg.text)
    except:
        await msg.answer("❌ Noto'g'ri ID, raqam kiriting:"); return
    await state.update_data(single_uid=uid)
    await state.set_state(AS.broadcast_uid_msg)
    await msg.answer(f"✅ ID: {uid}\n\n📝 Xabar matnini kiriting:", reply_markup=cancel_kb())

@dp.message(AS.broadcast_uid_msg)
async def bc_single_send(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    data = await state.get_data()
    uid  = data["single_uid"]
    try:
        await bot.send_message(uid, msg.text)
        await msg.answer(f"✅ {uid} ga xabar yuborildi!", reply_markup=admin_kb())
    except Exception as e:
        await msg.answer(f"❌ Xabar yuborib bo'lmadi: {e}", reply_markup=admin_kb())
    await state.clear()

@dp.callback_query(F.data.startswith("bc_"))
async def bc_type(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.update_data(bc_type=cb.data.replace("bc_",""))
    await state.set_state(AS.broadcast_msg)
    await cb.message.answer("📝 Xabarni yuboring:", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.broadcast_msg)
async def do_broadcast(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    data = await state.get_data()
    btype = data.get("bc_type","regular")
    conn  = db(); c = conn.cursor()
    c.execute("SELECT user_id FROM users"); users = c.fetchall(); conn.close()
    sent = failed = 0
    for (uid,) in users:
        try:
            if btype == "forward": await msg.forward(uid)
            else: await bot.send_message(uid, msg.text)
            sent += 1
        except: failed += 1
        await asyncio.sleep(0.05)
    await state.clear()
    await msg.answer(f"✅ Yuborildi!\n✅ Muvaffaqiyatli: {sent}\n❌ Xato: {failed}", reply_markup=admin_kb())

# ── Majbur obuna kanallar ──────────────────────────────────
@dp.message(F.text == "🔒 Majbur obuna kanallar")
async def channels_menu(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM channels"); n = c.fetchone()[0]; conn.close()
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Kanal qo'shish")],
        [KeyboardButton(text="📋 Ro'yxatni ko'rish")],
        [KeyboardButton(text="🗑 Kanalni o'chirish")],
        [KeyboardButton(text="◀️ Orqaga")],
    ], resize_keyboard=True)
    await msg.answer(f"🔒 Majburiy obuna kanallar: {n} ta", reply_markup=kb)

@dp.message(F.text == "➕ Kanal qo'shish")
async def add_ch(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.add_channel)
    await msg.answer(
        "📢 Formatda yuboring:\n@channel_id|Kanal nomi|https://t.me/channel",
        reply_markup=cancel_kb()
    )

@dp.message(AS.add_channel)
async def do_add_ch(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await channels_menu(msg); return
    try:
        parts = msg.text.split("|")
        cid, cname, clink = parts[0].strip(), parts[1].strip(), parts[2].strip()
        conn = db(); c = conn.cursor()
        c.execute("INSERT INTO channels(channel_id,channel_name,channel_link) VALUES(?,?,?)", (cid,cname,clink))
        conn.commit(); conn.close()
        await state.clear(); await msg.answer(f"✅ {cname} qo'shildi!")
        await channels_menu(msg)
    except: await msg.answer("❌ Noto'g'ri format")

@dp.message(F.text == "📋 Ro'yxatni ko'rish")
async def list_chs(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,channel_name,channel_id FROM channels")
    rows = c.fetchall(); conn.close()
    if not rows: await msg.answer("❌ Kanallar yo'q"); return
    text = "📋 Kanallar:\n\n"
    for row in rows: text += f"{row[0]}. {row[1]} ({row[2]})\n"
    await msg.answer(text)

@dp.message(F.text == "🗑 Kanalni o'chirish")
async def del_ch_menu(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,channel_name FROM channels")
    rows = c.fetchall(); conn.close()
    if not rows: await msg.answer("❌ Kanallar yo'q"); return
    b = InlineKeyboardBuilder()
    for rid, rname in rows:
        b.button(text=f"🗑 {rname}", callback_data=f"del_ch_{rid}")
    b.adjust(1)
    await msg.answer("O'chirish uchun tanlang:", reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("del_ch_"))
async def del_ch(cb: types.CallbackQuery):
    cid = int(cb.data.replace("del_ch_",""))
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM channels WHERE id=?", (cid,))
    conn.commit(); conn.close()
    await cb.message.answer("✅ Kanal o'chirildi!"); await cb.answer()

# ── To'lov tizimlar ────────────────────────────────────────
@dp.message(F.text == "💳 To'lov tizimlar")
async def pay_menu(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⚡ Avtomatik to'lov tizimlari")],
        [KeyboardButton(text="📝 Oddiy to'lov tizimlari")],
        [KeyboardButton(text="◀️ Orqaga")],
    ], resize_keyboard=True)
    await msg.answer("⚙️ To'lov tizim sozlamalarisiz:", reply_markup=kb)

@dp.message(F.text == "⚡ Avtomatik to'lov tizimlari")
async def auto_pay(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    p = "✅" if get_setting("payme_active")=="1" else "❌"
    cl= "✅" if get_setting("click_active")=="1" else "❌"
    b = InlineKeyboardBuilder()
    b.button(text=f"{p} Payme",  callback_data="tg_payme")
    b.button(text=f"{cl} Click", callback_data="tg_click")
    b.adjust(1)
    await msg.answer("⚡ Avtomatik to'lov tizimlari:", reply_markup=b.as_markup())

@dp.message(F.text == "📝 Oddiy to'lov tizimlari")
async def manual_pay(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,card_number,card_holder FROM manual_payments WHERE is_active=1")
    pays = c.fetchall(); conn.close()
    b = InlineKeyboardBuilder()
    for pid, pname, pcard, pholder in pays:
        b.button(text=f"💳 {pname} — {pcard}", callback_data=f"mpay_del_{pid}")
    b.button(text="➕ To'lov tizimi qo'shish", callback_data="mpay_add")
    b.adjust(1)
    text = f"📝 Oddiy to'lov tizimlari: {len(pays)} ta\n\n"
    for pid, pname, pcard, pholder in pays:
        text += f"• {pname}: {pcard} ({pholder})\n"
    await msg.answer(text or "📝 Oddiy to'lov tizimlari:", reply_markup=b.as_markup())

@dp.callback_query(F.data == "mpay_add")
async def mpay_add_start(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.mpay_name)
    await cb.message.answer("💳 To'lov tizimi nomini kiriting:\n(masalan: Humo, Uzcard, Visa)", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.mpay_name)
async def mpay_name_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    await state.update_data(mpay_name=msg.text)
    await state.set_state(AS.mpay_card)
    await msg.answer("💳 Karta raqamini kiriting:\n(masalan: 8600 1234 5678 9012)")

@dp.message(AS.mpay_card)
async def mpay_card_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    await state.update_data(mpay_card=msg.text.strip())
    await state.set_state(AS.mpay_expiry)
    await msg.answer("📅 Karta muddatini kiriting:\n(masalan: 12/27)")

@dp.message(AS.mpay_expiry)
async def mpay_expiry_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    await state.update_data(mpay_expiry=msg.text.strip())
    await state.set_state(AS.mpay_holder)
    await msg.answer("👤 Karta egasining to'liq ism-familiyasini kiriting:\n(masalan: Abdullayev Jahongir)")

@dp.message(AS.mpay_holder)
async def mpay_holder_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    data = await state.get_data()
    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO manual_payments(name,card_number,card_expiry,card_holder) VALUES(?,?,?,?)",
              (data["mpay_name"], data["mpay_card"], data["mpay_expiry"], msg.text.strip()))
    conn.commit(); conn.close()
    await state.clear()
    await msg.answer(
        f"✅ To'lov tizimi qo'shildi!\n\n"
        f"💳 Nomi: {data['mpay_name']}\n"
        f"🔢 Karta: {data['mpay_card']}\n"
        f"📅 Muddat: {data['mpay_expiry']}\n"
        f"👤 Egasi: {msg.text.strip()}",
        reply_markup=admin_kb()
    )

@dp.callback_query(F.data.startswith("mpay_del_"))
async def mpay_del(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    pid = int(cb.data.replace("mpay_del_",""))
    b = InlineKeyboardBuilder()
    b.button(text="🗑 Ha, o'chirish", callback_data=f"mpay_confirm_del_{pid}")
    b.button(text="❌ Bekor",         callback_data="mpay_cancel")
    b.adjust(2)
    await cb.message.answer("⚠️ Bu to'lov tizimini o'chirmoqchimisiz?", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("mpay_confirm_del_"))
async def mpay_confirm_del(cb: types.CallbackQuery):
    pid = int(cb.data.replace("mpay_confirm_del_",""))
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM manual_payments WHERE id=?", (pid,))
    conn.commit(); conn.close()
    await cb.message.answer("✅ To'lov tizimi o'chirildi!"); await cb.answer()

@dp.callback_query(F.data == "mpay_cancel")
async def mpay_cancel(cb: types.CallbackQuery):
    await cb.answer("Bekor qilindi")

@dp.callback_query(F.data.startswith("tg_"))
async def toggle_pay(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    method = cb.data.replace("tg_","")
    key    = f"{method}_active"
    v      = "0" if get_setting(key)=="1" else "1"
    set_setting(key, v)
    s = "faollashtirildi" if v=="1" else "o'chirildi"
    await cb.answer(f"✅ {method.capitalize()} {s}!")

# ── API ────────────────────────────────────────────────────
@dp.message(F.text == "🔑 API")
async def api_menu(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,price_per1000 FROM apis")
    apis = c.fetchall(); conn.close()
    text = f"🔑 API'lar ro'yhati: {len(apis)} ta\n\n"
    for i,(aid,aname,apr) in enumerate(apis, 1):
        text += f"{i}. {aname} — {apr:.0f} {cur()}\n"
    b = InlineKeyboardBuilder()
    for aid, aname, _ in apis:
        b.button(text=f"⚙️ {aname}", callback_data=f"api_det_{aid}")
    b.button(text="➕ API qo'shish", callback_data="api_add")
    b.adjust(1)
    await msg.answer(text, reply_markup=b.as_markup())

@dp.callback_query(F.data == "api_add")
async def add_api(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.api_url)
    await cb.message.answer(
        "🌐 <b>API manzilini kiriting:</b>\n\n"
        "Namuna: https://capitalsmmapi.uz/api/v2",
        reply_markup=cancel_kb(),
        parse_mode="HTML"
    )
    await cb.answer()

@dp.message(AS.api_url)
async def api_url_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await api_menu(msg); return
    url = msg.text.strip()
    await state.update_data(api_url=url)
    await state.set_state(AS.api_key)
    await msg.answer(
        f"❗️ <a href='{url}'>{url}</a> muvaffaqiyatli qabul qilindi!\n\n"
        f"🔑 <b>API kalitini kiriting:</b>",
        parse_mode="HTML",
        reply_markup=cancel_kb()
    )

@dp.message(AS.api_key)
async def api_key_h(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await api_menu(msg); return
    api_key = msg.text.strip()
    data    = await state.get_data()
    url     = data["api_url"]

    try:
        from urllib.parse import urlparse
        auto_name = urlparse(url).netloc.replace("www.", "")
    except:
        auto_name = url[:30]

    balance, api_cur = await api_balance(url, api_key)

    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO apis(name,url,api_key,price_per1000) VALUES(?,?,?,?)",
              (auto_name, url, api_key, 0))
    conn.commit(); conn.close()
    await state.clear()

    if balance is not None:
        bal_text = f"\n\n💰 <b>Balans:</b> {balance:.2f} {api_cur}"
    else:
        bal_text = ""

    await msg.answer(
        f"✅ <b>API muvaffaqiyatli qo'shildi!</b>{bal_text}",
        parse_mode="HTML",
        reply_markup=admin_kb()
    )

@dp.callback_query(F.data.startswith("api_det_"))
async def api_detail(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    aid  = int(cb.data.replace("api_det_",""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT * FROM apis WHERE id=?", (aid,))
    api  = c.fetchone(); conn.close()
    if not api: await cb.answer("❌ Topilmadi"); return
    await cb.answer("⏳ Balans tekshirilmoqda...")
    balance, api_cur = await api_balance(api[2], api[3])
    bal_text = f"\n💵 Balans: {balance:.2f} {api_cur}" if balance is not None else "\n💵 Balans: aniqlanmadi"
    b = InlineKeyboardBuilder()
    b.button(text="📋 Xizmatlarni yuklash", callback_data=f"api_fetch_{aid}")
    b.button(text="🗑 O'chirish",            callback_data=f"api_del_{aid}")
    b.adjust(1)
    await cb.message.answer(
        f"🔑 {api[1]}\n🌐 {api[2]}\n🔑 Key: {api[3][:12]}...{bal_text}",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data.startswith("api_fetch_"))
async def api_fetch(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    aid  = int(cb.data.replace("api_fetch_",""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT url,api_key FROM apis WHERE id=?", (aid,))
    api  = c.fetchone(); conn.close()
    await cb.answer("⏳ Yuklanmoqda...")
    svcs = await api_services(api[0], api[1])
    if not svcs:
        await cb.message.answer("❌ API dan yuklab bo'lmadi"); return
    text = f"📋 API xizmatlari ({len(svcs)} ta):\n\n"
    for s in svcs[:30]:
        sid  = s.get("service", s.get("id",""))
        name = s.get("name","")
        rate = s.get("rate","")
        text += f"ID:{sid} | {name[:40]} | {rate}\n"
    if len(svcs) > 30:
        text += f"\n... yana {len(svcs)-30} ta"
    await cb.message.answer(text[:4096])

@dp.callback_query(F.data.startswith("api_del_"))
async def api_del(cb: types.CallbackQuery):
    aid  = int(cb.data.replace("api_del_",""))
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM apis WHERE id=?", (aid,))
    conn.commit(); conn.close()
    await cb.message.answer("✅ API o'chirildi!"); await cb.answer()

# ── Foydalanuvchini boshqarish ─────────────────────────────
@dp.message(F.text == "👩‍💻 Foydalanuvchini boshqarish")
async def user_mgmt(msg: types.Message, state: FSMContext):
    if msg.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.user_id_input)
    await msg.answer("🆔 Foydalanuvchining ID raqamini yuboring:", reply_markup=cancel_kb())

@dp.message(AS.user_id_input)
async def get_user_info(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    try: uid = int(msg.text)
    except: await msg.answer("❌ Noto'g'ri ID"); return
    u = get_user(uid)
    if not u: await msg.answer("❌ Foydalanuvchi topilmadi"); return
    b = InlineKeyboardBuilder()
    b.button(text="➕ Balans qo'shish", callback_data=f"uadd_{uid}")
    b.button(text="➖ Balans ayirish",  callback_data=f"usub_{uid}")
    b.button(text="📨 Xabar yuborish",  callback_data=f"umsg_{uid}")
    b.adjust(2)
    await state.clear()
    await msg.answer(
        f"👤 {u[2]}\n🆔 {u[0]}\n💵 {u[3]:.0f} {cur()}\n"
        f"📊 Buyurtmalar: {orders_count(uid)}\n👥 Referallar: {u[5]}",
        reply_markup=b.as_markup()
    )

@dp.callback_query(F.data.startswith("uadd_"))
async def u_add(cb: types.CallbackQuery, state: FSMContext):
    uid = int(cb.data.replace("uadd_",""))
    await state.update_data(target_uid=uid, bal_action="add")
    await state.set_state(AS.balance_amount)
    await cb.message.answer("💰 Qo'shmoqchi bo'lgan miqdor:", reply_markup=cancel_kb())
    await cb.answer()

@dp.callback_query(F.data.startswith("usub_"))
async def u_sub(cb: types.CallbackQuery, state: FSMContext):
    uid = int(cb.data.replace("usub_",""))
    await state.update_data(target_uid=uid, bal_action="sub")
    await state.set_state(AS.balance_amount)
    await cb.message.answer("💰 Ayirmoqchi bo'lgan miqdor:", reply_markup=cancel_kb())
    await cb.answer()

@dp.callback_query(F.data.startswith("umsg_"))
async def u_msg(cb: types.CallbackQuery, state: FSMContext):
    uid = int(cb.data.replace("umsg_",""))
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
        try: await bot.send_message(uid, f"✅ Hisobingizga {amount:.0f} {cur()} qo'shildi!")
        except: pass
    else:
        c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, uid))
        c.execute("INSERT INTO transactions(user_id,amount,type,description) VALUES(?,?,?,?)",
                  (uid, -amount, "admin_sub", "Admin tomonidan ayirildi"))
        try: await bot.send_message(uid, f"⚠️ Hisobingizdan {amount:.0f} {cur()} ayirildi!")
        except: pass
    conn.commit(); conn.close()
    act_text = "qo'shildi" if action=="add" else "ayirildi"
    await state.clear()
    await msg.answer(f"✅ {uid} ga {amount:.0f} {cur()} {act_text}!", reply_markup=admin_kb())

# ── Qo'llanmalar (Admin) ────────────────────────────────────
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
    gid = int(cb.data.replace("del_guide_",""))
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM guides WHERE id=?", (gid,))
    conn.commit(); conn.close()
    await cb.message.answer("✅ Qo'llanma o'chirildi!"); await cb.answer()

# ── Buyurtmalar (Admin) ────────────────────────────────────
@dp.message(F.text == "📈 Buyurtmalar")
async def admin_orders(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM orders"); total = c.fetchone()[0]
    st = {}
    for s in ("completed","cancelled","pending","processing","partial"):
        c.execute("SELECT COUNT(*) FROM orders WHERE status=?", (s,))
        st[s] = c.fetchone()[0]
    conn.close()
    b = InlineKeyboardBuilder()
    b.button(text="🔍 Qidirish", callback_data="search_orders")
    await msg.answer(
        f"📈 Buyurtmalar: {total} ta\n\n"
        f"✅ Bajarilganlar: {st['completed']} ta\n"
        f"🚫 Bekor qilinganlar: {st['cancelled']} ta\n"
        f"⏳ Bajarilayotganlar: {st['pending']} ta\n"
        f"🔄 Jarayondagilar: {st['processing']} ta\n"
        f"♻️ Qayta ishlanganlar: {st['partial']} ta",
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
        text += f"#{r[0]} | {r[2] or '?'} | {r[3]} dona | {r[4]:.0f} {cur()} | {r[5]}\n"
    await cb.message.answer(text[:4096]); await cb.answer()

# ═══════════════════════════════════════════════════════════
#  ADMIN — Xizmatlar (Services)
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
    await msg.answer(f"📁 Xizmatlar\n📂 Bo'limlar: {nc} ta\n🛠 Xizmatlar: {ns} ta", reply_markup=kb)

# ── Bo'limlar ─────────────────────────────────────────────
@dp.message(F.text == "📂 Bo'limlar")
async def cat_menu(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,is_active FROM categories")
    cats = c.fetchall(); conn.close()
    b = InlineKeyboardBuilder()
    for cid, cname, cact in cats:
        status = "✅" if cact else "❌"
        b.button(text=f"{status} {cname}", callback_data=f"cat_{cid}")
    b.button(text="➕ Bo'lim qo'shish", callback_data="cat_add")
    b.adjust(2)
    await msg.answer(f"📂 Bo'limlar: {len(cats)} ta", reply_markup=b.as_markup())

@dp.callback_query(F.data == "cat_add")
async def cat_add(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    await state.set_state(AS.add_category)
    await cb.message.answer("📂 Bo'lim nomini kiriting:", reply_markup=cancel_kb())
    await cb.answer()

@dp.message(AS.add_category)
async def do_cat_add(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await cat_menu(msg); return
    conn = db(); c = conn.cursor()
    c.execute("INSERT INTO categories(name) VALUES(?)", (msg.text,))
    conn.commit(); conn.close()
    await state.clear()
    await msg.answer(f"✅ '{msg.text}' bo'limi qo'shildi!")
    await cat_menu(msg)

@dp.callback_query(F.data.startswith("cat_") & ~F.data.startswith("cat_add"))
async def cat_detail(cb: types.CallbackQuery):
    if cb.from_user.id not in ADMIN_IDS: return
    cid  = int(cb.data.replace("cat_",""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,is_active FROM categories WHERE id=?", (cid,))
    cat  = c.fetchone()
    c.execute("SELECT COUNT(*) FROM services WHERE category_id=?", (cid,))
    ns   = c.fetchone()[0]
    conn.close()
    if not cat: await cb.answer("❌ Topilmadi"); return
    status = "✅ Faol" if cat[2] else "❌ Nofaol"
    b = InlineKeyboardBuilder()
    toggle = "❌ O'chirish" if cat[2] else "✅ Faollashtirish"
    b.button(text=toggle,                  callback_data=f"cat_tog_{cid}")
    b.button(text="➕ Xizmat qo'shish",    callback_data=f"cat_svc_add_{cid}")
    b.button(text="📋 Xizmatlar ro'yhati", callback_data=f"cat_svcs_{cid}")
    b.button(text="🗑 Bo'limni o'chirish",  callback_data=f"cat_del_{cid}")
    b.adjust(2)
    await cb.message.answer(
        f"📂 {cat[1]}\n"
        f"Holat: {status}\n"
        f"Xizmatlar: {ns} ta",
        reply_markup=b.as_markup()
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("cat_tog_"))
async def cat_toggle(cb: types.CallbackQuery):
    cid  = int(cb.data.replace("cat_tog_",""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT is_active FROM categories WHERE id=?", (cid,))
    cur_val = c.fetchone()[0]
    c.execute("UPDATE categories SET is_active=? WHERE id=?", (0 if cur_val else 1, cid))
    conn.commit(); conn.close()
    await cb.answer("✅ O'zgartirildi!")

@dp.callback_query(F.data.startswith("cat_del_"))
async def cat_del(cb: types.CallbackQuery):
    cid  = int(cb.data.replace("cat_del_",""))
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM categories WHERE id=?", (cid,))
    c.execute("DELETE FROM services WHERE category_id=?", (cid,))
    conn.commit(); conn.close()
    await cb.message.answer("✅ Bo'lim o'chirildi!"); await cb.answer()

# ── Xizmat qo'shish ──────────────────────────────────────
@dp.callback_query(F.data.startswith("cat_svc_add_"))
async def svc_add_step1(cb: types.CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_IDS: return
    cat_id = int(cb.data.replace("cat_svc_add_",""))
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
    await cb.message.answer("🔑 API tanlang:", reply_markup=b.as_markup())
    await cb.answer()

@dp.callback_query(F.data.startswith("svc_api_"))
async def svc_add_step2(cb: types.CallbackQuery, state: FSMContext):
    api_id = int(cb.data.replace("svc_api_",""))
    await state.update_data(new_svc_api=api_id)
    await state.set_state(AS.svc_api_id)
    await cb.message.answer(
        "🔢 API xizmat ID sini kiriting:\n\n"
        "💡 ID ni bilish uchun: Admin panel → API → Xizmatlarni yuklash",
        reply_markup=cancel_kb()
    )
    await cb.answer()

@dp.message(AS.svc_api_id)
async def svc_add_step3(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    api_svc_id = msg.text.strip()
    await state.update_data(new_svc_api_id=api_svc_id)
    data   = await state.get_data()
    api_id = data["new_svc_api"]

    conn = db(); c = conn.cursor()
    c.execute("SELECT url,api_key FROM apis WHERE id=?", (api_id,))
    api  = c.fetchone(); conn.close()

    prefill = {}
    if api:
        svcs = await api_services(api[0], api[1])
        if svcs:
            for s in svcs:
                if str(s.get("service", s.get("id",""))) == api_svc_id:
                    prefill = {
                        "name":  s.get("name",""),
                        "min":   int(s.get("min",100)),
                        "max":   int(s.get("max",10000)),
                        "price": round(float(s.get("rate",0)) * 1000, 2)
                    }
                    break

    await state.update_data(prefill=prefill)
    await state.set_state(AS.svc_name)

    if prefill:
        await msg.answer(
            f"✅ Xizmat topildi:\n📌 {prefill['name']}\n"
            f"Min:{prefill['min']} Max:{prefill['max']} Narx:{prefill['price']}/1000\n\n"
            f"Bot uchun nomini kiriting (yoki /skip — avtomatik nom):"
        )
    else:
        await msg.answer("📌 Xizmat nomini kiriting:")

@dp.message(AS.svc_name)
async def svc_add_name(msg: types.Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear(); await msg.answer("Bekor qilindi", reply_markup=admin_kb()); return
    data    = await state.get_data()
    prefill = data.get("prefill", {})
    name    = prefill.get("name","") if msg.text == "/skip" else msg.text
    await state.update_data(new_svc_name=name)
    await state.set_state(AS.svc_min)
    await msg.answer(f"📊 Minimal miqdor (default: {prefill.get('min',100)}, /skip):")

@dp.message(AS.svc_min)
async def svc_add_min(msg: types.Message, state: FSMContext):
    data    = await state.get_data()
    prefill = data.get("prefill", {})
    try:    mn = int(msg.text) if msg.text != "/skip" else prefill.get("min", 100)
    except: mn = prefill.get("min", 100)
    await state.update_data(new_svc_min=mn)
    await state.set_state(AS.svc_max)
    await msg.answer(f"📊 Maksimal miqdor (default: {prefill.get('max',10000)}, /skip):")

@dp.message(AS.svc_max)
async def svc_add_max(msg: types.Message, state: FSMContext):
    data    = await state.get_data()
    prefill = data.get("prefill", {})
    try:    mx = int(msg.text) if msg.text != "/skip" else prefill.get("max", 10000)
    except: mx = prefill.get("max", 10000)
    await state.update_data(new_svc_max=mx)
    await state.set_state(AS.svc_price)
    await msg.answer(f"💰 Narx 1000 ta uchun {cur()} da (default: {prefill.get('price',0)}, /skip):")

@dp.message(AS.svc_price)
async def svc_add_price(msg: types.Message, state: FSMContext):
    data    = await state.get_data()
    prefill = data.get("prefill", {})
    try:    price = float(msg.text) if msg.text != "/skip" else prefill.get("price", 0)
    except: price = prefill.get("price", 0)

    cat_id = data["new_svc_cat"]

    conn = db(); c = conn.cursor()
    c.execute("""INSERT INTO services(category_id,api_id,api_service_id,name,min_qty,max_qty,price_per1000)
                 VALUES(?,?,?,?,?,?,?)""",
              (cat_id, data["new_svc_api"], data["new_svc_api_id"],
               data["new_svc_name"], data["new_svc_min"], data["new_svc_max"], price))
    # yangi qo'shilgan xizmat sonini olish
    c.execute("SELECT COUNT(*) FROM services WHERE category_id=?", (cat_id,))
    svc_count = c.fetchone()[0]
    c.execute("SELECT name FROM categories WHERE id=?", (cat_id,))
    cat_row = c.fetchone()
    conn.commit(); conn.close()

    cat_name = cat_row[0] if cat_row else "Bo'lim"

    # Xizmat qo'shilgandan keyin yana qo'shish tugmasi
    b = InlineKeyboardBuilder()
    b.button(text="➕ Yana xizmat qo'shish", callback_data=f"cat_svc_add_{cat_id}")
    b.button(text="📋 Xizmatlar ro'yhati",   callback_data=f"cat_svcs_{cat_id}")
    b.adjust(2)

    await state.clear()
    await msg.answer(
        f"✅ Xizmat qo'shildi!\n\n"
        f"📌 {data['new_svc_name']}\n"
        f"💰 {price:.0f} {cur()}/1000\n"
        f"📊 Min: {data['new_svc_min']}  |  Max: {data['new_svc_max']}\n"
        f"📁 Bo'lim: {cat_name}  ({svc_count} ta xizmat)",
        reply_markup=b.as_markup()
    )

# ── Bo'limdagi xizmatlar ────────────────────────────────────
@dp.callback_query(F.data.startswith("cat_svcs_"))
async def cat_svcs(cb: types.CallbackQuery):
    cid  = int(cb.data.replace("cat_svcs_",""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT id,name,price_per1000,is_active FROM services WHERE category_id=?", (cid,))
    svcs = c.fetchall(); conn.close()
    if not svcs: await cb.answer("❌ Xizmatlar yo'q", show_alert=True); return
    b = InlineKeyboardBuilder()
    for sid, sname, sprice, sact in svcs:
        st = "✅" if sact else "❌"
        b.button(text=f"{st} {sname} — {sprice:.0f} {cur()}", callback_data=f"svc_{sid}")
    b.adjust(1)
    await cb.message.answer(f"📋 Xizmatlar ({len(svcs)} ta):", reply_markup=b.as_markup())
    await cb.answer()

@dp.message(F.text == "🛠 Barcha xizmatlar")
async def all_svcs(msg: types.Message):
    if msg.from_user.id not in ADMIN_IDS: return
    conn = db(); c = conn.cursor()
    c.execute("""SELECT s.id,s.name,s.price_per1000,s.is_active,cat.name
                 FROM services s LEFT JOIN categories cat ON s.category_id=cat.id""")
    svcs = c.fetchall(); conn.close()
    if not svcs: await msg.answer("❌ Xizmatlar yo'q"); return
    b = InlineKeyboardBuilder()
    for sid, sname, sprice, sact, cname in svcs:
        st = "✅" if sact else "❌"
        b.button(text=f"{st} [{cname}] {sname} — {sprice:.0f} {cur()}", callback_data=f"svc_{sid}")
    b.adjust(1)
    await msg.answer(f"📋 Barcha xizmatlar ({len(svcs)} ta):", reply_markup=b.as_markup())

@dp.callback_query(F.data.startswith("svc_") & ~F.data.startswith("svc_api_"))
async def svc_detail(cb: types.CallbackQuery):
    sid  = int(cb.data.replace("svc_",""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT * FROM services WHERE id=?", (sid,))
    svc  = c.fetchone(); conn.close()
    if not svc: await cb.answer("❌ Topilmadi"); return
    status = "✅ Faol" if svc[8] else "❌ Nofaol"
    b = InlineKeyboardBuilder()
    b.button(text="❌ O'chirish" if svc[8] else "✅ Faollashtirish", callback_data=f"svc_tog_{sid}")
    b.button(text="🗑 O'chirish", callback_data=f"svc_del_{sid}")
    b.adjust(2)
    await cb.message.answer(
        f"🛠 {svc[4]}\nHolat: {status}\n"
        f"💰 {svc[7]:.0f} {cur()}/1000\nMin:{svc[5]} Max:{svc[6]}\n"
        f"API ID: {svc[3]}",
        reply_markup=b.as_markup()
    )
    await cb.answer()

@dp.callback_query(F.data.startswith("svc_tog_"))
async def svc_toggle(cb: types.CallbackQuery):
    sid  = int(cb.data.replace("svc_tog_",""))
    conn = db(); c = conn.cursor()
    c.execute("SELECT is_active FROM services WHERE id=?", (sid,))
    v    = c.fetchone()[0]
    c.execute("UPDATE services SET is_active=? WHERE id=?", (0 if v else 1, sid))
    conn.commit(); conn.close()
    await cb.answer("✅ O'zgartirildi!")

@dp.callback_query(F.data.startswith("svc_del_"))
async def svc_del(cb: types.CallbackQuery):
    sid  = int(cb.data.replace("svc_del_",""))
    conn = db(); c = conn.cursor()
    c.execute("DELETE FROM services WHERE id=?", (sid,))
    conn.commit(); conn.close()
    await cb.message.answer("✅ Xizmat o'chirildi!"); await cb.answer()

# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════
async def main():
    init_db()
    logger.info("✅ SMM Bot ishga tushdi!")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
