import re
import logging
import os
import openpyxl
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Dummy web server to satisfy Render's port binding requirement
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Bot is active!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

# Conversation States
GET_COOKIES, GET_PASSWORD = range(2)

# Temporary memory storage
user_data_store = {}

def extract_pairs_from_cookies(cookies_text: str) -> list:
    """Prottek ta cookie line theke UID ebong tar cookie alada kore pair toiri korbe"""
    lines = cookies_text.split('\n')
    pairs = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # c_user ba general numeric ID khuje ber kora
        c_match = re.search(r'c_user[=\s\t:]+(\d+)', line, re.IGNORECASE)
        if c_match:
            uid = c_match.group(1)
            pairs.append({'uid': uid, 'cookie': line})
        else:
            gen_match = re.search(r'\b\d{10,16}\b', line)
            if gen_match:
                uid = gen_match.group(0)
                pairs.append({'uid': uid, 'cookie': line})
    return pairs

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "👋 **Welcome!**\n\n"
        "Doya kore apnar onek gulo **Cookies** line-by-line paste korun.\n"
        "Bot prottek ta cookie theke UID automatic alada kore nibe."
    )
    return GET_COOKIES

async def receive_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    raw_text = update.message.text.strip()

    pairs = extract_pairs_from_cookies(raw_text)

    if not pairs:
        await update.message.reply_text(
            "⚠️ Kono valid UID ba cookies paowa jayni!\n"
            "Doya kore thik bhabe cookies-gulo abar paste korun:"
        )
        return GET_COOKIES

    user_data_store[user_id] = {'pairs': pairs}

    await update.message.reply_text(
        f"✅ Total **{len(pairs)}**-ti UID cookies theke alada kora hoyeche.\n\n"
        "Ekhon ekta **Common Password** din (ei password sob UID-r sathe bose jabe):",
        parse_mode="Markdown"
    )
    return GET_PASSWORD

async def receive_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    password = update.message.text.strip()

    if user_id not in user_data_store:
        await update.message.reply_text("Session expire hoye geche. /start diye abar shuru korun.")
        return ConversationHandler.END

    data = user_data_store[user_id]
    pairs = data['pairs']

    # Excel File Generation using openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Accounts Data"

    # Gridlines enable
    ws.views.sheetView[0].showGridLines = True

    # Headers
    headers = ["SL", "UID", "Password", "Cookies"]
    ws.append(headers)

    # Add Data mapping extracted UID, Password and Cookie row by row
    for idx, item in enumerate(pairs, start=1):
        ws.append([idx, item['uid'], password, item['cookie']])

    file_name = f"accounts_{user_id}.xlsx"
    wb.save(file_name)

    await update.message.reply_text("🎉 **Processing Completed!** Apnar Excel file toiri kora hoyeche:")
    
    # Send Excel Document to Telegram
    with open(file_name, "rb") as f:
        await update.message.reply_document(
            document=f,
            caption="📊 UID, Password ebong Cookies er Complete Excel File."
        )

    del user_data_store[user_id]
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if user_id in user_data_store:
        del user_data_store[user_id]
    await update.message.reply_text("Action cancel kora hoyeche.")
    return ConversationHandler.END

def main():
    # Start Flask server in a background thread to satisfy Render port binding
    t = Thread(target=run_flask)
    t.start()

    TOKEN = "9149922182:AAHy8DbsIKNS04ng9niIrIjd2gPn7pTZ2Rc"

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            GET_COOKIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_cookies)],
            GET_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_password)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(conv_handler)
    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()
