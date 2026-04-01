import os
import logging
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

# ===================== CONFIG =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "123456789").split(",")]
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@UzDubGo_Drama")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# ===================== DATABASE (in-memory) =====================
# { "DramaNomi": { "episodes": {1: file_id, 2: file_id}, "info": {...} } }
dramas_db = {}

# ===================== PER-USER STATE =====================
user_state = {}
# uid -> { "action": ..., "step": ..., ...data }

# ===================== HELPERS =====================

def is_admin(uid):
    return uid in ADMIN_IDS

def admin_main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Drama qo'shish",  callback_data="adm_add_drama"),
         InlineKeyboardButton("📺 Qism qo'shish",  callback_data="adm_add_ep")],
        [InlineKeyboardButton("📋 Ro'yxat",         callback_data="adm_list"),
         InlineKeyboardButton("🗑 O'chirish",        callback_data="adm_del")],
        [InlineKeyboardButton("📊 Statistika",       callback_data="adm_stats"),
         InlineKeyboardButton("❌ Yopish",           callback_data="adm_close")],
    ])

def drama_list_kb(prefix="drama"):
    rows = [[InlineKeyboardButton(f"🎬 {n}", callback_data=f"{prefix}|{n}")]
            for n in dramas_db]
    rows.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_home")])
    return InlineKeyboardMarkup(rows)

def episodes_kb(drama_name):
    episodes = sorted(dramas_db.get(drama_name, {}).get("episodes", {}).keys())
    rows, row = [], []
    for ep in episodes:
        row.append(InlineKeyboardButton(f"{ep}-qism", callback_data=f"ep|{drama_name}|{ep}"))
        if len(row) == 4:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="user_list")])
    return InlineKeyboardMarkup(rows)

def cancel_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Bekor qilish", callback_data="adm_cancel")]])

# ===================== /start =====================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 Salom, <b>{user.first_name}</b>!\n\n"
        "🎬 <b>UzDubGo Drama Bot</b>ga xush kelibsiz!\n\n"
        "O'zbek tilida dublyaj qilingan dramalarni shu botda tomosha qiling.\n"
        "⚠️ <i>Yuklab olish, ekran yozuv va screenshot taqiqlangan!</i>"
    )
    if is_admin(user.id):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎬 Dramalar",      callback_data="user_list"),
             InlineKeyboardButton("🛠 Admin panel",   callback_data="admin_panel")],
            [InlineKeyboardButton("📢 Kanal", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
        ])
    else:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎬 Dramalar ro'yxati", callback_data="user_list")],
            [InlineKeyboardButton("📢 Kanal", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")],
        ])
    msg = update.message or (update.callback_query and update.callback_query.message)
    if update.message:
        await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await update.callback_query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Sizda ruxsat yo'q.")
        return
    await update.message.reply_text(
        "🛠 <b>Admin Panel</b>\n\nBir amalni tanlang:",
        parse_mode=ParseMode.HTML, reply_markup=admin_main_kb()
    )

# ===================== CALLBACK ROUTER =====================

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    uid  = q.from_user.id

    # ── USER FLOWS ──────────────────────────────────────────
    if data == "back_home":
        await cmd_start(update, context)

    elif data == "user_list":
        if not dramas_db:
            await q.edit_message_text(
                "📭 Hozircha drama yo'q. Tez orada qo'shiladi!",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ Orqaga", callback_data="back_home")]])
            )
            return
        await q.edit_message_text(
            "🎬 <b>Dramalar ro'yxati:</b>\n\nKo'rmoqchi bo'lgan dramanGizni tanlang:",
            parse_mode=ParseMode.HTML, reply_markup=drama_list_kb("drama")
        )

    elif data.startswith("drama|"):
        drama_name = data.split("|", 1)[1]
        drama = dramas_db.get(drama_name)
        if not drama:
            await q.edit_message_text("❌ Drama topilmadi.")
            return
        info = drama["info"]
        ep_count = len(drama["episodes"])
        txt = (
            f"🎬 <b>{info['name']}</b>\n\n"
            f"🌍 Davlat: {info.get('country','?')}\n"
            f"📅 Yil: {info.get('year','?')}\n"
            f"🎭 Janr: {info.get('genre','?')}\n"
            f"📺 Qismlar: {ep_count}/{info.get('total','?')}\n"
            f"🌐 Tili: O'zbek tilida\n\n👇 Qismni tanlang:"
        )
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML,
                                   reply_markup=episodes_kb(drama_name))

    elif data.startswith("ep|"):
        _, drama_name, ep_str = data.split("|")
        ep_num = int(ep_str)
        drama  = dramas_db.get(drama_name)
        file_id = drama["episodes"].get(ep_num) if drama else None
        if not file_id:
            await q.answer("❌ Bu qism hali yuklanmagan.", show_alert=True)
            return
        caption = (
            f"🎬 <b>{drama_name}</b> — {ep_num}-qism\n\n"
            f"⚠️ Yuklab olish, forward va screenshot taqiqlangan!\n"
            f"📢 {CHANNEL_USERNAME}"
        )
        await q.message.reply_text(
            "🔒 <b>Himoya yoqilgan!</b> Video faqat botda ko'rish uchun.",
            parse_mode=ParseMode.HTML
        )
        await q.message.reply_video(
            video=file_id, caption=caption,
            parse_mode=ParseMode.HTML, protect_content=True,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Orqaga", callback_data=f"drama|{drama_name}")]])
        )

    # ── ADMIN PANEL ─────────────────────────────────────────
    elif data == "admin_panel":
        if not is_admin(uid):
            await q.answer("❌ Sizda ruxsat yo'q!", show_alert=True)
            return
        await q.edit_message_text(
            "🛠 <b>Admin Panel</b>\n\nBir amalni tanlang:",
            parse_mode=ParseMode.HTML, reply_markup=admin_main_kb()
        )

    elif data == "adm_close":
        user_state.pop(uid, None)
        await q.edit_message_text("✅ Admin panel yopildi.")

    elif data == "adm_cancel":
        user_state.pop(uid, None)
        await q.edit_message_text(
            "❌ Bekor qilindi.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Admin panel", callback_data="admin_panel")]])
        )

    elif data == "adm_stats":
        if not is_admin(uid): return
        total_d = len(dramas_db)
        total_e = sum(len(d["episodes"]) for d in dramas_db.values())
        txt = f"📊 <b>Statistika:</b>\n\n🎬 Jami drama: <b>{total_d}</b>\n📺 Jami qism: <b>{total_e}</b>\n\n"
        for name, d in dramas_db.items():
            txt += f"• {name}: {len(d['episodes'])}/{d['info'].get('total','?')} qism\n"
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Admin panel", callback_data="admin_panel")]]))

    elif data == "adm_list":
        if not is_admin(uid): return
        if not dramas_db:
            await q.edit_message_text("📭 Drama yo'q.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ Admin panel", callback_data="admin_panel")]]))
            return
        txt = "📋 <b>Barcha dramalar:</b>\n\n"
        for name, d in dramas_db.items():
            info = d["info"]
            txt += (f"🎬 <b>{name}</b>\n"
                    f"   {len(d['episodes'])}/{info.get('total','?')} qism | "
                    f"{info.get('country','?')} | {info.get('year','?')}\n\n")
        await q.edit_message_text(txt, parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Admin panel", callback_data="admin_panel")]]))

    # ── ADD DRAMA ────────────────────────────────────────────
    elif data == "adm_add_drama":
        if not is_admin(uid): return
        user_state[uid] = {"action": "add_drama", "step": "name"}
        await q.edit_message_text(
            "➕ <b>Yangi drama qo'shish</b>\n\n1️⃣ Drama nomini yozing:",
            parse_mode=ParseMode.HTML, reply_markup=cancel_kb()
        )

    # ── ADD EPISODE ──────────────────────────────────────────
    elif data == "adm_add_ep":
        if not is_admin(uid): return
        if not dramas_db:
            await q.answer("❌ Avval drama qo'shing!", show_alert=True)
            return
        user_state[uid] = {"action": "add_ep", "step": "select_drama"}
        await q.edit_message_text(
            "📺 <b>Qism qo'shish</b>\n\nQaysi dramaga qism qo'shmoqchisiz?",
            parse_mode=ParseMode.HTML, reply_markup=drama_list_kb("adm_ep")
        )

    elif data.startswith("adm_ep|"):
        drama_name = data.split("|", 1)[1]
        user_state[uid] = {"action": "add_ep", "step": "ep_num", "drama": drama_name}
        ep_count = len(dramas_db.get(drama_name, {}).get("episodes", {}))
        await q.edit_message_text(
            f"📺 <b>{drama_name}</b>\nHozir {ep_count} ta qism bor.\n\n"
            f"2️⃣ Necha-qism ekanligini yozing (raqam):",
            parse_mode=ParseMode.HTML, reply_markup=cancel_kb()
        )

    # ── DELETE DRAMA ─────────────────────────────────────────
    elif data == "adm_del":
        if not is_admin(uid): return
        if not dramas_db:
            await q.answer("❌ O'chirish uchun drama yo'q!", show_alert=True)
            return
        await q.edit_message_text(
            "🗑 <b>Drama o'chirish</b>\n\nQaysi dramani o'chirmoqchisiz?",
            parse_mode=ParseMode.HTML, reply_markup=drama_list_kb("adm_del")
        )

    elif data.startswith("adm_del|"):
        drama_name = data.split("|", 1)[1]
        user_state[uid] = {"action": "confirm_del", "drama": drama_name}
        await q.edit_message_text(
            f"⚠️ <b>Tasdiqlash</b>\n\n<b>{drama_name}</b> ni o'chirishni tasdiqlaysizmi?\n"
            f"Barcha qismlar ham o'chiriladi!",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Ha, o'chir", callback_data=f"adm_del_yes|{drama_name}"),
                 InlineKeyboardButton("❌ Yo'q",        callback_data="admin_panel")]
            ])
        )

    elif data.startswith("adm_del_yes|"):
        drama_name = data.split("|", 1)[1]
        dramas_db.pop(drama_name, None)
        user_state.pop(uid, None)
        await q.edit_message_text(
            f"✅ <b>{drama_name}</b> o'chirildi!",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Admin panel", callback_data="admin_panel")]])
        )

# ===================== TEXT MESSAGES =====================

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid): return
    state = user_state.get(uid)
    if not state: return
    text = update.message.text.strip()
    action, step = state.get("action"), state.get("step")

    # ── ADD DRAMA ──
    if action == "add_drama":
        if step == "name":
            state.update({"drama_name": text, "step": "country"})
            await update.message.reply_text(
                "2️⃣ Davlatni kiriting:\n<i>Masalan: Xitoy</i>",
                parse_mode=ParseMode.HTML, reply_markup=cancel_kb())

        elif step == "country":
            state.update({"country": text, "step": "year"})
            await update.message.reply_text(
                "3️⃣ Yilni kiriting:\n<i>Masalan: 2026</i>",
                parse_mode=ParseMode.HTML, reply_markup=cancel_kb())

        elif step == "year":
            state.update({"year": text, "step": "genre"})
            await update.message.reply_text(
                "4️⃣ Janrni kiriting:\n<i>Masalan: Mini drama</i>",
                parse_mode=ParseMode.HTML, reply_markup=cancel_kb())

        elif step == "genre":
            state.update({"genre": text, "step": "total"})
            await update.message.reply_text(
                "5️⃣ Jami qismlar sonini kiriting:\n<i>Masalan: 100</i>",
                parse_mode=ParseMode.HTML, reply_markup=cancel_kb())

        elif step == "total":
            name = state["drama_name"]
            dramas_db[name] = {
                "episodes": {},
                "info": {
                    "name": name,
                    "country": state.get("country", "?"),
                    "year":    state.get("year",    "?"),
                    "genre":   state.get("genre",   "?"),
                    "total":   text,
                }
            }
            user_state.pop(uid)
            await update.message.reply_text(
                f"✅ <b>{name}</b> drama qo'shildi!\n\n"
                f"🌍 {state['country']}  📅 {state['year']}  🎭 {state['genre']}  📺 {text} qism",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📺 Qism qo'shish", callback_data="adm_add_ep"),
                     InlineKeyboardButton("⬅️ Admin panel",   callback_data="admin_panel")]
                ])
            )

    # ── ADD EP – ep_num ──
    elif action == "add_ep" and step == "ep_num":
        try:
            ep_num = int(text)
            state.update({"ep_num": ep_num, "step": "video"})
            await update.message.reply_text(
                f"3️⃣ <b>{state['drama']} — {ep_num}-qism</b> videosini yuboring:",
                parse_mode=ParseMode.HTML, reply_markup=cancel_kb())
        except ValueError:
            await update.message.reply_text("❌ Faqat raqam kiriting!", reply_markup=cancel_kb())

# ===================== VIDEO HANDLER =====================

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid): return
    state = user_state.get(uid)
    if not (state and state.get("action") == "add_ep" and state.get("step") == "video"):
        return
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("❌ Video yuboring!", reply_markup=cancel_kb())
        return
    drama_name = state["drama"]
    ep_num     = state["ep_num"]
    dramas_db[drama_name]["episodes"][ep_num] = video.file_id
    user_state.pop(uid)
    ep_count = len(dramas_db[drama_name]["episodes"])
    total    = dramas_db[drama_name]["info"].get("total", "?")
    await update.message.reply_text(
        f"✅ <b>{drama_name}</b> — {ep_num}-qism saqlandi!\n📊 Jami: {ep_count}/{total} qism",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Yana qism qo'shish", callback_data="adm_add_ep"),
             InlineKeyboardButton("⬅️ Admin panel",        callback_data="admin_panel")]
        ])
    )

# ===================== SETUP & MAIN =====================

async def post_init(app: Application):
    await app.bot.set_my_commands([
        BotCommand("start", "Botni boshlash"),
        BotCommand("admin", "Admin panel"),
    ])

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("🤖 Bot ishga tushdi!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
