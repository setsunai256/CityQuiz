# Простое хранение в памяти для теста
games = {}
stats = {}


def get_game(user_id):
    return games.get(user_id)


def set_game(user_id, game):
    games[user_id] = game


def clear_game(user_id):
    if user_id in games:
        del games[user_id]


def get_stats(user_id):
    if user_id not in stats:
        stats[user_id] = {"sessions": 0, "record_moves": 0}
    return stats[user_id]


def set_stats(user_id, s):
    stats[user_id] = s
