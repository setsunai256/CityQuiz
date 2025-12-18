# storage.py
_games = {}

def get_game(user_id: int):
    return _games.get(user_id)

def set_game(user_id: int, game_state: dict):
    _games[user_id] = game_state

def clear_game(user_id: int):
    _games.pop(user_id, None)