import requests
import time
import uuid
from typing import Optional, Tuple

from storage import get_game, set_game, clear_game, get_stats, set_stats
from data.cities_list import CITIES

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEBUG = True
SKIP_LETTERS = {'ь', 'ъ', 'ы'}

# ------------------------
# Настройки GigaChat
# ------------------------
AUTHORIZATION_KEY = "MDE5YjM4NWMtYzk1Ni03MjE0LTliOGQtZWE1NmNiNTBmMTdhOmFiM2U3YWQ5LTQxZWEtNGQ3Yy1iOWFiLWVmMDk2ZmZjZGQ0Zg=="
OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"  # ← УБРАНЫ ПРОБЕЛЫ!
GIGACHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"  # ← УБРАНЫ ПРОБЕЛЫ!
MODELS_URL = "https://gigachat.devices.sberbank.ru/api/v1/models"  # ← новый, без пробелов
SCOPE = "GIGACHAT_API_PERS"

# ------------------------
# Кэширование токена
# ------------------------
_cached_token: Optional[str] = None
_cached_token_expires_at: int = 0  # ms
_city_fact_cache = {}  # кэш фактов

def dprint(*args):
    if DEBUG:
        print("[DEBUG]", *args)


# =========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================
def normalize_city(text: str) -> str:
    return text.strip().lower()


def find_city_in_db(city_norm: str) -> Tuple[Optional[str], Optional[str]]:
    alt = city_norm.replace(" ", "-")
    for c in CITIES:
        c_low = c.lower()
        if c_low == city_norm or c_low == alt:
            return c_low, c
    return None, None


def city_exists(letter: str, used: set) -> bool:
    for c in CITIES:
        c_norm = c.lower()
        if c_norm in used:
            continue
        if c_norm[0] == letter:
            return True
    return False


def get_last_letter(city: str, used: set) -> str:
    for ch in reversed(city):
        if ch in SKIP_LETTERS:
            continue
        if city_exists(ch, used):
            return ch
    return city[-1]


# =========================
# GIGACHAT: АВТОРИЗАЦИЯ И ЗАПРОСЫ
# =========================
def get_access_token() -> Optional[str]:
    global _cached_token, _cached_token_expires_at

    now_ms = int(time.time() * 1000)
    if _cached_token and _cached_token_expires_at > now_ms + 30_000:
        dprint("Using cached access token")
        return _cached_token

    try:
        payload = {'scope': SCOPE}
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'Authorization': f'Basic {AUTHORIZATION_KEY}',
            'RqUID': str(uuid.uuid4())
        }
        response = requests.post(OAUTH_URL, headers=headers, data=payload, timeout=10, verify=False)
        response.raise_for_status()  # ← явная проверка статуса
        data = response.json()
        dprint("Access token response:", data)

        token = data.get("access_token")
        expires_at = data.get("expires_at")

        if token and isinstance(expires_at, (int, float)):
            _cached_token = token
            _cached_token_expires_at = expires_at
            return token
        else:
            dprint("❌ Token or expires_at missing in response")
            return None

    except Exception as e:
        dprint("❌ Ошибка получения Access token:", e)
        return None


def get_available_models(access_token: str) -> list:
    try:
        headers = {"Authorization": f"Bearer {access_token}"}
        resp = requests.get(MODELS_URL, headers=headers, timeout=10, verify=False)
        resp.raise_for_status()
        data = resp.json()
        dprint("Available models raw:", data)
        models = [m["id"] for m in data.get("data", []) if m.get("type") == "chat"]
        dprint("Available chat models:", models)
        return models
    except Exception as e:
        dprint("❌ Ошибка получения моделей:", e)
        return []


def generate_city_fact(city_name: str) -> str:
    # Кэш
    if city_name in _city_fact_cache:
        dprint(f"✅ Fact for {city_name} from cache")
        return _city_fact_cache[city_name]

    access_token = get_access_token()
    if not access_token:
        dprint("❌ No access token → fallback")
        return "Интересный факт временно недоступен."

    # Выбор модели (предпочтительно русскоязычная)
    models = get_available_models(access_token)
    if not models:
        dprint("❌ No models available")
        return "Интересный факт временно недоступен."

    # Приоритет: GigaChat, GigaChat-2, GigaChat-Pro, иначе первая
    preferred = ["GigaChat", "GigaChat-2", "GigaChat-Pro"]
    model_name = next((m for m in preferred if m in models), models[0])
    dprint(f"✅ Selected model: {model_name}")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": f"Дай один короткий и интересный факт о городе {city_name}, на русском языке. Только факт, без пояснений и вступлений."
            }
        ],
        "max_tokens": 100,
        "temperature": 0.7
    }

    try:
        resp = requests.post(GIGACHAT_URL, headers=headers, json=payload, timeout=15, verify=False)
        dprint(f"GigaChat response status: {resp.status_code}")
        if resp.status_code != 200:
            dprint("❌ Non-200 response:", resp.text)
            return "Интересный факт временно недоступен."

        data = resp.json()
        dprint("GigaChat response JSON:", data)

        choices = data.get("choices", [])
        if not choices:
            dprint("❌ No 'choices' in response")
            return "Интересный факт временно недоступен."

        fact = choices[0].get("message", {}).get("content", "").strip()
        if not fact:
            dprint("❌ Empty fact content")
            return "Интересный факт временно недоступен."

        _city_fact_cache[city_name] = fact
        return fact

    except Exception as e:
        dprint("❌ Ошибка генерации факта:", e)
        return "Интересный факт временно недоступен."


# =========================
# УПРАВЛЕНИЕ ИГРОЙ
# =========================
def start_game(user_id: int):
    stats = get_stats(user_id)
    stats.setdefault("sessions", 0)
    stats["sessions"] += 1
    set_stats(user_id, stats)

    game = {"used": set(), "last": None, "finished": False, "player_moves": 0}
    set_game(user_id, game)
    dprint("Game started for", user_id)


def stop_game(user_id: int) -> str:
    game = get_game(user_id)
    if game:
        final_msg = _finalize_game(user_id, game)
        clear_game(user_id)
        return f"Игра остановлена.\n{final_msg}"
    return "Игра не запущена."


# =========================
# ПРОВЕРКА ХОДА
# =========================
def validate_move(game: dict, city_input: str) -> Tuple[bool, str, str, str]:
    if game["finished"]:
        return False, "Игра уже завершена.", "", ""
    if not isinstance(city_input, str) or not city_input.strip():
        return False, "Введите название города.", "", ""
    city_norm = normalize_city(city_input)
    city_norm, city_orig = find_city_in_db(city_norm)
    if not city_norm:
        return False, "❌ Такого города нет.", "", ""
    if city_norm in game["used"]:
        return False, "🔄 Этот город уже был.", "", ""
    if game["last"]:
        need = get_last_letter(game["last"], game["used"])
        if city_norm[0] != need:
            return False, f"🔤 Нужно на букву «{need.upper()}».", "", ""
    return True, "", city_norm, city_orig


# =========================
# ЗАВЕРШЕНИЕ ИГРЫ
# =========================
def _finalize_game(user_id: int, game: dict) -> str:
    stats = get_stats(user_id)
    moves = game.get("player_moves", 0)
    stats.setdefault("record_moves", 0)

    message_lines = [f"🎉 Игра завершена! Вы назвали {moves} город{'ов' if moves != 1 else ''} за эту сессию."]
    if moves > stats["record_moves"]:
        stats["record_moves"] = moves
        message_lines.append(f"🏆 Новый рекорд: {moves} ход{'ов' if moves != 1 else ''}!")
    else:
        message_lines.append(f"📈 Ваш рекорд: {stats['record_moves']} ход{'ов' if stats['record_moves'] != 1 else ''}")
    set_stats(user_id, stats)
    return "\n".join(message_lines)


# =========================
# ОСНОВНАЯ ЛОГИКА ХОДА
# =========================
def make_move(user_id: int, city_input: str) -> str:
    game = get_game(user_id)
    if game is None:
        return "Сначала начните игру (/start)."

    valid, msg, city_norm, city_orig = validate_move(game, city_input)
    if not valid:
        return msg

    # ---- ХОД ИГРОКА ----
    game["used"].add(city_norm)
    game["last"] = city_norm
    game["player_moves"] += 1
    set_game(user_id, game)

    response = [f"✅ {city_orig} — принято!"]

    # Генерация факта (может быть медленной, но теперь стабильной)
    fact = generate_city_fact(city_orig)
    response.append(f"ℹ️ {fact}")

    # ---- Определяем следующую букву ----
    need = get_last_letter(city_norm, game["used"])
    if not need:
        game["finished"] = True
        final_msg = _finalize_game(user_id, game)
        clear_game(user_id)
        response.append(final_msg)
        return "\n".join(response)

    response.append(f"🔤 Буква: **{need.upper()}**")

    # ---- ХОД БОТА ----
    bot_city_norm, bot_city_orig = None, None
    for c in CITIES:
        c_norm = c.lower()
        if c_norm in game["used"]:
            continue
        if c_norm[0] == need:
            bot_city_norm, bot_city_orig = c_norm, c
            break

    if not bot_city_norm:
        game["finished"] = True
        final_msg = _finalize_game(user_id, game)
        clear_game(user_id)
        response.append("🤖 Бот больше не может ходить.")
        response.append(final_msg)
        return "\n".join(response)

    game["used"].add(bot_city_norm)
    game["last"] = bot_city_norm
    set_game(user_id, game)

    response.append(f"🤖 Бот: {bot_city_orig}")
    fact_bot = generate_city_fact(bot_city_orig)
    response.append(f"ℹ️ {fact_bot}")

    next_need = get_last_letter(bot_city_norm, game["used"])
    if not next_need:
        game["finished"] = True
        final_msg = _finalize_game(user_id, game)
        clear_game(user_id)
        response.append("🤖 Бот загнал себя в тупик.")
        response.append(final_msg)
    else:
        response.append(f"🔤 Ваша очередь! Буква: **{next_need.upper()}**")

    return "\n".join(response)