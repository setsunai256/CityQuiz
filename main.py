from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from game_logic import start_game, make_move, stop_game
from storage import get_game, get_stats

# =========================
# /start
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    game = get_game(user_id)

    if game and not game.get("finished") and game.get("last"):
        await update.message.reply_text(
            f"🔄 Игра уже идёт!\n"
            f"Последний город: {game['last']}\n\n"
            "Продолжай называть город.\n"
            "Если хочешь начать заново — напиши /stop."
        )
        return

    start_game(user_id)
    await update.message.reply_text(
        "✅ Новая игра начата!\n"
        "Назови любой город — я отвечу на последнюю букву.\n\n"
        "Команды:\n"
        "/start — начать игру\n"
        "/stop — остановить игру\n"
        "/stats — статистика"
    )

# =========================
# /stop
# =========================
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    result = stop_game(user_id)

    await update.message.reply_text(
        f"⏹ {result}\n"
        "Чтобы начать заново — напиши /start."
    )

# =========================
# /stats
# =========================
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    stats = get_stats(user_id)

    await update.message.reply_text(
        "📊 Ваша статистика:\n\n"
        f"• Сессий сыграно: {stats['sessions']}\n"
        f"• Рекорд по ходам: {stats['record_moves']}"
    )

# =========================
# ОБРАБОТКА ТЕКСТА
# =========================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    city = update.message.text.strip()

    response = make_move(user_id, city)
    await update.message.reply_text(response)

# =========================
# ЗАПУСК
# =========================
if __name__ == "__main__":
    TOKEN = "8118367092:AAFIK24jl2a6LXdaPZ6u6z5RD62JrT4jHzs"

    app = ApplicationBuilder().token(TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("stats", stats))

    # Текстовые сообщения
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("✅ Бот запущен. Нажми Ctrl+C для остановки.")
    app.run_polling()
