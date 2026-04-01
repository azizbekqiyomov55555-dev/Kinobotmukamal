#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎬 KinoBOT — To'liq ishlaydigan versiya
- Admin panel: ReplyKeyboard menyu (pastda chiqadi)
- /start: rangli inline tugmalar
- Kanal post: rasmlar bilan, "Tomosha qilish" bosa bot ochiladi
- Bot: start bosa kino ma'lumoti + "Yuklab olish" tugmasi
- Yuklab olish: barcha qismlar inline tugma
- Qismni tanlaydi → video yuboriladi
"""

import sqlite3, logging, os, json
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

# ══════════════════════════════════════════════════════════════════
# SOZLAMALAR
# ══════════════════════════════════════════════════════════════════
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS    = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
CHANNEL_ID   = os.environ.get("CHANNEL_ID", "")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "your_bot")

logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
# RANGLI TUGMALAR — Bot API 9.4 (style maydoni)
# ══════════════════════════════════════════════════════════════════
def G(text, cbd):  # Yashil
    return InlineKeyboardButton(text, callback_data=cbd, api_kwargs={"style": "success"})
def R(text, cbd):  # Qizil
    return InlineKeyboardButton(text, callback_data=cbd, api_kwargs={"style": "danger"})
def B(text, cbd):  # Ko'k
    return InlineKeyboardButton(text, callback_data=cbd, api_kwargs={"style": "primary"})
def L(text, url):  # Link (ko'k)
    return InlineKeyboardButton(text, url=url)
def S(text, q):    # Share
    return InlineKeyboardButton(text, switch_inline_query=q)

# ══════════════════════════════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════════════════════════════
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

# ══════════════════════════════════════════════════════════════════
# STATE MACHINE (DB da saqlangani uchun restart bo'lsa ham ishlaydi)
# ══════════════════════════════════════════════════════════════════
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

def state_update(uid, key, val):
    state, data = state_get(uid)
    data[key] = val
    state_set(uid, state, data)

def state_clear(uid):
    con = db()
    con.execute("DELETE FROM states WHERE user_id=?", (uid,))
    con.commit(); con.close()

# ══════════════════════════════════════════════════════════════════
# YORDAMCHI
# ══════════════════════════════════════════════════════════════════
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

def is_admin(uid): return uid in ADMIN_IDS

def is_vip(uid):
    u = get_user(uid)
    if not u or not u["vip_expire"]: return False
    return datetime.fromisoformat(u["vip_expire"]) > datetime.now()

def get_karta():
    con = db()
    k = con.execute("SELECT * FROM kartalar WHERE is_active=1 LIMIT 1").fetchone()
    con.close()
    return k

# ══════════════════════════════════════════════════════════════════
# MAJBURIY OBUNA
# ══════════════════════════════════════════════════════════════════
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
    btns = [[L(f"📢 {r['nomi'] or r['link']}", r["link"])] for r in failed]
    btns.append([G("✅ Tekshirish", "check_sub")])
    await update.effective_message.reply_text(
        "⚠️ *Botdan foydalanish uchun obuna bo'ling:*",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

# ══════════════════════════════════════════════════════════════════
# FOYDALANUVCHI MENYUSI — pastda chiqadigan tugmalar
# ══════════════════════════════════════════════════════════════════
def user_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎬 Kinolar"),     KeyboardButton("🔍 Qidirish")],
        [KeyboardButton("💎 VIP Tariflar"), KeyboardButton("👤 Hisobim")],
    ], resize_keyboard=True)

# ══════════════════════════════════════════════════════════════════
# ADMIN MENYUSI — pastda chiqadigan ReplyKeyboard
# ══════════════════════════════════════════════════════════════════
def admin_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎬 Kino qo'shish"),  KeyboardButton("📢 Kanal post")],
        [KeyboardButton("💎 VIP Tariflar"),    KeyboardButton("💳 Karta qo'shish")],
        [KeyboardButton("🔒 Majburiy obuna"),  KeyboardButton("📊 Statistika")],
        [KeyboardButton("📨 Xabar yuborish"),  KeyboardButton("💰 Pulik qism")],
        [KeyboardButton("🔙 Foydalanuvchi menyu")],
    ], resize_keyboard=True)

# ══════════════════════════════════════════════════════════════════
# /start
# ══════════════════════════════════════════════════════════════════
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
        # Deep link — kod bilan keldi (kanal postdan)
        kod = args[0].upper()
        await show_kino_by_kod(update, ctx, kod, from_start=True)
        return

    btns = [
        [G("🎬 Kinolarni ko'rish", "kinolar_menu"),
         B("🔍 Kino qidirish",     "qidirish")],
        [B("💎 VIP Tariflar",       "vip_menu"),
         G("👤 Hisobim",            "hisobim")],
    ]
    await update.message.reply_text(
        f"🎬 *Xush kelibsiz, {update.effective_user.first_name}!*\n\n"
        "Kino kodini yuboring yoki quyidagi tugmalardan foydalaning:",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )
    # Foydalanuvchi menyusini ham ko'rsatamiz
    await update.message.reply_text(
        "👇 Quyidagi tugmalardan ham foydalanishingiz mumkin:",
        reply_markup=user_kb()
    )

# ══════════════════════════════════════════════════════════════════
# /admin
# ══════════════════════════════════════════════════════════════════
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return
    state_clear(uid)
    await update.message.reply_text(
        "🔧 *Admin Panel*\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=admin_kb(),
        parse_mode=ParseMode.MARKDOWN
    )

# ══════════════════════════════════════════════════════════════════
# KINO KO'RSATISH
# ══════════════════════════════════════════════════════════════════
async def show_kino_by_kod(update, ctx, kod, from_start=False):
    con = db()
    kino = con.execute("SELECT * FROM kinolar WHERE kod=?", (kod,)).fetchone()
    con.close()
    if not kino:
        txt = "❌ Kino topilmadi! Kodni tekshiring."
        if from_start:
            await update.effective_message.reply_text(txt, reply_markup=user_kb())
        else:
            await update.effective_message.reply_text(txt)
        return
    await show_kino(update, ctx, kino, from_start)

async def show_kino(update, ctx, kino, from_start=False):
    """
    /start?KOD orqali kelganda: rasm + ma'lumot + "Yuklab olish" tugmasi
    Oddiy koddan kelganda: xuddi shu
    """
    con = db()
    qismlar = con.execute(
        "SELECT * FROM qismlar WHERE kino_id=? ORDER BY qism_raqam", (kino["id"],)
    ).fetchall()
    con.close()

    jami = len(qismlar)
    joriy = max(q["qism_raqam"] for q in qismlar) if qismlar else 0

    caption = (
        f"🎬 *Nomi: {kino['nomi']}*\n\n"
        f"🎞 Qismi: {joriy}\n"
        f"🌍 Davlati: {kino['davlat'] or 'Xitoy'}\n"
        f"🇺🇿 Tili: {kino['til']}\n"
        f"📅 Yili: {kino['yil'] or datetime.now().year}\n"
        f"🎭 Janri: {kino['janr'] or 'Mini drama'}\n\n"
        f"🍿 @{BOT_USERNAME}"
    )

    btns = [[G(f"📥 Yuklab olish", f"yuklab_{kino['id']}")]]

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

# ══════════════════════════════════════════════════════════════════
# YUKLAB OLISH — barcha qismlar tugmalar bilan
# ══════════════════════════════════════════════════════════════════
async def cb_yuklab(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    kino_id = int(q.data.split("_")[1])
    con = db()
    kino = con.execute("SELECT * FROM kinolar WHERE id=?", (kino_id,)).fetchone()
    qismlar = con.execute(
        "SELECT * FROM qismlar WHERE kino_id=? ORDER BY qism_raqam", (kino_id,)
    ).fetchall()
    con.close()

    if not qismlar:
        await q.message.reply_text("❌ Qismlar hali qo'shilmagan.")
        return

    # Qismlar tugmalari — 3 tadan qator
    btns = []
    row = []
    for i, qism in enumerate(qismlar):
        label = f"{qism['qism_raqam']}-qism"
        if qism["is_vip"]:
            label = f"💎 {label}"
            btn = R(label, f"qism_{qism['id']}")
        else:
            btn = B(label, f"qism_{qism['id']}")
        row.append(btn)
        if len(row) == 3 or i == len(qismlar) - 1:
            btns.append(row)
            row = []

    await q.message.reply_text(
        f"📥 *{kino['nomi']}* — qismni tanlang:",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

# ══════════════════════════════════════════════════════════════════
# QISM YUBORISH
# ══════════════════════════════════════════════════════════════════
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

    # VIP tekshiruv
    if qism["is_vip"] and not is_vip(uid):
        user = get_user(uid)
        balans = user["balans"] if user else 0
        btns = [
            [G(f"💳 Balansdan to'lash ({som(qism['narx'])} so'm)", f"balans_{qism_id}")],
            [B("💎 VIP sotib olish", "vip_menu")],
            [G("💰 Hisobni to'ldirish", "toldirish")],
        ]
        await q.message.reply_text(
            f"🔒 *Bu qism pullik!*\n\n"
            f"💰 Narxi: {som(qism['narx'])} so'm\n"
            f"💼 Balansingiz: {som(balans)} so'm",
            reply_markup=InlineKeyboardMarkup(btns),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    # Allaqachon sotib olinganmi yoki bepulmi — yuborish
    share_txt = f"{kino['nomi']} — {qism['qism_raqam']}-qism\nKod: {kino['kod']}"
    btns = [[S("📤 Do'stlarga ulashish", share_txt)]]

    await q.message.reply_video(
        qism["file_id"],
        caption=(
            f"🎬 *{kino['nomi']}*\n"
            f"📺 {qism['qism_raqam']}-qism\n\n"
            f"🤖 @{BOT_USERNAME}"
        ),
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN,
        protect_content=True
    )

# ══════════════════════════════════════════════════════════════════
# BALANSDAN TO'LOV
# ══════════════════════════════════════════════════════════════════
async def cb_balans(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    qism_id = int(q.data.split("_")[1])

    con = db()
    qism = con.execute("SELECT * FROM qismlar WHERE id=?", (qism_id,)).fetchone()
    kino = con.execute("SELECT * FROM kinolar WHERE id=?", (qism["kino_id"],)).fetchone()
    user = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

    if not user or user["balans"] < qism["narx"]:
        con.close()
        await q.message.reply_text(
            f"❌ Balans yetarli emas!\n"
            f"💰 Kerak: {som(qism['narx'])} so'm\n"
            f"💼 Sizda: {som(user['balans'] if user else 0)} so'm",
            reply_markup=InlineKeyboardMarkup([[G("💳 To'ldirish", "toldirish")]])
        )
        return

    con.execute("UPDATE users SET balans=balans-? WHERE id=?", (qism["narx"], uid))
    con.execute("INSERT INTO xaridlar(user_id,qism_id) VALUES(?,?)", (uid, qism_id))
    con.commit(); con.close()

    share_txt = f"{kino['nomi']} — {qism['qism_raqam']}-qism\nKod: {kino['kod']}"
    await q.message.reply_video(
        qism["file_id"],
        caption=(
            f"✅ To'lov amalga oshirildi!\n"
            f"🎬 *{kino['nomi']}* — {qism['qism_raqam']}-qism"
        ),
        reply_markup=InlineKeyboardMarkup([[S("📤 Do'stlarga ulashish", share_txt)]]),
        parse_mode=ParseMode.MARKDOWN,
        protect_content=True
    )

# ══════════════════════════════════════════════════════════════════
# HISOBIM
# ══════════════════════════════════════════════════════════════════
async def show_hisobim(update, ctx):
    uid = update.effective_user.id
    user = get_user(uid)
    vip_txt = "❌ Yo'q"
    if is_vip(uid):
        exp = datetime.fromisoformat(user["vip_expire"])
        vip_txt = f"✅ {exp.strftime('%d.%m.%Y')} gacha"

    con = db()
    tlist = con.execute(
        "SELECT * FROM tolovlar WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (uid,)
    ).fetchall()
    con.close()

    tarix = ""
    for t in tlist:
        e = {"tasdiqlandi": "✅", "kutilmoqda": "⏳", "bekor": "❌"}.get(t["status"], "❓")
        tarix += f"{e} {som(t['miqdor'])} so'm — {t['created_at'][:10]}\n"

    btns = [[G("💳 Hisobni to'ldirish", "toldirish")]]
    await update.effective_message.reply_text(
        f"👤 *Mening hisobim*\n\n"
        f"🆔 ID: `{uid}`\n"
        f"💰 Balans: *{som(user['balans'] if user else 0)} so'm*\n"
        f"💎 VIP: {vip_txt}\n\n"
        f"📋 *So'nggi to'lovlar:*\n{tarix or 'Hali to\'lov yo\'q'}",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_hisobim(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await show_hisobim(update, ctx)

# ══════════════════════════════════════════════════════════════════
# HISOBNI TO'LDIRISH
# ══════════════════════════════════════════════════════════════════
async def cb_toldirish(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    state_set(uid, "tolov_miqdor")
    await q.message.reply_text(
        "💳 *Qancha miqdorda to'ldirmoqchisiz?*\n\n"
        "Miqdorni so'mda kiriting (masalan: 50000):",
        parse_mode=ParseMode.MARKDOWN
    )

# ══════════════════════════════════════════════════════════════════
# VIP TARIFLAR
# ══════════════════════════════════════════════════════════════════
async def show_vip(update, ctx):
    con = db()
    tariflar = con.execute("SELECT * FROM tariflar WHERE is_active=1").fetchall()
    con.close()
    if not tariflar:
        await update.effective_message.reply_text("💎 Hozirda VIP tariflar mavjud emas.")
        return
    txt = "💎 *VIP Tariflar*\n\n"
    btns = []
    for t in tariflar:
        txt += f"⭐ *{t['nomi']}* — {som(t['narx'])} so'm ({t['kunlar']} kun)\n"
        btns.append([B(f"⭐ {t['nomi']} — {som(t['narx'])} so'm", f"vipbuy_{t['id']}")])
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
        await q.message.reply_text("❌ Karta mavjud emas! Admin bilan bog'laning.")
        return
    state_set(uid, "vip_chek", {"tarif_id": tarif_id})
    await q.message.reply_text(
        f"💎 *{tarif['nomi']}* sotib olish\n\n"
        f"💰 Narxi: {som(tarif['narx'])} so'm\n"
        f"📅 Muddat: {tarif['kunlar']} kun\n\n"
        f"💳 Karta raqami:\n`{k['raqam']}`\n"
        f"👤 Egasi: {k['egasi'] or '-'}\n\n"
        f"To'lovni amalga oshirib, *chek rasmini* yuboring:",
        parse_mode=ParseMode.MARKDOWN
    )

# ══════════════════════════════════════════════════════════════════
# CHECK_SUB CALLBACK
# ══════════════════════════════════════════════════════════════════
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
        await q.message.reply_text("✅ Obuna tasdiqlandi!", reply_markup=user_kb())

# ══════════════════════════════════════════════════════════════════
# KINOLAR MENYU
# ══════════════════════════════════════════════════════════════════
async def cb_kinolar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text(
        "🔍 Kino *kodini* kiriting (masalan: OMADLIZARBA):",
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_qidirish(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.message.reply_text("🔍 Kino kodini kiriting:")

# ══════════════════════════════════════════════════════════════════
# TO'LOV TASDIQLASH/BEKOR (ADMIN)
# ══════════════════════════════════════════════════════════════════
async def cb_tok(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    parts = q.data.split("_")  # tok_tid_uid_miqdor
    tid, uid, miqdor = int(parts[1]), int(parts[2]), int(parts[3])
    con = db()
    con.execute("UPDATE tolovlar SET status='tasdiqlandi' WHERE id=?", (tid,))
    con.execute("UPDATE users SET balans=balans+? WHERE id=?", (miqdor, uid))
    con.commit(); con.close()
    await q.edit_message_caption(
        (q.message.caption or "") + f"\n\n✅ *TASDIQLANDI* — {datetime.now().strftime('%H:%M')}",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        await ctx.bot.send_message(uid,
            f"✅ *Hisobingiz to'ldirildi!*\n💰 +{som(miqdor)} so'm",
            parse_mode=ParseMode.MARKDOWN)
    except: pass

async def cb_tno(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    parts = q.data.split("_")  # tno_tid_uid_miqdor
    tid, uid, miqdor = int(parts[1]), int(parts[2]), int(parts[3])
    con = db()
    con.execute("UPDATE tolovlar SET status='bekor' WHERE id=?", (tid,))
    con.commit(); con.close()
    await q.edit_message_caption(
        (q.message.caption or "") + f"\n\n❌ *BEKOR* — {datetime.now().strftime('%H:%M')}",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        await ctx.bot.send_message(uid, f"❌ To'lov bekor qilindi. ({som(miqdor)} so'm)")
    except: pass

# VIP tasdiqlash
async def cb_vok(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    parts = q.data.split("_")  # vok_tid_uid_tarifid
    tid, uid, tarif_id = int(parts[1]), int(parts[2]), int(parts[3])
    con = db()
    tarif = con.execute("SELECT * FROM tariflar WHERE id=?", (tarif_id,)).fetchone()
    user = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
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
        (q.message.caption or "") + f"\n\n✅ *VIP BERILDI* — {expire.strftime('%d.%m.%Y')} gacha",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        await ctx.bot.send_message(uid,
            f"🎉 *VIP faollashtirildi!*\n⭐ {tarif['nomi']}\n📅 {expire.strftime('%d.%m.%Y')} gacha",
            parse_mode=ParseMode.MARKDOWN)
    except: pass

async def cb_vno(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    parts = q.data.split("_")  # vno_tid_uid
    tid, uid = int(parts[1]), int(parts[2])
    con = db()
    con.execute("UPDATE tolovlar SET status='bekor' WHERE id=?", (tid,))
    con.commit(); con.close()
    await q.edit_message_caption(
        (q.message.caption or "") + "\n\n❌ *BEKOR QILINDI*", parse_mode=ParseMode.MARKDOWN
    )
    try: await ctx.bot.send_message(uid, "❌ VIP so'rovingiz bekor qilindi.")
    except: pass

# Admin xabar yuborish
async def cb_xyu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    target = int(q.data.split("_")[1])
    state_set(q.from_user.id, "xabar_send", {"target": str(target)})
    await q.message.reply_text(f"📨 Foydalanuvchi ({target}) ga xabar yuboring:")

# ══════════════════════════════════════════════════════════════════
# MATN XABAR HANDLERI — barcha matnlar shu yerdan
# ══════════════════════════════════════════════════════════════════
async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    uid = update.effective_user.id
    text = (update.message.text or "").strip()

    # Majburiy obuna
    failed = await check_sub(ctx.bot, uid)
    if failed:
        await send_sub_msg(update, failed)
        return

    state, data = state_get(uid)

    # ── Admin menyu tugmalari ──────────────────────────────────────
    if is_admin(uid) and not state:
        if text == "🎬 Kino qo'shish":
            state_set(uid, "k_nomi", {})
            await update.message.reply_text(
                "🎬 *Kino qo'shish*\n\n1️⃣ Kino *nomini* kiriting:",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        elif text == "📢 Kanal post":
            state_set(uid, "p_rasm", {})
            await update.message.reply_text(
                "📢 *Kanal Post*\n\n1️⃣ Kino *rasmini* yuboring:",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        elif text == "💎 VIP Tariflar":
            await show_vip_admin(update, ctx)
            return
        elif text == "💳 Karta qo'shish":
            await show_kartalar(update, ctx)
            return
        elif text == "🔒 Majburiy obuna":
            await show_majburiy(update, ctx)
            return
        elif text == "📊 Statistika":
            await show_stat(update, ctx)
            return
        elif text == "📨 Xabar yuborish":
            await show_xabar_menu(update, ctx)
            return
        elif text == "💰 Pulik qism":
            state_set(uid, "pulik_kod", {})
            await update.message.reply_text(
                "💰 *Pulik qism*\n\nKino *kodini* kiriting:",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        elif text == "🔙 Foydalanuvchi menyu":
            state_clear(uid)
            await update.message.reply_text(
                "👤 Foydalanuvchi menyusi:",
                reply_markup=user_kb()
            )
            return

    # ── Admin state machine ────────────────────────────────────────
    if is_admin(uid) and state:
        handled = await admin_state_text(update, ctx, state, data, text)
        if handled:
            return

    # ── Foydalanuvchi state machine ────────────────────────────────
    if state == "tolov_miqdor":
        await tolov_miqdor(update, ctx, text)
        return
    if state and state.startswith("xabar_send"):
        target = data.get("target", "all")
        await do_xabar_send(update, ctx, target)
        return

    # ── Foydalanuvchi menyu tugmalari ──────────────────────────────
    if text == "👤 Hisobim":
        await show_hisobim(update, ctx)
    elif text == "💎 VIP Tariflar":
        await show_vip(update, ctx)
    elif text in ("🎬 Kinolar", "🔍 Qidirish"):
        await update.message.reply_text("🔍 Kino kodini kiriting:")
    else:
        # Kod orqali kino qidirish
        kod = text.upper()
        await show_kino_by_kod(update, ctx, kod)

# ══════════════════════════════════════════════════════════════════
# MEDIA HANDLER (rasm, video)
# ══════════════════════════════════════════════════════════════════
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
        target = data.get("target", "all")
        await do_xabar_send(update, ctx, target)

# ══════════════════════════════════════════════════════════════════
# TO'LOV QADAMLARI
# ══════════════════════════════════════════════════════════════════
async def tolov_miqdor(update, ctx, text):
    uid = update.effective_user.id
    try:
        miqdor = int(text.replace(" ", "").replace(",", ""))
        if miqdor < 1000: raise ValueError
    except:
        await update.message.reply_text("❌ Kamida 1 000 so'm kiriting:")
        return
    k = get_karta()
    if not k:
        await update.message.reply_text("❌ Karta mavjud emas. Admin bilan bog'laning.")
        state_clear(uid)
        return
    state_set(uid, "tolov_chek", {"miqdor": miqdor})
    await update.message.reply_text(
        f"💳 *To'lov ma'lumotlari:*\n\n"
        f"📱 Karta raqami:\n`{k['raqam']}`\n"
        f"👤 Egasi: {k['egasi'] or '-'}\n"
        f"💰 Miqdor: *{som(miqdor)} so'm*\n\n"
        f"✅ To'lovni amalga oshirib, *chek rasmini* yuboring:",
        parse_mode=ParseMode.MARKDOWN
    )

async def tolov_chek(update, ctx, data):
    uid = update.effective_user.id
    if not update.message.photo:
        await update.message.reply_text("❌ Chek *rasmini* yuboring!", parse_mode=ParseMode.MARKDOWN)
        return
    miqdor = data.get("miqdor", 0)
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
                    f"💳 *Yangi to'lov so'rovi*\n\n"
                    f"👤 {tg.full_name}\n"
                    f"🆔 `{uid}`\n"
                    f"💰 {som(miqdor)} so'm"
                ),
                reply_markup=InlineKeyboardMarkup([
                    [G("✅ Tasdiqlash", f"tok_{tid}_{uid}_{miqdor}"),
                     R("❌ Bekor", f"tno_{tid}_{uid}_{miqdor}")],
                    [B("💬 Xabar yuborish", f"xyu_{uid}")],
                ]),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            log.error(f"Admin xabar xato: {e}")
    await update.message.reply_text(
        "✅ Chek yuborildi! Admin tekshirib hisobingizni to'ldiradi.\n⏳ 1–30 daqiqa.",
        reply_markup=user_kb()
    )

async def vip_chek(update, ctx, data):
    uid = update.effective_user.id
    if not update.message.photo:
        await update.message.reply_text("❌ Chek rasmini yuboring!")
        return
    tarif_id = data.get("tarif_id", 0)
    file_id = update.message.photo[-1].file_id
    con = db()
    tarif = con.execute("SELECT * FROM tariflar WHERE id=?", (tarif_id,)).fetchone()
    if not tarif:
        con.close()
        await update.message.reply_text("❌ Tarif topilmadi!")
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
                    f"💎 *VIP So'rovi*\n\n"
                    f"👤 {tg.full_name}\n"
                    f"🆔 `{uid}`\n"
                    f"⭐ Tarif: {tarif['nomi']}\n"
                    f"💰 {som(tarif['narx'])} so'm"
                ),
                reply_markup=InlineKeyboardMarkup([
                    [G("✅ VIP Berish", f"vok_{tid}_{uid}_{tarif_id}"),
                     R("❌ Bekor", f"vno_{tid}_{uid}")],
                    [B("💬 Xabar yuborish", f"xyu_{uid}")],
                ]),
                parse_mode=ParseMode.MARKDOWN
            )
        except: pass
    await update.message.reply_text(
        "✅ Chek yuborildi! Tez orada VIP beriladi.", reply_markup=user_kb()
    )

# ══════════════════════════════════════════════════════════════════
# ADMIN STATE MACHINE — MATN
# ══════════════════════════════════════════════════════════════════
async def admin_state_text(update, ctx, state, data, text):
    uid = update.effective_user.id
    msg = update.message

    # ── KINO QO'SHISH ──────────────────────────────────────────────
    if state == "k_nomi":
        state_set(uid, "k_rasm", {"nomi": text})
        await msg.reply_text("2️⃣ Kino *rasmini* yuboring (poster):", parse_mode=ParseMode.MARKDOWN)
        return True

    elif state == "k_kod":
        kod = text.upper()
        con = db()
        if con.execute("SELECT id FROM kinolar WHERE kod=?", (kod,)).fetchone():
            con.close()
            await msg.reply_text("❌ Bu kod mavjud! Boshqa kod kiriting:")
            return True
        con.close()
        data["kod"] = kod
        state_set(uid, "k_davlat", data)
        await msg.reply_text("4️⃣ *Davlatni* kiriting (masalan: Xitoy):", parse_mode=ParseMode.MARKDOWN)
        return True

    elif state == "k_davlat":
        data["davlat"] = text
        state_set(uid, "k_til", data)
        btns = [
            [B("🇺🇿 O'zbek tilida", "ktil_uz")],
            [B("🇷🇺 Rus tilida",    "ktil_ru")],
            [B("🇬🇧 Ingliz tilida", "ktil_en")],
        ]
        await msg.reply_text("5️⃣ *Tilni* tanlang:", reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)
        return True

    elif state == "k_janr":
        data["janr"] = text
        state_set(uid, "k_qism", data)
        await msg.reply_text(
            f"✅ Ma'lumotlar saqlandi:\n"
            f"📽 {data.get('nomi')} | 🔑 {data.get('kod')} | 🌍 {data.get('davlat')}\n"
            f"🎭 {text}\n\n7️⃣ 1-qism *videosini* yuboring:",
            parse_mode=ParseMode.MARKDOWN
        )
        return True

    # ── KANAL POST ──────────────────────────────────────────────────
    elif state == "p_nomi":
        data["nomi"] = text
        state_set(uid, "p_qism", data)
        await msg.reply_text("3️⃣ Jami *qismlar sonini* kiriting (masalan: 100):", parse_mode=ParseMode.MARKDOWN)
        return True

    elif state == "p_qism":
        try:
            data["qism"] = int(text)
        except:
            await msg.reply_text("❌ Raqam kiriting!")
            return True
        state_set(uid, "p_til", data)
        btns = [
            [B("🇺🇿 O'zbek tilida", "ptil_uz")],
            [B("🇷🇺 Rus tilida",    "ptil_ru")],
        ]
        await msg.reply_text("4️⃣ *Tilni* tanlang:", reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)
        return True

    elif state == "p_kod":
        data["kod"] = text.upper()
        state_set(uid, "p_tasdiq", data)
        await send_post_preview(msg, ctx, data, uid)
        return True

    # ── TARIF ──────────────────────────────────────────────────────
    elif state == "tarif_nomi":
        state_set(uid, "tarif_narx", {"nomi": text})
        await msg.reply_text("💰 Narxini kiriting (so'mda, masalan: 50000):")
        return True

    elif state == "tarif_narx":
        try:
            data["narx"] = int(text.replace(" ", ""))
        except:
            await msg.reply_text("❌ Raqam kiriting!")
            return True
        state_set(uid, "tarif_kun", data)
        await msg.reply_text("📅 Necha kun amal qiladi:")
        return True

    elif state == "tarif_kun":
        try:
            kun = int(text)
        except:
            await msg.reply_text("❌ Raqam kiriting!")
            return True
        con = db()
        con.execute("INSERT INTO tariflar(nomi,narx,kunlar) VALUES(?,?,?)",
                    (data["nomi"], data["narx"], kun))
        con.commit(); con.close()
        state_clear(uid)
        await msg.reply_text(
            f"✅ Tarif qo'shildi!\n⭐ {data['nomi']} — {som(data['narx'])} so'm ({kun} kun)",
            reply_markup=admin_kb()
        )
        return True

    # ── KARTA ──────────────────────────────────────────────────────
    elif state == "karta_raqam":
        state_set(uid, "karta_egasi", {"raqam": text})
        await msg.reply_text("👤 Karta *egasini* kiriting:", parse_mode=ParseMode.MARKDOWN)
        return True

    elif state == "karta_egasi":
        con = db()
        con.execute("INSERT INTO kartalar(raqam,egasi) VALUES(?,?)", (data["raqam"], text))
        con.commit(); con.close()
        state_clear(uid)
        await msg.reply_text(
            f"✅ Karta qo'shildi!\n💳 `{data['raqam']}` — {text}",
            reply_markup=admin_kb(), parse_mode=ParseMode.MARKDOWN
        )
        return True

    # ── MAJBURIY OBUNA ─────────────────────────────────────────────
    elif state == "maj_link":
        data["link"] = text
        state_set(uid, "maj_nomi", data)
        await msg.reply_text("📝 Ko'rinadigan *nomini* kiriting:", parse_mode=ParseMode.MARKDOWN)
        return True

    elif state == "maj_nomi":
        con = db()
        con.execute("INSERT INTO majburiy(nomi,link,tur) VALUES(?,?,?)",
                    (text, data["link"], data.get("tur", "kanal")))
        con.commit(); con.close()
        state_clear(uid)
        await msg.reply_text(
            f"✅ Majburiy obuna qo'shildi!\n🔒 {text}: {data['link']}",
            reply_markup=admin_kb()
        )
        return True

    # ── XABAR YUBORISH ─────────────────────────────────────────────
    elif state == "xabar_send":
        target = data.get("target", "all")
        await do_xabar_send(update, ctx, target)
        return True

    # ── PULIK QISM ─────────────────────────────────────────────────
    elif state == "pulik_kod":
        kod = text.upper()
        con = db()
        kino = con.execute("SELECT * FROM kinolar WHERE kod=?", (kod,)).fetchone()
        con.close()
        if not kino:
            await msg.reply_text("❌ Kino topilmadi! Kodni qayta kiriting:")
            return True
        state_set(uid, "pulik_qism", {"kino_id": kino["id"], "kino_nomi": kino["nomi"]})
        await msg.reply_text(
            f"🎬 *{kino['nomi']}*\n\n"
            "Qaysi qism raqamini pulik qilmoqchisiz? (masalan: 5):",
            parse_mode=ParseMode.MARKDOWN
        )
        return True

    elif state == "pulik_qism":
        try:
            qraqam = int(text)
        except:
            await msg.reply_text("❌ Raqam kiriting!")
            return True
        data["qraqam"] = qraqam
        state_set(uid, "pulik_narx", data)
        await msg.reply_text(f"💰 {qraqam}-qism uchun narxni kiriting (so'mda):")
        return True

    elif state == "pulik_narx":
        try:
            narx = int(text.replace(" ", ""))
        except:
            await msg.reply_text("❌ Raqam kiriting!")
            return True
        con = db()
        con.execute(
            "UPDATE qismlar SET is_vip=1, narx=? WHERE kino_id=? AND qism_raqam=?",
            (narx, data["kino_id"], data["qraqam"])
        )
        con.commit(); con.close()
        state_clear(uid)
        await msg.reply_text(
            f"✅ {data['qraqam']}-qism pulik qilindi!\n💰 Narxi: {som(narx)} so'm",
            reply_markup=admin_kb()
        )
        return True

    return False  # Handled bo'lmadi

# ══════════════════════════════════════════════════════════════════
# ADMIN STATE MACHINE — MEDIA
# ══════════════════════════════════════════════════════════════════
async def admin_state_media(update, ctx, state, data):
    uid = update.effective_user.id
    msg = update.message

    if state == "k_rasm":
        rasm = msg.photo[-1].file_id if msg.photo else None
        data["rasm"] = rasm
        state_set(uid, "k_kod", data)
        await msg.reply_text(
            "3️⃣ Kino *kodini* kiriting (masalan: OMADLIZARBA):\n"
            "⚠️ Faqat katta harf va raqam:",
            parse_mode=ParseMode.MARKDOWN
        )

    elif state == "k_qism":
        if not (msg.video or msg.document):
            await msg.reply_text("❌ Video yuboring!")
            return
        file_id = (msg.video or msg.document).file_id
        qismlar = data.get("qismlar", [])
        qismlar.append(file_id)
        data["qismlar"] = qismlar
        qn = len(qismlar)
        state_set(uid, "k_qism", data)
        btns = [
            [B(f"➕ Yana qism qo'shish ({qn+1}-qism)", "qism_yana")],
            [G("✅ Tugatish va saqlash",                 "qism_save")],
        ]
        await msg.reply_text(
            f"✅ {qn}-qism qo'shildi!",
            reply_markup=InlineKeyboardMarkup(btns)
        )

    elif state == "p_rasm":
        if not msg.photo:
            await msg.reply_text("❌ Rasm yuboring!")
            return
        data["rasm"] = msg.photo[-1].file_id
        state_set(uid, "p_nomi", data)
        await msg.reply_text("2️⃣ Kino *nomini* kiriting:", parse_mode=ParseMode.MARKDOWN)

# ══════════════════════════════════════════════════════════════════
# INLINE CALLBACKS — TIL TANLASH
# ══════════════════════════════════════════════════════════════════
async def cb_ktil(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    til_map = {"ktil_uz": "O'zbek tilida", "ktil_ru": "Rus tilida", "ktil_en": "Ingliz tilida"}
    til = til_map.get(q.data, "O'zbek tilida")
    state, data = state_get(uid)
    data["til"] = til
    state_set(uid, "k_janr", data)
    await q.message.reply_text("6️⃣ *Janrini* kiriting (masalan: Mini drama):", parse_mode=ParseMode.MARKDOWN)

async def cb_ptil(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    til_map = {"ptil_uz": "O'zbek tilida", "ptil_ru": "Rus tilida"}
    til = til_map.get(q.data, "O'zbek tilida")
    state, data = state_get(uid)
    data["til"] = til
    state_set(uid, "p_kod", data)
    await q.message.reply_text(
        "5️⃣ Bot *kodini* kiriting\n"
        "(foydalanuvchi botga shu kodni kiritganda kino chiqadi):",
        parse_mode=ParseMode.MARKDOWN
    )

# ══════════════════════════════════════════════════════════════════
# QISM YANA / SAVE
# ══════════════════════════════════════════════════════════════════
async def cb_qism_yana(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    _, data = state_get(uid)
    n = len(data.get("qismlar", [])) + 1
    await q.message.reply_text(f"📹 {n}-qism *videosini* yuboring:", parse_mode=ParseMode.MARKDOWN)

async def cb_qism_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    _, data = state_get(uid)
    nomi   = data.get("nomi", "Nomsiz")
    rasm   = data.get("rasm") or None
    kod    = data.get("kod", "KOD")
    davlat = data.get("davlat", "Xitoy")
    til    = data.get("til", "O'zbek tilida")
    janr   = data.get("janr", "Mini drama")
    qismlar = data.get("qismlar", [])
    con = db()
    con.execute(
        "INSERT INTO kinolar(nomi,kod,rasm_file_id,til,janr,davlat,yil) VALUES(?,?,?,?,?,?,?)",
        (nomi, kod, rasm, til, janr, davlat, datetime.now().year)
    )
    kino_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    for i, fid in enumerate(qismlar):
        con.execute(
            "INSERT INTO qismlar(kino_id,qism_raqam,file_id) VALUES(?,?,?)",
            (kino_id, i+1, fid)
        )
    con.commit(); con.close()
    state_clear(uid)
    await q.message.reply_text(
        f"✅ *Kino saqlandi!*\n\n"
        f"🎬 {nomi}\n🔑 Kod: `{kod}`\n📹 {len(qismlar)} ta qism\n\n"
        f"Foydalanuvchilar {kod} kodni botga yozib ko'rishi mumkin.",
        reply_markup=admin_kb(),
        parse_mode=ParseMode.MARKDOWN
    )

# ══════════════════════════════════════════════════════════════════
# KANAL POST PREVIEW VA YUBORISH
# ══════════════════════════════════════════════════════════════════
async def send_post_preview(msg, ctx, data, uid):
    """Post ko'rinishini ko'rsatish"""
    nomi  = data.get("nomi", "")
    qism  = data.get("qism", 0)
    til   = data.get("til", "O'zbek tilida")
    kod   = data.get("kod", "")
    rasm  = data.get("rasm", "")

    caption = (
        f"🎬 *{nomi}*\n\n"
        f"▶ Qism : {qism}\n"
        f"▶ Janrlari : Mini drama\n"
        f"▶ Tili : {til}\n"
        f"▶ Ko'rish : [Tomosha qilish](https://t.me/{BOT_USERNAME}?start={kod})"
    )

    # Kanal tugmasi
    kanal_btns = [[L("🎬 Tomosha qilish 🎬", f"https://t.me/{BOT_USERNAME}?start={kod}")]]

    await msg.reply_photo(
        rasm,
        caption=caption + "\n\n⬆️ *Ko'rinishi shunaqa. Kanalga yuborilsinmi?*",
        reply_markup=InlineKeyboardMarkup([
            [G("✅ Kanalga yuborish", f"postsend_{uid}"),
             R("❌ Bekor", "ap_back")],
        ]),
        parse_mode=ParseMode.MARKDOWN
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

    caption = (
        f"🎬 *{nomi}*\n\n"
        f"▶ Qism : {qism}\n"
        f"▶ Janrlari : Mini drama\n"
        f"▶ Tili : {til}\n"
        f"▶ Ko'rish : [Tomosha qilish](https://t.me/{BOT_USERNAME}?start={kod})"
    )
    kanal_btns = [[L("🎬 Tomosha qilish 🎬", f"https://t.me/{BOT_USERNAME}?start={kod}")]]

    try:
        await ctx.bot.send_photo(
            CHANNEL_ID, rasm,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(kanal_btns),
            parse_mode=ParseMode.MARKDOWN
        )
        state_clear(uid)
        await q.message.reply_text(
            "✅ Post kanalga yuborildi!",
            reply_markup=admin_kb()
        )
    except Exception as e:
        await q.message.reply_text(
            f"❌ Xato: {e}\n\n"
            f"CHANNEL_ID ni tekshiring: `{CHANNEL_ID}`\n"
            f"Bot kanalga admin bo'lishi kerak!",
            parse_mode=ParseMode.MARKDOWN
        )

async def cb_ap_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    state_clear(q.from_user.id)
    await q.message.reply_text("🔧 Admin Panel:", reply_markup=admin_kb())

# ══════════════════════════════════════════════════════════════════
# ADMIN — VIP TARIFLAR PANEL
# ══════════════════════════════════════════════════════════════════
async def show_vip_admin(update, ctx):
    con = db()
    tariflar = con.execute("SELECT * FROM tariflar WHERE is_active=1").fetchall()
    con.close()
    txt = "💎 *VIP Tariflar*\n\n"
    btns = []
    for t in tariflar:
        txt += f"⭐ {t['nomi']} — {som(t['narx'])} so'm ({t['kunlar']} kun)\n"
        btns.append([R(f"🗑 {t['nomi']} o'chirish", f"tdel_{t['id']}")])
    btns.append([G("➕ Yangi tarif qo'shish", "tadd")])
    await update.message.reply_text(
        txt or "💎 Tariflar yo'q",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_tadd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    state_set(q.from_user.id, "tarif_nomi", {})
    await q.message.reply_text("💎 Tarif *nomini* kiriting (masalan: 1 oylik):", parse_mode=ParseMode.MARKDOWN)

async def cb_tdel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    tid = int(q.data.split("_")[1])
    con = db()
    con.execute("UPDATE tariflar SET is_active=0 WHERE id=?", (tid,))
    con.commit(); con.close()
    await q.message.reply_text("✅ Tarif o'chirildi!", reply_markup=admin_kb())

# ══════════════════════════════════════════════════════════════════
# ADMIN — KARTALAR PANEL
# ══════════════════════════════════════════════════════════════════
async def show_kartalar(update, ctx):
    con = db()
    kartalar = con.execute("SELECT * FROM kartalar WHERE is_active=1").fetchall()
    con.close()
    txt = "💳 *Kartalar*\n\n"
    btns = []
    for k in kartalar:
        txt += f"• `{k['raqam']}` — {k['egasi'] or '-'}\n"
        btns.append([R(f"🗑 {k['raqam']}", f"kdel_{k['id']}")])
    btns.append([G("➕ Karta qo'shish", "kadd")])
    await update.message.reply_text(
        txt or "💳 Kartalar yo'q",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_kadd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    state_set(q.from_user.id, "karta_raqam", {})
    await q.message.reply_text("💳 Karta *raqamini* kiriting (8600 1234 5678 9012):", parse_mode=ParseMode.MARKDOWN)

async def cb_kdel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    kid = int(q.data.split("_")[1])
    con = db()
    con.execute("UPDATE kartalar SET is_active=0 WHERE id=?", (kid,))
    con.commit(); con.close()
    await q.message.reply_text("✅ Karta o'chirildi!", reply_markup=admin_kb())

# ══════════════════════════════════════════════════════════════════
# ADMIN — MAJBURIY OBUNA PANEL
# ══════════════════════════════════════════════════════════════════
async def show_majburiy(update, ctx):
    con = db()
    rows = con.execute("SELECT * FROM majburiy WHERE is_active=1").fetchall()
    con.close()
    txt = "🔒 *Majburiy Obunalar*\n\n"
    btns = []
    for r in rows:
        txt += f"• {r['nomi'] or r['link']} ({r['tur']})\n"
        btns.append([R(f"🗑 {r['nomi'] or r['link']}", f"mdel_{r['id']}")])
    btns.append([G("➕ Qo'shish", "madd")])
    await update.message.reply_text(
        txt or "🔒 Majburiy obunalar yo'q",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_madd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    btns = [
        [B("📢 Telegram kanal", "mtur_kanal")],
        [B("🔗 Oddiy link",     "mtur_link")],
    ]
    await q.message.reply_text("Tur tanlang:", reply_markup=InlineKeyboardMarkup(btns))

async def cb_mtur(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    tur = q.data.split("_")[1]
    state_set(q.from_user.id, "maj_link", {"tur": tur})
    await q.message.reply_text("🔗 Link kiriting (masalan: @kanal_username yoki https://...):")

async def cb_mdel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    mid = int(q.data.split("_")[1])
    con = db()
    con.execute("UPDATE majburiy SET is_active=0 WHERE id=?", (mid,))
    con.commit(); con.close()
    await q.message.reply_text("✅ O'chirildi!", reply_markup=admin_kb())

# ══════════════════════════════════════════════════════════════════
# ADMIN — STATISTIKA
# ══════════════════════════════════════════════════════════════════
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
    top_txt = "\n".join(f"{i+1}. {u['full_name'] or u['id']} — {som(u['balans'])} so'm"
                        for i, u in enumerate(top15))
    await update.message.reply_text(
        f"📊 *Statistika*\n\n"
        f"👥 Jami foydalanuvchi: {jami}\n"
        f"📅 Bu oy yangi: +{yangi}\n"
        f"💎 Aktiv VIP: {vips}\n"
        f"💰 Bu oy daromad: {som(daromad)} so'm\n"
        f"🔄 Bu hafta to'ldirgan: {haf_tol} kishi\n\n"
        f"🏆 *Top 15 balans:*\n{top_txt or 'Ma\'lumot yo\'q'}",
        reply_markup=admin_kb(),
        parse_mode=ParseMode.MARKDOWN
    )

# ══════════════════════════════════════════════════════════════════
# ADMIN — XABAR YUBORISH
# ══════════════════════════════════════════════════════════════════
async def show_xabar_menu(update, ctx):
    btns = [
        [G("👥 Hammaga",       "xall")],
        [B("💎 Faqat VIP",     "xvip"),
         B("🆓 Bepul",         "xfree")],
    ]
    await update.message.reply_text(
        "📨 *Kimga xabar yuborish?*",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_xabar_target(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    target = q.data  # xall / xvip / xfree
    state_set(q.from_user.id, "xabar_send", {"target": target})
    await q.message.reply_text("📨 Xabar yuboring (matn, rasm yoki video):")

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
    await msg.reply_text(f"✅ {sent} ta foydalanuvchiga yuborildi.", reply_markup=admin_kb())

# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    if not BOT_TOKEN:
        raise RuntimeError("❌ BOT_TOKEN o'rnatilmagan!")

    db_init()
    log.info("✅ DB tayyor. Bot ishga tushmoqda...")

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))

    # Inline callbacks
    app.add_handler(CallbackQueryHandler(cb_check_sub,    pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(cb_hisobim,      pattern="^hisobim$"))
    app.add_handler(CallbackQueryHandler(cb_toldirish,    pattern="^toldirish$"))
    app.add_handler(CallbackQueryHandler(cb_vip_menu,     pattern="^vip_menu$"))
    app.add_handler(CallbackQueryHandler(cb_vipbuy,       pattern=r"^vipbuy_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_yuklab,       pattern=r"^yuklab_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_qism,         pattern=r"^qism_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_balans,       pattern=r"^balans_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_tok,          pattern="^tok_"))
    app.add_handler(CallbackQueryHandler(cb_tno,          pattern="^tno_"))
    app.add_handler(CallbackQueryHandler(cb_vok,          pattern="^vok_"))
    app.add_handler(CallbackQueryHandler(cb_vno,          pattern="^vno_"))
    app.add_handler(CallbackQueryHandler(cb_xyu,          pattern="^xyu_"))
    app.add_handler(CallbackQueryHandler(cb_kinolar,      pattern="^kinolar_menu$"))
    app.add_handler(CallbackQueryHandler(cb_qidirish,     pattern="^qidirish$"))
    # Admin
    app.add_handler(CallbackQueryHandler(cb_ap_back,      pattern="^ap_back$"))
    app.add_handler(CallbackQueryHandler(cb_ktil,         pattern="^ktil_"))
    app.add_handler(CallbackQueryHandler(cb_ptil,         pattern="^ptil_"))
    app.add_handler(CallbackQueryHandler(cb_qism_yana,    pattern="^qism_yana$"))
    app.add_handler(CallbackQueryHandler(cb_qism_save,    pattern="^qism_save$"))
    app.add_handler(CallbackQueryHandler(cb_postsend,     pattern="^postsend_"))
    app.add_handler(CallbackQueryHandler(cb_tadd,         pattern="^tadd$"))
    app.add_handler(CallbackQueryHandler(cb_tdel,         pattern="^tdel_"))
    app.add_handler(CallbackQueryHandler(cb_kadd,         pattern="^kadd$"))
    app.add_handler(CallbackQueryHandler(cb_kdel,         pattern="^kdel_"))
    app.add_handler(CallbackQueryHandler(cb_madd,         pattern="^madd$"))
    app.add_handler(CallbackQueryHandler(cb_mtur,         pattern="^mtur_"))
    app.add_handler(CallbackQueryHandler(cb_mdel,         pattern="^mdel_"))
    app.add_handler(CallbackQueryHandler(cb_xabar_target, pattern="^x(all|vip|free)$"))

    # Media handler
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.Document.VIDEO | filters.VOICE,
        on_media
    ))

    # Matn handler
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        on_text
    ))

    log.info("🤖 Bot tayyor!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
