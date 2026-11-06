import os
import re
import json
import time
import uuid
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime, timezone
from functools import wraps

from flask import (
    Flask, request, redirect, url_for, session,
    render_template_string, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


# ------------------------------------------------------------
# CS2 ARENA — Flask app
# Existing users.db is kept and upgraded without deleting users.
# ------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "users.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("CS2_ARENA_SECRET")
if not app.secret_key:
    raise RuntimeError("Set CS2_ARENA_SECRET in the hosting environment.")
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

# You can replace this demo key with your own key using the
# CITO_API_KEY environment variable. Never put a private key in HTML.
CITO_API_KEY = os.environ.get("CITO_API_KEY", "")
API_BASE = "https://api.citoapi.com/api/v1"
API_CACHE = {}
API_CACHE_SECONDS = 60

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

PRESETS = {
    "target": "🎯", "fire": "🔥", "wolf": "🐺", "skull": "💀",
    "crown": "👑", "ghost": "👻", "dragon": "🐉", "robot": "🤖"
}

TEXT = {
    "ru": {
        "home": "Главная", "news": "Новости", "tournaments": "Турниры",
        "teams": "Команды", "stats": "Статистика", "profile": "Профиль",
        "login": "Войти", "register": "Регистрация", "logout": "Выйти",
        "hero_text": "Твой портал в мире Counter-Strike 2.",
        "hero_button": "Смотреть события", "latest_news": "Последние события",
        "live": "СЕЙЧАС ИГРАЮТ", "upcoming": "СКОРО", "recent": "ПОСЛЕДНИЕ РЕЗУЛЬТАТЫ",
        "world_rank": "Мировой рейтинг команд", "all_news": "Все события",
        "all_matches": "Матчи", "all_teams": "Все команды",
        "no_data": "Пока нет доступных данных от поставщика. Попробуй обновить страницу позже.",
        "api_error": "Не удалось получить данные. Источник может быть временно недоступен.",
        "api_source": "Источник данных: Cito API. Данные могут иметь задержку.",
        "updated": "Последняя проверка", "rank": "Место", "team": "Команда",
        "points": "Очки", "change": "Изменение", "event": "Турнир",
        "date": "Дата", "status": "Статус", "score": "Счёт",
        "details": "Подробнее", "back": "Назад", "roster": "Состав",
        "team_page": "Страница команды", "match_details": "Информация о матче",
        "hero_label": "COUNTER-STRIKE 2 COMMUNITY",
        "section_news": "События сцены CS2",
        "section_matches": "Матчи и результаты",
        "section_rank": "Топ команд",
        "login_title": "Вход в аккаунт", "register_title": "Создание аккаунта",
        "username": "Логин", "password": "Пароль",
        "login_button": "Войти", "register_button": "Зарегистрироваться",
        "profile_title": "Мой игровой профиль", "player": "Игрок CS2 ARENA",
        "active": "Аккаунт активен", "level": "Уровень", "wins": "Победы",
        "matches": "Матчи", "avatar_title": "Настройка аватарки",
        "avatar_text": "Выбери готовую аватарку или загрузи свою.",
        "presets": "Готовые аватарки", "upload": "Загрузить свою",
        "save": "Сохранить профиль", "file_info": "PNG, JPG, WEBP. Максимум 2 МБ.",
        "wrong_login": "Неправильный логин или пароль.", "taken": "Такой логин уже занят.",
        "bad_file": "Выбери изображение PNG, JPG или WEBP.",
        "bad_username": "Логин должен содержать от 3 до 20 символов.",
        "bad_password": "Пароль должен содержать минимум 8 символов.",
        "hello": "Привет", "footer": "Неофициальный фанатский проект",
        "api_setup": "Для расширенных лимитов добавь собственный API-ключ в переменную CITO_API_KEY.",
        "no_roster": "Состав команды пока не предоставлен источником."
    },
    "uk": {
        "home": "Головна", "news": "Новини", "tournaments": "Турніри",
        "teams": "Команди", "stats": "Статистика", "profile": "Профіль",
        "login": "Увійти", "register": "Реєстрація", "logout": "Вийти",
        "hero_text": "Твій портал у світі Counter-Strike 2.",
        "hero_button": "Дивитися події", "latest_news": "Останні події",
        "live": "ЗАРАЗ ГРАЮТЬ", "upcoming": "НЕЗАБАРОМ", "recent": "ОСТАННІ РЕЗУЛЬТАТИ",
        "world_rank": "Світовий рейтинг команд", "all_news": "Усі події",
        "all_matches": "Матчі", "all_teams": "Усі команди",
        "no_data": "Поки немає доступних даних від постачальника. Спробуй оновити сторінку пізніше.",
        "api_error": "Не вдалося отримати дані. Джерело може бути тимчасово недоступне.",
        "api_source": "Джерело даних: Cito API. Дані можуть мати затримку.",
        "updated": "Остання перевірка", "rank": "Місце", "team": "Команда",
        "points": "Бали", "change": "Зміна", "event": "Турнір",
        "date": "Дата", "status": "Статус", "score": "Рахунок",
        "details": "Докладніше", "back": "Назад", "roster": "Склад",
        "team_page": "Сторінка команди", "match_details": "Інформація про матч",
        "hero_label": "COUNTER-STRIKE 2 COMMUNITY",
        "section_news": "Події сцени CS2",
        "section_matches": "Матчі та результати",
        "section_rank": "Топ команд",
        "login_title": "Вхід до акаунта", "register_title": "Створення акаунта",
        "username": "Логін", "password": "Пароль",
        "login_button": "Увійти", "register_button": "Зареєструватися",
        "profile_title": "Мій ігровий профіль", "player": "Гравець CS2 ARENA",
        "active": "Акаунт активний", "level": "Рівень", "wins": "Перемоги",
        "matches": "Матчі", "avatar_title": "Налаштування аватарки",
        "avatar_text": "Обери готову аватарку або завантаж власну.",
        "presets": "Готові аватарки", "upload": "Завантажити власну",
        "save": "Зберегти профіль", "file_info": "PNG, JPG, WEBP. Максимум 2 МБ.",
        "wrong_login": "Неправильний логін або пароль.", "taken": "Такий логін уже зайнятий.",
        "bad_file": "Обери зображення PNG, JPG або WEBP.",
        "bad_username": "Логін має містити від 3 до 20 символів.",
        "bad_password": "Пароль має містити щонайменше 8 символів.",
        "hello": "Привіт", "footer": "Неофіційний фанатський проєкт",
        "api_setup": "Для більших лімітів додай власний API-ключ у змінну CITO_API_KEY.",
        "no_roster": "Склад команди поки не надано джерелом."
    },
    "en": {
        "home": "Home", "news": "News", "tournaments": "Tournaments",
        "teams": "Teams", "stats": "Statistics", "profile": "Profile",
        "login": "Login", "register": "Register", "logout": "Logout",
        "hero_text": "Your portal to the world of Counter-Strike 2.",
        "hero_button": "Explore events", "latest_news": "Latest events",
        "live": "LIVE NOW", "upcoming": "UPCOMING", "recent": "RECENT RESULTS",
        "world_rank": "World team ranking", "all_news": "All events",
        "all_matches": "Matches", "all_teams": "All teams",
        "no_data": "No data is currently available from the provider. Try again later.",
        "api_error": "Could not load data. The provider may be temporarily unavailable.",
        "api_source": "Data source: Cito API. Data may be delayed.",
        "updated": "Last checked", "rank": "Rank", "team": "Team",
        "points": "Points", "change": "Change", "event": "Event",
        "date": "Date", "status": "Status", "score": "Score",
        "details": "Details", "back": "Back", "roster": "Roster",
        "team_page": "Team page", "match_details": "Match details",
        "hero_label": "COUNTER-STRIKE 2 COMMUNITY",
        "section_news": "CS2 scene updates",
        "section_matches": "Matches and results",
        "section_rank": "Top teams",
        "login_title": "Login to your account", "register_title": "Create account",
        "username": "Username", "password": "Password",
        "login_button": "Login", "register_button": "Register",
        "profile_title": "My gaming profile", "player": "CS2 ARENA Player",
        "active": "Account active", "level": "Level", "wins": "Wins",
        "matches": "Matches", "avatar_title": "Avatar settings",
        "avatar_text": "Choose an avatar or upload your own.",
        "presets": "Available avatars", "upload": "Upload your own",
        "save": "Save profile", "file_info": "PNG, JPG, WEBP. Maximum 2 MB.",
        "wrong_login": "Incorrect username or password.", "taken": "This username is already taken.",
        "bad_file": "Choose a PNG, JPG or WEBP image.",
        "bad_username": "Username must contain 3 to 20 characters.",
        "bad_password": "Password must contain at least 8 characters.",
        "hello": "Hello", "footer": "Unofficial fan project",
        "api_setup": "For higher limits, set your own API key in CITO_API_KEY.",
        "no_roster": "The provider has not supplied a roster for this team yet."
    }
}


def get_db():
    return sqlite3.connect(DATABASE)


def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    columns = [row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()]
    if "avatar" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN avatar TEXT DEFAULT 'preset:target'")
    db.commit()
    db.close()


def get_user():
    username = session.get("username")
    if not username:
        return None
    db = get_db()
    user = db.execute(
        "SELECT username, avatar FROM users WHERE username = ?", (username,)
    ).fetchone()
    db.close()
    return user


def current_lang():
    lang = session.get("lang", "ru")
    return lang if lang in TEXT else "ru"


def api_get(path, cache_seconds=API_CACHE_SECONDS):
    """Read-only Cito API request with a small in-memory cache."""
    now = time.time()
    cached = API_CACHE.get(path)
    if cached and now - cached["time"] < cache_seconds:
        return cached["value"], None

    req = urllib.request.Request(
        API_BASE + path,
        headers={
            "x-api-key": CITO_API_KEY,
            "Accept": "application/json",
            "User-Agent": "CS2-ARENA/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not payload.get("success", True):
            return None, "provider_error"
        value = payload.get("data", [])
        API_CACHE[path] = {"time": now, "value": value}
        return value, None
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError):
        if cached:
            return cached["value"], "stale_cache"
        return None, "unavailable"


def as_list(value):
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("items", "results", "matches", "rankings", "teams", "data"):
            if isinstance(value.get(key), list):
                return value[key]
    return []


def pick(obj, *keys, default=""):
    if not isinstance(obj, dict):
        return default
    for key in keys:
        value = obj.get(key)
        if value is not None and value != "":
            return value
    return default


def match_id(match):
    return str(pick(match, "id", "matchId", "match_id", default=""))


def match_status(match):
    return str(pick(match, "status", "state", default="")).lower()


def team_name(match, number):
    return str(pick(match, f"team{number}Name", f"team{number}", default="TBD"))


def match_score(match):
    score = match.get("score") if isinstance(match, dict) else None
    if isinstance(score, dict):
        return f'{score.get("team1", 0)} - {score.get("team2", 0)}'
    a = pick(match, "team1Score", "team1_score", default=None)
    b = pick(match, "team2Score", "team2_score", default=None)
    if a is not None and b is not None:
        return f"{a} - {b}"
    return "—"


def format_date(value):
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone().strftime("%d.%m.%Y %H:%M")
    except (ValueError, TypeError):
        return str(value)


def match_card_data(match):
    mid = match_id(match)
    return {
        "id": mid,
        "team1": team_name(match, 1),
        "team2": team_name(match, 2),
        "score": match_score(match),
        "event": str(pick(match, "eventName", "event", "tournamentName", default="CS2")),
        "date": format_date(pick(match, "startsAt", "startTime", "date", "scheduledAt")),
        "status": match_status(match) or "unknown",
        "map": str(pick(match, "currentMap", "map", default="")),
        "raw": match
    }


def load_dashboard_data():
    live, live_err = api_get("/cs2/live")
    upcoming, up_err = api_get("/cs2/matches/upcoming?limit=8")
    recent, recent_err = api_get("/cs2/matches/recent?limit=8")
    ranking, rank_err = api_get("/cs2/rankings/world?limit=10")

    return {
        "live": [match_card_data(x) for x in as_list(live)[:8]],
        "upcoming": [match_card_data(x) for x in as_list(upcoming)[:8]],
        "recent": [match_card_data(x) for x in as_list(recent)[:8]],
        "ranking": as_list(ranking)[:10],
        "errors": [x for x in (live_err, up_err, recent_err, rank_err) if x],
        "checked": datetime.now().astimezone().strftime("%d.%m.%Y %H:%M:%S")
    }


def render_page(page, message=None, **extra):
    user = get_user()
    return render_template_string(
        HTML,
        page=page,
        t=TEXT[current_lang()],
        lang=current_lang(),
        user=user[0] if user else None,
        avatar=user[1] if user else "preset:target",
        presets=PRESETS,
        message=message,
        **extra
    )


HTML = r"""
<!DOCTYPE html>
<html lang="{{ lang }}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CS2 ARENA</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{background:#090a0e;color:#fff;font-family:Arial,sans-serif;min-height:100vh}
header{min-height:78px;padding:18px 7%;background:#11141c;border-bottom:1px solid #292d38;display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap}
.logo{color:#ff4141;font-size:26px;font-weight:900;letter-spacing:2px;text-decoration:none}
nav{display:flex;align-items:center;gap:18px;flex-wrap:wrap}
nav a{color:#ddd;text-decoration:none;font-size:14px;transition:.2s}
nav a:hover,nav a.active{color:#ff4141}
select,input{background:#090b10;color:white;border:1px solid #343b49;border-radius:6px;padding:12px}
select{background:#202531;padding:9px}
.hero{min-height:420px;padding:80px 10%;display:flex;flex-direction:column;justify-content:center;background:linear-gradient(90deg,#090a0e 10%,#090a0edb 55%,#090a0e66),url("https://images.unsplash.com/photo-1542751371-adc38448a05e?w=1800");background-size:cover;background-position:center}
.hero-label,.tag{color:#ff4141;font-size:12px;font-weight:bold;letter-spacing:2px;margin-bottom:14px;display:block}
.hero h1{font-size:clamp(42px,7vw,76px);margin-bottom:16px}
.hero h1 span{color:#ff4141}
.hero p{color:#c2c2c2;font-size:19px;margin-bottom:25px}
.button,button{display:inline-block;background:#ff4141;color:white;padding:13px 22px;border:0;border-radius:6px;text-decoration:none;font-weight:bold;cursor:pointer}
.button:hover,button:hover{background:#d72c2c}
section,main{padding:55px 8%}
main{min-height:65vh}
.section-title{font-size:29px;margin-bottom:25px}
.section-title span{color:#ff4141}
.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}
.card,.panel,.welcome{background:#151923;border:1px solid #292d38;border-radius:10px;overflow:hidden}
.card{transition:.2s}
.card:hover{border-color:#ff4141;transform:translateY(-3px)}
.card img{width:100%;height:160px;object-fit:cover;display:block}
.card-content{padding:20px}
.card h3,.card h2{margin:8px 0 12px}
.card p,.muted{color:#aaa;line-height:1.55}
.card a,.text-link{display:inline-block;margin-top:14px;color:#ff6666;text-decoration:none}
.welcome{padding:30px;text-align:center}
.welcome p{color:#aaa;margin:12px 0 20px}
.panel{padding:25px;margin:18px 0}
.notice{background:#201b1b;border:1px solid #633333;color:#ffb2b2;padding:14px;border-radius:7px;margin:15px 0}
.source{color:#777;font-size:12px;margin-top:20px}
.grid-two{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.match{display:flex;justify-content:space-between;align-items:center;gap:14px;padding:15px 0;border-bottom:1px solid #2a2e39}
.match:last-child{border-bottom:0}
.match strong{font-size:16px}
.score{color:#ff5555;font-size:20px;font-weight:bold;white-space:nowrap}
.pill{font-size:11px;color:#ff7777;border:1px solid #6b3434;padding:5px 8px;border-radius:20px;white-space:nowrap}
table{width:100%;border-collapse:collapse;margin-top:15px}
th,td{text-align:left;padding:13px 10px;border-bottom:1px solid #2a2e39}
th{color:#ff7777;font-size:13px}
td{color:#ddd}
.rank{color:#ff5555;font-weight:bold}
.team-link{color:#fff;text-decoration:none;font-weight:bold}
.team-link:hover{color:#ff5555}
.form-panel{max-width:650px;margin:55px auto;padding:0 20px}
.form-panel .panel{padding:28px}
.form-panel input{width:100%;margin:10px 0}
.profile-top{display:flex;align-items:center;gap:22px}
.avatar{width:105px;height:105px;border-radius:50%;border:3px solid #ff4141;display:flex;justify-content:center;align-items:center;font-size:48px;overflow:hidden;background:#090b10;flex-shrink:0}
.avatar img{width:100%;height:100%;object-fit:cover}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:15px;margin-top:25px}
.stat{background:#090b10;padding:20px;text-align:center;border-radius:8px}
.stat strong{display:block;font-size:25px;color:#ff4141;margin-bottom:7px}
.presets{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-top:18px}
.preset{background:#090b10;border:2px solid #343b49;border-radius:10px;padding:15px;text-align:center}
.preset input{width:auto}
.preset span{display:block;font-size:32px}
.message{background:#292d38;padding:13px;border-radius:6px;margin-top:15px;color:#ff7777}
footer{text-align:center;padding:30px;color:#777;border-top:1px solid #292d38}
@media(max-width:850px){.cards{grid-template-columns:1fr 1fr}.grid-two{grid-template-columns:1fr}}
@media(max-width:600px){header{justify-content:center}nav{justify-content:center;gap:12px}.hero{padding:60px 7%}.cards,.stats{grid-template-columns:1fr}.presets{grid-template-columns:repeat(2,1fr)}.profile-top{flex-direction:column;align-items:flex-start}.match{align-items:flex-start;flex-direction:column}section,main{padding:38px 6%}}
</style>
</head>
<body>
<header>
<a class="logo" href="/">CS2 ARENA</a>
<nav>
<a href="/" class="{% if page=='home' %}active{% endif %}">{{t.home}}</a>
<a href="/news" class="{% if page=='news' %}active{% endif %}">{{t.news}}</a>
<a href="/tournaments" class="{% if page=='tournaments' %}active{% endif %}">{{t.tournaments}}</a>
<a href="/teams" class="{% if page=='teams' or page=='team' %}active{% endif %}">{{t.teams}}</a>
<a href="/stats" class="{% if page=='stats' %}active{% endif %}">{{t.stats}}</a>
{% if user %}<a href="/profile">{{t.profile}}</a><a href="/logout">{{t.logout}}</a>
{% else %}<a href="/login">{{t.login}}</a><a href="/register">{{t.register}}</a>{% endif %}
<form method="POST" action="/language">
<select name="lang" onchange="this.form.submit()">
<option value="ru" {% if lang=='ru' %}selected{% endif %}>RU</option>
<option value="uk" {% if lang=='uk' %}selected{% endif %}>UA</option>
<option value="en" {% if lang=='en' %}selected{% endif %}>EN</option>
</select></form>
</nav>
</header>

{% if page == "home" %}
<div class="hero">
<div class="hero-label">{{t.hero_label}}</div>
<h1>ENTER THE <span>ARENA</span></h1>
<p>{{t.hero_text}}</p>
<a class="button" href="/tournaments">{{t.hero_button}}</a>
</div>
<section>
<h2 class="section-title">{{t.latest_news}}</h2>
{% if data.recent %}
<div class="cards">
{% for m in data.recent[:3] %}
<div class="card"><div class="card-content">
<span class="tag">MATCH UPDATE</span>
<h3>{{m.team1}} — {{m.team2}}</h3>
<p>{{m.event}}</p><p class="score">{{m.score}}</p>
<a href="/match/{{m.id}}">{{t.details}} →</a>
</div></div>
{% endfor %}
</div>
{% else %}<div class="notice">{{t.no_data}}</div>{% endif %}
</section>
<section>
<h2 class="section-title">{{t.section_matches}}</h2>
<div class="grid-two">
<div class="panel"><h3>{{t.live}}</h3>
{% for m in data.live %}
<div class="match"><div><strong>{{m.team1}} vs {{m.team2}}</strong><p class="muted">{{m.event}}</p></div><span class="score">{{m.score}}</span></div>
{% else %}<p class="muted">{{t.no_data}}</p>{% endfor %}
</div>
<div class="panel"><h3>{{t.upcoming}}</h3>
{% for m in data.upcoming[:5] %}
<div class="match"><div><strong>{{m.team1}} vs {{m.team2}}</strong><p class="muted">{{m.date}} · {{m.event}}</p></div><span class="pill">{{t.upcoming}}</span></div>
{% else %}<p class="muted">{{t.no_data}}</p>{% endfor %}
</div>
</div>
</section>
<section>
<h2 class="section-title">{{t.section_rank}}</h2>
{% if data.ranking %}
<div class="panel"><table><tr><th>{{t.rank}}</th><th>{{t.team}}</th><th>{{t.points}}</th></tr>
{% for r in data.ranking[:5] %}
<tr><td class="rank">{{pick(r,'rank','position',default=loop.index)}}</td><td>{{pick(r,'teamName','name','team',default='—')}}</td><td>{{pick(r,'points','rating',default='—')}}</td></tr>
{% endfor %}</table><a class="text-link" href="/stats">{{t.details}} →</a></div>
{% else %}<div class="notice">{{t.no_data}}</div>{% endif %}
</section>

{% elif page == "news" %}
<main><h1 class="section-title">{{t.all_news}}</h1>
<p class="muted">Здесь отображаются реальные результаты и события матчей, а не выдуманные редакционные статьи.</p>
{% for m in data.live + data.recent %}
<div class="panel">
<span class="tag">{% if m.status=='live' %}LIVE{% else %}MATCH RESULT{% endif %}</span>
<h2>{{m.team1}} — {{m.team2}}</h2><p class="muted">{{m.event}} · {{m.date}}</p>
<p class="score">{{m.score}}</p><a class="text-link" href="/match/{{m.id}}">{{t.details}} →</a>
</div>
{% else %}<div class="notice">{{t.no_data}}</div>{% endfor %}
</main>

{% elif page == "tournaments" %}
<main><h1 class="section-title">{{t.tournaments}}</h1>
<div class="grid-two">
<div class="panel"><h2>{{t.live}}</h2>
{% for m in data.live %}
<div class="match"><div><strong>{{m.team1}} vs {{m.team2}}</strong><p class="muted">{{m.event}}{% if m.map %} · {{m.map}}{% endif %}</p></div><span class="score">{{m.score}}</span></div>
{% else %}<p class="muted">{{t.no_data}}</p>{% endfor %}
</div>
<div class="panel"><h2>{{t.upcoming}}</h2>
{% for m in data.upcoming %}
<div class="match"><div><strong>{{m.team1}} vs {{m.team2}}</strong><p class="muted">{{m.event}} · {{m.date}}</p></div><a class="text-link" href="/match/{{m.id}}">{{t.details}}</a></div>
{% else %}<p class="muted">{{t.no_data}}</p>{% endfor %}
</div></div>
<h2 class="section-title" style="margin-top:35px">{{t.recent}}</h2>
{% for m in data.recent %}
<div class="panel"><strong>{{m.team1}} — {{m.team2}}</strong><span class="score" style="float:right">{{m.score}}</span><p class="muted">{{m.event}} · {{m.date}}</p></div>
{% else %}<p class="muted">{{t.no_data}}</p>{% endfor %}
</main>

{% elif page == "teams" or page == "stats" %}
<main><h1 class="section-title">{% if page=='stats' %}{{t.world_rank}}{% else %}{{t.all_teams}}{% endif %}</h1>
{% if data.ranking %}
<div class="panel"><table>
<tr><th>{{t.rank}}</th><th>{{t.team}}</th><th>{{t.points}}</th><th>{{t.change}}</th></tr>
{% for r in data.ranking %}
{% set slug = pick(r,'teamSlug','slug',default='') %}
<tr>
<td class="rank">{{pick(r,'rank','position',default=loop.index)}}</td>
<td>{% if slug %}<a class="team-link" href="/team/{{slug}}">{{pick(r,'teamName','name','team',default='—')}}</a>{% else %}{{pick(r,'teamName','name','team',default='—')}}{% endif %}</td>
<td>{{pick(r,'points','rating',default='—')}}</td>
<td>{{pick(r,'change','rankChange','movement',default='—')}}</td>
</tr>
{% endfor %}
</table></div>
{% else %}<div class="notice">{{t.no_data}}</div>{% endif %}
</main>

{% elif page == "team" %}
<main><a class="text-link" href="/teams">← {{t.back}}</a>
<h1 class="section-title">{{team.get('name','Team')}}</h1>
<div class="panel">
<p class="muted">{{team.get('region','')}} {% if team.get('country') %}· {{team.get('country')}}{% endif %}</p>
<p>{{t.rank}}: {{team.get('rank','—')}} · {{t.points}}: {{team.get('points','—')}}</p>
</div>
<h2>{{t.roster}}</h2>
{% if roster %}
<div class="panel">{% for p in roster %}<p>{{pick(p,'nickname','name','playerName',default='Player')}}</p>{% endfor %}</div>
{% else %}<p class="muted">{{t.no_roster}}</p>{% endif %}
</main>

{% elif page == "match" %}
<main><a class="text-link" href="/tournaments">← {{t.back}}</a>
<h1 class="section-title">{{t.match_details}}</h1>
<div class="panel">
<span class="tag">{{match.status|upper}}</span>
<h2>{{match.team1}} — {{match.team2}}</h2>
<p class="score">{{match.score}}</p>
<p class="muted">{{match.event}} · {{match.date}}</p>
{% if match.map %}<p>{{match.map}}</p>{% endif %}
</div></main>

{% elif page == "register" %}
<main class="form-panel"><h1>{{t.register_title}}</h1><div class="panel">
<form method="POST"><input name="username" placeholder="{{t.username}}" minlength="3" maxlength="20" required>
<input name="password" type="password" placeholder="{{t.password}}" minlength="8" required>
<button type="submit">{{t.register_button}}</button></form>
{% if message %}<div class="message">{{message}}</div>{% endif %}
</div></main>

{% elif page == "login" %}
<main class="form-panel"><h1>{{t.login_title}}</h1><div class="panel">
<form method="POST"><input name="username" placeholder="{{t.username}}" required>
<input name="password" type="password" placeholder="{{t.password}}" required>
<button type="submit">{{t.login_button}}</button></form>
{% if message %}<div class="message">{{message}}</div>{% endif %}
</div></main>

{% elif page == "profile" %}
<main><h1>{{t.profile_title}}</h1><div class="panel">
<div class="profile-top"><div class="avatar">
{% if avatar.startswith("uploads/") %}<img src="{{url_for('static',filename=avatar)}}">{% else %}{{presets.get(avatar.replace("preset:",""),"🎮")}}{% endif %}
</div><div><h2>{{t.hello}}, {{user}}!</h2><p>{{t.player}}</p><p style="color:#ff4141">● {{t.active}}</p></div></div>
<div class="stats"><div class="stat"><strong>1</strong>{{t.level}}</div><div class="stat"><strong>0</strong>{{t.wins}}</div><div class="stat"><strong>0</strong>{{t.matches}}</div></div>
</div>
<div class="panel"><h2>{{t.avatar_title}}</h2><p class="muted">{{t.avatar_text}}</p>
<form method="POST" action="/edit_profile" enctype="multipart/form-data">
<h3 style="margin-top:20px">{{t.presets}}</h3><div class="presets">
{% for key,emoji in presets.items() %}<label class="preset"><input type="radio" name="preset" value="{{key}}" {% if avatar=="preset:"+key %}checked{% endif %}><span>{{emoji}}</span></label>{% endfor %}
</div><h3 style="margin-top:22px">{{t.upload}}</h3><input type="file" name="avatar" accept=".png,.jpg,.jpeg,.webp">
<p class="muted">{{t.file_info}}</p><button type="submit">{{t.save}}</button></form>
{% if message %}<div class="message">{{message}}</div>{% endif %}</div></main>
{% endif %}

<footer>CS2 ARENA © 2026 | {{t.footer}}<p class="source">{{t.api_source}} · {{t.updated}}: {{data.checked if data else ''}}</p></footer>
</body></html>
"""


@app.context_processor
def template_helpers():
    return {"pick": pick}


@app.route("/")
def home():
    return render_page("home", data=load_dashboard_data())


@app.route("/news")
def news():
    return render_page("news", data=load_dashboard_data())


@app.route("/tournaments")
def tournaments():
    return render_page("tournaments", data=load_dashboard_data())


@app.route("/teams")
def teams():
    return render_page("teams", data=load_dashboard_data())


@app.route("/stats")
def stats():
    return render_page("stats", data=load_dashboard_data())


@app.route("/team/<slug>")
def team_detail(slug):
    safe_slug = re.sub(r"[^a-zA-Z0-9_-]", "", slug)[:80]
    if not safe_slug:
        abort(404)
    team_data, error = api_get("/cs2/teams/" + safe_slug)
    if not team_data or not isinstance(team_data, dict):
        abort(404)
    # The team profile may already include its current roster.
    roster = as_list(team_data.get("roster") or team_data.get("players"))
    if not roster:
        roster_data, roster_error = api_get("/cs2/teams/" + safe_slug + "/roster-history")
        roster = as_list(roster_data)
    team = {
        "name": pick(team_data, "name", "teamName", default=safe_slug),
        "region": pick(team_data, "region", default=""),
        "country": pick(team_data, "country", default=""),
        "rank": pick(team_data, "rank", "worldRank", default="—"),
        "points": pick(team_data, "points", "rankingPoints", default="—")
    }
    return render_page("team", data=load_dashboard_data(), team=team, roster=roster)


@app.route("/match/<matchid>")
def match_detail(matchid):
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "", matchid)[:100]
    if not safe_id:
        abort(404)
    raw, error = api_get("/cs2/matches/" + safe_id)
    if not raw or not isinstance(raw, dict):
        abort(404)
    match = match_card_data(raw)
    return render_page("match", data=load_dashboard_data(), match=match)


@app.route("/language", methods=["POST"])
def language():
    selected = request.form.get("lang", "ru")
    if selected in TEXT:
        session["lang"] = selected
    return redirect(request.referrer or url_for("home"))


@app.route("/register", methods=["GET", "POST"])
def register():
    message = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        lang = current_lang()
        if len(username) < 3 or len(username) > 20:
            message = TEXT[lang]["bad_username"]
        elif len(password) < 8:
            message = TEXT[lang]["bad_password"]
        else:
            db = get_db()
            try:
                db.execute(
                    "INSERT INTO users (username,password,avatar) VALUES (?,?,?)",
                    (username, generate_password_hash(password), "preset:target")
                )
                db.commit()
                session["username"] = username
                return redirect(url_for("profile"))
            except sqlite3.IntegrityError:
                message = TEXT[lang]["taken"]
            finally:
                db.close()
    return render_page("register", message)


@app.route("/login", methods=["GET", "POST"])
def login():
    message = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute(
            "SELECT username,password FROM users WHERE username=?", (username,)
        ).fetchone()
        db.close()
        if user and check_password_hash(user[1], password):
            session.clear()
            session["username"] = user[0]
            return redirect(url_for("profile"))
        message = TEXT[current_lang()]["wrong_login"]
    return render_page("login", message)


@app.route("/profile")
def profile():
    if not session.get("username"):
        return redirect(url_for("login"))
    return render_page("profile")


@app.route("/edit_profile", methods=["POST"])
def edit_profile():
    if not session.get("username"):
        return redirect(url_for("login"))
    lang = current_lang()
    preset = request.form.get("preset", "target")
    if preset not in PRESETS:
        preset = "target"
    avatar_value = "preset:" + preset
    uploaded = request.files.get("avatar")
    if uploaded and uploaded.filename:
        filename = secure_filename(uploaded.filename)
        if "." not in filename:
            return render_page("profile", TEXT[lang]["bad_file"])
        extension = filename.rsplit(".", 1)[1].lower()
        if extension not in ALLOWED_EXTENSIONS:
            return render_page("profile", TEXT[lang]["bad_file"])
        new_filename = uuid.uuid4().hex + "." + extension
        uploaded.save(os.path.join(UPLOAD_FOLDER, new_filename))
        avatar_value = "uploads/" + new_filename
    db = get_db()
    db.execute("UPDATE users SET avatar=? WHERE username=?", (avatar_value, session["username"]))
    db.commit()
    db.close()
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))


@app.errorhandler(413)
def too_large(error):
    return "Image is too large. Maximum size is 2 MB.", 413


# Initialize the database when imported by the production server.
init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=False
    )
