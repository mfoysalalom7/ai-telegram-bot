import os
from openai import OpenAI
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name

    await update.message.reply_text(
        f"👋 Hello {name}!\n\n"
        "🤖 আমি তোমার AI Telegram Assistant.\n\n"
        "আমাকে যেকোনো প্রশ্ন করতে পারো।"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📚 Commands\n\n"
        "/start - Start bot\n"
        "/help - Help\n"
        "/clear - Clear conversation\n\n"
        "💬 সাধারণ message পাঠালেই AI উত্তর দেবে।"
    )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("previous_response_id", None)

    await update.message.reply_text(
        "🧹 Conversation memory cleared."
    )


async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    await update.message.chat.send_action("typing")

    previous_id = context.user_data.get(
        "previous_response_id"
    )

    try:
        request = {
            "model": MODEL,
            "instructions": INSTRUCTIONS,
            "input": user_message,
        }

        if previous_id:
            request["previous_response_id"] = previous_id

        response = client.responses.create(**request)

        answer = response.output_text

        context.user_data["previous_response_id"] = response.id

        if not answer:
            answer = "দুঃখিত, কোনো উত্তর পাওয়া যায়নি।"

        # Telegram message length protection
        for i in range(0, len(answer), 4000):
            await update.message.reply_text(
                answer[i:i + 4000]
            )

    except Exception as e:
        print("ERROR:", repr(e))

        await update.message.reply_text(
            "❌ AI response পাওয়া যায়নি।\n\n"
            "Server configuration অথবা API key check করো।"
        )


def main():
    print("🤖 AI Telegram Bot starting...")

    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("help", help_command)
    )

    app.add_handler(
        CommandHandler("clear", clear_command)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            chat
        )
    )

    print("✅ Bot is running!")

    app.run_polling()


if __name__ == "__main__":
    main()
