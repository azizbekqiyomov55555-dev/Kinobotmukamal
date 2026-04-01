import os
import logging
import asyncio
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaVideo, BotCommand
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode
import json

# ===================== CONFIG =====================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = [int(x) for x in os.environ.get("ADMIN_IDS", "123456789").split(",")]
CHANNEL_USERNAME = os.environ.get("CHANNEL_USERNAME", "@UzDubGo_Drama")  # Kanal username

# ===================== LOGGING =====================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===================== IN-MEMORY DATABASE =====================
# { drama_name: { "episodes": { ep_num: file_id }, "info": {...} } }
dramas_db = {}

# ===================== HELPERS =====================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def drama_list_keyboard():
    buttons = []
    for name in dramas_db.keys():
        buttons.append([InlineKeyboardButton(f"🎬 {name}", callback_data=f"drama_{name}")])
    if not buttons:
        return None
    return InlineKeyboardMarkup(buttons)

def episodes_keyboard(drama_name: str):
    drama = dramas_db.get(drama_name)
    if not drama:
        return None
    episodes = sorted(drama["episodes"].keys())
    buttons = []
    row = []
    for ep in episodes:
        row.append(InlineKeyboardButton(f"{ep}-qism", callback_data=f"ep_{drama_name}_{ep}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_to_list")])
    return InlineKeyboardMarkup(buttons)

# ===================== PROTECTION MESSAGE =====================
PROTECTION_TEXT = """
⚠️ <b>Diqqat!</b>

Bu video faqat botda ko'rish uchun.
❌ Yuklab olish mumkin emas
❌ Ekran yozuv qilish taqiqlangan
❌ Screenshot olish taqiqlangan

📌 Bu video faqat shu botda mavjud.
"""

# ===================== COMMANDS =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 Salom, <b>{user.first_name}</b>!\n\n"
        f"🎬 <b>UzDubGo Drama Bot</b>ga xush kelibsiz!\n\n"
        f"Bu botda O'zbek tilida dublyaj qilingan dramalarni tomosha qilishingiz mumkin.\n\n"
        f"⚠️ <i>Videolar faqat botda ko'rish uchun. Yuklab olish, ekran yozuv va screenshot taqiqlangan.</i>\n\n"
        f"👇 Quyidagi tugmani bosing:"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Dramalar ro'yxati", callback_data="list_dramas")],
        [InlineKeyboardButton("📢 Asosiy kanal", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")]
    ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Sizda ruxsat yo'q.")
        return
    text = (
        "🛠 <b>Admin buyruqlari:</b>\n\n"
        "/add_drama <code>DramaNomi | Davlat | Yil | Janr | Qismlar soni</code>\n"
        "  ➕ Yangi drama qo'shish\n\n"
        "/add_ep <code>DramaNomi | QismSoni</code>\n"
        "  ➕ Keyin video yuboring\n\n"
        "/list_dramas\n"
        "  📋 Barcha dramalar ro'yxati\n\n"
        "/del_drama <code>DramaNomi</code>\n"
        "  🗑 Dramani o'chirish\n\n"
        "/stats\n"
        "  📊 Statistika"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def admin_add_drama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Ruxsat yo'q.")
        return
    try:
        args = " ".join(context.args).split("|")
        name = args[0].strip()
        country = args[1].strip()
        year = args[2].strip()
        genre = args[3].strip()
        total = args[4].strip()
        dramas_db[name] = {
            "episodes": {},
            "info": {
                "name": name,
                "country": country,
                "year": year,
                "genre": genre,
                "total": total
            }
        }
        await update.message.reply_text(
            f"✅ <b>{name}</b> drama qo'shildi!\n"
            f"📊 Jami qismlar: {total}",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        await update.message.reply_text(
            "❌ Format:\n/add_drama DramaNomi | Davlat | Yil | Janr | QismlarSoni"
        )


# State: waiting for video upload
pending_episode = {}  # admin_id: (drama_name, ep_num)

async def admin_add_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Ruxsat yo'q.")
        return
    try:
        args = " ".join(context.args).split("|")
        drama_name = args[0].strip()
        ep_num = int(args[1].strip())
        if drama_name not in dramas_db:
            await update.message.reply_text(f"❌ '{drama_name}' topilmadi.")
            return
        pending_episode[update.effective_user.id] = (drama_name, ep_num)
        await update.message.reply_text(
            f"✅ Endi <b>{drama_name}</b> - {ep_num}-qism videosini yuboring:",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        await update.message.reply_text("❌ Format:\n/add_ep DramaNomi | QismSoni")


async def receive_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    if user_id not in pending_episode:
        return
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("❌ Iltimos video yuboring.")
        return
    drama_name, ep_num = pending_episode.pop(user_id)
    file_id = video.file_id
    dramas_db[drama_name]["episodes"][ep_num] = file_id
    await update.message.reply_text(
        f"✅ <b>{drama_name}</b> - {ep_num}-qism saqlandi!",
        parse_mode=ParseMode.HTML
    )


async def admin_list_dramas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Ruxsat yo'q.")
        return
    if not dramas_db:
        await update.message.reply_text("📭 Hech qanday drama yo'q.")
        return
    text = "📋 <b>Barcha dramalar:</b>\n\n"
    for name, data in dramas_db.items():
        ep_count = len(data["episodes"])
        total = data["info"].get("total", "?")
        text += f"🎬 <b>{name}</b> - {ep_count}/{total} qism\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def admin_del_drama(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Ruxsat yo'q.")
        return
    name = " ".join(context.args).strip()
    if name in dramas_db:
        del dramas_db[name]
        await update.message.reply_text(f"🗑 <b>{name}</b> o'chirildi.", parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(f"❌ '{name}' topilmadi.")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Ruxsat yo'q.")
        return
    total_dramas = len(dramas_db)
    total_eps = sum(len(d["episodes"]) for d in dramas_db.values())
    await update.message.reply_text(
        f"📊 <b>Statistika:</b>\n\n"
        f"🎬 Jami drama: {total_dramas}\n"
        f"📺 Jami qism: {total_eps}",
        parse_mode=ParseMode.HTML
    )

# ===================== CALLBACKS =====================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "list_dramas" or data == "back_to_list":
        kb = drama_list_keyboard()
        if not kb:
            await query.edit_message_text("📭 Hozircha drama yo'q. Tez orada qo'shiladi!")
            return
        await query.edit_message_text(
            "🎬 <b>Dramalar ro'yxati:</b>\n\nKo'rmoqchi bo'lgan dramangiazni tanlang:",
            parse_mode=ParseMode.HTML,
            reply_markup=kb
        )

    elif data.startswith("drama_"):
        drama_name = data[len("drama_"):]
        drama = dramas_db.get(drama_name)
        if not drama:
            await query.edit_message_text("❌ Drama topilmadi.")
            return
        info = drama["info"]
        ep_count = len(drama["episodes"])
        text = (
            f"🎬 <b>{info['name']}</b>\n\n"
            f"🌍 Davlat: {info.get('country', '?')}\n"
            f"📅 Yil: {info.get('year', '?')}\n"
            f"🎭 Janr: {info.get('genre', '?')}\n"
            f"📺 Qismlar: {ep_count}/{info.get('total', '?')}\n"
            f"🌐 Tili: O'zbek tilida\n\n"
            f"👇 Qismni tanlang:"
        )
        kb = episodes_keyboard(drama_name)
        if not kb:
            await query.edit_message_text("❌ Qismlar hali yuklanmagan.")
            return
        await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)

    elif data.startswith("ep_"):
        parts = data[3:].rsplit("_", 1)
        drama_name = parts[0]
        ep_num = int(parts[1])
        drama = dramas_db.get(drama_name)
        if not drama:
            await query.edit_message_text("❌ Drama topilmadi.")
            return
        file_id = drama["episodes"].get(ep_num)
        if not file_id:
            await query.edit_message_text("❌ Bu qism hali yuklanmagan.")
            return

        # Send protection warning first
        await query.message.reply_text(PROTECTION_TEXT, parse_mode=ParseMode.HTML)

        # Send video - NO caption with download link, streaming only
        caption = (
            f"🎬 <b>{drama_name}</b>\n"
            f"📺 {ep_num}-qism\n\n"
            f"⚠️ Yuklab olish, ekran yozuv va screenshot taqiqlangan!\n"
            f"📢 {CHANNEL_USERNAME}"
        )
        await query.message.reply_video(
            video=file_id,
            caption=caption,
            parse_mode=ParseMode.HTML,
            # protect_content=True disables forwarding and saving
            protect_content=True,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Orqaga", callback_data=f"drama_{drama_name}")]
            ])
        )


# ===================== MAIN =====================

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start", "Botni boshlash"),
        BotCommand("help", "Admin yordam"),
        BotCommand("add_drama", "Drama qo'shish (Admin)"),
        BotCommand("add_ep", "Qism qo'shish (Admin)"),
        BotCommand("list_dramas", "Dramalar ro'yxati (Admin)"),
        BotCommand("del_drama", "Drama o'chirish (Admin)"),
        BotCommand("stats", "Statistika (Admin)"),
    ])


def main():
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # User commands
    app.add_handler(CommandHandler("start", start))

    # Admin commands
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("add_drama", admin_add_drama))
    app.add_handler(CommandHandler("add_ep", admin_add_episode))
    app.add_handler(CommandHandler("list_dramas", admin_list_dramas))
    app.add_handler(CommandHandler("del_drama", admin_del_drama))
    app.add_handler(CommandHandler("stats", stats))

    # Video upload handler (admin only)
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, receive_video))

    # Button callbacks
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("Bot ishga tushdi...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
