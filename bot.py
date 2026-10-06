import os
import asyncio
from contextlib import asynccontextmanager

from openai import OpenAI
from fastapi import FastAPI, Request
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

# Render automatically provides this
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

if not RENDER_EXTERNAL_URL:
    raise RuntimeError("RENDER_EXTERNAL_URL is not available.")


# =========================================================
# OPENAI
# =========================================================

client = OpenAI(api_key=OPENAI_API_KEY)

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
    .connect_timeout(30)
    .read_timeout(30)
    .write_timeout(30)
    .pool_timeout(30)
    .build()
)


# =========================================================
# /start
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    name = update.effective_user.first_name or "Friend"

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
    context.user_data.pop("previous_response_id", None)

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

    if not update.message or not update.message.text:
        return

    user_message = update.message.text.strip()

    if not user_message:
        return

    try:

        # Typing indicator
        await update.message.chat.send_action("typing")

        previous_id = context.user_data.get(
            "previous_response_id"
        )

        request = {
            "model": MODEL,
            "instructions": INSTRUCTIONS,
            "input": user_message,
        }

        if previous_id:
            request["previous_response_id"] = previous_id

        # OpenAI SDK is synchronous,
        # so run it in a background thread.
        response = await asyncio.to_thread(
            client.responses.create,
            **request
        )

        answer = response.output_text

        context.user_data["previous_response_id"] = response.id

        if not answer:
            answer = "দুঃখিত, কোনো উত্তর পাওয়া যায়নি।"

        # Telegram maximum message protection
        chunk_size = 4000

        for i in range(0, len(answer), chunk_size):

            chunk = answer[i:i + chunk_size]

            await update.message.reply_text(
                chunk
            )

    except Exception as e:

        print(
            "AI ERROR:",
            repr(e)
        )

        try:

            await update.message.reply_text(
                "❌ AI response পাওয়া যায়নি।\n\n"
                "কিছুক্ষণ পরে আবার চেষ্টা করো।"
            )

        except Exception as telegram_error:

            print(
                "TELEGRAM ERROR:",
                repr(telegram_error)
            )


# =========================================================
# HANDLERS
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

    print("🚀 Starting Telegram AI Bot...")

    # Initialize Telegram application
    await telegram_app.initialize()

    # Start Telegram application
    await telegram_app.start()

    # Webhook URL
    webhook_url = (
        f"{RENDER_EXTERNAL_URL.rstrip('/')}/telegram/webhook"
    )

    print(
        f"🔗 Setting Telegram webhook: {webhook_url}"
    )

    try:

        await telegram_app.bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
        )

        print("✅ Telegram webhook configured!")

    except Exception as e:

        print(
            "⚠️ Webhook setup error:",
            repr(e)
        )

    print("🤖 AI Telegram Bot is running!")

    yield

    # Shutdown
    print("🛑 Shutting down bot...")

    try:
        await telegram_app.bot.delete_webhook()
    except Exception:
        pass

    await telegram_app.stop()
    await telegram_app.shutdown()

    print("✅ Bot stopped.")


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(
    title="AI Telegram Bot",
    lifespan=lifespan
)


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/")
async def home():

    return {
        "status": "online",
        "message": "🤖 AI Telegram Bot is running!"
    }


@app.get("/health")
async def health():

    return {
        "status": "healthy"
    }
# =========================================================
# webhook-status
# =========================================================
@app.get("/webhook-status")
async def webhook_status():

    try:
        info = await telegram_app.bot.get_webhook_info()

        return {
            "ok": True,
            "url": info.url,
            "pending_update_count": info.pending_update_count,
            "last_error_message": info.last_error_message,
            "last_error_date": info.last_error_date,
            "has_custom_certificate": info.has_custom_certificate,
            "max_connections": info.max_connections,
        }

    except Exception as e:

        return {
            "ok": False,
            "error": str(e),
        }
# =========================================================
# TELEGRAM WEBHOOK
# =========================================================

@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request
):

    try:

        data = await request.json()

        update = Update.de_json(
            data,
            telegram_app.bot
        )

        # Put update into Telegram application's queue.
        # This returns immediately so Telegram doesn't timeout.
        await telegram_app.update_queue.put(
            update
        )

        return {
            "ok": True
        }

    except Exception as e:

        print(
            "WEBHOOK ERROR:",
            repr(e)
        )

        return {
            "ok": False
        }


# =========================================================
# LOCAL RUN
# =========================================================

if __name__ == "__main__":

    import uvicorn

    port = int(
        os.environ.get(
            "PORT",
            8000
        )
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
)
