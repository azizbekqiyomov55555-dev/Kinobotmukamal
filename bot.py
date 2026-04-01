#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KinoBOT \u2014 To'liq versiya (rangli tugmalar + image 2 format)
- /start: pastki ReplyKeyboard
- Kanal post: rasm + chiroyli matn + "Tomosha qilish" tugmasi
- Bot: image 2 formatida kino ma'lumoti + rangli tugmalar
- Admin panel: "Boshqarish" tugmasi orqali
"""

import sqlite3, logging, os, json
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# SOZLAMALAR
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS    = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
CHANNEL_ID   = os.environ.get("CHANNEL_ID", "")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "VipDramlarBot")

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# INLINE TUGMA YORDAMCHILAR \u2014 style qo'shildi
# style="primary" \u2192 Ko'k
# style="success" \u2192 Yashil
# style="danger"  \u2192 Qizil
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
def ib(text, cbd, style=None):
    if style:
        return InlineKeyboardButton(text, callback_data=cbd, style=style)
    return InlineKeyboardButton(text, callback_data=cbd)

def lb(text, url, style=None):
    if style:
        return InlineKeyboardButton(text, url=url, style=style)
    return InlineKeyboardButton(text, url=url)

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# DATABASE
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
def db():
    c = sqlite3.connect("kinobot.db", check_same_thread=False)
    c.row_factory = sqlite3.Row
    return c

def db_init():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS kinolar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nomi TEXT NOT NULL,
        kod TEXT UNIQUE NOT NULL,
        rasm_file_id TEXT,
        til TEXT DEFAULT 'O''zbek tilida',
        janr TEXT DEFAULT 'Mini drama',
        davlat TEXT DEFAULT 'Xitoy',
        yil INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS qismlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kino_id INTEGER NOT NULL,
        qism_raqam INTEGER NOT NULL,
        file_id TEXT NOT NULL,
        is_vip INTEGER DEFAULT 0,
        narx INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        balans INTEGER DEFAULT 0,
        vip_expire TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS tolovlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        miqdor INTEGER NOT NULL,
        chek_file_id TEXT,
        tur TEXT DEFAULT 'balans',
        tarif_id INTEGER DEFAULT 0,
        status TEXT DEFAULT 'kutilmoqda',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS tariflar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nomi TEXT NOT NULL,
        narx INTEGER NOT NULL,
        kunlar INTEGER NOT NULL,
        is_active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS kartalar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        raqam TEXT NOT NULL,
        egasi TEXT,
        is_active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS majburiy (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nomi TEXT,
        link TEXT NOT NULL,
        tur TEXT DEFAULT 'kanal',
        is_active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS xaridlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        qism_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS states (
        user_id INTEGER PRIMARY KEY,
        state TEXT NOT NULL,
        data TEXT DEFAULT '{}'
    );
    """)
    con.commit()
    con.close()

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# STATE MACHINE
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
def state_set(uid, state, data=None):
    con = db()
    con.execute(
        "INSERT OR REPLACE INTO states(user_id,state,data) VALUES(?,?,?)",
        (uid, state, json.dumps(data or {}))
    )
    con.commit(); con.close()

def state_get(uid):
    con = db()
    row = con.execute("SELECT state,data FROM states WHERE user_id=?", (uid,)).fetchone()
    con.close()
    if row:
        return row["state"], json.loads(row["data"] or "{}")
    return None, {}

def state_clear(uid):
    con = db()
    con.execute("DELETE FROM states WHERE user_id=?", (uid,))
    con.commit(); con.close()

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# YORDAMCHI FUNKSIYALAR
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
def som(n):
    return f"{int(n):,}".replace(",", " ")

def ensure_user(tg):
    con = db()
    con.execute(
        "INSERT OR IGNORE INTO users(id,username,full_name) VALUES(?,?,?)",
        (tg.id, tg.username, tg.full_name)
    )
    con.commit(); con.close()

def get_user(uid):
    con = db()
    u = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    con.close()
    return u

def is_admin(uid):
    return uid in ADMIN_IDS

def is_vip(uid):
    u = get_user(uid)
    if not u or not u["vip_expire"]: return False
    return datetime.fromisoformat(u["vip_expire"]) > datetime.now()

def get_karta():
    con = db()
    k = con.execute("SELECT * FROM kartalar WHERE is_active=1 LIMIT 1").fetchone()
    con.close()
    return k

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# KLAVIATURALAR
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
def user_kb():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Kinolar"),       KeyboardButton("Qidirish")],
            [KeyboardButton("VIP Tariflar"),  KeyboardButton("Hisobim")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Kino kodini yozing..."
    )

def admin_kb():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Kino qo'shish"),   KeyboardButton("Kanal post")],
            [KeyboardButton("VIP Tariflar"),     KeyboardButton("Karta qo'shish")],
            [KeyboardButton("Majburiy obuna"),   KeyboardButton("Statistika")],
            [KeyboardButton("Xabar yuborish"),   KeyboardButton("Pulik qism")],
            [KeyboardButton("Foydalanuvchi menyu")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Bo'lim tanlang..."
    )

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# MAJBURIY OBUNA
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def check_sub(bot, uid):
    con = db()
    rows = con.execute("SELECT * FROM majburiy WHERE is_active=1").fetchall()
    con.close()
    failed = []
    for r in rows:
        if r["tur"] == "kanal":
            try:
                m = await bot.get_chat_member(r["link"], uid)
                if m.status in ("left", "kicked"):
                    failed.append(r)
            except:
                failed.append(r)
        else:
            failed.append(r)
    return failed

async def send_sub_msg(update, failed):
    btns = [[lb(r["nomi"] or r["link"], r["link"])] for r in failed]
    btns.append([ib("\u2705 Tekshirish", "check_sub", style="success")])
    await update.effective_message.reply_text(
        "*Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:*",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# /start
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    uid = update.effective_user.id
    state_clear(uid)

    failed = await check_sub(ctx.bot, uid)
    if failed:
        await send_sub_msg(update, failed)
        return

    args = ctx.args
    if args:
        kod = args[0].upper()
        await show_kino_by_kod(update, ctx, kod, from_start=True)
        return

    name = update.effective_user.first_name or "Foydalanuvchi"

    if is_admin(uid):
        await update.message.reply_text(
            f"*Xush kelibsiz, {name}!*\n\n"
            "Kino kodini yuboring yoki pastdagi tugmalardan foydalaning.",
            reply_markup=admin_kb(),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            f"*Xush kelibsiz, {name}!*\n\n"
            "Kino kodini yuboring yoki pastdagi tugmalardan foydalaning.",
            reply_markup=user_kb(),
            parse_mode=ParseMode.MARKDOWN
        )

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# /admin
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("Ruxsat yo'q!")
        return
    state_clear(uid)
    await update.message.reply_text(
        "*Admin Panel*\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=admin_kb(),
        parse_mode=ParseMode.MARKDOWN
    )

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# KINO KO'RSATISH \u2014 Image 2 format
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def show_kino_by_kod(update, ctx, kod, from_start=False):
    con = db()
    kino = con.execute("SELECT * FROM kinolar WHERE kod=?", (kod,)).fetchone()
    con.close()
    if not kino:
        await update.effective_message.reply_text(
            "Kino topilmadi! Kodni tekshiring.",
            reply_markup=user_kb()
        )
        return
    await show_kino(update, ctx, kino)

async def show_kino(update, ctx, kino):
    con = db()
    qismlar = con.execute(
        "SELECT * FROM qismlar WHERE kino_id=? ORDER BY qism_raqam", (kino["id"],)
    ).fetchall()
    con.close()

    joriy = max((q["qism_raqam"] for q in qismlar), default=0)
    jami  = len(qismlar)

    # Image 2 formatida caption
    til_nomi = kino['til'] or "O'zbek tilida"
    janr_nomi = kino['janr'] or 'Mini drama'
    caption = (
        f"\ud83c\udfac *{kino['nomi']}*\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"  Qism       :  {joriy}/{jami}\n"
        f"  Janrlari   :  {janr_nomi}\n"
        f"  Tili       :  {til_nomi}\n"
        f"  Ko'rish    :  \ud83c\udf7f @{BOT_USERNAME}\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
    )

    btns = [
        [ib("\ud83d\udce5 Yuklab olish", f"yuklab_{kino['id']}", style="primary")],
    ]

    if kino["rasm_file_id"]:
        await update.effective_message.reply_photo(
            kino["rasm_file_id"],
            caption=caption,
            reply_markup=InlineKeyboardMarkup(btns),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.effective_message.reply_text(
            caption,
            reply_markup=InlineKeyboardMarkup(btns),
            parse_mode=ParseMode.MARKDOWN
        )

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# YUKLAB OLISH \u2014 rangli qism tugmalari
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def cb_yuklab(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kino_id = int(q.data.split("_")[1])
    con = db()
    kino    = con.execute("SELECT * FROM kinolar WHERE id=?", (kino_id,)).fetchone()
    qismlar = con.execute(
        "SELECT * FROM qismlar WHERE kino_id=? ORDER BY qism_raqam", (kino_id,)
    ).fetchall()
    con.close()

    if not qismlar:
        await q.message.reply_text("Qismlar hali qo'shilmagan.")
        return

    btns = []
    row  = []
    for i, qism in enumerate(qismlar):
        if qism["is_vip"]:
            label = f"\ud83d\udc51 {qism['qism_raqam']}-qism"
            btn   = ib(label, f"qism_{qism['id']}", style="danger")
        else:
            label = f"{qism['qism_raqam']}-qism"
            btn   = ib(label, f"qism_{qism['id']}", style="primary")
        row.append(btn)
        if len(row) == 3 or i == len(qismlar) - 1:
            btns.append(row)
            row = []

    await q.message.reply_text(
        f"\ud83c\udfac *{kino['nomi']}*\n\nQismni tanlang \ud83d\udc47",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# QISM YUBORISH
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def cb_qism(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    qism_id = int(q.data.split("_")[1])

    con = db()
    qism = con.execute("SELECT * FROM qismlar WHERE id=?", (qism_id,)).fetchone()
    if not qism:
        await q.answer("Qism topilmadi!", show_alert=True)
        con.close()
        return
    kino = con.execute("SELECT * FROM kinolar WHERE id=?", (qism["kino_id"],)).fetchone()
    con.close()

    if qism["is_vip"] and not is_vip(uid):
        user   = get_user(uid)
        balans = user["balans"] if user else 0
        btns = [
            [ib(f"\ud83d\udcb3 Balansdan to'lash ({som(qism['narx'])} so'm)", f"balans_{qism_id}", style="primary")],
            [ib("\ud83d\udc51 VIP sotib olish", "vip_menu", style="success")],
        ]
        await q.message.reply_text(
            f"*Bu qism VIP!*\n\n"
            f"Narxi: {som(qism['narx'])} so'm\n"
            f"Sizning balansingiz: {som(balans)} so'm",
            reply_markup=InlineKeyboardMarkup(btns),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    await q.message.reply_text(
        f"*{kino['nomi']}* \u2014 {qism['qism_raqam']}-qism yuklanmoqda..."
    )
    await ctx.bot.send_video(
        uid,
        qism["file_id"],
        caption=f"*{kino['nomi']}* | {qism['qism_raqam']}-qism\n@{BOT_USERNAME}",
        parse_mode=ParseMode.MARKDOWN
    )

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# BALANSDAN TO'LASH
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def cb_balans(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    qism_id = int(q.data.split("_")[1])

    con = db()
    qism = con.execute("SELECT * FROM qismlar WHERE id=?", (qism_id,)).fetchone()
    user = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

    if not qism or not user:
        await q.answer("Xato!", show_alert=True)
        con.close()
        return

    if user["balans"] < qism["narx"]:
        await q.answer(f"Balans yetarli emas! Kerak: {som(qism['narx'])} so'm", show_alert=True)
        con.close()
        return

    con.execute("UPDATE users SET balans=balans-? WHERE id=?", (qism["narx"], uid))
    con.execute("INSERT INTO xaridlar(user_id,qism_id) VALUES(?,?)", (uid, qism_id))
    kino = con.execute("SELECT * FROM kinolar WHERE id=?", (qism["kino_id"],)).fetchone()
    con.commit(); con.close()

    await ctx.bot.send_video(
        uid,
        qism["file_id"],
        caption=f"*{kino['nomi']}* | {qism['qism_raqam']}-qism\n@{BOT_USERNAME}",
        parse_mode=ParseMode.MARKDOWN
    )
    await q.message.reply_text(f"To'lov amalga oshirildi! -{som(qism['narx'])} so'm")

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# HISOBIM
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def show_hisobim(update, ctx):
    uid = update.effective_user.id
    user = get_user(uid)
    vip_txt = "Yo'q"
    if is_vip(uid):
        exp = datetime.fromisoformat(user["vip_expire"])
        vip_txt = f"Ha ({exp.strftime('%d.%m.%Y')} gacha)"

    con = db()
    tlist = con.execute(
        "SELECT * FROM tolovlar WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (uid,)
    ).fetchall()
    con.close()

    tarix = ""
    for t in tlist:
        e = {"tasdiqlandi": "\u2705", "kutilmoqda": "\u23f3", "bekor": "\u274c"}.get(t["status"], "?")
        tarix += f"{e} {som(t['miqdor'])} so'm \u2014 {t['created_at'][:10]}\n"

    btns = [[ib("\ud83d\udcb3 Hisobni to'ldirish", "toldirish", style="primary")]]
    await update.effective_message.reply_text(
        f"*Mening hisobim*\n\n"
        f"ID      : `{uid}`\n"
        f"Balans  : *{som(user['balans'] if user else 0)} so'm*\n"
        f"VIP     : {vip_txt}\n\n"
        f"*So'nggi to'lovlar:*\n{tarix or 'Hali tolov yoq'}",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_hisobim(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await show_hisobim(update, ctx)

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# HISOBNI TO'LDIRISH
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def cb_toldirish(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    state_set(uid, "tolov_miqdor")
    await q.message.reply_text(
        "*Qancha miqdorda to'ldirmoqchisiz?*\n\nMiqdorni so'mda kiriting (masalan: 50000):",
        parse_mode=ParseMode.MARKDOWN
    )

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# VIP TARIFLAR
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def show_vip(update, ctx):
    con = db()
    tariflar = con.execute("SELECT * FROM tariflar WHERE is_active=1").fetchall()
    con.close()
    if not tariflar:
        await update.effective_message.reply_text("Hozirda VIP tariflar mavjud emas.")
        return
    txt = "*\ud83d\udc51 VIP Tariflar*\n\n"
    btns = []
    for t in tariflar:
        txt += f"\u2022 {t['nomi']} \u2014 {som(t['narx'])} so'm ({t['kunlar']} kun)\n"
        btns.append([ib(f"\ud83d\udc51 {t['nomi']} \u2014 {som(t['narx'])} so'm", f"vipbuy_{t['id']}", style="success")])
    await update.effective_message.reply_text(
        txt, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN
    )

async def cb_vip_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await show_vip(update, ctx)

async def cb_vipbuy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    tarif_id = int(q.data.split("_")[1])
    con = db()
    tarif = con.execute("SELECT * FROM tariflar WHERE id=?", (tarif_id,)).fetchone()
    con.close()
    k = get_karta()
    if not k:
        await q.message.reply_text("Karta mavjud emas! Admin bilan bog'laning.")
        return
    state_set(uid, "vip_chek", {"tarif_id": tarif_id})
    await q.message.reply_text(
        f"*{tarif['nomi']}* sotib olish\n\n"
        f"Narxi   : {som(tarif['narx'])} so'm\n"
        f"Muddat  : {tarif['kunlar']} kun\n\n"
        f"Karta raqami:\n`{k['raqam']}`\n"
        f"Egasi   : {k['egasi'] or '-'}\n\n"
        f"To'lovni amalga oshirib, *chek rasmini* yuboring:",
        parse_mode=ParseMode.MARKDOWN
    )

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# CHECK_SUB CALLBACK
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def cb_check_sub(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    failed = await check_sub(ctx.bot, uid)
    if failed:
        await send_sub_msg(update, failed)
    else:
        try: await q.message.delete()
        except: pass
        await q.message.reply_text("\u2705 Obuna tasdiqlandi!", reply_markup=user_kb())

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# TO'LOV TASDIQLASH / BEKOR (ADMIN)
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def cb_tok(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    parts = q.data.split("_")
    tid, uid, miqdor = int(parts[1]), int(parts[2]), int(parts[3])
    con = db()
    con.execute("UPDATE tolovlar SET status='tasdiqlandi' WHERE id=?", (tid,))
    con.execute("UPDATE users SET balans=balans+? WHERE id=?", (miqdor, uid))
    con.commit(); con.close()
    await q.edit_message_caption(
        (q.message.caption or "") + f"\n\n\u2705 TASDIQLANDI \u2014 {datetime.now().strftime('%H:%M')}",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        await ctx.bot.send_message(uid,
            f"*\u2705 Hisobingiz to'ldirildi!*\n+{som(miqdor)} so'm",
            parse_mode=ParseMode.MARKDOWN)
    except: pass

async def cb_tno(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    parts = q.data.split("_")
    tid, uid, miqdor = int(parts[1]), int(parts[2]), int(parts[3])
    con = db()
    con.execute("UPDATE tolovlar SET status='bekor' WHERE id=?", (tid,))
    con.commit(); con.close()
    await q.edit_message_caption(
        (q.message.caption or "") + f"\n\n\u274c BEKOR \u2014 {datetime.now().strftime('%H:%M')}",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        await ctx.bot.send_message(uid, f"To'lov bekor qilindi. ({som(miqdor)} so'm)")
    except: pass

# VIP tasdiqlash
async def cb_vok(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    parts = q.data.split("_")
    tid, uid, tarif_id = int(parts[1]), int(parts[2]), int(parts[3])
    con = db()
    tarif = con.execute("SELECT * FROM tariflar WHERE id=?", (tarif_id,)).fetchone()
    user  = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    expire = datetime.now() + timedelta(days=tarif["kunlar"])
    if user and user["vip_expire"]:
        try:
            ex = datetime.fromisoformat(user["vip_expire"])
            if ex > datetime.now():
                expire = ex + timedelta(days=tarif["kunlar"])
        except: pass
    con.execute("UPDATE users SET vip_expire=? WHERE id=?", (expire.isoformat(), uid))
    con.execute("UPDATE tolovlar SET status='tasdiqlandi' WHERE id=?", (tid,))
    con.commit(); con.close()
    await q.edit_message_caption(
        (q.message.caption or "") + f"\n\n\ud83d\udc51 VIP BERILDI \u2014 {expire.strftime('%d.%m.%Y')} gacha",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        await ctx.bot.send_message(uid,
            f"*\ud83d\udc51 VIP faollashtirildi!*\n{tarif['nomi']}\n{expire.strftime('%d.%m.%Y')} gacha",
            parse_mode=ParseMode.MARKDOWN)
    except: pass

async def cb_vno(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    parts = q.data.split("_")
    tid, uid = int(parts[1]), int(parts[2])
    con = db()
    con.execute("UPDATE tolovlar SET status='bekor' WHERE id=?", (tid,))
    con.commit(); con.close()
    await q.edit_message_caption(
        (q.message.caption or "") + "\n\n\u274c BEKOR QILINDI", parse_mode=ParseMode.MARKDOWN
    )
    try: await ctx.bot.send_message(uid, "VIP so'rovingiz bekor qilindi.")
    except: pass

async def cb_xyu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    target = int(q.data.split("_")[1])
    state_set(q.from_user.id, "xabar_send", {"target": str(target)})
    await q.message.reply_text(f"Foydalanuvchi ({target}) ga xabar yuboring:")

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# KANAL POST
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def send_post_preview(msg, ctx, data, uid):
    nomi = data.get("nomi", "")
    qism = data.get("qism", 0)
    til  = data.get("til", "O'zbek tilida")
    kod  = data.get("kod", "")
    rasm = data.get("rasm", "")

    caption = _post_caption(nomi, qism, til, kod)

    await msg.reply_photo(
        rasm,
        caption=caption + "\n\n_Ko'rinishi shunaqa. Kanalga yuborilsinmi?_",
        reply_markup=InlineKeyboardMarkup([
            [ib("\u2705 Kanalga yuborish", f"postsend_{uid}", style="success"),
             ib("\u274c Bekor", "ap_back", style="danger")],
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

def _post_caption(nomi, qism, til, kod):
    return (
        f"*{nomi}*\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
        f"  Qism        :  {qism}/7\n"
        f"  Janrlari    :  Mini drama\n"
        f"  Tili        :  {til}\n"
        f"  Ko'rish     :  [Tomosha qilish](https://t.me/{BOT_USERNAME}?start={kod})\n"
        f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
    )

async def cb_postsend(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    uid = int(q.data.split("_")[1])
    _, data = state_get(uid)

    nomi = data.get("nomi", "")
    qism = data.get("qism", 0)
    til  = data.get("til", "O'zbek tilida")
    kod  = data.get("kod", "")
    rasm = data.get("rasm", "")

    caption    = _post_caption(nomi, qism, til, kod)
    kanal_btns = [[lb("\u25b6\ufe0f Tomosha qilish", f"https://t.me/{BOT_USERNAME}?start={kod}", style="primary")]]

    try:
        await ctx.bot.send_photo(
            CHANNEL_ID, rasm,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(kanal_btns),
            parse_mode=ParseMode.MARKDOWN
        )
        state_clear(uid)
        await q.message.reply_text("\u2705 Post kanalga yuborildi!", reply_markup=admin_kb())
    except Exception as e:
        await q.message.reply_text(
            f"Xato: {e}\n\nCHANNEL_ID ni tekshiring: `{CHANNEL_ID}`\n"
            f"Bot kanalga admin bo'lishi kerak!",
            parse_mode=ParseMode.MARKDOWN
        )

async def cb_ap_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    state_clear(q.from_user.id)
    await q.message.reply_text("Admin Panel:", reply_markup=admin_kb())

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# ADMIN \u2014 VIP TARIFLAR PANEL
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def show_vip_admin(update, ctx):
    con = db()
    tariflar = con.execute("SELECT * FROM tariflar WHERE is_active=1").fetchall()
    con.close()
    txt = "*VIP Tariflar*\n\n"
    btns = []
    for t in tariflar:
        txt += f"{t['nomi']} \u2014 {som(t['narx'])} so'm ({t['kunlar']} kun)\n"
        btns.append([ib(f"\ud83d\uddd1 O'chirish: {t['nomi']}", f"tdel_{t['id']}", style="danger")])
    btns.append([ib("\u2795 Yangi tarif qo'shish", "tadd", style="success")])
    await update.message.reply_text(
        txt or "Tariflar yo'q",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_tadd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    state_set(q.from_user.id, "tarif_nomi", {})
    await q.message.reply_text("Tarif nomini kiriting (masalan: 1 oylik):")

async def cb_tdel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    tid = int(q.data.split("_")[1])
    con = db()
    con.execute("UPDATE tariflar SET is_active=0 WHERE id=?", (tid,))
    con.commit(); con.close()
    await q.message.reply_text("Tarif o'chirildi!", reply_markup=admin_kb())

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# ADMIN \u2014 KARTALAR PANEL
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def show_kartalar(update, ctx):
    con = db()
    kartalar = con.execute("SELECT * FROM kartalar WHERE is_active=1").fetchall()
    con.close()
    txt = "*Kartalar*\n\n"
    btns = []
    for k in kartalar:
        txt += f"`{k['raqam']}` \u2014 {k['egasi'] or '-'}\n"
        btns.append([ib(f"\ud83d\uddd1 O'chirish: {k['raqam']}", f"kdel_{k['id']}", style="danger")])
    btns.append([ib("\u2795 Karta qo'shish", "kadd", style="success")])
    await update.message.reply_text(
        txt or "Kartalar yo'q",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_kadd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    state_set(q.from_user.id, "karta_raqam", {})
    await q.message.reply_text("Karta raqamini kiriting (8600 1234 5678 9012):")

async def cb_kdel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    kid = int(q.data.split("_")[1])
    con = db()
    con.execute("UPDATE kartalar SET is_active=0 WHERE id=?", (kid,))
    con.commit(); con.close()
    await q.message.reply_text("Karta o'chirildi!", reply_markup=admin_kb())

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# ADMIN \u2014 MAJBURIY OBUNA PANEL
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def show_majburiy(update, ctx):
    con = db()
    rows = con.execute("SELECT * FROM majburiy WHERE is_active=1").fetchall()
    con.close()
    txt = "*Majburiy Obunalar*\n\n"
    btns = []
    for r in rows:
        txt += f"\u2014 {r['nomi'] or r['link']} ({r['tur']})\n"
        btns.append([ib(f"\ud83d\uddd1 O'chirish: {r['nomi'] or r['link']}", f"mdel_{r['id']}", style="danger")])
    btns.append([ib("\u2795 Qo'shish", "madd", style="success")])
    await update.message.reply_text(
        txt or "Majburiy obunalar yo'q",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_madd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    btns = [
        [ib("\ud83d\udce2 Telegram kanal", "mtur_kanal", style="primary")],
        [ib("\ud83d\udd17 Oddiy link",     "mtur_link",  style="primary")],
    ]
    await q.message.reply_text("Tur tanlang:", reply_markup=InlineKeyboardMarkup(btns))

async def cb_mtur(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    tur = q.data.split("_")[1]
    state_set(q.from_user.id, "maj_link", {"tur": tur})
    await q.message.reply_text("Link kiriting (masalan: @kanal_username yoki https://...):")

async def cb_mdel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    mid = int(q.data.split("_")[1])
    con = db()
    con.execute("UPDATE majburiy SET is_active=0 WHERE id=?", (mid,))
    con.commit(); con.close()
    await q.message.reply_text("O'chirildi!", reply_markup=admin_kb())

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# ADMIN \u2014 STATISTIKA
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def show_stat(update, ctx):
    con = db()
    bir_oy  = (datetime.now() - timedelta(days=30)).isoformat()
    bir_haf = (datetime.now() - timedelta(days=7)).isoformat()
    jami    = con.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    yangi   = con.execute("SELECT COUNT(*) FROM users WHERE created_at>=?", (bir_oy,)).fetchone()[0]
    vips    = con.execute("SELECT COUNT(*) FROM users WHERE vip_expire>?", (datetime.now().isoformat(),)).fetchone()[0]
    daromad = con.execute("SELECT SUM(miqdor) FROM tolovlar WHERE status='tasdiqlandi' AND created_at>=?", (bir_oy,)).fetchone()[0] or 0
    haf_tol = con.execute("SELECT COUNT(DISTINCT user_id) FROM tolovlar WHERE created_at>=?", (bir_haf,)).fetchone()[0]
    top15   = con.execute("SELECT id,full_name,balans FROM users ORDER BY balans DESC LIMIT 15").fetchall()
    con.close()
    top_txt = "\n".join(
        f"{i+1}. {u['full_name'] or u['id']} \u2014 {som(u['balans'])} so'm"
        for i, u in enumerate(top15)
    )
    await update.message.reply_text(
        f"*\ud83d\udcca Statistika*\n\n"
        f"\ud83d\udc65 Jami foydalanuvchi  : {jami}\n"
        f"\ud83c\udd95 Bu oy yangi         : +{yangi}\n"
        f"\ud83d\udc51 Aktiv VIP           : {vips}\n"
        f"\ud83d\udcb0 Bu oy daromad       : {som(daromad)} so'm\n"
        f"\ud83d\udcb3 Bu hafta to'ldirgan : {haf_tol} kishi\n\n"
        f"*Top 15 balans:*\n{top_txt or 'Malumot yoq'}",
        reply_markup=admin_kb(),
        parse_mode=ParseMode.MARKDOWN
    )

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# ADMIN \u2014 XABAR YUBORISH
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def show_xabar_menu(update, ctx):
    btns = [
        [ib("\ud83d\udce2 Hammaga",    "xall",  style="primary")],
        [ib("\ud83d\udc51 Faqat VIP",  "xvip",  style="success"),
         ib("\ud83d\udc64 Bepul",      "xfree", style="primary")],
    ]
    await update.message.reply_text(
        "*Kimga xabar yuborish?*",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_xabar_target(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    target = q.data
    state_set(q.from_user.id, "xabar_send", {"target": target})
    await q.message.reply_text("Xabar yuboring (matn, rasm yoki video):")

async def do_xabar_send(update, ctx, target):
    uid = update.effective_user.id
    msg = update.message
    con = db()
    now = datetime.now().isoformat()
    if target == "xall":
        users = con.execute("SELECT id FROM users").fetchall()
    elif target == "xvip":
        users = con.execute("SELECT id FROM users WHERE vip_expire>?", (now,)).fetchall()
    elif target == "xfree":
        users = con.execute("SELECT id FROM users WHERE vip_expire IS NULL OR vip_expire<=?", (now,)).fetchall()
    else:
        try:
            users = [{"id": int(target)}]
        except:
            users = []
    con.close()
    sent = 0
    for u in users:
        try:
            if msg.photo:
                await ctx.bot.send_photo(u["id"], msg.photo[-1].file_id, caption=msg.caption or "")
            elif msg.video:
                await ctx.bot.send_video(u["id"], msg.video.file_id, caption=msg.caption or "")
            elif msg.voice:
                await ctx.bot.send_voice(u["id"], msg.voice.file_id)
            elif msg.text:
                await ctx.bot.send_message(u["id"], msg.text)
            sent += 1
        except: pass
    state_clear(uid)
    await msg.reply_text(f"\u2705 {sent} ta foydalanuvchiga yuborildi.", reply_markup=admin_kb())

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# MATN HANDLER
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    uid  = update.effective_user.id
    text = (update.message.text or "").strip()

    failed = await check_sub(ctx.bot, uid)
    if failed:
        await send_sub_msg(update, failed)
        return

    state, data = state_get(uid)

    # \u2500\u2500 Admin menyu tugmalari \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    if is_admin(uid) and not state:
        if text == "Kino qo'shish":
            state_set(uid, "k_nomi", {})
            await update.message.reply_text(
                "*Kino qo'shish*\n\n1. Kino nomini kiriting:",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        elif text == "Kanal post":
            state_set(uid, "p_rasm", {})
            await update.message.reply_text(
                "*Kanal Post*\n\n1. Kino rasmini yuboring:",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        elif text == "VIP Tariflar":
            await show_vip_admin(update, ctx)
            return
        elif text == "Karta qo'shish":
            await show_kartalar(update, ctx)
            return
        elif text == "Majburiy obuna":
            await show_majburiy(update, ctx)
            return
        elif text == "Statistika":
            await show_stat(update, ctx)
            return
        elif text == "Xabar yuborish":
            await show_xabar_menu(update, ctx)
            return
        elif text == "Pulik qism":
            state_set(uid, "pulik_kod", {})
            await update.message.reply_text(
                "*Pulik qism*\n\nKino kodini kiriting:",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        elif text == "Foydalanuvchi menyu":
            state_clear(uid)
            await update.message.reply_text(
                "Foydalanuvchi menyusi:",
                reply_markup=user_kb()
            )
            return

    # \u2500\u2500 Admin state machine \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    if is_admin(uid) and state:
        handled = await admin_state_text(update, ctx, state, data, text)
        if handled:
            return

    # \u2500\u2500 Foydalanuvchi state machine \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    if state == "tolov_miqdor":
        await tolov_miqdor(update, ctx, text)
        return
    if state and state.startswith("xabar_send"):
        target = data.get("target", "xall")
        await do_xabar_send(update, ctx, target)
        return

    # \u2500\u2500 Foydalanuvchi menyu tugmalari \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    if text == "Hisobim":
        await show_hisobim(update, ctx)
    elif text == "VIP Tariflar":
        await show_vip(update, ctx)
    elif text in ("Kinolar", "Qidirish"):
        await update.message.reply_text("Kino kodini kiriting:")
    elif text == "Boshqarish":
        if is_admin(uid):
            await cmd_admin(update, ctx)
        else:
            await update.message.reply_text("Ruxsat yo'q!")
    else:
        kod = text.upper()
        await show_kino_by_kod(update, ctx, kod)

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# MEDIA HANDLER
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def on_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    uid = update.effective_user.id
    state, data = state_get(uid)

    if state == "tolov_chek":
        await tolov_chek(update, ctx, data)
    elif state == "vip_chek":
        await vip_chek(update, ctx, data)
    elif state in ("k_rasm", "k_qism"):
        await admin_state_media(update, ctx, state, data)
    elif state == "p_rasm":
        await admin_state_media(update, ctx, state, data)
    elif state and state.startswith("xabar_send"):
        target = data.get("target", "xall")
        await do_xabar_send(update, ctx, target)

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# TO'LOV QADAMLARI
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def tolov_miqdor(update, ctx, text):
    uid = update.effective_user.id
    try:
        miqdor = int(text.replace(" ", "").replace(",", ""))
        if miqdor < 1000: raise ValueError
    except:
        await update.message.reply_text("Kamida 1 000 so'm kiriting:")
        return
    k = get_karta()
    if not k:
        await update.message.reply_text("Karta mavjud emas. Admin bilan bog'laning.")
        state_clear(uid)
        return
    state_set(uid, "tolov_chek", {"miqdor": miqdor})
    await update.message.reply_text(
        f"*To'lov ma'lumotlari:*\n\n"
        f"Karta raqami :\n`{k['raqam']}`\n"
        f"Egasi        : {k['egasi'] or '-'}\n"
        f"Miqdor       : *{som(miqdor)} so'm*\n\n"
        f"To'lovni amalga oshirib, *chek rasmini* yuboring:",
        parse_mode=ParseMode.MARKDOWN
    )

async def tolov_chek(update, ctx, data):
    uid = update.effective_user.id
    if not update.message.photo:
        await update.message.reply_text("Chek rasmini yuboring!")
        return
    miqdor  = data.get("miqdor", 0)
    file_id = update.message.photo[-1].file_id
    con = db()
    con.execute(
        "INSERT INTO tolovlar(user_id,miqdor,chek_file_id,tur) VALUES(?,?,?,?)",
        (uid, miqdor, file_id, "balans")
    )
    tid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.commit(); con.close()
    state_clear(uid)
    tg = update.effective_user
    for aid in ADMIN_IDS:
        try:
            await ctx.bot.send_photo(aid, file_id,
                caption=(
                    f"*\ud83d\udcb3 Yangi to'lov so'rovi*\n\n"
                    f"Ism    : {tg.full_name}\n"
                    f"ID     : `{uid}`\n"
                    f"Miqdor : {som(miqdor)} so'm"
                ),
                reply_markup=InlineKeyboardMarkup([
                    [ib("\u2705 Tasdiqlash", f"tok_{tid}_{uid}_{miqdor}", style="success"),
                     ib("\u274c Bekor",      f"tno_{tid}_{uid}_{miqdor}", style="danger")],
                    [ib("\ud83d\udcac Xabar yuborish", f"xyu_{uid}", style="primary")],
                ]),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            log.error(f"Admin xabar xato: {e}")
    await update.message.reply_text(
        "\u2705 Chek yuborildi! Admin tekshirib hisobingizni to'ldiradi. (1\u201330 daqiqa)",
        reply_markup=user_kb()
    )

async def vip_chek(update, ctx, data):
    uid = update.effective_user.id
    if not update.message.photo:
        await update.message.reply_text("Chek rasmini yuboring!")
        return
    tarif_id = data.get("tarif_id", 0)
    file_id  = update.message.photo[-1].file_id
    con = db()
    tarif = con.execute("SELECT * FROM tariflar WHERE id=?", (tarif_id,)).fetchone()
    if not tarif:
        con.close()
        await update.message.reply_text("Tarif topilmadi!")
        state_clear(uid)
        return
    con.execute(
        "INSERT INTO tolovlar(user_id,miqdor,chek_file_id,tur,tarif_id) VALUES(?,?,?,?,?)",
        (uid, tarif["narx"], file_id, "vip", tarif_id)
    )
    tid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.commit(); con.close()
    state_clear(uid)
    tg = update.effective_user
    for aid in ADMIN_IDS:
        try:
            await ctx.bot.send_photo(aid, file_id,
                caption=(
                    f"*\ud83d\udc51 VIP So'rovi*\n\n"
                    f"Ism    : {tg.full_name}\n"
                    f"ID     : `{uid}`\n"
                    f"Tarif  : {tarif['nomi']}\n"
                    f"Narx   : {som(tarif['narx'])} so'm"
                ),
                reply_markup=InlineKeyboardMarkup([
                    [ib("\u2705 VIP Berish", f"vok_{tid}_{uid}_{tarif_id}", style="success"),
                     ib("\u274c Bekor",      f"vno_{tid}_{uid}",            style="danger")],
                    [ib("\ud83d\udcac Xabar yuborish", f"xyu_{uid}", style="primary")],
                ]),
                parse_mode=ParseMode.MARKDOWN
            )
        except: pass
    await update.message.reply_text(
        "\u2705 Chek yuborildi! Tez orada VIP beriladi.",
        reply_markup=user_kb()
    )

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# ADMIN STATE MACHINE \u2014 MATN
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def admin_state_text(update, ctx, state, data, text):
    uid = update.effective_user.id
    msg = update.message

    if state == "k_nomi":
        state_set(uid, "k_rasm", {"nomi": text})
        await msg.reply_text("2. Kino rasmini yuboring (poster):")
        return True

    elif state == "k_kod":
        kod = text.upper()
        con = db()
        if con.execute("SELECT id FROM kinolar WHERE kod=?", (kod,)).fetchone():
            con.close()
            await msg.reply_text("Bu kod mavjud! Boshqa kod kiriting:")
            return True
        con.close()
        data["kod"] = kod
        state_set(uid, "k_davlat", data)
        await msg.reply_text("4. Davlatni kiriting (masalan: Xitoy):")
        return True

    elif state == "k_davlat":
        data["davlat"] = text
        state_set(uid, "k_til", data)
        btns = [
            [ib("\ud83c\uddfa\ud83c\uddff O'zbek tilida", "ktil_uz", style="primary")],
            [ib("\ud83c\uddf7\ud83c\uddfa Rus tilida",    "ktil_ru", style="primary")],
            [ib("\ud83c\uddec\ud83c\udde7 Ingliz tilida", "ktil_en", style="primary")],
        ]
        await msg.reply_text("5. Tilni tanlang:", reply_markup=InlineKeyboardMarkup(btns))
        return True

    elif state == "k_janr":
        data["janr"] = text
        state_set(uid, "k_qism", data)
        await msg.reply_text(
            f"Malumotlar saqlandi:\n{data.get('nomi')} | {data.get('kod')} | {data.get('davlat')}\n\n"
            f"7. 1-qism videosini yuboring:"
        )
        return True

    elif state == "p_nomi":
        data["nomi"] = text
        state_set(uid, "p_qism", data)
        await msg.reply_text("3. Jami qismlar sonini kiriting (masalan: 100):")
        return True

    elif state == "p_qism":
        try:
            data["qism"] = int(text)
        except:
            await msg.reply_text("Raqam kiriting!")
            return True
        state_set(uid, "p_til", data)
        btns = [
            [ib("\ud83c\uddfa\ud83c\uddff O'zbek tilida", "ptil_uz", style="primary")],
            [ib("\ud83c\uddf7\ud83c\uddfa Rus tilida",    "ptil_ru", style="primary")],
        ]
        await msg.reply_text("4. Tilni tanlang:", reply_markup=InlineKeyboardMarkup(btns))
        return True

    elif state == "p_kod":
        data["kod"] = text.upper()
        state_set(uid, "p_tasdiq", data)
        await send_post_preview(msg, ctx, data, uid)
        return True

    elif state == "tarif_nomi":
        state_set(uid, "tarif_narx", {"nomi": text})
        await msg.reply_text("Narxini kiriting (so'mda, masalan: 50000):")
        return True

    elif state == "tarif_narx":
        try:
            data["narx"] = int(text.replace(" ", ""))
        except:
            await msg.reply_text("Raqam kiriting!")
            return True
        state_set(uid, "tarif_kun", data)
        await msg.reply_text("Necha kun amal qiladi:")
        return True

    elif state == "tarif_kun":
        try:
            kun = int(text)
        except:
            await msg.reply_text("Raqam kiriting!")
            return True
        con = db()
        con.execute("INSERT INTO tariflar(nomi,narx,kunlar) VALUES(?,?,?)",
                    (data["nomi"], data["narx"], kun))
        con.commit(); con.close()
        state_clear(uid)
        await msg.reply_text(
            f"\u2705 Tarif qo'shildi!\n{data['nomi']} \u2014 {som(data['narx'])} so'm ({kun} kun)",
            reply_markup=admin_kb()
        )
        return True

    elif state == "karta_raqam":
        state_set(uid, "karta_egasi", {"raqam": text})
        await msg.reply_text("Karta egasini kiriting:")
        return True

    elif state == "karta_egasi":
        con = db()
        con.execute("INSERT INTO kartalar(raqam,egasi) VALUES(?,?)", (data["raqam"], text))
        con.commit(); con.close()
        state_clear(uid)
        await msg.reply_text(
            f"\u2705 Karta qo'shildi!\n`{data['raqam']}` \u2014 {text}",
            reply_markup=admin_kb(), parse_mode=ParseMode.MARKDOWN
        )
        return True

    elif state == "maj_link":
        data["link"] = text
        state_set(uid, "maj_nomi", data)
        await msg.reply_text("Ko'rinadigan nomini kiriting:")
        return True

    elif state == "maj_nomi":
        con = db()
        con.execute("INSERT INTO majburiy(nomi,link,tur) VALUES(?,?,?)",
                    (text, data["link"], data.get("tur", "kanal")))
        con.commit(); con.close()
        state_clear(uid)
        await msg.reply_text(
            f"\u2705 Majburiy obuna qo'shildi!\n{text}: {data['link']}",
            reply_markup=admin_kb()
        )
        return True

    elif state == "xabar_send":
        target = data.get("target", "xall")
        await do_xabar_send(update, ctx, target)
        return True

    elif state == "pulik_kod":
        kod = text.upper()
        con = db()
        kino = con.execute("SELECT * FROM kinolar WHERE kod=?", (kod,)).fetchone()
        con.close()
        if not kino:
            await msg.reply_text("Kino topilmadi! Kodni qayta kiriting:")
            return True
        state_set(uid, "pulik_qism", {"kino_id": kino["id"], "kino_nomi": kino["nomi"]})
        await msg.reply_text(
            f"*{kino['nomi']}*\n\nQaysi qism raqamini pulik qilmoqchisiz? (masalan: 5):",
            parse_mode=ParseMode.MARKDOWN
        )
        return True

    elif state == "pulik_qism":
        try:
            qraqam = int(text)
        except:
            await msg.reply_text("Raqam kiriting!")
            return True
        data["qraqam"] = qraqam
        state_set(uid, "pulik_narx", data)
        await msg.reply_text(f"{qraqam}-qism uchun narxni kiriting (so'mda):")
        return True

    elif state == "pulik_narx":
        try:
            narx = int(text.replace(" ", ""))
        except:
            await msg.reply_text("Raqam kiriting!")
            return True
        con = db()
        con.execute(
            "UPDATE qismlar SET is_vip=1, narx=? WHERE kino_id=? AND qism_raqam=?",
            (narx, data["kino_id"], data["qraqam"])
        )
        con.commit(); con.close()
        state_clear(uid)
        await msg.reply_text(
            f"\u2705 {data['qraqam']}-qism pulik qilindi!\nNarxi: {som(narx)} so'm",
            reply_markup=admin_kb()
        )
        return True

    return False

# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
# ADMIN STATE MACHINE \u2014 MEDIA
# \u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
async def admin_state_media(update, ctx, state, data):
    uid = update.effective_user.id
    msg = update.message

    if state == "k_rasm":
        rasm = msg.photo[-1].file_id if msg.photo else None
        data["rasm"] = rasm
        state_set(uid, "k_kod", data)
        await msg.reply_text(
            "3
