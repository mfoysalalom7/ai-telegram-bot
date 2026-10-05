import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from openai import OpenAI

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

# Render gives us PORT automatically.
PORT = int(os.environ.get("PORT", "10000"))

# We will add this environment variable later.
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")


# =========================================================
# OPENAI
# =========================================================

client = OpenAI(
    api_key=OPENAI_API_KEY
)

MODEL = "gpt-5"

INSTRUCTIONS = """
You are a helpful AI assistant inside Telegram.

Rules:
- Reply in the same language as the user when possible.
- If the user writes Bangla, reply in Bangla.
- Be friendly, clear and useful.
- Do not pretend to be human.
"""


# =========================================================
# TELEGRAM APPLICATION
# =========================================================

telegram_app = (
    Application.builder()
    .token(TELEGRAM_BOT_TOKEN)
    .updater(None)
    .build()
)


# =========================================================
# /start
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    name = update.effective_user.first_name

    await update.message.reply_text(
        f"👋 Hello {name}!\n\n"
        "🤖 আমি তোমার AI Telegram Assistant.\n\n"
        "আমাকে যেকোনো প্রশ্ন করতে পারো।"
    )


# =========================================================
# /help
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "📚 Commands\n\n"
        "/start - Start bot\n"
        "/help - Help\n"
        "/clear - Clear conversation\n\n"
        "💬 সাধারণ message পাঠালেই AI উত্তর দেবে।"
    )


# =========================================================
# /clear
# =========================================================

async def clear_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    context.user_data.pop(
        "previous_response_id",
        None
    )

    await update.message.reply_text(
        "🧹 Conversation memory cleared."
    )


# =========================================================
# AI CHAT
# =========================================================

async def chat(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_message = update.message.text

    if not user_message:
        return

    await update.message.chat.send_action(
        "typing"
    )

    previous_id = context.user_data.get(
        "previous_response_id"
    )

    try:

        request_data = {
            "model": MODEL,
            "instructions": INSTRUCTIONS,
            "input": user_message,
        }

        if previous_id:
            request_data[
                "previous_response_id"
            ] = previous_id

        response = client.responses.create(
            **request_data
        )

        answer = response.output_text

        context.user_data[
            "previous_response_id"
        ] = response.id

        if not answer:
            answer = (
                "দুঃখিত, কোনো উত্তর পাওয়া যায়নি।"
            )

        # Telegram message size protection
        for i in range(
            0,
            len(answer),
            4000
        ):

            await update.message.reply_text(
                answer[i:i + 4000]
            )

    except Exception as error:

        print(
            "AI ERROR:",
            repr(error)
        )

        await update.message.reply_text(
            "❌ AI response পাওয়া যায়নি।"
        )


# =========================================================
# REGISTER HANDLERS
# =========================================================

telegram_app.add_handler(
    CommandHandler(
        "start",
        start
    )
)

telegram_app.add_handler(
    CommandHandler(
        "help",
        help_command
    )
)

telegram_app.add_handler(
    CommandHandler(
        "clear",
        clear_command
    )
)

telegram_app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        chat
    )
)


# =========================================================
# FASTAPI LIFESPAN
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    await telegram_app.initialize()
    await telegram_app.start()

    if WEBHOOK_URL:

        webhook = WEBHOOK_URL.rstrip("/") + "/telegram"

        await telegram_app.bot.set_webhook(
            url=webhook
        )

        print(
            "✅ Telegram webhook:",
            webhook
        )

    else:

        print(
            "⚠️ WEBHOOK_URL is not configured."
        )

    print("✅ AI Telegram Bot started.")

    yield

    await telegram_app.stop()
    await telegram_app.shutdown()


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    lifespan=lifespan
)


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/")
async def home():

    return {
        "status": "online",
        "bot": "AI Telegram Bot"
    }


# =========================================================
# TELEGRAM WEBHOOK
# =========================================================

@app.post("/telegram")
async def telegram_webhook(
    request: Request
):

    data = await request.json()

    update = Update.de_json(
        data,
        telegram_app.bot
    )

    await telegram_app.process_update(
        update
    )

    return {
        "ok": True
    }
