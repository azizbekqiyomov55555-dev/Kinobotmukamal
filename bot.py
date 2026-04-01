#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎬 KinoBOT — To'liq versiya
Railway + SQLite + Rangli tugmalar (Bot API 9.4)
"""

import sqlite3, logging, os
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

# ═══════════════════════════════════════════════════════════════════
# SOZLAMALAR — Railway Environment Variables
# ═══════════════════════════════════════════════════════════════════
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
ADMIN_IDS    = [int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
CHANNEL_ID   = os.environ.get("CHANNEL_ID", "")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "your_bot")

logging.basicConfig(
    format="%(asctime)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
# RANGLI TUGMALAR — Bot API 9.4 style maydoni
# ═══════════════════════════════════════════════════════════════════
def btn_green(text, cbd):
    """✅ Yashil — tasdiqlash, saqlash"""
    return InlineKeyboardButton(text, callback_data=cbd,
                                api_kwargs={"style": "success"})

def btn_red(text, cbd):
    """🔴 Qizil — bekor, o'chirish, xavfli"""
    return InlineKeyboardButton(text, callback_data=cbd,
                                api_kwargs={"style": "danger"})

def btn_blue(text, cbd):
    """🔵 Ko'k — asosiy amallar"""
    return InlineKeyboardButton(text, callback_data=cbd,
                                api_kwargs={"style": "primary"})

def btn_link(text, url):
    return InlineKeyboardButton(text, url=url)

def btn_share(text, query):
    return InlineKeyboardButton(text, switch_inline_query=query)

# ═══════════════════════════════════════════════════════════════════
# MA'LUMOTLAR BAZASI
# ═══════════════════════════════════════════════════════════════════
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
        janr TEXT,
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
        narx INTEGER DEFAULT 0,
        FOREIGN KEY(kino_id) REFERENCES kinolar(id)
    );
    CREATE TABLE IF NOT EXISTS foydalanuvchilar (
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
    CREATE TABLE IF NOT EXISTS majburiy_obunalar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nomi TEXT,
        link TEXT NOT NULL,
        tur TEXT DEFAULT 'kanal',
        is_active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS qism_xaridlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        qism_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS admin_state (
        user_id INTEGER PRIMARY KEY,
        state TEXT,
        data TEXT
    );
    """)
    con.commit()
    con.close()

# ═══════════════════════════════════════════════════════════════════
# YORDAMCHI FUNKSIYALAR
# ═══════════════════════════════════════════════════════════════════
def som(n):
    return f"{int(n):,}".replace(",", " ")

def get_user(uid):
    con = db()
    u = con.execute("SELECT * FROM foydalanuvchilar WHERE id=?", (uid,)).fetchone()
    con.close()
    return u

def ensure_user(tg):
    con = db()
    con.execute(
        "INSERT OR IGNORE INTO foydalanuvchilar(id,username,full_name) VALUES(?,?,?)",
        (tg.id, tg.username, tg.full_name)
    )
    con.commit()
    con.close()

def is_admin(uid):
    return uid in ADMIN_IDS

def is_vip(uid):
    u = get_user(uid)
    if not u or not u["vip_expire"]:
        return False
    return datetime.fromisoformat(u["vip_expire"]) > datetime.now()

def karta():
    con = db()
    k = con.execute("SELECT * FROM kartalar WHERE is_active=1 LIMIT 1").fetchone()
    con.close()
    return k

# Admin state (DB orqali — Railway restart bo'lganda ham saqlanadi)
def set_state(uid, state, data=""):
    con = db()
    con.execute(
        "INSERT OR REPLACE INTO admin_state(user_id,state,data) VALUES(?,?,?)",
        (uid, state, data)
    )
    con.commit()
    con.close()

def get_state(uid):
    con = db()
    row = con.execute("SELECT state,data FROM admin_state WHERE user_id=?", (uid,)).fetchone()
    con.close()
    if row:
        return row["state"], row["data"]
    return None, None

def clear_state(uid):
    con = db()
    con.execute("DELETE FROM admin_state WHERE user_id=?", (uid,))
    con.commit()
    con.close()

# ═══════════════════════════════════════════════════════════════════
# MAJBURIY OBUNA TEKSHIRUVI
# ═══════════════════════════════════════════════════════════════════
async def check_sub(bot, uid):
    con = db()
    rows = con.execute("SELECT * FROM majburiy_obunalar WHERE is_active=1").fetchall()
    con.close()
    failed = []
    for r in rows:
        if r["tur"] == "kanal":
            try:
                m = await bot.get_chat_member(r["link"], uid)
                if m.status in ("left", "kicked"):
                    failed.append(r)
            except:
                pass
        else:
            failed.append(r)
    return failed

async def sub_msg(update, failed):
    btns = [[btn_link(f"📢 {r['nomi'] or r['link']}", r["link"])] for r in failed]
    btns.append([btn_green("✅ Tekshirish", "check_sub")])
    await update.effective_message.reply_text(
        "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
        reply_markup=InlineKeyboardMarkup(btns)
    )

# ═══════════════════════════════════════════════════════════════════
# FOYDALANUVCHI MENYUSI
# ═══════════════════════════════════════════════════════════════════
def user_menu():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎬 Kinolar"),    KeyboardButton("🔍 Qidirish")],
        [KeyboardButton("💎 VIP Tariflar"), KeyboardButton("👤 Hisobim")],
    ], resize_keyboard=True)

# ═══════════════════════════════════════════════════════════════════
# ADMIN PANEL MENYUSI — Rangli InlineKeyboard
# ═══════════════════════════════════════════════════════════════════
def admin_menu():
    return InlineKeyboardMarkup([
        [btn_green("🎬 Kino qo'shish",   "ap_kino"),
         btn_blue( "📢 Kanal post",       "ap_post")],
        [btn_blue( "💎 VIP Tariflar",     "ap_tarif"),
         btn_green("💳 Karta qo'shish",   "ap_karta")],
        [btn_red(  "🔒 Majburiy obuna",   "ap_majburiy"),
         btn_blue( "📊 Statistika",       "ap_stat")],
        [btn_blue( "📨 Xabar yuborish",   "ap_xabar"),
         btn_red(  "💰 Pulik qism",       "ap_pulik")],
    ])

# ═══════════════════════════════════════════════════════════════════
# /start
# ═══════════════════════════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    uid = update.effective_user.id
    clear_state(uid)

    failed = await check_sub(ctx.bot, uid)
    if failed:
        await sub_msg(update, failed)
        return

    # Deep link — kod bo'lsa
    args = ctx.args
    if args:
        kod = args[0].upper()
        await kino_show_by_kod(update, ctx, kod)
        return

    await update.message.reply_text(
        f"🎬 *Xush kelibsiz, {update.effective_user.first_name}!*\n\n"
        "Kino kodini yuboring yoki quyidagi tugmalardan foydalaning:",
        reply_markup=user_menu(),
        parse_mode=ParseMode.MARKDOWN
    )

# ═══════════════════════════════════════════════════════════════════
# /admin
# ═══════════════════════════════════════════════════════════════════
async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return
    clear_state(update.effective_user.id)
    await update.message.reply_text(
        "🔧 *Admin Panel*\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=admin_menu(),
        parse_mode=ParseMode.MARKDOWN
    )

# ═══════════════════════════════════════════════════════════════════
# CHECK_SUB CALLBACK
# ═══════════════════════════════════════════════════════════════════
async def cb_check_sub(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    failed = await check_sub(ctx.bot, uid)
    if failed:
        await sub_msg(update, failed)
    else:
        await q.message.delete()
        await q.message.reply_text(
            "✅ Obuna tasdiqlandi!",
            reply_markup=user_menu()
        )

# ═══════════════════════════════════════════════════════════════════
# KINO KO'RSATISH
# ═══════════════════════════════════════════════════════════════════
async def kino_show_by_kod(update, ctx, kod):
    con = db()
    kino = con.execute("SELECT * FROM kinolar WHERE kod=?", (kod,)).fetchone()
    con.close()
    if not kino:
        await update.effective_message.reply_text(
            "❌ Kino topilmadi! Kodni tekshiring."
        )
        return
    await kino_show(update, ctx, kino)

async def kino_show(update, ctx, kino):
    uid = update.effective_user.id
    con = db()
    qismlar = con.execute(
        "SELECT * FROM qismlar WHERE kino_id=? ORDER BY qism_raqam", (kino["id"],)
    ).fetchall()
    con.close()

    caption = (
        f"🎬 *{kino['nomi']}*\n\n"
        f"🎞 Qismi: {len(qismlar)}\n"
        f"🌍 Davlati: {kino['davlat'] or 'Xitoy'}\n"
        f"🇺🇿 Tili: {kino['til']}\n"
        f"📅 Yili: {kino['yil'] or '-'}\n"
        f"🎭 Janri: {kino['janr'] or '-'}\n\n"
        f"📂 Kod: `{kino['kod']}`"
    )

    btns = []
    row = []
    for i, q in enumerate(qismlar):
        label = f"{q['qism_raqam']}-qism"
        if q["is_vip"]:
            label = f"💎{label}"
        # qism tugmalari — ko'k (oddiy), sariq (vip)
        row.append(btn_blue(label, f"qism_{q['id']}") if not q["is_vip"]
                   else btn_red(label, f"qism_{q['id']}"))
        if len(row) == 3 or i == len(qismlar) - 1:
            btns.append(row)
            row = []

    kb = InlineKeyboardMarkup(btns) if btns else None

    if kino["rasm_file_id"]:
        await update.effective_message.reply_photo(
            kino["rasm_file_id"], caption=caption,
            reply_markup=kb, parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.effective_message.reply_text(
            caption, reply_markup=kb, parse_mode=ParseMode.MARKDOWN
        )

# ═══════════════════════════════════════════════════════════════════
# QISM YUBORISH
# ═══════════════════════════════════════════════════════════════════
async def cb_qism(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    qism_id = int(q.data.split("_")[1])

    con = db()
    qism = con.execute("SELECT * FROM qismlar WHERE id=?", (qism_id,)).fetchone()
    kino = con.execute("SELECT * FROM kinolar WHERE id=?", (qism["kino_id"],)).fetchone() if qism else None
    con.close()

    if not qism:
        await q.answer("Qism topilmadi!", show_alert=True)
        return

    # VIP tekshiruv
    if qism["is_vip"] and not is_vip(uid):
        user = get_user(uid)
        narx = qism["narx"]
        btns = [
            [btn_green(f"💳 Balansdan to'lash ({som(narx)} so'm)", f"balans_{qism_id}")],
            [btn_blue("💎 VIP sotib olish", "vip_menu")],
            [btn_link("💳 Hisobni to'ldirish", f"https://t.me/{BOT_USERNAME}")],
        ]
        await q.message.reply_text(
            f"🔒 *Bu qism pullik!*\n\n"
            f"💰 Narxi: {som(narx)} so'm\n"
            f"💼 Balansingiz: {som(user['balans'] if user else 0)} so'm",
            reply_markup=InlineKeyboardMarkup(btns),
            parse_mode=ParseMode.MARKDOWN
        )
        return

    share_text = f"🎬 {kino['nomi']} — {qism['qism_raqam']}-qism\nKod: {kino['kod']}"
    btns = [[btn_share("📤 Do'stlarga ulashish", share_text)]]

    await q.message.reply_video(
        qism["file_id"],
        caption=f"🎬 *{kino['nomi']}* — {qism['qism_raqam']}-qism",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN,
        protect_content=True
    )

# ═══════════════════════════════════════════════════════════════════
# BALANSDAN TO'LOV
# ═══════════════════════════════════════════════════════════════════
async def cb_balans_tolov(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    qism_id = int(q.data.split("_")[1])

    con = db()
    qism = con.execute("SELECT * FROM qismlar WHERE id=?", (qism_id,)).fetchone()
    kino = con.execute("SELECT * FROM kinolar WHERE id=?", (qism["kino_id"],)).fetchone()
    user = con.execute("SELECT * FROM foydalanuvchilar WHERE id=?", (uid,)).fetchone()

    if user["balans"] < qism["narx"]:
        con.close()
        await q.message.reply_text(
            f"❌ Balans yetarli emas!\n"
            f"💰 Kerak: {som(qism['narx'])} so'm\n"
            f"💼 Sizda: {som(user['balans'])} so'm",
            reply_markup=InlineKeyboardMarkup([
                [btn_green("💳 Hisobni to'ldirish", "toldirish")]
            ])
        )
        return

    con.execute("UPDATE foydalanuvchilar SET balans=balans-? WHERE id=?", (qism["narx"], uid))
    con.execute("INSERT INTO qism_xaridlar(user_id,qism_id) VALUES(?,?)", (uid, qism_id))
    con.commit()
    con.close()

    share_text = f"🎬 {kino['nomi']} — {qism['qism_raqam']}-qism\nKod: {kino['kod']}"
    await q.message.reply_video(
        qism["file_id"],
        caption=f"✅ To'lov amalga oshirildi!\n🎬 *{kino['nomi']}* — {qism['qism_raqam']}-qism",
        reply_markup=InlineKeyboardMarkup([[btn_share("📤 Do'stlarga ulashish", share_text)]]),
        parse_mode=ParseMode.MARKDOWN,
        protect_content=True
    )

# ═══════════════════════════════════════════════════════════════════
# HISOBIM
# ═══════════════════════════════════════════════════════════════════
async def show_hisobim(update, ctx):
    uid = update.effective_user.id
    user = get_user(uid)
    vip = "❌ Yo'q"
    if is_vip(uid):
        exp = datetime.fromisoformat(user["vip_expire"])
        vip = f"✅ {exp.strftime('%d.%m.%Y')} gacha"

    con = db()
    tlist = con.execute(
        "SELECT * FROM tolovlar WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (uid,)
    ).fetchall()
    con.close()

    tarix = ""
    for t in tlist:
        e = {"tasdiqlandi": "✅", "kutilmoqda": "⏳", "bekor": "❌"}.get(t["status"], "❓")
        tarix += f"{e} {som(t['miqdor'])} so'm — {t['created_at'][:10]}\n"

    await update.effective_message.reply_text(
        f"👤 *Mening hisobim*\n\n"
        f"🆔 ID: `{uid}`\n"
        f"💰 Balans: *{som(user['balans'])} so'm*\n"
        f"💎 VIP: {vip}\n\n"
        f"📋 *So'nggi to'lovlar:*\n{tarix or 'Hali to\'lov yo\'q'}",
        reply_markup=InlineKeyboardMarkup([
            [btn_green("💳 Hisobni to'ldirish", "toldirish")]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

# ═══════════════════════════════════════════════════════════════════
# HISOBNI TO'LDIRISH
# ═══════════════════════════════════════════════════════════════════
async def cb_toldirish(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    set_state(uid, "tolov_miqdor")
    await q.message.reply_text(
        "💳 *Qancha miqdorda to'ldirmoqchisiz?*\n\n"
        "Miqdorni so'mda kiriting (masalan: 50000):",
        parse_mode=ParseMode.MARKDOWN
    )

async def tolov_miqdor_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    try:
        miqdor = int(update.message.text.replace(" ", "").replace(",", ""))
        if miqdor < 1000:
            raise ValueError
    except:
        await update.message.reply_text("❌ Kamida 1,000 so'm kiriting:")
        return

    k = karta()
    if not k:
        await update.message.reply_text("❌ Karta mavjud emas. Admin bilan bog'laning.")
        clear_state(uid)
        return

    set_state(uid, "tolov_chek", str(miqdor))
    await update.message.reply_text(
        f"💳 *To'lov ma'lumotlari:*\n\n"
        f"📱 Karta: `{k['raqam']}`\n"
        f"👤 Egasi: {k['egasi'] or '-'}\n"
        f"💰 Miqdor: *{som(miqdor)} so'm*\n\n"
        f"To'lovni amalga oshiring va *chek rasmini* yuboring:",
        parse_mode=ParseMode.MARKDOWN
    )

async def tolov_chek_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    _, miqdor_str = get_state(uid)
    miqdor = int(miqdor_str or 0)

    if not update.message.photo:
        await update.message.reply_text("❌ Iltimos chek rasmini yuboring!")
        return

    file_id = update.message.photo[-1].file_id
    con = db()
    con.execute(
        "INSERT INTO tolovlar(user_id,miqdor,chek_file_id,tur) VALUES(?,?,?,?)",
        (uid, miqdor, file_id, "balans")
    )
    tid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.commit()
    con.close()
    clear_state(uid)

    tg = update.effective_user
    for aid in ADMIN_IDS:
        try:
            await ctx.bot.send_photo(
                aid, file_id,
                caption=(
                    f"💳 *Yangi to'lov so'rovi*\n\n"
                    f"👤 {tg.full_name}\n"
                    f"🆔 `{uid}`\n"
                    f"💰 {som(miqdor)} so'm\n"
                    f"#tolov_{tid}"
                ),
                reply_markup=InlineKeyboardMarkup([
                    [btn_green("✅ Tasdiqlash", f"tok_{tid}_{uid}_{miqdor}"),
                     btn_red("❌ Bekor", f"tno_{tid}_{uid}_{miqdor}")],
                    [btn_blue("💬 Xabar yuborish", f"xyu_{uid}")],
                ]),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            log.error(f"Admin xabar: {e}")

    await update.message.reply_text(
        "✅ Chek yuborildi! Admin tekshirib, hisobingizni to'ldiradi.\n"
        "⏳ Odatda 1–30 daqiqa ichida.",
        reply_markup=user_menu()
    )

# ═══════════════════════════════════════════════════════════════════
# TO'LOV TASDIQLASH / BEKOR (ADMIN)
# ═══════════════════════════════════════════════════════════════════
async def cb_tok(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    _, tid, uid, miqdor = q.data.split("_")
    tid, uid, miqdor = int(tid), int(uid), int(miqdor)
    con = db()
    con.execute("UPDATE tolovlar SET status='tasdiqlandi' WHERE id=?", (tid,))
    con.execute("UPDATE foydalanuvchilar SET balans=balans+? WHERE id=?", (miqdor, uid))
    con.commit()
    con.close()
    await q.edit_message_caption(
        q.message.caption + f"\n\n✅ *TASDIQLANDI* — {datetime.now().strftime('%H:%M')}",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        await ctx.bot.send_message(uid,
            f"✅ *Hisobingiz to'ldirildi!*\n💰 +{som(miqdor)} so'm qo'shildi.",
            parse_mode=ParseMode.MARKDOWN)
    except: pass

async def cb_tno(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    _, tid, uid, miqdor = q.data.split("_")
    tid, uid, miqdor = int(tid), int(uid), int(miqdor)
    con = db()
    con.execute("UPDATE tolovlar SET status='bekor' WHERE id=?", (tid,))
    con.commit()
    con.close()
    await q.edit_message_caption(
        q.message.caption + f"\n\n❌ *BEKOR QILINDI* — {datetime.now().strftime('%H:%M')}",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        await ctx.bot.send_message(uid,
            f"❌ To'lov bekor qilindi.\nMiqdor: {som(miqdor)} so'm",
            parse_mode=ParseMode.MARKDOWN)
    except: pass

# ═══════════════════════════════════════════════════════════════════
# VIP TARIFLAR
# ═══════════════════════════════════════════════════════════════════
async def show_vip_menu(update, ctx):
    con = db()
    tariflar = con.execute("SELECT * FROM tariflar WHERE is_active=1").fetchall()
    con.close()
    if not tariflar:
        await update.effective_message.reply_text("Hozirda VIP tariflar mavjud emas.")
        return
    text = "💎 *VIP Tariflar*\n\n"
    btns = []
    for t in tariflar:
        text += f"⭐ *{t['nomi']}* — {som(t['narx'])} so'm ({t['kunlar']} kun)\n"
        btns.append([btn_blue(f"⭐ {t['nomi']} — {som(t['narx'])} so'm", f"vip_{t['id']}")])
    await update.effective_message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN
    )

async def cb_vip_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    tarif_id = int(q.data.split("_")[1])
    con = db()
    tarif = con.execute("SELECT * FROM tariflar WHERE id=?", (tarif_id,)).fetchone()
    con.close()
    k = karta()
    if not k:
        await q.message.reply_text("❌ Karta mavjud emas!")
        return
    set_state(uid, "vip_chek", str(tarif_id))
    await q.message.reply_text(
        f"💎 *{tarif['nomi']}* sotib olish\n\n"
        f"💰 Narxi: {som(tarif['narx'])} so'm\n"
        f"📅 Muddat: {tarif['kunlar']} kun\n\n"
        f"💳 Karta: `{k['raqam']}`\n"
        f"👤 Egasi: {k['egasi'] or '-'}\n\n"
        f"To'lovni amalga oshirib, *chek rasmini* yuboring:",
        parse_mode=ParseMode.MARKDOWN
    )

async def vip_chek_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    _, tarif_id_str = get_state(uid)
    tarif_id = int(tarif_id_str or 0)
    if not update.message.photo:
        await update.message.reply_text("❌ Chek rasmini yuboring!")
        return
    file_id = update.message.photo[-1].file_id
    con = db()
    tarif = con.execute("SELECT * FROM tariflar WHERE id=?", (tarif_id,)).fetchone()
    con.execute(
        "INSERT INTO tolovlar(user_id,miqdor,chek_file_id,tur,tarif_id) VALUES(?,?,?,?,?)",
        (uid, tarif["narx"], file_id, "vip", tarif_id)
    )
    tid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.commit()
    con.close()
    clear_state(uid)
    tg = update.effective_user
    for aid in ADMIN_IDS:
        try:
            await ctx.bot.send_photo(
                aid, file_id,
                caption=(
                    f"💎 *VIP So'rovi*\n\n"
                    f"👤 {tg.full_name}\n"
                    f"🆔 `{uid}`\n"
                    f"⭐ Tarif: {tarif['nomi']}\n"
                    f"💰 {som(tarif['narx'])} so'm\n"
                    f"#vip_{tid}"
                ),
                reply_markup=InlineKeyboardMarkup([
                    [btn_green("✅ VIP Berish", f"vok_{tid}_{uid}_{tarif_id}"),
                     btn_red("❌ Bekor", f"vno_{tid}_{uid}")],
                    [btn_blue("💬 Xabar yuborish", f"xyu_{uid}")],
                ]),
                parse_mode=ParseMode.MARKDOWN
            )
        except: pass
    await update.message.reply_text(
        "✅ Chek yuborildi! Tez orada VIP beriladi.",
        reply_markup=user_menu()
    )

async def cb_vok(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    _, tid, uid, tarif_id = q.data.split("_")
    tid, uid, tarif_id = int(tid), int(uid), int(tarif_id)
    con = db()
    tarif = con.execute("SELECT * FROM tariflar WHERE id=?", (tarif_id,)).fetchone()
    user = con.execute("SELECT * FROM foydalanuvchilar WHERE id=?", (uid,)).fetchone()
    expire = datetime.now() + timedelta(days=tarif["kunlar"])
    if user["vip_expire"]:
        try:
            ex = datetime.fromisoformat(user["vip_expire"])
            if ex > datetime.now():
                expire = ex + timedelta(days=tarif["kunlar"])
        except: pass
    con.execute("UPDATE foydalanuvchilar SET vip_expire=? WHERE id=?", (expire.isoformat(), uid))
    con.execute("UPDATE tolovlar SET status='tasdiqlandi' WHERE id=?", (tid,))
    con.commit()
    con.close()
    await q.edit_message_caption(
        q.message.caption + f"\n\n✅ *VIP BERILDI* — {expire.strftime('%d.%m.%Y')} gacha",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        await ctx.bot.send_message(uid,
            f"🎉 *VIP faollashtirildi!*\n⭐ Tarif: {tarif['nomi']}\n📅 {expire.strftime('%d.%m.%Y')} gacha",
            parse_mode=ParseMode.MARKDOWN)
    except: pass

async def cb_vno(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    _, tid, uid = q.data.split("_")
    tid, uid = int(tid), int(uid)
    con = db()
    con.execute("UPDATE tolovlar SET status='bekor' WHERE id=?", (tid,))
    con.commit()
    con.close()
    await q.edit_message_caption(
        q.message.caption + "\n\n❌ *BEKOR QILINDI*", parse_mode=ParseMode.MARKDOWN
    )
    try:
        await ctx.bot.send_message(uid, "❌ VIP so'rovingiz bekor qilindi.")
    except: pass

# ═══════════════════════════════════════════════════════════════════
# ADMIN — KINO QO'SHISH
# ═══════════════════════════════════════════════════════════════════
async def cb_ap_kino(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if not is_admin(uid): return
    set_state(uid, "kino_nomi")
    await q.message.reply_text(
        "🎬 *Yangi kino qo'shish*\n\n"
        "1️⃣ Kino *nomini* kiriting:",
        parse_mode=ParseMode.MARKDOWN
    )

# ═══════════════════════════════════════════════════════════════════
# ADMIN — KANAL POST
# ═══════════════════════════════════════════════════════════════════
async def cb_ap_post(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if not is_admin(uid): return
    set_state(uid, "post_rasm")
    await q.message.reply_text(
        "📢 *Kanal Post*\n\n"
        "1️⃣ Kino *rasmini* yuboring (poster):",
        parse_mode=ParseMode.MARKDOWN
    )

# ═══════════════════════════════════════════════════════════════════
# ADMIN — VIP TARIFLAR
# ═══════════════════════════════════════════════════════════════════
async def cb_ap_tarif(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    con = db()
    tariflar = con.execute("SELECT * FROM tariflar WHERE is_active=1").fetchall()
    con.close()
    text = "💎 *VIP Tariflar*\n\n"
    btns = []
    for t in tariflar:
        text += f"• {t['nomi']} — {som(t['narx'])} so'm ({t['kunlar']} kun)\n"
        btns.append([btn_red(f"🗑 {t['nomi']} o'chirish", f"tdel_{t['id']}")])
    btns.append([btn_green("➕ Yangi tarif qo'shish", "tadd")])
    btns.append([btn_red("🔙 Orqaga", "ap_back")])
    await q.edit_message_text(
        text or "💎 Tariflar yo'q",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_tadd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    set_state(q.from_user.id, "tarif_nomi")
    await q.message.reply_text(
        "💎 Tarif *nomini* kiriting (masalan: 1 oylik):",
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_tdel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    tarif_id = int(q.data.split("_")[1])
    con = db()
    con.execute("UPDATE tariflar SET is_active=0 WHERE id=?", (tarif_id,))
    con.commit()
    con.close()
    await cb_ap_tarif(update, ctx)

# ═══════════════════════════════════════════════════════════════════
# ADMIN — KARTA
# ═══════════════════════════════════════════════════════════════════
async def cb_ap_karta(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    con = db()
    kartalar = con.execute("SELECT * FROM kartalar WHERE is_active=1").fetchall()
    con.close()
    text = "💳 *Kartalar*\n\n"
    btns = []
    for k in kartalar:
        text += f"• `{k['raqam']}` — {k['egasi'] or '-'}\n"
        btns.append([btn_red(f"🗑 {k['raqam']}", f"kdel_{k['id']}")])
    btns.append([btn_green("➕ Karta qo'shish", "kadd")])
    btns.append([btn_red("🔙 Orqaga", "ap_back")])
    await q.edit_message_text(
        text or "💳 Kartalar yo'q",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_kadd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    set_state(q.from_user.id, "karta_raqam")
    await q.message.reply_text(
        "💳 Karta *raqamini* kiriting\n(masalan: 8600 1234 5678 9012):",
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_kdel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    kid = int(q.data.split("_")[1])
    con = db()
    con.execute("UPDATE kartalar SET is_active=0 WHERE id=?", (kid,))
    con.commit()
    con.close()
    await cb_ap_karta(update, ctx)

# ═══════════════════════════════════════════════════════════════════
# ADMIN — MAJBURIY OBUNA
# ═══════════════════════════════════════════════════════════════════
async def cb_ap_majburiy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    con = db()
    rows = con.execute("SELECT * FROM majburiy_obunalar WHERE is_active=1").fetchall()
    con.close()
    text = "🔒 *Majburiy Obunalar*\n\n"
    btns = []
    for r in rows:
        text += f"• {r['nomi'] or r['link']} ({r['tur']})\n"
        btns.append([btn_red(f"🗑 {r['nomi'] or r['link']}", f"mdel_{r['id']}")])
    btns.append([btn_green("➕ Qo'shish", "madd")])
    btns.append([btn_red("🔙 Orqaga", "ap_back")])
    await q.edit_message_text(
        text or "🔒 Majburiy obunalar yo'q",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_madd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    btns = [
        [btn_blue("📢 Telegram kanal", "mtur_kanal")],
        [btn_blue("🔗 Oddiy link",     "mtur_link")],
    ]
    await q.message.reply_text(
        "🔒 Tur tanlang:", reply_markup=InlineKeyboardMarkup(btns)
    )

async def cb_mtur(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    tur = q.data.split("_")[1]
    set_state(q.from_user.id, "maj_link", tur)
    await q.message.reply_text(
        "🔗 Link kiriting (masalan: @kanal_username yoki https://...):"
    )

async def cb_mdel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    mid = int(q.data.split("_")[1])
    con = db()
    con.execute("UPDATE majburiy_obunalar SET is_active=0 WHERE id=?", (mid,))
    con.commit()
    con.close()
    await cb_ap_majburiy(update, ctx)

# ═══════════════════════════════════════════════════════════════════
# ADMIN — STATISTIKA
# ═══════════════════════════════════════════════════════════════════
async def cb_ap_stat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    con = db()
    bir_oy  = (datetime.now() - timedelta(days=30)).isoformat()
    bir_haf = (datetime.now() - timedelta(days=7)).isoformat()
    jami   = con.execute("SELECT COUNT(*) FROM foydalanuvchilar").fetchone()[0]
    yangi  = con.execute("SELECT COUNT(*) FROM foydalanuvchilar WHERE created_at>=?", (bir_oy,)).fetchone()[0]
    vips   = con.execute("SELECT COUNT(*) FROM foydalanuvchilar WHERE vip_expire>?", (datetime.now().isoformat(),)).fetchone()[0]
    daromad = con.execute("SELECT SUM(miqdor) FROM tolovlar WHERE status='tasdiqlandi' AND created_at>=?", (bir_oy,)).fetchone()[0] or 0
    haf_tol = con.execute("SELECT COUNT(DISTINCT user_id) FROM tolovlar WHERE created_at>=?", (bir_haf,)).fetchone()[0]
    top15  = con.execute("SELECT id,full_name,balans FROM foydalanuvchilar ORDER BY balans DESC LIMIT 15").fetchall()
    con.close()
    top_txt = "\n".join(f"{i+1}. {u['full_name'] or u['id']} — {som(u['balans'])} so'm"
                        for i, u in enumerate(top15))
    await q.edit_message_text(
        f"📊 *Statistika*\n\n"
        f"👥 Jami foydalanuvchi: {jami}\n"
        f"📅 Bu oy yangi: +{yangi}\n"
        f"💎 Aktiv VIP: {vips}\n"
        f"💰 Bu oy daromad: {som(daromad)} so'm\n"
        f"🔄 Bu hafta to'ldirgan: {haf_tol} kishi\n\n"
        f"🏆 *Top 15 balans:*\n{top_txt or 'Ma\'lumot yo\'q'}",
        reply_markup=InlineKeyboardMarkup([[btn_red("🔙 Orqaga", "ap_back")]]),
        parse_mode=ParseMode.MARKDOWN
    )

# ═══════════════════════════════════════════════════════════════════
# ADMIN — XABAR YUBORISH
# ═══════════════════════════════════════════════════════════════════
async def cb_ap_xabar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    btns = [
        [btn_green("👥 Hammaga", "xall")],
        [btn_blue("💎 Faqat VIP", "xvip"), btn_blue("🆓 Bepul", "xfree")],
        [btn_red("🔙 Orqaga", "ap_back")],
    ]
    await q.edit_message_text(
        "📨 *Kimga xabar yuborish?*",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )

async def cb_xabar_target(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    target = q.data  # xall / xvip / xfree
    set_state(q.from_user.id, "xabar_send", target)
    await q.message.reply_text(
        "📨 Xabar yuboring (matn, rasm yoki video):"
    )

async def cb_xyu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admindan konkret usernick ga xabar"""
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    target_uid = int(q.data.split("_")[1])
    set_state(q.from_user.id, "xabar_send", str(target_uid))
    await q.message.reply_text(
        f"📨 Foydalanuvchi ({target_uid}) ga xabar yuboring:"
    )

# ═══════════════════════════════════════════════════════════════════
# ADMIN — PULIK QISM
# ═══════════════════════════════════════════════════════════════════
async def cb_ap_pulik(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    set_state(q.from_user.id, "pulik_kod")
    await q.edit_message_text(
        "💰 *Qismni pulik qilish*\n\nKino *kodini* kiriting:",
        parse_mode=ParseMode.MARKDOWN
    )

# ═══════════════════════════════════════════════════════════════════
# ADMIN — ORQAGA
# ═══════════════════════════════════════════════════════════════════
async def cb_ap_back(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    clear_state(q.from_user.id)
    await q.edit_message_text(
        "🔧 *Admin Panel*\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=admin_menu(),
        parse_mode=ParseMode.MARKDOWN
    )

# ═══════════════════════════════════════════════════════════════════
# VIP MENU CALLBACK
# ═══════════════════════════════════════════════════════════════════
async def cb_vip_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await show_vip_menu(update, ctx)

# ═══════════════════════════════════════════════════════════════════
# ASOSIY XABAR HANDLERI — barcha matnlar shu yerdan o'tadi
# ═══════════════════════════════════════════════════════════════════
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    text = update.message.text or ""
    
    ensure_user(update.effective_user)

    # ── Majburiy obuna tekshiruvi ──────────────────────────────────
    failed = await check_sub(ctx.bot, uid)
    if failed:
        await sub_msg(update, failed)
        return

    # ── Admin state machine ────────────────────────────────────────
    state, data = get_state(uid)
    if state and is_admin(uid):
        await handle_admin_state(update, ctx, state, data)
        return

    # ── Foydalanuvchi state machine ────────────────────────────────
    if state == "tolov_miqdor":
        await tolov_miqdor_msg(update, ctx)
        return
    if state == "tolov_chek":
        await tolov_chek_msg(update, ctx)
        return
    if state == "vip_chek":
        await vip_chek_msg(update, ctx)
        return
    if state and state.startswith("xabar_send"):
        await xabar_send_msg(update, ctx, data)
        return

    # ── Menyu tugmalari ────────────────────────────────────────────
    if text == "👤 Hisobim":
        await show_hisobim(update, ctx)
    elif text == "💎 VIP Tariflar":
        await show_vip_menu(update, ctx)
    elif text in ("🎬 Kinolar", "🔍 Qidirish"):
        await update.message.reply_text("🔍 Kino kodini kiriting:")
    else:
        # Kod qidirish
        kod = text.strip().upper()
        await kino_show_by_kod(update, ctx, kod)

# ═══════════════════════════════════════════════════════════════════
# ADMIN STATE MACHINE
# ═══════════════════════════════════════════════════════════════════
async def handle_admin_state(update: Update, ctx: ContextTypes.DEFAULT_TYPE, state: str, data: str):
    uid  = update.effective_user.id
    msg  = update.message
    text = msg.text or ""

    # ── KINO QO'SHISH ──────────────────────────────────────────────
    if state == "kino_nomi":
        set_state(uid, "kino_rasm", text.strip())
        await msg.reply_text("2️⃣ Kino *rasmini* yuboring (poster):", parse_mode=ParseMode.MARKDOWN)

    elif state == "kino_rasm":
        rasm = msg.photo[-1].file_id if msg.photo else None
        prev = data  # nomi
        set_state(uid, "kino_kod", f"{prev}|||{rasm or ''}")
        await msg.reply_text(
            "3️⃣ Kino *kodini* kiriting (masalan: OMADLIZARBA):\n"
            "⚠️ Faqat katta harf va raqamlar:",
            parse_mode=ParseMode.MARKDOWN
        )

    elif state == "kino_kod":
        kod = text.strip().upper()
        con = db()
        if con.execute("SELECT id FROM kinolar WHERE kod=?", (kod,)).fetchone():
            con.close()
            await msg.reply_text("❌ Bu kod mavjud! Boshqa kod kiriting:")
            return
        con.close()
        nomi_rasm = data.split("|||")
        nomi = nomi_rasm[0]
        rasm = nomi_rasm[1] if len(nomi_rasm) > 1 else ""
        set_state(uid, "kino_davlat", f"{nomi}|||{rasm}|||{kod}")
        await msg.reply_text("4️⃣ *Davlatni* kiriting (masalan: Xitoy):", parse_mode=ParseMode.MARKDOWN)

    elif state == "kino_davlat":
        parts = data.split("|||")
        nomi, rasm, kod = parts[0], parts[1], parts[2]
        set_state(uid, "kino_til", f"{nomi}|||{rasm}|||{kod}|||{text.strip()}")
        btns = [
            [btn_blue("🇺🇿 O'zbek tilida",  "ktil_uz")],
            [btn_blue("🇷🇺 Rus tilida",      "ktil_ru")],
            [btn_blue("🇬🇧 Ingliz tilida",   "ktil_en")],
        ]
        await msg.reply_text("5️⃣ *Tilni* tanlang:", reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)

    elif state == "kino_janr":
        # data = nomi|||rasm|||kod|||davlat|||til
        parts = data.split("|||")
        nomi, rasm, kod, davlat, til = parts[0], parts[1], parts[2], parts[3], parts[4]
        janr = text.strip()
        set_state(uid, "kino_qism1", f"{nomi}|||{rasm}|||{kod}|||{davlat}|||{til}|||{janr}|||")
        await msg.reply_text(
            f"✅ Ma'lumotlar:\n"
            f"📽 Nomi: {nomi}\n🔑 Kod: {kod}\n🌍 Davlat: {davlat}\n🇺🇿 Til: {til}\n🎭 Janr: {janr}\n\n"
            f"7️⃣ 1-qism *videosini* yuboring:",
            parse_mode=ParseMode.MARKDOWN
        )

    elif state == "kino_qism1" or (state and state.startswith("kino_qismN")):
        if not (msg.video or msg.document):
            await msg.reply_text("❌ Video yuboring!")
            return
        file_id = (msg.video or msg.document).file_id
        # qismlar list ni data oxiriga qo'shamiz
        qismlar_str = data.split("|||")[-1]
        qismlar_str = (qismlar_str + "," if qismlar_str else "") + file_id
        base = "|||".join(data.split("|||")[:-1])
        new_data = base + "|||" + qismlar_str
        qism_count = len([x for x in qismlar_str.split(",") if x])
        set_state(uid, "kino_qismN", new_data)
        btns = [
            [btn_blue(f"➕ Yana qism qo'shish ({qism_count+1}-qism)", "qism_yana")],
            [btn_green("✅ Tugatish va saqlash", "qism_save")],
        ]
        await msg.reply_text(
            f"✅ {qism_count}-qism qo'shildi!",
            reply_markup=InlineKeyboardMarkup(btns)
        )

    # ── KANAL POST ──────────────────────────────────────────────────
    elif state == "post_rasm":
        if not msg.photo:
            await msg.reply_text("❌ Rasm yuboring!")
            return
        rasm = msg.photo[-1].file_id
        set_state(uid, "post_nomi", rasm)
        await msg.reply_text("2️⃣ Kino *nomini* kiriting:", parse_mode=ParseMode.MARKDOWN)

    elif state == "post_nomi":
        set_state(uid, "post_qism", f"{data}|||{text.strip()}")
        await msg.reply_text("3️⃣ Jami *qismlar sonini* kiriting (masalan: 100):", parse_mode=ParseMode.MARKDOWN)

    elif state == "post_qism":
        try:
            qism = int(text.strip())
        except:
            await msg.reply_text("❌ Raqam kiriting!")
            return
        set_state(uid, "post_til", f"{data}|||{qism}")
        btns = [
            [btn_blue("🇺🇿 O'zbek tilida", "ptil_uz")],
            [btn_blue("🇷🇺 Rus tilida",    "ptil_ru")],
        ]
        await msg.reply_text("4️⃣ *Tilni* tanlang:", reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)

    elif state == "post_kod":
        kod = text.strip().upper()
        parts = data.split("|||")
        rasm, nomi, qism, til = parts[0], parts[1], parts[2], parts[3]
        caption = (
            f"🎬 *{nomi}*\n\n"
            f"▶ Qism : {qism}\n"
            f"▶ Tili : {til}\n"
            f"▶ Ko'rish : [Tomosha qilish](https://t.me/{BOT_USERNAME}?start={kod})"
        )
        btns_preview = [[btn_link("🎬 Tomosha qilish 🎬",
                                   f"https://t.me/{BOT_USERNAME}?start={kod}")]]
        await msg.reply_photo(
            rasm, caption=caption + "\n\n⬆️ *Ko'rinishi shunaqa. Yuborilsinmi?*",
            reply_markup=InlineKeyboardMarkup([
                [btn_green("✅ Kanalga yuborish", f"postsend_{rasm}_{nomi}_{qism}_{til}_{kod}"),
                 btn_red("❌ Bekor", "ap_back")],
            ]),
            parse_mode=ParseMode.MARKDOWN
        )
        clear_state(uid)

    # ── TARIF QO'SHISH ─────────────────────────────────────────────
    elif state == "tarif_nomi":
        set_state(uid, "tarif_narx", text.strip())
        await msg.reply_text("💰 Narxni kiriting (so'mda, masalan: 50000):", parse_mode=ParseMode.MARKDOWN)

    elif state == "tarif_narx":
        try:
            narx = int(text.replace(" ", ""))
        except:
            await msg.reply_text("❌ Raqam kiriting!")
            return
        set_state(uid, "tarif_kun", f"{data}|||{narx}")
        await msg.reply_text("📅 Necha kun amal qiladi:")

    elif state == "tarif_kun":
        try:
            kun = int(text.strip())
        except:
            await msg.reply_text("❌ Raqam kiriting!")
            return
        parts = data.split("|||")
        nomi, narx = parts[0], int(parts[1])
        con = db()
        con.execute("INSERT INTO tariflar(nomi,narx,kunlar) VALUES(?,?,?)", (nomi, narx, kun))
        con.commit()
        con.close()
        clear_state(uid)
        await msg.reply_text(
            f"✅ Tarif qo'shildi!\n⭐ {nomi} — {som(narx)} so'm ({kun} kun)",
            reply_markup=admin_menu()
        )

    # ── KARTA ──────────────────────────────────────────────────────
    elif state == "karta_raqam":
        set_state(uid, "karta_egasi", text.strip())
        await msg.reply_text("👤 Karta *egasini* kiriting:", parse_mode=ParseMode.MARKDOWN)

    elif state == "karta_egasi":
        raqam = data
        con = db()
        con.execute("INSERT INTO kartalar(raqam,egasi) VALUES(?,?)", (raqam, text.strip()))
        con.commit()
        con.close()
        clear_state(uid)
        await msg.reply_text(
            f"✅ Karta qo'shildi!\n💳 `{raqam}`",
            reply_markup=admin_menu(),
            parse_mode=ParseMode.MARKDOWN
        )

    # ── MAJBURIY LINK ──────────────────────────────────────────────
    elif state == "maj_link":
        tur = data
        set_state(uid, "maj_nomi", f"{tur}|||{text.strip()}")
        await msg.reply_text("📝 Ko'rinadigan *nomini* kiriting:", parse_mode=ParseMode.MARKDOWN)

    elif state == "maj_nomi":
        parts = data.split("|||")
        tur, link = parts[0], parts[1]
        nomi = text.strip()
        con = db()
        con.execute("INSERT INTO majburiy_obunalar(nomi,link,tur) VALUES(?,?,?)", (nomi, link, tur))
        con.commit()
        con.close()
        clear_state(uid)
        await msg.reply_text(
            f"✅ Majburiy obuna qo'shildi!\n🔒 {nomi}: {link}",
            reply_markup=admin_menu()
        )

    # ── XABAR YUBORISH ─────────────────────────────────────────────
    elif state == "xabar_send":
        await xabar_send_msg(update, ctx, data)

    # ── PULIK QISM ─────────────────────────────────────────────────
    elif state == "pulik_kod":
        kod = text.strip().upper()
        con = db()
        kino = con.execute("SELECT * FROM kinolar WHERE kod=?", (kod,)).fetchone()
        con.close()
        if not kino:
            await msg.reply_text("❌ Kino topilmadi! Kodni qayta kiriting:")
            return
        set_state(uid, "pulik_qism", str(kino["id"]))
        await msg.reply_text(
            f"🎬 *{kino['nomi']}*\n\n"
            "Qaysi qism raqamini pulik qilmoqchisiz? (masalan: 5):",
            parse_mode=ParseMode.MARKDOWN
        )

    elif state == "pulik_qism":
        try:
            qraqam = int(text.strip())
        except:
            await msg.reply_text("❌ Raqam kiriting!")
            return
        set_state(uid, "pulik_narx", f"{data}|||{qraqam}")
        await msg.reply_text("💰 Narxni kiriting (so'mda):")

    elif state == "pulik_narx":
        try:
            narx = int(text.replace(" ", ""))
        except:
            await msg.reply_text("❌ Raqam kiriting!")
            return
        parts = data.split("|||")
        kino_id, qraqam = int(parts[0]), int(parts[1])
        con = db()
        con.execute(
            "UPDATE qismlar SET is_vip=1, narx=? WHERE kino_id=? AND qism_raqam=?",
            (narx, kino_id, qraqam)
        )
        con.commit()
        con.close()
        clear_state(uid)
        await msg.reply_text(
            f"✅ {qraqam}-qism pulik qilindi!\n💰 Narxi: {som(narx)} so'm",
            reply_markup=admin_menu()
        )

# ═══════════════════════════════════════════════════════════════════
# XABAR YUBORISH AMALGA OSHIRISH
# ═══════════════════════════════════════════════════════════════════
async def xabar_send_msg(update, ctx, target):
    uid = update.effective_user.id
    msg = update.message
    con = db()
    if target == "xall":
        users = con.execute("SELECT id FROM foydalanuvchilar").fetchall()
    elif target == "xvip":
        users = con.execute(
            "SELECT id FROM foydalanuvchilar WHERE vip_expire>?", (datetime.now().isoformat(),)
        ).fetchall()
    elif target == "xfree":
        users = con.execute(
            "SELECT id FROM foydalanuvchilar WHERE vip_expire IS NULL OR vip_expire<=?",
            (datetime.now().isoformat(),)
        ).fetchall()
    else:
        # Konkret user
        users = [{"id": int(target)}]
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

    clear_state(uid)
    await msg.reply_text(
        f"✅ {sent} ta foydalanuvchiga yuborildi.",
        reply_markup=admin_menu()
    )

# ═══════════════════════════════════════════════════════════════════
# INLINE CALLBACK — TIL TANLASH (kino va post)
# ═══════════════════════════════════════════════════════════════════
async def cb_ktil(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    til_map = {"ktil_uz": "O'zbek tilida", "ktil_ru": "Rus tilida", "ktil_en": "Ingliz tilida"}
    til = til_map.get(q.data, "O'zbek tilida")
    state, data = get_state(uid)
    # data = nomi|||rasm|||kod|||davlat
    new_data = data + "|||" + til
    set_state(uid, "kino_janr", new_data)
    await q.message.reply_text("6️⃣ *Janrini* kiriting (masalan: Mini drama):", parse_mode=ParseMode.MARKDOWN)

async def cb_ptil(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    til_map = {"ptil_uz": "O'zbek tilida", "ptil_ru": "Rus tilida"}
    til = til_map.get(q.data, "O'zbek tilida")
    state, data = get_state(uid)
    # data = rasm|||nomi|||qism
    new_data = data + "|||" + til
    set_state(uid, "post_kod", new_data)
    await q.message.reply_text("5️⃣ Bot *kodini* kiriting (foydalanuvchi botga shu kodni yozadi):", parse_mode=ParseMode.MARKDOWN)

# ═══════════════════════════════════════════════════════════════════
# QISM YANA / SAVE CALLBACKS
# ═══════════════════════════════════════════════════════════════════
async def cb_qism_yana(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    state, data = get_state(uid)
    qismlar_str = data.split("|||")[-1]
    qism_count = len([x for x in qismlar_str.split(",") if x])
    await q.message.reply_text(f"📹 {qism_count+1}-qism *videosini* yuboring:", parse_mode=ParseMode.MARKDOWN)

async def cb_qism_save(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    _, data = get_state(uid)
    parts = data.split("|||")
    # nomi|||rasm|||kod|||davlat|||til|||janr|||file1,file2,...
    nomi    = parts[0]
    rasm    = parts[1] or None
    kod     = parts[2]
    davlat  = parts[3]
    til     = parts[4]
    janr    = parts[5]
    qism_files = [x for x in parts[6].split(",") if x] if len(parts) > 6 else []

    con = db()
    con.execute(
        "INSERT INTO kinolar(nomi,kod,rasm_file_id,til,janr,davlat,yil) VALUES(?,?,?,?,?,?,?)",
        (nomi, kod, rasm, til, janr, davlat, datetime.now().year)
    )
    kino_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    for i, fid in enumerate(qism_files):
        con.execute(
            "INSERT INTO qismlar(kino_id,qism_raqam,file_id) VALUES(?,?,?)",
            (kino_id, i+1, fid)
        )
    con.commit()
    con.close()
    clear_state(uid)
    await q.message.reply_text(
        f"✅ *Kino saqlandi!*\n\n"
        f"🎬 {nomi}\n🔑 Kod: `{kod}`\n📹 {len(qism_files)} ta qism",
        reply_markup=admin_menu(),
        parse_mode=ParseMode.MARKDOWN
    )

# ═══════════════════════════════════════════════════════════════════
# KANAL POST YUBORISH
# ═══════════════════════════════════════════════════════════════════
async def cb_postsend(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id): return
    # postsend_rasm_nomi_qism_til_kod — underscore bilan emas, shuning uchun state ishlatamiz
    # Oddiy yondashuv: parse from callback_data
    parts = q.data.split("_")  # postsend | rasm | nomi | qism | til | kod
    # Lekin rasm file_id ichida _ bo'lishi mumkin, shuning uchun kontekstdan olamiz
    # Biz state ni clear qildik, shuning uchun q.message.caption dan parse qilamiz
    cap = q.message.caption or ""
    try:
        await ctx.bot.send_photo(
            CHANNEL_ID,
            q.message.photo[-1].file_id,
            caption=cap.replace("\n\n⬆️ *Ko'rinishi shunaqa. Yuborilsinmi?*", ""),
            reply_markup=q.message.reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        await q.message.reply_text("✅ Post kanalga yuborildi!", reply_markup=admin_menu())
    except Exception as e:
        await q.message.reply_text(f"❌ Xato: {e}\n\nKANAL_ID to'g'ri ekanligini tekshiring: {CHANNEL_ID}")

# ═══════════════════════════════════════════════════════════════════
# PHOTO / VIDEO HANDLER (chek va video qism uchun)
# ═══════════════════════════════════════════════════════════════════
async def handle_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(update.effective_user)
    state, data = get_state(uid)

    if state == "tolov_chek":
        await tolov_chek_msg(update, ctx)
    elif state == "vip_chek":
        await vip_chek_msg(update, ctx)
    elif state in ("kino_rasm", "kino_qism1", "kino_qismN"):
        await handle_admin_state(update, ctx, state, data)
    elif state == "post_rasm":
        await handle_admin_state(update, ctx, state, data)
    elif state == "xabar_send":
        await xabar_send_msg(update, ctx, data)
    else:
        # Rasm = kino qidirish emas, ignore
        pass

# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════
def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable o'rnatilmagan!")

    db_init()
    log.info("✅ DB tayyor")

    app = Application.builder().token(BOT_TOKEN).build()

    # ── Commands ──────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))

    # ── Inline Callbacks ──────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(cb_check_sub,     pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(cb_toldirish,     pattern="^toldirish$"))
    app.add_handler(CallbackQueryHandler(cb_tok,           pattern="^tok_"))
    app.add_handler(CallbackQueryHandler(cb_tno,           pattern="^tno_"))
    app.add_handler(CallbackQueryHandler(cb_vip_menu,      pattern="^vip_menu$"))
    app.add_handler(CallbackQueryHandler(cb_vip_buy,       pattern=r"^vip_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_vok,           pattern="^vok_"))
    app.add_handler(CallbackQueryHandler(cb_vno,           pattern="^vno_"))
    app.add_handler(CallbackQueryHandler(cb_qism,          pattern=r"^qism_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_balans_tolov,  pattern=r"^balans_\d+$"))
    app.add_handler(CallbackQueryHandler(cb_xyu,           pattern="^xyu_"))
    # Admin panel
    app.add_handler(CallbackQueryHandler(cb_ap_back,       pattern="^ap_back$"))
    app.add_handler(CallbackQueryHandler(cb_ap_kino,       pattern="^ap_kino$"))
    app.add_handler(CallbackQueryHandler(cb_ap_post,       pattern="^ap_post$"))
    app.add_handler(CallbackQueryHandler(cb_ap_tarif,      pattern="^ap_tarif$"))
    app.add_handler(CallbackQueryHandler(cb_tadd,          pattern="^tadd$"))
    app.add_handler(CallbackQueryHandler(cb_tdel,          pattern="^tdel_"))
    app.add_handler(CallbackQueryHandler(cb_ap_karta,      pattern="^ap_karta$"))
    app.add_handler(CallbackQueryHandler(cb_kadd,          pattern="^kadd$"))
    app.add_handler(CallbackQueryHandler(cb_kdel,          pattern="^kdel_"))
    app.add_handler(CallbackQueryHandler(cb_ap_majburiy,   pattern="^ap_majburiy$"))
    app.add_handler(CallbackQueryHandler(cb_madd,          pattern="^madd$"))
    app.add_handler(CallbackQueryHandler(cb_mtur,          pattern="^mtur_"))
    app.add_handler(CallbackQueryHandler(cb_mdel,          pattern="^mdel_"))
    app.add_handler(CallbackQueryHandler(cb_ap_stat,       pattern="^ap_stat$"))
    app.add_handler(CallbackQueryHandler(cb_ap_xabar,      pattern="^ap_xabar$"))
    app.add_handler(CallbackQueryHandler(cb_xabar_target,  pattern="^x(all|vip|free)$"))
    app.add_handler(CallbackQueryHandler(cb_ap_pulik,      pattern="^ap_pulik$"))
    app.add_handler(CallbackQueryHandler(cb_ktil,          pattern="^ktil_"))
    app.add_handler(CallbackQueryHandler(cb_ptil,          pattern="^ptil_"))
    app.add_handler(CallbackQueryHandler(cb_qism_yana,     pattern="^qism_yana$"))
    app.add_handler(CallbackQueryHandler(cb_qism_save,     pattern="^qism_save$"))
    app.add_handler(CallbackQueryHandler(cb_postsend,      pattern="^postsend"))

    # ── Media handler (photo, video) ──────────────────────────────
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.Document.VIDEO,
        handle_media
    ))

    # ── Matn handler ──────────────────────────────────────────────
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))

    log.info("🤖 Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
