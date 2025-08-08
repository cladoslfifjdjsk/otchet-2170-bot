# bot.py
import os
import json
import asyncio
import logging

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import Forbidden
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    logger.error("Environment variable BOT_TOKEN is not set. Exiting.")
    raise SystemExit("Set BOT_TOKEN env var (see README)")

USERS_FILE = "users.json"

def load_users():
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(int(x) for x in data)
    except FileNotFoundError:
        return set()
    except Exception:
        logger.exception("Failed to load users.json")
        return set()

def save_users(users_set):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(users_set), f, ensure_ascii=False)
    except Exception:
        logger.exception("Failed to save users.json")

users = load_users()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in users:
        await update.message.reply_text("Ты уже подписан(а). Я буду напоминать каждую пятницу в 15:00.")
        return
    users.add(chat_id)
    save_users(users)
    await update.message.reply_text(
        "Готово — я буду присылать напоминание каждую пятницу в 15:00 (Europe/Amsterdam).\n"
        "Чтобы отписаться — используй /stop"
    )

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in users:
        users.remove(chat_id)
        save_users(users)
        await update.message.reply_text("Ты отписан(а).")
    else:
        await update.message.reply_text("Ты не был(а) подписан(а).")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/start — подписаться\n"
        "/stop — отписаться\n"
        "/count — количество подписчиков\n"
        "/test — получить тестовое напоминание сейчас\n"
        "/help — помощь"
    )

async def count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Подписчиков: {len(users)}")

async def test_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Тестовое напоминание: Напоминаю, необходимо сделать отчет о проделанной работе!")

async def send_reminders(application):
    logger.info("Запуск рассылки напоминаний (cron). Подписчиков: %d", len(users))
    for user_id in list(users):
        try:
            await application.bot.send_message(
                chat_id=user_id,
                text="Напоминаю, необходимо сделать отчет о проделанной работе!"
            )
        except Forbidden:
            # пользователь заблокировал бота — удаляем
            logger.info("Пользователь %s заблокировал бота — удаляю из подписчиков", user_id)
            try:
                users.remove(user_id)
                save_users(users)
            except Exception:
                pass
        except Exception:
            logger.exception("Ошибка отправки сообщения %s", user_id)

async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("count", count_cmd))
    app.add_handler(CommandHandler("test", test_cmd))

    scheduler = AsyncIOScheduler(timezone="Europe/Amsterdam")
    # каждую пятницу в 15:00 (Europe/Amsterdam)
    scheduler.add_job(send_reminders, "cron", day_of_week="fri", hour=15, minute=0, args=[app])
    scheduler.start()

    logger.info("Бот запущен. Ожидаю обновления...")
    await app.run_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown")
