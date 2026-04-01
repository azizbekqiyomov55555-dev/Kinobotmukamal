#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🎬 KinoBOT - To'liq Telegram Bot
Barcha funksiyalar bitta faylda
"""

import sqlite3
import logging
import os
from datetime import datetime, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton, InputMediaPhoto
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

# ─── SOZLAMALAR ──────────────────────────────────────────────────────────────
BOT_TOKEN = "8693668045:AAGY-fCRkzaDNO9xHqJAFcrpI_OLpYIBMdI"
ADMIN_IDS = [8537782289]  # Admin Telegram ID larini qo'shing
CHANNEL_ID = "@Azizbekl2026"  # Kanal username

# ─── RANGLAR (InlineKeyboard uchun) ──────────────────────────────────────────
# Telegram 3 xil rang qo'llab-quvvatlaydi:
# "" - oddiy (kulrang)  |  "✅" prefix - yashil  |  "🔴" prefix - qizil
# Haqiqiy rang uchun InlineKeyboardButton(text, callback_data, ...) yetarli
# Telegram Bot API 7.0+ da "pay" tugmasi yashil, "url" tugmasi ko'k bo'ladi

# ─── HOLAT KONSTANTLARI ──────────────────────────────────────────────────────
(
    # Admin panel holatlari
    AP_MAIN, AP_KINO_ADD, AP_KINO_NOMI, AP_KINO_RASM, AP_KINO_KOD,
    AP_KINO_TIL, AP_KINO_JANR, AP_KINO_QISM_ADD, AP_KINO_QISM_FILE,
    AP_KINO_QISM_YANA, AP_KINO_VIP, AP_KINO_VIP_QISM, AP_KINO_VIP_NARX,
    AP_KANAL_POST, AP_KANAL_RASM, AP_KANAL_NOMI, AP_KANAL_QISM, AP_KANAL_TIL,
    AP_KANAL_KO, AP_KANAL_TASDIQLASH,
    AP_TARIF_ADD, AP_TARIF_NOMI, AP_TARIF_NARX, AP_TARIF_KUN,
    AP_KARTA_ADD, AP_MAJBURIY_ADD, AP_MAJBURIY_TUR, AP_MAJBURIY_LINK,
    AP_TOLOV_TASDIQLASH, AP_XABAR_YUBORISH, AP_XABAR_MATN,
    # Foydalanuvchi holatlari
    U_MAIN, U_KOD_IZLASH, U_TOLOV_MIQDOR, U_TOLOV_CHEK,
    U_TOLOV_BALANS, U_VIP_TOLOV, U_VIP_CHEK,
) = range(42)

# ─── LOGGING ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── MA'LUMOTLAR BAZASI ───────────────────────────────────────────────────────
def db_connect():
    conn = sqlite3.connect('kinobot.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def db_init():
    conn = db_connect()
    c = conn.cursor()
    
    c.executescript("""
    CREATE TABLE IF NOT EXISTS kinolar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nomi TEXT NOT NULL,
        kod TEXT UNIQUE NOT NULL,
        rasm_file_id TEXT,
        til TEXT DEFAULT 'O\'zbek tilida',
        janr TEXT,
        davlat TEXT DEFAULT 'Xitoy',
        yil INTEGER,
        is_vip INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE IF NOT EXISTS qismlar (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kino_id INTEGER NOT NULL,
        qism_raqam INTEGER NOT NULL,
        file_id TEXT NOT NULL,
        is_vip INTEGER DEFAULT 0,
        narx INTEGER DEFAULT 0,
        FOREIGN KEY (kino_id) REFERENCES kinolar(id)
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
        status TEXT DEFAULT 'kutilmoqda',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES foydalanuvchilar(id)
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
        usul TEXT DEFAULT 'balans',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    
    conn.commit()
    conn.close()

# ─── YORDAMCHI FUNKSIYALAR ────────────────────────────────────────────────────
def get_user(user_id):
    conn = db_connect()
    user = conn.execute("SELECT * FROM foydalanuvchilar WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return user

def ensure_user(tg_user):
    conn = db_connect()
    conn.execute("""
        INSERT OR IGNORE INTO foydalanuvchilar (id, username, full_name)
        VALUES (?, ?, ?)
    """, (tg_user.id, tg_user.username, tg_user.full_name))
    conn.commit()
    conn.close()

def is_admin(user_id):
    return user_id in ADMIN_IDS

def is_vip(user_id):
    user = get_user(user_id)
    if not user or not user['vip_expire']:
        return False
    expire = datetime.fromisoformat(user['vip_expire'])
    return expire > datetime.now()

def get_active_karta():
    conn = db_connect()
    karta = conn.execute("SELECT * FROM kartalar WHERE is_active=1 ORDER BY RANDOM() LIMIT 1").fetchone()
    conn.close()
    return karta

def format_son(n):
    return f"{n:,}".replace(",", " ")

# ─── MAJBURIY OBUNA TEKSHIRUVI ────────────────────────────────────────────────
async def check_subscription(bot, user_id):
    conn = db_connect()
    majburiylar = conn.execute("SELECT * FROM majburiy_obunalar WHERE is_active=1").fetchall()
    conn.close()
    
    not_subscribed = []
    for m in majburiylar:
        if m['tur'] == 'kanal':
            try:
                member = await bot.get_chat_member(m['link'], user_id)
                if member.status in ['left', 'kicked']:
                    not_subscribed.append(m)
            except:
                pass
        else:
            not_subscribed.append(m)
    return not_subscribed

async def send_subscription_msg(update, not_subscribed):
    buttons = []
    for m in not_subscribed:
        buttons.append([InlineKeyboardButton(
            f"📢 {m['nomi'] or m['link']}", url=m['link']
        )])
    buttons.append([InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub")])
    
    await update.effective_message.reply_text(
        "⚠️ Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# ═══════════════════════════════════════════════════════════════════════════════
#  FOYDALANUVCHI QISMI
# ═══════════════════════════════════════════════════════════════════════════════

# ─── ASOSIY MENYU ─────────────────────────────────────────────────────────────
def main_menu_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🎬 Kinolar"), KeyboardButton("🔍 Qidirish")],
        [KeyboardButton("💎 VIP Tariflar"), KeyboardButton("👤 Hisobim")],
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user(update.effective_user)
    user_id = update.effective_user.id
    
    # Majburiy obuna tekshiruv
    not_sub = await check_subscription(update.get_bot(), user_id)
    if not_sub:
        await send_subscription_msg(update, not_sub)
        return U_MAIN
    
    await update.message.reply_text(
        f"🎬 *Xush kelibsiz, {update.effective_user.first_name}!*\n\n"
        "Kino kodini yuboring yoki quyidagi tugmalardan foydalaning:",
        reply_markup=main_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    return U_MAIN

async def check_sub_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    not_sub = await check_subscription(update.get_bot(), query.from_user.id)
    if not_sub:
        await send_subscription_msg(update, not_sub)
    else:
        await query.message.delete()
        await query.message.reply_text(
            "✅ Obuna tasdiqlandi! Botdan foydalanishingiz mumkin.",
            reply_markup=main_menu_keyboard()
        )

# ─── HISOBIM ──────────────────────────────────────────────────────────────────
async def hisobim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    vip_status = "❌ Yo'q"
    if is_vip(user_id):
        expire = datetime.fromisoformat(user['vip_expire'])
        vip_status = f"✅ {expire.strftime('%d.%m.%Y')} gacha"
    
    conn = db_connect()
    tolovlar = conn.execute(
        "SELECT * FROM tolovlar WHERE user_id=? ORDER BY created_at DESC LIMIT 5",
        (user_id,)
    ).fetchall()
    conn.close()
    
    tarix = ""
    for t in tolovlar:
        emoji = "✅" if t['status'] == 'tasdiqlandi' else "⏳" if t['status'] == 'kutilmoqda' else "❌"
        tarix += f"{emoji} {format_son(t['miqdor'])} so'm — {t['created_at'][:10]}\n"
    
    text = (
        f"👤 *Mening hisobim*\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"💰 Balans: *{format_son(user['balans'])} so'm*\n"
        f"💎 VIP: {vip_status}\n\n"
        f"📋 *So'nggi to'lovlar:*\n{tarix or 'Hali to\'lov yo\'q'}"
    )
    
    buttons = [[InlineKeyboardButton(
        "💳 Hisobni to'ldirish", callback_data="hisobni_toldirish"
    )]]
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN
    )

# ─── HISOBNI TO'LDIRISH ───────────────────────────────────────────────────────
async def hisobni_toldirish_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        msg = query.message
    else:
        msg = update.message
    
    await msg.reply_text(
        "💳 *Qancha miqdorda to'ldirmoqchisiz?*\n\n"
        "Miqdorni so'mda kiriting (masalan: 50000):",
        parse_mode=ParseMode.MARKDOWN
    )
    return U_TOLOV_MIQDOR

async def tolov_miqdor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        miqdor = int(update.message.text.replace(" ", "").replace(",", ""))
        if miqdor < 1000:
            await update.message.reply_text("❌ Minimal miqdor 1,000 so'm!")
            return U_TOLOV_MIQDOR
    except:
        await update.message.reply_text("❌ Iltimos, raqam kiriting!")
        return U_TOLOV_MIQDOR
    
    context.user_data['tolov_miqdor'] = miqdor
    karta = get_active_karta()
    
    if not karta:
        await update.message.reply_text("❌ Hozirda karta mavjud emas. Admin bilan bog'laning.")
        return U_MAIN
    
    await update.message.reply_text(
        f"💳 *To'lov ma'lumotlari:*\n\n"
        f"📱 Karta raqami: `{karta['raqam']}`\n"
        f"👤 Egasi: {karta['egasi'] or '-'}\n"
        f"💰 Miqdor: *{format_son(miqdor)} so'm*\n\n"
        f"To'lovni amalga oshiring va chek (screenshot) yuboring:",
        parse_mode=ParseMode.MARKDOWN
    )
    return U_TOLOV_CHEK

async def tolov_chek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Iltimos, chek rasmini yuboring!")
        return U_TOLOV_CHEK
    
    user_id = update.effective_user.id
    miqdor = context.user_data.get('tolov_miqdor', 0)
    file_id = update.message.photo[-1].file_id
    
    conn = db_connect()
    conn.execute(
        "INSERT INTO tolovlar (user_id, miqdor, chek_file_id) VALUES (?, ?, ?)",
        (user_id, miqdor, file_id)
    )
    tolov_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    
    # Adminga xabar yuborish
    user = update.effective_user
    for admin_id in ADMIN_IDS:
        try:
            buttons = [
                [
                    InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"tolov_ok_{tolov_id}_{user_id}_{miqdor}"),
                    InlineKeyboardButton("❌ Bekor qilish", callback_data=f"tolov_no_{tolov_id}_{user_id}_{miqdor}"),
                ],
                [InlineKeyboardButton("💬 Xabar yuborish", callback_data=f"xabar_yu_{user_id}")]
            ]
            await update.get_bot().send_photo(
                admin_id,
                file_id,
                caption=(
                    f"💳 *Yangi to'lov so'rovi!*\n\n"
                    f"👤 Foydalanuvchi: {user.full_name}\n"
                    f"🆔 ID: `{user_id}`\n"
                    f"💰 Miqdor: {format_son(miqdor)} so'm\n"
                    f"🆔 To'lov ID: #{tolov_id}"
                ),
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Admin xabar xatosi: {e}")
    
    await update.message.reply_text(
        "✅ Chek yuborildi! Admin tekshirib, hisobingizni to'ldiradi.\n"
        "⏳ Odatda 1-30 daqiqa ichida tasdiqlandi.",
        reply_markup=main_menu_keyboard()
    )
    return U_MAIN

# ─── TO'LOV TASDIQLASH (ADMIN) ────────────────────────────────────────────────
async def tolov_ok_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        return
    
    _, _, tolov_id, user_id, miqdor = query.data.split("_")
    tolov_id, user_id, miqdor = int(tolov_id), int(user_id), int(miqdor)
    
    conn = db_connect()
    conn.execute("UPDATE tolovlar SET status='tasdiqlandi' WHERE id=?", (tolov_id,))
    conn.execute("UPDATE foydalanuvchilar SET balans=balans+? WHERE id=?", (miqdor, user_id))
    conn.commit()
    conn.close()
    
    await query.edit_message_caption(
        query.message.caption + f"\n\n✅ *TASDIQLANDI* — {datetime.now().strftime('%H:%M')}",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        await update.get_bot().send_message(
            user_id,
            f"✅ *Hisobingiz to'ldirildi!*\n\n"
            f"💰 +{format_son(miqdor)} so'm qo'shildi.",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass

async def tolov_no_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        return
    
    _, _, tolov_id, user_id, miqdor = query.data.split("_")
    tolov_id, user_id, miqdor = int(tolov_id), int(user_id), int(miqdor)
    
    conn = db_connect()
    conn.execute("UPDATE tolovlar SET status='bekor' WHERE id=?", (tolov_id,))
    conn.commit()
    conn.close()
    
    await query.edit_message_caption(
        query.message.caption + f"\n\n❌ *BEKOR QILINDI* — {datetime.now().strftime('%H:%M')}",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        await update.get_bot().send_message(
            user_id,
            f"❌ *Hisobni to'ldirish bekor qilindi.*\n\n"
            f"💰 Miqdor: {format_son(miqdor)} so'm\n"
            f"Muammo bo'lsa admin bilan bog'laning.",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass

# ─── KOD ORQALI KINO TOPISH ───────────────────────────────────────────────────
async def kod_qidirish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().upper()
    
    conn = db_connect()
    kino = conn.execute("SELECT * FROM kinolar WHERE kod=?", (text,)).fetchone()
    conn.close()
    
    if not kino:
        return  # Boshqa handlerga o'tsin
    
    await show_kino(update, context, kino)

async def show_kino(update, context, kino):
    user_id = update.effective_user.id
    conn = db_connect()
    qismlar = conn.execute(
        "SELECT * FROM qismlar WHERE kino_id=? ORDER BY qism_raqam",
        (kino['id'],)
    ).fetchall()
    conn.close()
    
    jami_qism = len(qismlar)
    
    caption = (
        f"🎬 *{kino['nomi']}*\n\n"
        f"🎞 Qismi: {jami_qism}\n"
        f"🌍 Davlati: {kino['davlat']}\n"
        f"🇺🇿 Tili: {kino['til']}\n"
        f"📅 Yili: {kino['yil'] or '-'}\n"
        f"🎭 Janri: {kino['janr'] or '-'}\n\n"
        f"📂 Kodni eslab qoling: `{kino['kod']}`"
    )
    
    buttons = []
    row = []
    for i, q in enumerate(qismlar):
        label = f"{q['qism_raqam']}-qism"
        if q['is_vip']:
            label = f"💎 {label}"
        row.append(InlineKeyboardButton(label, callback_data=f"qism_{q['id']}_{kino['id']}"))
        if len(row) == 3 or i == len(qismlar) - 1:
            buttons.append(row)
            row = []
    
    if kino['rasm_file_id']:
        await update.message.reply_photo(
            kino['rasm_file_id'],
            caption=caption,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            caption,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN
        )

# ─── QISM YUBORISH ────────────────────────────────────────────────────────────
async def qism_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    _, qism_id, kino_id = query.data.split("_")
    qism_id, kino_id = int(qism_id), int(kino_id)
    
    conn = db_connect()
    qism = conn.execute("SELECT * FROM qismlar WHERE id=?", (qism_id,)).fetchone()
    kino = conn.execute("SELECT * FROM kinolar WHERE id=?", (kino_id,)).fetchone()
    
    if not qism:
        await query.answer("Qism topilmadi!", show_alert=True)
        conn.close()
        return
    
    # VIP tekshiruv
    if qism['is_vip'] and not is_vip(user_id):
        # Balansdan to'lash
        user = get_user(user_id)
        narx = qism['narx']
        
        buttons = [
            [InlineKeyboardButton(
                f"💳 Balansdan to'lash ({format_son(narx)} so'm)",
                callback_data=f"balans_tolov_{qism_id}_{kino_id}"
            )],
            [InlineKeyboardButton("💎 VIP sotib olish", callback_data="vip_menu")],
        ]
        
        await query.message.reply_text(
            f"🔒 *Bu qism pullik!*\n\n"
            f"💰 Narxi: {format_son(narx)} so'm\n"
            f"💼 Balansingiz: {format_son(user['balans'])} so'm",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.MARKDOWN
        )
        conn.close()
        return
    
    # Allaqachon sotib olinganmi?
    xarid = conn.execute(
        "SELECT * FROM qism_xaridlar WHERE user_id=? AND qism_id=?",
        (user_id, qism_id)
    ).fetchone()
    
    conn.close()
    
    # Ulashish tugmasi
    share_text = f"🎬 {kino['nomi']} — {qism['qism_raqam']}-qism\nKod: {kino['kod']}"
    buttons = [
        [InlineKeyboardButton(
            "📤 Do'stlarga ulashish",
            switch_inline_query=share_text
        )]
    ]
    
    await query.message.reply_video(
        qism['file_id'],
        caption=f"🎬 *{kino['nomi']}* — {qism['qism_raqam']}-qism",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN,
        protect_content=True  # Screenshot va saqlashdan himoya
    )

# ─── BALANSDAN TO'LOV ─────────────────────────────────────────────────────────
async def balans_tolov_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    _, _, qism_id, kino_id = query.data.split("_")
    qism_id, kino_id = int(qism_id), int(kino_id)
    
    conn = db_connect()
    qism = conn.execute("SELECT * FROM qismlar WHERE id=?", (qism_id,)).fetchone()
    user = conn.execute("SELECT * FROM foydalanuvchilar WHERE id=?", (user_id,)).fetchone()
    kino = conn.execute("SELECT * FROM kinolar WHERE id=?", (kino_id,)).fetchone()
    
    if user['balans'] < qism['narx']:
        conn.close()
        await query.message.reply_text(
            f"❌ Balans yetarli emas!\n"
            f"💰 Kerak: {format_son(qism['narx'])} so'm\n"
            f"💼 Balansingiz: {format_son(user['balans'])} so'm",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💳 To'ldirish", callback_data="hisobni_toldirish")
            ]])
        )
        return
    
    conn.execute(
        "UPDATE foydalanuvchilar SET balans=balans-? WHERE id=?",
        (qism['narx'], user_id)
    )
    conn.execute(
        "INSERT INTO qism_xaridlar (user_id, qism_id, usul) VALUES (?, ?, 'balans')",
        (user_id, qism_id)
    )
    conn.commit()
    conn.close()
    
    share_text = f"🎬 {kino['nomi']} — {qism['qism_raqam']}-qism\nKod: {kino['kod']}"
    buttons = [[InlineKeyboardButton("📤 Do'stlarga ulashish", switch_inline_query=share_text)]]
    
    await query.message.reply_video(
        qism['file_id'],
        caption=f"✅ To'lov muvaffaqiyatli!\n🎬 *{kino['nomi']}* — {qism['qism_raqam']}-qism",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN,
        protect_content=True
    )

# ─── VIP TARIFLAR ─────────────────────────────────────────────────────────────
async def vip_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        msg = update.callback_query.message
        await update.callback_query.answer()
    else:
        msg = update.message
    
    conn = db_connect()
    tariflar = conn.execute("SELECT * FROM tariflar WHERE is_active=1").fetchall()
    conn.close()
    
    if not tariflar:
        await msg.reply_text("Hozirda VIP tariflar mavjud emas.")
        return
    
    text = "💎 *VIP Tariflar*\n\n"
    buttons = []
    for t in tariflar:
        text += f"⭐ *{t['nomi']}* — {format_son(t['narx'])} so'm ({t['kunlar']} kun)\n"
        buttons.append([InlineKeyboardButton(
            f"⭐ {t['nomi']} — {format_son(t['narx'])} so'm",
            callback_data=f"vip_buy_{t['id']}"
        )])
    
    # Kanalga xabar tugmasi (foydalanuvchilar uchun emas)
    await msg.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN
    )

async def vip_buy_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    tarif_id = int(query.data.split("_")[2])
    conn = db_connect()
    tarif = conn.execute("SELECT * FROM tariflar WHERE id=?", (tarif_id,)).fetchone()
    conn.close()
    
    context.user_data['vip_tarif_id'] = tarif_id
    
    karta = get_active_karta()
    if not karta:
        await query.message.reply_text("❌ Karta mavjud emas!")
        return
    
    await query.message.reply_text(
        f"💎 *{tarif['nomi']}* sotib olish\n\n"
        f"💰 Narxi: {format_son(tarif['narx'])} so'm\n"
        f"📅 Muddat: {tarif['kunlar']} kun\n\n"
        f"💳 Karta: `{karta['raqam']}`\n"
        f"👤 Egasi: {karta['egasi'] or '-'}\n\n"
        f"To'lovni amalga oshirib, chek yuboring:",
        parse_mode=ParseMode.MARKDOWN
    )
    return U_VIP_CHEK

async def vip_chek(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Chek rasmini yuboring!")
        return U_VIP_CHEK
    
    user_id = update.effective_user.id
    tarif_id = context.user_data.get('vip_tarif_id')
    file_id = update.message.photo[-1].file_id
    
    conn = db_connect()
    tarif = conn.execute("SELECT * FROM tariflar WHERE id=?", (tarif_id,)).fetchone()
    conn.execute(
        "INSERT INTO tolovlar (user_id, miqdor, chek_file_id) VALUES (?, ?, ?)",
        (user_id, tarif['narx'], file_id)
    )
    tolov_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    
    user = update.effective_user
    for admin_id in ADMIN_IDS:
        try:
            buttons = [
                [
                    InlineKeyboardButton(
                        "✅ VIP Berish",
                        callback_data=f"vip_ok_{tolov_id}_{user_id}_{tarif_id}"
                    ),
                    InlineKeyboardButton(
                        "❌ Bekor",
                        callback_data=f"vip_no_{tolov_id}_{user_id}"
                    ),
                ],
                [InlineKeyboardButton("💬 Xabar", callback_data=f"xabar_yu_{user_id}")]
            ]
            await update.get_bot().send_photo(
                admin_id, file_id,
                caption=(
                    f"💎 *VIP So'rovi!*\n\n"
                    f"👤 {user.full_name}\n"
                    f"🆔 {user_id}\n"
                    f"⭐ Tarif: {tarif['nomi']}\n"
                    f"💰 {format_son(tarif['narx'])} so'm"
                ),
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            pass
    
    await update.message.reply_text(
        "✅ Chek yuborildi! Tez orada VIP beriladi.",
        reply_markup=main_menu_keyboard()
    )
    return U_MAIN

async def vip_ok_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    
    parts = query.data.split("_")
    tolov_id, user_id, tarif_id = int(parts[2]), int(parts[3]), int(parts[4])
    
    conn = db_connect()
    tarif = conn.execute("SELECT * FROM tariflar WHERE id=?", (tarif_id,)).fetchone()
    user = conn.execute("SELECT * FROM foydalanuvchilar WHERE id=?", (user_id,)).fetchone()
    
    expire = datetime.now() + timedelta(days=tarif['kunlar'])
    if user['vip_expire']:
        try:
            existing = datetime.fromisoformat(user['vip_expire'])
            if existing > datetime.now():
                expire = existing + timedelta(days=tarif['kunlar'])
        except:
            pass
    
    conn.execute(
        "UPDATE foydalanuvchilar SET vip_expire=? WHERE id=?",
        (expire.isoformat(), user_id)
    )
    conn.execute(
        "UPDATE tolovlar SET status='tasdiqlandi' WHERE id=?", (tolov_id,)
    )
    conn.commit()
    conn.close()
    
    await query.edit_message_caption(
        query.message.caption + f"\n\n✅ *VIP BERILDI* — {expire.strftime('%d.%m.%Y')} gacha",
        parse_mode=ParseMode.MARKDOWN
    )
    
    try:
        await update.get_bot().send_message(
            user_id,
            f"🎉 *VIP maqomingiz faollashtirildi!*\n\n"
            f"💎 Tarif: {tarif['nomi']}\n"
            f"📅 {expire.strftime('%d.%m.%Y')} gacha",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass

async def vip_no_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    
    parts = query.data.split("_")
    tolov_id, user_id = int(parts[2]), int(parts[3])
    
    conn = db_connect()
    conn.execute("UPDATE tolovlar SET status='bekor' WHERE id=?", (tolov_id,))
    conn.commit()
    conn.close()
    
    await query.edit_message_caption(
        query.message.caption + "\n\n❌ *BEKOR QILINDI*",
        parse_mode=ParseMode.MARKDOWN
    )
    try:
        await update.get_bot().send_message(user_id, "❌ VIP so'rovingiz bekor qilindi.")
    except:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN PANELI
# ═══════════════════════════════════════════════════════════════════════════════

def admin_menu_keyboard():
    """Admin menyu - rangli tugmalar (InlineKeyboard orqali)"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 Kino qo'shish", callback_data="ap_kino_add"),
            InlineKeyboardButton("📢 Kanal post", callback_data="ap_kanal_post"),
        ],
        [
            InlineKeyboardButton("💎 VIP Tariflar", callback_data="ap_tarif"),
            InlineKeyboardButton("💳 Karta qo'shish", callback_data="ap_karta"),
        ],
        [
            InlineKeyboardButton("🔒 Majburiy obuna", callback_data="ap_majburiy"),
            InlineKeyboardButton("📊 Statistika", callback_data="ap_stat"),
        ],
        [
            InlineKeyboardButton("📨 Xabar yuborish", callback_data="ap_xabar"),
            InlineKeyboardButton("💰 Pulik qism", callback_data="ap_pulik"),
        ],
    ])

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Ruxsat yo'q!")
        return
    
    await update.message.reply_text(
        "🔧 *Admin Panel*\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=admin_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def ap_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔧 *Admin Panel*",
        reply_markup=admin_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

# ─── KINO QO'SHISH ────────────────────────────────────────────────────────────
async def ap_kino_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    context.user_data['qismlar'] = []
    
    await query.edit_message_text(
        "🎬 *Yangi kino qo'shish*\n\nKino nomini kiriting:",
        parse_mode=ParseMode.MARKDOWN
    )
    return AP_KINO_NOMI

async def ap_kino_nomi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['kino_nomi'] = update.message.text.strip()
    await update.message.reply_text(
        "🖼 Kino rasmini yuboring (poster):"
    )
    return AP_KINO_RASM

async def ap_kino_rasm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data['kino_rasm'] = update.message.photo[-1].file_id
    else:
        context.user_data['kino_rasm'] = None
    
    await update.message.reply_text(
        "🔑 Kino kodini kiriting (masalan: OMADLIZARBA):\n\n"
        "⚠️ Faqat katta harf va son, bo'sh joy yo'q!"
    )
    return AP_KINO_KOD

async def ap_kino_kod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kod = update.message.text.strip().upper()
    
    conn = db_connect()
    existing = conn.execute("SELECT id FROM kinolar WHERE kod=?", (kod,)).fetchone()
    conn.close()
    
    if existing:
        await update.message.reply_text("❌ Bu kod allaqachon mavjud! Boshqa kod kiriting:")
        return AP_KINO_KOD
    
    context.user_data['kino_kod'] = kod
    
    await update.message.reply_text(
        "🌍 Davlatni kiriting (masalan: Xitoy):"
    )
    return AP_KINO_TIL

async def ap_kino_til(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['kino_davlat'] = update.message.text.strip()
    
    buttons = [
        [InlineKeyboardButton("O'zbek tilida", callback_data="til_uz")],
        [InlineKeyboardButton("Rus tilida", callback_data="til_ru")],
        [InlineKeyboardButton("Ingliz tilida", callback_data="til_en")],
    ]
    await update.message.reply_text(
        "🇺🇿 Tilni tanlang:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return AP_KINO_JANR

async def ap_til_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    til_map = {"til_uz": "O'zbek tilida", "til_ru": "Rus tilida", "til_en": "Ingliz tilida"}
    context.user_data['kino_til'] = til_map.get(query.data, "O'zbek tilida")
    
    await query.message.reply_text("🎭 Janrini kiriting (masalan: Mini drama):")
    return AP_KINO_QISM_ADD

async def ap_kino_janr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['kino_janr'] = update.message.text.strip()
    await update.message.reply_text(
        f"✅ Ma'lumotlar:\n"
        f"📽 Nomi: {context.user_data.get('kino_nomi')}\n"
        f"🔑 Kod: {context.user_data.get('kino_kod')}\n"
        f"🌍 Davlat: {context.user_data.get('kino_davlat')}\n"
        f"🇺🇿 Til: {context.user_data.get('kino_til')}\n"
        f"🎭 Janr: {context.user_data.get('kino_janr')}\n\n"
        f"Endi 1-qism videosini yuboring:"
    )
    return AP_KINO_QISM_FILE

async def ap_qism_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.video and not update.message.document:
        await update.message.reply_text("❌ Video yuboring!")
        return AP_KINO_QISM_FILE
    
    file_id = (update.message.video or update.message.document).file_id
    qismlar = context.user_data.get('qismlar', [])
    qism_raqam = len(qismlar) + 1
    qismlar.append({'raqam': qism_raqam, 'file_id': file_id})
    context.user_data['qismlar'] = qismlar
    
    buttons = [
        [InlineKeyboardButton("➕ Yana qism qo'shish", callback_data="ap_qism_yana")],
        [InlineKeyboardButton("✅ Tugatish va saqlash", callback_data="ap_qism_save")],
    ]
    await update.message.reply_text(
        f"✅ {qism_raqam}-qism qo'shildi! (Jami: {len(qismlar)} qism)\n\n"
        f"Davom etasizmi?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return AP_KINO_QISM_YANA

async def ap_qism_yana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    qismlar = context.user_data.get('qismlar', [])
    await query.message.reply_text(
        f"📹 {len(qismlar)+1}-qism videosini yuboring:"
    )
    return AP_KINO_QISM_FILE

async def ap_qism_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = context.user_data
    conn = db_connect()
    conn.execute(
        "INSERT INTO kinolar (nomi, kod, rasm_file_id, til, janr, davlat, yil) VALUES (?,?,?,?,?,?,?)",
        (
            data.get('kino_nomi'), data.get('kino_kod'), data.get('kino_rasm'),
            data.get('kino_til', "O'zbek tilida"), data.get('kino_janr'),
            data.get('kino_davlat', 'Xitoy'), datetime.now().year
        )
    )
    kino_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    
    for q in data.get('qismlar', []):
        conn.execute(
            "INSERT INTO qismlar (kino_id, qism_raqam, file_id) VALUES (?,?,?)",
            (kino_id, q['raqam'], q['file_id'])
        )
    conn.commit()
    conn.close()
    
    await query.message.reply_text(
        f"✅ *Kino saqlandi!*\n\n"
        f"🎬 {data.get('kino_nomi')}\n"
        f"🔑 Kod: `{data.get('kino_kod')}`\n"
        f"📹 {len(data.get('qismlar', []))} qism",
        reply_markup=admin_menu_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data.clear()
    return AP_MAIN

# ─── KANAL POST ───────────────────────────────────────────────────────────────
async def ap_kanal_post_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['post'] = {}
    
    await query.edit_message_text(
        "📢 *Kanal uchun post*\n\nKino rasmini yuboring:",
        parse_mode=ParseMode.MARKDOWN
    )
    return AP_KANAL_RASM

async def ap_kanal_rasm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ Rasm yuboring!")
        return AP_KANAL_RASM
    
    context.user_data['post']['rasm'] = update.message.photo[-1].file_id
    await update.message.reply_text("🎬 Kino nomini kiriting:")
    return AP_KANAL_NOMI

async def ap_kanal_nomi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['post']['nomi'] = update.message.text.strip()
    await update.message.reply_text("🔢 Jami qismlar sonini kiriting (masalan: 100):")
    return AP_KANAL_QISM

async def ap_kanal_qism(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['post']['qism'] = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Raqam kiriting!")
        return AP_KANAL_QISM
    
    buttons = [
        [InlineKeyboardButton("O'zbek tilida", callback_data="post_til_uz")],
        [InlineKeyboardButton("Rus tilida", callback_data="post_til_ru")],
    ]
    await update.message.reply_text("🇺🇿 Tilni tanlang:", reply_markup=InlineKeyboardMarkup(buttons))
    return AP_KANAL_TIL

async def ap_kanal_til_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    til_map = {"post_til_uz": "O'zbek tilida", "post_til_ru": "Rus tilida"}
    context.user_data['post']['til'] = til_map.get(query.data, "O'zbek tilida")
    await query.message.reply_text("🔑 Bot kodi kiriting (foydalanuvchi botga shu kodni yozadi):")
    return AP_KANAL_KO

async def ap_kanal_kod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['post']['kod'] = update.message.text.strip().upper()
    
    post = context.user_data['post']
    
    # Post ko'rinishi
    caption = (
        f"🎬 *{post['nomi']}*\n\n"
        f"▶ Qism : {post['qism']}\n"
        f"▶ Tili : {post['til']}\n"
        f"▶ Ko'rish : [Tomosha qilish](https://t.me/YOUR_BOT_USERNAME)"
    )
    
    # Ko'rish tugmasi
    buttons = [
        [InlineKeyboardButton(
            "🎬 Tomosha qilish 🎬",
            url=f"https://t.me/YOUR_BOT_USERNAME?start={post['kod']}"
        )]
    ]
    
    context.user_data['post']['caption'] = caption
    context.user_data['post']['buttons'] = buttons
    
    await update.message.reply_photo(
        post['rasm'],
        caption=caption + "\n\n*Ko'rinishi shunday bo'ladi. Tasdiqlaysizmi?*",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yuborish", callback_data="post_yuborish"),
                InlineKeyboardButton("❌ Bekor", callback_data="ap_back"),
            ]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )
    return AP_KANAL_TASDIQLASH

async def ap_post_yuborish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    post = context.user_data.get('post', {})
    
    try:
        await update.get_bot().send_photo(
            CHANNEL_ID,
            post['rasm'],
            caption=post['caption'],
            reply_markup=InlineKeyboardMarkup(post['buttons']),
            parse_mode=ParseMode.MARKDOWN
        )
        await query.message.reply_text(
            "✅ Post kanalga yuborildi!",
            reply_markup=admin_menu_keyboard()
        )
    except Exception as e:
        await query.message.reply_text(f"❌ Xato: {e}")
    
    context.user_data.clear()
    return AP_MAIN

# ─── VIP TARIFLAR (ADMIN) ─────────────────────────────────────────────────────
async def ap_tarif_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = db_connect()
    tariflar = conn.execute("SELECT * FROM tariflar WHERE is_active=1").fetchall()
    conn.close()
    
    text = "💎 *VIP Tariflar*\n\n"
    buttons = []
    for t in tariflar:
        text += f"• {t['nomi']} — {format_son(t['narx'])} so'm ({t['kunlar']} kun)\n"
        buttons.append([InlineKeyboardButton(
            f"🗑 {t['nomi']} o'chirish", callback_data=f"tarif_del_{t['id']}"
        )])
    
    buttons.append([InlineKeyboardButton("➕ Yangi tarif", callback_data="tarif_add")])
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="ap_back")])
    
    await query.edit_message_text(
        text or "Tariflar yo'q",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN
    )

async def ap_tarif_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("💎 Tarif nomini kiriting (masalan: 1 oylik):")
    return AP_TARIF_NOMI

async def ap_tarif_nomi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['tarif_nomi'] = update.message.text.strip()
    await update.message.reply_text("💰 Narxini kiriting (so'mda, masalan: 50000):")
    return AP_TARIF_NARX

async def ap_tarif_narx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['tarif_narx'] = int(update.message.text.replace(" ", ""))
    except:
        await update.message.reply_text("❌ Raqam kiriting!")
        return AP_TARIF_NARX
    await update.message.reply_text("📅 Necha kun amal qiladi:")
    return AP_TARIF_KUN

async def ap_tarif_kun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        kunlar = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Raqam kiriting!")
        return AP_TARIF_KUN
    
    conn = db_connect()
    conn.execute(
        "INSERT INTO tariflar (nomi, narx, kunlar) VALUES (?,?,?)",
        (context.user_data['tarif_nomi'], context.user_data['tarif_narx'], kunlar)
    )
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ Tarif qo'shildi!",
        reply_markup=admin_menu_keyboard()
    )
    return AP_MAIN

async def tarif_del_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tarif_id = int(query.data.split("_")[2])
    conn = db_connect()
    conn.execute("UPDATE tariflar SET is_active=0 WHERE id=?", (tarif_id,))
    conn.commit()
    conn.close()
    await ap_tarif_start(update, context)

# ─── KARTA QO'SHISH (ADMIN) ───────────────────────────────────────────────────
async def ap_karta_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = db_connect()
    kartalar = conn.execute("SELECT * FROM kartalar WHERE is_active=1").fetchall()
    conn.close()
    
    text = "💳 *Kartalar*\n\n"
    buttons = []
    for k in kartalar:
        text += f"• `{k['raqam']}` — {k['egasi'] or '-'}\n"
        buttons.append([InlineKeyboardButton(
            f"🗑 {k['raqam']} o'chirish", callback_data=f"karta_del_{k['id']}"
        )])
    
    buttons.append([InlineKeyboardButton("➕ Karta qo'shish", callback_data="karta_add")])
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="ap_back")])
    
    await query.edit_message_text(
        text or "Kartalar yo'q",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN
    )

async def ap_karta_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "💳 Karta raqamini kiriting (masalan: 8600 1234 5678 9012):"
    )
    return AP_KARTA_ADD

async def ap_karta_raqam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raqam = update.message.text.strip()
    context.user_data['karta_raqam'] = raqam
    await update.message.reply_text("👤 Karta egasining ismini kiriting:")
    return AP_KARTA_ADD + 1

async def ap_karta_egasi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    egasi = update.message.text.strip()
    conn = db_connect()
    conn.execute(
        "INSERT INTO kartalar (raqam, egasi) VALUES (?,?)",
        (context.user_data['karta_raqam'], egasi)
    )
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Karta qo'shildi!", reply_markup=admin_menu_keyboard())
    return AP_MAIN

async def karta_del_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    karta_id = int(query.data.split("_")[2])
    conn = db_connect()
    conn.execute("UPDATE kartalar SET is_active=0 WHERE id=?", (karta_id,))
    conn.commit()
    conn.close()
    await ap_karta_start(update, context)

# ─── MAJBURIY OBUNA (ADMIN) ───────────────────────────────────────────────────
async def ap_majburiy_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = db_connect()
    majburiylar = conn.execute("SELECT * FROM majburiy_obunalar WHERE is_active=1").fetchall()
    conn.close()
    
    text = "🔒 *Majburiy Obunalar*\n\n"
    buttons = []
    for m in majburiylar:
        text += f"• {m['nomi'] or m['link']} ({m['tur']})\n"
        buttons.append([InlineKeyboardButton(
            f"🗑 {m['nomi'] or m['link']}", callback_data=f"maj_del_{m['id']}"
        )])
    
    buttons.append([InlineKeyboardButton("➕ Qo'shish", callback_data="maj_add")])
    buttons.append([InlineKeyboardButton("🔙 Orqaga", callback_data="ap_back")])
    
    await query.edit_message_text(
        text or "Majburiy obunalar yo'q",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN
    )

async def ap_majburiy_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    buttons = [
        [InlineKeyboardButton("📢 Telegram kanal", callback_data="maj_tur_kanal")],
        [InlineKeyboardButton("🤖 Bot linki", callback_data="maj_tur_bot")],
        [InlineKeyboardButton("🔗 Oddiy link", callback_data="maj_tur_link")],
    ]
    await query.message.reply_text("Tur tanlang:", reply_markup=InlineKeyboardMarkup(buttons))
    return AP_MAJBURIY_TUR

async def ap_majburiy_tur(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tur_map = {"maj_tur_kanal": "kanal", "maj_tur_bot": "bot", "maj_tur_link": "link"}
    context.user_data['maj_tur'] = tur_map.get(query.data, "kanal")
    await query.message.reply_text("🔗 Link kiriting (masalan: @channel_username yoki https://...):")
    return AP_MAJBURIY_LINK

async def ap_majburiy_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text.strip()
    await update.message.reply_text("📝 Nom kiriting (ko'rinadigan nom):")
    context.user_data['maj_link'] = link
    return AP_MAJBURIY_LINK + 1

async def ap_majburiy_nomi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nomi = update.message.text.strip()
    conn = db_connect()
    conn.execute(
        "INSERT INTO majburiy_obunalar (nomi, link, tur) VALUES (?,?,?)",
        (nomi, context.user_data['maj_link'], context.user_data['maj_tur'])
    )
    conn.commit()
    conn.close()
    await update.message.reply_text("✅ Majburiy obuna qo'shildi!", reply_markup=admin_menu_keyboard())
    return AP_MAIN

async def maj_del_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    maj_id = int(query.data.split("_")[2])
    conn = db_connect()
    conn.execute("UPDATE majburiy_obunalar SET is_active=0 WHERE id=?", (maj_id,))
    conn.commit()
    conn.close()
    await ap_majburiy_start(update, context)

# ─── PULIK QISM (ADMIN) ───────────────────────────────────────────────────────
async def ap_pulik_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "💰 *Qismni pulik qilish*\n\nKino kodini kiriting:",
        parse_mode=ParseMode.MARKDOWN
    )
    return AP_KINO_VIP

async def ap_pulik_kod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kod = update.message.text.strip().upper()
    conn = db_connect()
    kino = conn.execute("SELECT * FROM kinolar WHERE kod=?", (kod,)).fetchone()
    
    if not kino:
        conn.close()
        await update.message.reply_text("❌ Kino topilmadi! Kod qayta kiriting:")
        return AP_KINO_VIP
    
    context.user_data['pulik_kino_id'] = kino['id']
    context.user_data['pulik_kino_nomi'] = kino['nomi']
    
    qismlar = conn.execute(
        "SELECT * FROM qismlar WHERE kino_id=? ORDER BY qism_raqam",
        (kino['id'],)
    ).fetchall()
    conn.close()
    
    text = f"🎬 {kino['nomi']}\n\n"
    for q in qismlar:
        status = "💎 Pulik" if q['is_vip'] else "🆓 Bepul"
        text += f"{q['qism_raqam']}-qism: {status} ({format_son(q['narx'])} so'm)\n"
    
    text += "\nQaysi qismni pulik qilmoqchisiz? Raqamini kiriting:"
    await update.message.reply_text(text)
    return AP_KINO_VIP_QISM

async def ap_pulik_qism(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        qism_raqam = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Raqam kiriting!")
        return AP_KINO_VIP_QISM
    
    context.user_data['pulik_qism_raqam'] = qism_raqam
    await update.message.reply_text("💰 Narxni kiriting (so'mda):")
    return AP_KINO_VIP_NARX

async def ap_pulik_narx(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        narx = int(update.message.text.replace(" ", ""))
    except:
        await update.message.reply_text("❌ Raqam kiriting!")
        return AP_KINO_VIP_NARX
    
    kino_id = context.user_data['pulik_kino_id']
    qism_raqam = context.user_data['pulik_qism_raqam']
    
    conn = db_connect()
    conn.execute(
        "UPDATE qismlar SET is_vip=1, narx=? WHERE kino_id=? AND qism_raqam=?",
        (narx, kino_id, qism_raqam)
    )
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ {qism_raqam}-qism pulik qilindi! Narxi: {format_son(narx)} so'm",
        reply_markup=admin_menu_keyboard()
    )
    return AP_MAIN

# ─── STATISTIKA (ADMIN) ───────────────────────────────────────────────────────
async def ap_stat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = db_connect()
    
    bir_oy_oldin = (datetime.now() - timedelta(days=30)).isoformat()
    bir_hafta_oldin = (datetime.now() - timedelta(days=7)).isoformat()
    
    jami_users = conn.execute("SELECT COUNT(*) FROM foydalanuvchilar").fetchone()[0]
    yangi_oy = conn.execute(
        "SELECT COUNT(*) FROM foydalanuvchilar WHERE created_at>=?", (bir_oy_oldin,)
    ).fetchone()[0]
    
    jami_vip = conn.execute(
        "SELECT COUNT(*) FROM foydalanuvchilar WHERE vip_expire>?", (datetime.now().isoformat(),)
    ).fetchone()[0]
    
    oy_daromad = conn.execute(
        "SELECT SUM(miqdor) FROM tolovlar WHERE status='tasdiqlandi' AND created_at>=?",
        (bir_oy_oldin,)
    ).fetchone()[0] or 0
    
    hafta_toldirgan = conn.execute(
        "SELECT COUNT(DISTINCT user_id) FROM tolovlar WHERE created_at>=?",
        (bir_hafta_oldin,)
    ).fetchone()[0]
    
    top15 = conn.execute(
        "SELECT id, full_name, balans FROM foydalanuvchilar ORDER BY balans DESC LIMIT 15"
    ).fetchall()
    
    conn.close()
    
    top_text = "\n".join([
        f"{i+1}. {u['full_name'] or u['id']} — {format_son(u['balans'])} so'm"
        for i, u in enumerate(top15)
    ])
    
    text = (
        f"📊 *Statistika*\n\n"
        f"👥 Jami foydalanuvchilar: {jami_users}\n"
        f"📅 Bu oy yangi: +{yangi_oy}\n"
        f"💎 Aktiv VIP: {jami_vip}\n"
        f"💰 Bu oy daromad: {format_son(oy_daromad)} so'm\n"
        f"🔄 Bu hafta to'ldirgan: {hafta_toldirgan} kishi\n\n"
        f"🏆 *Top 15 balans:*\n{top_text or 'Ma\'lumot yo\'q'}"
    )
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Orqaga", callback_data="ap_back")
        ]]),
        parse_mode=ParseMode.MARKDOWN
    )

# ─── XABAR YUBORISH (ADMIN ↔ USER) ───────────────────────────────────────────
async def xabar_yu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return
    
    user_id = int(query.data.split("_")[2])
    context.user_data['xabar_user_id'] = user_id
    await query.message.reply_text(
        f"📨 Foydalanuvchi ({user_id}) ga xabar yuboring:\n"
        "(Matn, rasm yoki ovozli xabar)"
    )
    return AP_XABAR_MATN

async def ap_xabar_all_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['xabar_user_id'] = 'all'
    await query.message.reply_text(
        "📨 *Barcha foydalanuvchilarga xabar*\n\nXabarni yuboring:",
        parse_mode=ParseMode.MARKDOWN
    )
    return AP_XABAR_MATN

async def ap_xabar_matn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target = context.user_data.get('xabar_user_id')
    
    conn = db_connect()
    
    if target == 'all':
        users = conn.execute("SELECT id FROM foydalanuvchilar").fetchall()
        yuborildi = 0
        for u in users:
            try:
                await _forward_message(update, update.get_bot(), u['id'])
                yuborildi += 1
            except:
                pass
        await update.message.reply_text(
            f"✅ {yuborildi} ta foydalanuvchiga yuborildi.",
            reply_markup=admin_menu_keyboard()
        )
    else:
        try:
            await _forward_message(update, update.get_bot(), int(target))
            # Foydalanuvchi tomonidan adminlarga javob berish imkoni
            for admin_id in ADMIN_IDS:
                await update.get_bot().send_message(
                    admin_id,
                    f"👤 Foydalanuvchi ({target}) ga xabar yuborildi.",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("💬 Javob", callback_data=f"xabar_yu_{target}")
                    ]])
                )
            await update.message.reply_text("✅ Xabar yuborildi!")
        except Exception as e:
            await update.message.reply_text(f"❌ Xato: {e}")
    
    conn.close()
    return AP_MAIN

async def _forward_message(update, bot, chat_id):
    msg = update.message
    if msg.text:
        await bot.send_message(chat_id, msg.text)
    elif msg.photo:
        await bot.send_photo(chat_id, msg.photo[-1].file_id, caption=msg.caption or "")
    elif msg.voice:
        await bot.send_voice(chat_id, msg.voice.file_id)
    elif msg.video:
        await bot.send_video(chat_id, msg.video.file_id, caption=msg.caption or "")

# ─── VIP KINOLAR QIDIRISH ─────────────────────────────────────────────────────
async def vip_qidirish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """VIP tariflar sahifasida bepul kinolar kodini kiritsa chiqmaydi"""
    pass  # Oddiy kinolar uchun kod_qidirish ishlatiladi

# ─── KANAL XABARLARI (BEPUL / VIP) ───────────────────────────────────────────
async def ap_kanal_xabar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    buttons = [
        [
            InlineKeyboardButton("📢 Bepul foydalanuvchilarga", callback_data="ap_xabar_bepul"),
            InlineKeyboardButton("💎 VIP foydalanuvchilarga", callback_data="ap_xabar_vip"),
        ],
        [InlineKeyboardButton("👥 Hammaga", callback_data="ap_xabar_all")],
        [InlineKeyboardButton("🔙 Orqaga", callback_data="ap_back")],
    ]
    await query.edit_message_text(
        "📨 *Xabar yuborish*\n\nKimga?",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.MARKDOWN
    )

# ═══════════════════════════════════════════════════════════════════════════════
#  ASOSIY TUGMALAR HANDLERLARI
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    not_sub = await check_subscription(update.get_bot(), user_id)
    if not_sub:
        await send_subscription_msg(update, not_sub)
        return
    
    if text == "👤 Hisobim":
        await hisobim(update, context)
    elif text == "💎 VIP Tariflar":
        await vip_menu(update, context)
    elif text == "🎬 Kinolar":
        await update.message.reply_text(
            "🔍 Kino kodini kiriting (masalan: OMADLIZARBA):"
        )
    elif text == "🔍 Qidirish":
        await update.message.reply_text("🔍 Qidirish uchun kino kodini kiriting:")
    else:
        # Kod qidirish
        await kod_qidirish(update, context)

# ═══════════════════════════════════════════════════════════════════════════════
#  ASOSIY FUNKSIYA
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    db_init()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    # ── Admin ConversationHandler ──────────────────────────────────────────────
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", admin_panel)],
        states={
            AP_MAIN: [
                CallbackQueryHandler(ap_kino_add_start, pattern="^ap_kino_add$"),
                CallbackQueryHandler(ap_kanal_post_start, pattern="^ap_kanal_post$"),
                CallbackQueryHandler(ap_tarif_start, pattern="^ap_tarif$"),
                CallbackQueryHandler(ap_karta_start, pattern="^ap_karta$"),
                CallbackQueryHandler(ap_majburiy_start, pattern="^ap_majburiy$"),
                CallbackQueryHandler(ap_stat, pattern="^ap_stat$"),
                CallbackQueryHandler(ap_kanal_xabar, pattern="^ap_xabar$"),
                CallbackQueryHandler(ap_pulik_start, pattern="^ap_pulik$"),
                CallbackQueryHandler(ap_back, pattern="^ap_back$"),
            ],
            AP_KINO_NOMI: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_kino_nomi)],
            AP_KINO_RASM: [MessageHandler(filters.PHOTO | filters.TEXT, ap_kino_rasm)],
            AP_KINO_KOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_kino_kod)],
            AP_KINO_TIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_kino_til)],
            AP_KINO_JANR: [
                CallbackQueryHandler(ap_til_callback, pattern="^til_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ap_kino_janr),
            ],
            AP_KINO_QISM_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_kino_janr)],
            AP_KINO_QISM_FILE: [MessageHandler(filters.VIDEO | filters.Document.VIDEO, ap_qism_file)],
            AP_KINO_QISM_YANA: [
                CallbackQueryHandler(ap_qism_yana, pattern="^ap_qism_yana$"),
                CallbackQueryHandler(ap_qism_save, pattern="^ap_qism_save$"),
            ],
            AP_KANAL_RASM: [MessageHandler(filters.PHOTO, ap_kanal_rasm)],
            AP_KANAL_NOMI: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_kanal_nomi)],
            AP_KANAL_QISM: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_kanal_qism)],
            AP_KANAL_TIL: [CallbackQueryHandler(ap_kanal_til_cb, pattern="^post_til_")],
            AP_KANAL_KO: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_kanal_kod)],
            AP_KANAL_TASDIQLASH: [
                CallbackQueryHandler(ap_post_yuborish, pattern="^post_yuborish$"),
                CallbackQueryHandler(ap_back, pattern="^ap_back$"),
            ],
            AP_TARIF_NOMI: [
                CallbackQueryHandler(ap_tarif_add_start, pattern="^tarif_add$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ap_tarif_nomi),
            ],
            AP_TARIF_NARX: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_tarif_narx)],
            AP_TARIF_KUN: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_tarif_kun)],
            AP_KARTA_ADD: [
                CallbackQueryHandler(ap_karta_add, pattern="^karta_add$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ap_karta_raqam),
            ],
            AP_KARTA_ADD + 1: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_karta_egasi)],
            AP_MAJBURIY_TUR: [CallbackQueryHandler(ap_majburiy_tur, pattern="^maj_tur_")],
            AP_MAJBURIY_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_majburiy_link)],
            AP_MAJBURIY_LINK + 1: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_majburiy_nomi)],
            AP_KINO_VIP: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_pulik_kod)],
            AP_KINO_VIP_QISM: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_pulik_qism)],
            AP_KINO_VIP_NARX: [MessageHandler(filters.TEXT & ~filters.COMMAND, ap_pulik_narx)],
            AP_XABAR_MATN: [MessageHandler(
                filters.TEXT | filters.PHOTO | filters.VOICE | filters.VIDEO,
                ap_xabar_matn
            )],
        },
        fallbacks=[CommandHandler("admin", admin_panel)],
        per_user=True,
    )
    
    # ── Foydalanuvchi ConversationHandler ─────────────────────────────────────
    user_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            U_MAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
            U_TOLOV_MIQDOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, tolov_miqdor)],
            U_TOLOV_CHEK: [MessageHandler(filters.PHOTO, tolov_chek)],
            U_VIP_CHEK: [MessageHandler(filters.PHOTO, vip_chek)],
        },
        fallbacks=[CommandHandler("start", start)],
        per_user=True,
    )
    
    app.add_handler(admin_conv)
    app.add_handler(user_conv)
    
    # ── Callback handlerlari ──────────────────────────────────────────────────
    app.add_handler(CallbackQueryHandler(check_sub_callback, pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(hisobni_toldirish_start, pattern="^hisobni_toldirish$"))
    app.add_handler(CallbackQueryHandler(tolov_ok_callback, pattern="^tolov_ok_"))
    app.add_handler(CallbackQueryHandler(tolov_no_callback, pattern="^tolov_no_"))
    app.add_handler(CallbackQueryHandler(vip_menu, pattern="^vip_menu$"))
    app.add_handler(CallbackQueryHandler(vip_buy_callback, pattern="^vip_buy_"))
    app.add_handler(CallbackQueryHandler(vip_ok_callback, pattern="^vip_ok_"))
    app.add_handler(CallbackQueryHandler(vip_no_callback, pattern="^vip_no_"))
    app.add_handler(CallbackQueryHandler(qism_callback, pattern="^qism_"))
    app.add_handler(CallbackQueryHandler(balans_tolov_callback, pattern="^balans_tolov_"))
    app.add_handler(CallbackQueryHandler(xabar_yu_callback, pattern="^xabar_yu_"))
    app.add_handler(CallbackQueryHandler(ap_xabar_all_start, pattern="^ap_xabar_all$"))
    app.add_handler(CallbackQueryHandler(tarif_del_callback, pattern="^tarif_del_"))
    app.add_handler(CallbackQueryHandler(karta_del_callback, pattern="^karta_del_"))
    app.add_handler(CallbackQueryHandler(maj_del_callback, pattern="^maj_del_"))
    app.add_handler(CallbackQueryHandler(ap_majburiy_add, pattern="^maj_add$"))
    app.add_handler(CallbackQueryHandler(ap_tarif_add_start, pattern="^tarif_add$"))
    
    print("🤖 Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
