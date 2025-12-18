from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from game_logic import start_game, make_move, stop_game
from storage import get_game


async def start(update: Update, context):
    user_id = update.message.from_user.id
    game = get_game(user_id)
    if game and game.get("last_city"):
        await update.message.reply_text(
            f"🔄 Игра уже идёт!\nПоследний город: {game['last_city']}\n"
            "Продолжай называть город.\n\n"
            "Хочешь начать заново? Напиши /stop, потом /start."
        )
        return
    start_game(user_id)
    await update.message.reply_text(
        "✅ Новая игра начата!\n"
        "Назови любой город — я отвечу на последнюю букву.\n\n"
        "Команды:\n"
        "/start — начать или проверить статус\n"
        "/stop — остановить игру"
    )


async def stop(update: Update, context):
    user_id = update.message.from_user.id
    stop_game(user_id)
    await update.message.reply_text(
        "⏹ Игра остановлена.\n"
        "Чтобы начать заново — напиши /start"
    )


async def handle_text(update: Update, context):
    user_id = update.message.from_user.id
    city = update.message.text.strip()
    response = make_move(user_id, city)
    await update.message.reply_text(response)


if __name__ == "__main__":
    # 🔑 ЗАМЕНИ ЭТОТ ТОКЕН НА СВОЙ!
    TOKEN = "8118367092:AAFIK24jl2a6LXdaPZ6u6z5RD62JrT4jHzs"

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))  # ← добавлено!
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("✅ Бот запущен. Нажми Ctrl+C в терминале, чтобы остановить.")
    app.run_polling()