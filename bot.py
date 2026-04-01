#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=== O'ZGARTIRISH KERAK BO'LGAN QISMLAR ===

1. pip install python-telegram-bot --upgrade  (21.x kerak style uchun)

2. Quyidagi funksiyalarni asosiy kodda ALMASHTIRING:
   - ib() va lb() yordamchi funksiyalar
   - show_kino()
   - cb_yuklab()
   - cb_postsend() ichidagi kanal_btns
   - send_sub_msg()
"""

# ══════════════════════════════════════════════════════════════════
# 1. YORDAMCHI FUNKSIYALAR — style qo'shildi
#    (37-42 qatorlarni almashtiring)
# ══════════════════════════════════════════════════════════════════
def ib(text, cbd, style=None):
    """Inline button — callback"""
    if style:
        return InlineKeyboardButton(text, callback_data=cbd, style=style)
    return InlineKeyboardButton(text, callback_data=cbd)

def lb(text, url, style=None):
    """Inline button — URL"""
    if style:
        return InlineKeyboardButton(text, url=url, style=style)
    return InlineKeyboardButton(text, url=url)


# ══════════════════════════════════════════════════════════════════
# 2. KINO KO'RSATISH — Image 2 formatida
#    (307-340 qatorlarni almashtiring)
# ══════════════════════════════════════════════════════════════════
async def show_kino(update, ctx, kino):
    con = db()
    qismlar = con.execute(
        "SELECT * FROM qismlar WHERE kino_id=? ORDER BY qism_raqam", (kino["id"],)
    ).fetchall()
    con.close()

    joriy = max((q["qism_raqam"] for q in qismlar), default=0)
    jami  = len(qismlar)

    # Image 2 formatidagi caption
    caption = (
        f"🎬 *{kino['nomi']}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"  Qism       :  {joriy}/{jami}\n"
        f"  Janrlari   :  {kino['janr'] or 'Mini drama'}\n"
        f"  Tili       :  {kino['til'] or \"O'zbek tilida\"}\n"
        f"  Ko'rish    :  🍿 @{BOT_USERNAME}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━"
    )

    btns = [
        [ib("📥 Yuklab olish", f"yuklab_{kino['id']}", style="primary")],
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


# ══════════════════════════════════════════════════════════════════
# 3. YUKLAB OLISH — rangli qism tugmalari
#    (345-375 qatorlarni almashtiring)
# ══════════════════════════════════════════════════════════════════
async def cb_yuklab(update, ctx):
    q = update.callback_query
    await q.answer()
    kino_id = int(q.data.split("_")[1])
    con = db()
    kino   = con.execute("SELECT * FROM kinolar WHERE id=?", (kino_id,)).fetchone()
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
            label = f"👑 {qism['qism_raqam']}-qism"
            btn   = ib(label, f"qism_{qism['id']}", style="danger")
        else:
            label = f"{qism['qism_raqam']}-qism"
            btn   = ib(label, f"qism_{qism['id']}", style="primary")
        row.append(btn)
        if len(row) == 3 or i == len(qismlar) - 1:
            btns.append(row)
            row = []

    await q.message.reply_text(
        f"🎬 *{kino['nomi']}*\n\nQismni tanlang 👇",
        reply_markup=InlineKeyboardMarkup(btns),
        parse_mode=ParseMode.MARKDOWN
    )


# ══════════════════════════════════════════════════════════════════
# 4. KANAL POST tugmasi — rangli
#    cb_postsend() ichida (710-qator) shuni almashtiring:
#
#   ESKI:
#     kanal_btns = [[lb("Tomosha qilish", f"https://t.me/{BOT_USERNAME}?start={kod}")]]
#
#   YANGI:
# ══════════════════════════════════════════════════════════════════
kanal_btns_yangi = [[
    lb("▶️ Tomosha qilish", f"https://t.me/BOT_USERNAME?start=KOD", style="primary")
]]
# Eslatma: yuqoridagi misol — cb_postsend ichida kanal_btns ni shu formatda yozing:
# kanal_btns = [[lb("▶️ Tomosha qilish", f"https://t.me/{BOT_USERNAME}?start={kod}", style="primary")]]


# ══════════════════════════════════════════════════════════════════
# 5. OBUNA TEKSHIRISH tugmasi — rangli
#    send_sub_msg() ichida (234-qator) almashtiring:
#
#   ESKI:
#     btns.append([ib("Tekshirish", "check_sub")])
#
#   YANGI:
#     btns.append([ib("✅ Tekshirish", "check_sub", style="success")])
# ══════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════
# 6. VIP SOTIB OLISH tugmasi — rangli
#    cb_qism() ichida (398-qator):
#
#   ESKI:
#     [ib(f"Balansdan to'lash ({som(qism['narx'])} so'm)", f"balans_{qism_id}")],
#     [ib("VIP sotib olish", "vip_menu")],
#
#   YANGI:
#     [ib(f"💳 Balansdan to'lash ({som(qism['narx'])} so'm)", f"balans_{qism_id}", style="primary")],
#     [ib("👑 VIP sotib olish", "vip_menu", style="success")],
# ══════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════
# ESLATMA:
# style="primary"  → Ko'k tugma
# style="success"  → Yashil tugma
# style="danger"   → Qizil tugma
#
# python-telegram-bot versiyani yangilash:
#   pip install python-telegram-bot --upgrade
# ══════════════════════════════════════════════════════════════════
