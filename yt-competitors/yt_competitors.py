#!/usr/bin/env python3
"""
Анализ конкурентов на YouTube (YouTube Data API v3).

  python3 yt_competitors.py stage1   -> candidates.csv  (поиск и фильтр каналов)
  python3 yt_competitors.py stage2   -> outliers.csv + thumbnails/  (аутлайеры)

Этап 2 берёт каналы из selected.txt (по одной ссылке или ID канала на строку).
Если selected.txt нет, берутся все каналы из candidates.csv.
Ключ API читается из файла .env (строка YOUTUBE_API_KEY=...).
"""
import csv
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
API = "https://www.googleapis.com/youtube/v3/"
NOW = datetime.now(timezone.utc)

# ---------------------------------------------------------------- настройки
SUBS_MIN, SUBS_MAX = 5_000, 150_000
ACTIVE_DAYS = 183            # было видео за последние 6 месяцев
SEARCH_YEARS = 2             # publishedAfter = 2 года назад
LAST_N = 30                  # сколько последних видео проверяем
STAGE2_DAYS = 365            # этап 2: видео за последние 12 месяцев
MIN_DURATION_SEC = 180       # этап 2: длиннее 3 минут
OUTLIER_X = 3.0              # аутлайер: в 3+ раза выше медианы

UKR_LETTERS = set("іїєґ")

# Запрещённые слова (ищем по началу слова, чтобы ловить падежи: "Москве", "России"...)
BANNED = [
    r"автостоп", r"росси", r"дагестан", r"чечн", r"москв", r"питер",
    r"сибир", r"бали\b", r"таиланд", r"тайланд", r"африк",
    r"нов\w*\s+зеланди",
]
BANNED_RE = re.compile(r"\b(?:" + "|".join(BANNED) + ")", re.IGNORECASE)

# Признаки «видео про Европу или Турцию» (начала слов: страны, города, регионы)
EUROPE_TURKEY = [
    # общее
    "европ", "евротур", "шенген", "балкан", "скандинав", "прибалти", "альп", "доломит",
    "europe", "balkan",
    # Турция
    "турц", "турец", "стамбул", "анкар", "анталь", "антали", "каппадок", "каппадоки",
    "кападок", "измир", "бодрум", "фетхие", "кемер", "алань", "алани", "мармарис",
    "памуккале", "трабзон", "эфес", "сиде\\b", "даламан", "олюдениз", "бурс", "ликийск",
    "turkey", "turkiye", "türkiye", "istanbul", "cappadocia", "antalya",
    # страны и города Европы
    "австри", "вен[аеуы]\\b", "вене\\b", "зальцбург", "инсбрук", "гальштат",
    "бельги", "брюссел", "брюгге", "гент\\b", "антверпен",
    "болгар", "софи[яиюе]\\b", "варн[аеуы]\\b", "бургас", "пловдив",
    "британ", "англи", "лондон", "шотланд", "эдинбург", "уэльс",
    "венгр", "будапешт", "балатон", "дебрецен",
    "герман", "немецк", "берлин", "мюнхен", "гамбург", "дрезден", "кельн", "франкфурт", "бавари",
    "греци", "греческ", "афин", "крит\\b", "крит[аеу]\\b", "родос", "корфу", "санторин", "салоник", "халкидик",
    "метеор", "пелопоннес", "закинф", "кефалони", "наксос", "миконос",
    "дани[яиюе]\\b", "датск", "копенгаген",
    "ирланд", "дублин", "исланд",
    "испани", "испанск", "барселон", "мадрид", "севиль", "валенси", "малаг", "тенериф",
    "канарск", "майорк", "андалуси", "гранад",
    "итали", "итальян", "рим\\b", "рим[аеу]\\b", "милан", "венеци", "флоренци", "неапол",
    "сицили", "сардини", "тоскан", "болонь", "турин", "генуя", "генуе", "верон", "пиз[аеуы]\\b",
    "амальфи", "комо\\b", "гард[аеуы]\\b", "палермо", "доломит",
    "кипр", "лимассол", "пафос", "ларнак", "айя-напа",
    "латви", "рига\\b", "риге\\b", "ригу\\b", "юрмал", "литв", "вильнюс", "каунас",
    "эстони", "таллин", "тарту",
    "люксембург", "мальт", "монако", "андорр", "лихтенштейн", "сан-марино", "ватикан",
    "нидерланд", "голланд", "амстердам", "роттердам",
    "норвеги", "осло", "берген", "лофотен",
    "польш", "польск", "варшав", "краков", "гданьск", "вроцлав",
    "португал", "лиссабон", "порту\\b", "мадейр", "азорск",
    "румын", "бухарест", "трансильвани", "брашов", "сибиу", "клуж", "сигишоар", "констанц",
    "серби", "сербск", "белград", "нови-сад", "нови сад",
    "словаки", "словацк", "братислав", "татр",
    "словени", "любляна", "любляне", "блед\\b",
    "финлянд", "финск", "хельсинк", "лапланди",
    "франци", "француз", "париж", "ницц", "прованс", "марсел", "лион", "бордо", "лазурн", "нормандии",
    "хорвати", "хорватск", "сплит\\b", "дубровник", "загреб", "истри", "плитвиц",
    "черногори", "будв", "котор", "тиват",
    "чехи", "чешск", "праг[аеиу]\\b", "карловы вары", "брно",
    "швейцар", "цюрих", "женев", "люцерн", "интерлакен",
    "швеци", "шведск", "стокгольм",
    "албани", "албанск", "тиран", "македони", "охрид", "скопье",
    "босни", "сараево", "мостар", "молдов", "кишин",
    "paris", "rome", "italy", "spain", "greece", "prague", "vienna", "budapest", "romania", "serbia",
]
EUROPE_RE = re.compile(r"\b(?:" + "|".join(EUROPE_TURKEY) + ")", re.IGNORECASE)


# ---------------------------------------------------------------- утилиты
def load_key():
    env = HERE / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("YOUTUBE_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("YOUTUBE_API_KEY", "")


KEY = load_key()
SESSION = requests.Session()
UNITS = {"n": 0}


def api(endpoint, cost=1, **params):
    """Запрос к YouTube API с повторами при сетевых ошибках."""
    headers = {"X-Goog-Api-Key": KEY or "missing"}
    for attempt in range(5):
        try:
            r = SESSION.get(API + endpoint, params=params, headers=headers, timeout=30)
        except requests.RequestException as e:
            print(f"  сеть: {e}; повтор...")
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 200:
            UNITS["n"] += cost
            return r.json()
        if r.status_code in (500, 502, 503, 504):
            time.sleep(2 ** attempt)
            continue
        try:
            reason = r.json()["error"]["errors"][0].get("reason", "")
            msg = r.json()["error"].get("message", "")
        except Exception:
            reason, msg = "", r.text[:300]
        if reason in ("quotaExceeded", "dailyLimitExceeded"):
            sys.exit("\n!!! Закончилась дневная квота YouTube API. Попробуйте завтра "
                     "(квота обновляется в полночь по тихоокеанскому времени).")
        raise RuntimeError(f"YouTube API {r.status_code} {reason}: {msg}")
    raise RuntimeError("YouTube API: не удалось выполнить запрос после 5 попыток")


def norm(text):
    return (text or "").lower().replace("ё", "е")


def parse_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def parse_duration(iso):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def fmt_duration(sec):
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def chunks(seq, n=50):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def cached(name, fn):
    """Кэш ответов поиска, чтобы повторный запуск не тратил квоту."""
    d = HERE / "cache"
    d.mkdir(exist_ok=True)
    p = d / (re.sub(r"[^\w-]+", "_", name) + ".json")
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    data = fn()
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def get_channels(ids):
    out = {}
    for batch in chunks(list(ids)):
        data = api("channels", part="snippet,statistics,contentDetails",
                   id=",".join(batch), maxResults=50)
        for ch in data.get("items", []):
            out[ch["id"]] = ch
    return out


def recent_uploads(uploads_pl, limit=None, since=None):
    """Последние загрузки канала (новые первыми)."""
    items, token = [], None
    while True:
        params = dict(part="snippet,contentDetails", playlistId=uploads_pl, maxResults=50)
        if token:
            params["pageToken"] = token
        try:
            data = api("playlistItems", **params)
        except RuntimeError as e:
            if "404" in str(e):
                return items
            raise
        page = data.get("items", [])
        for it in page:
            pub = it["contentDetails"].get("videoPublishedAt") or it["snippet"]["publishedAt"]
            items.append({"id": it["contentDetails"]["videoId"],
                          "title": it["snippet"]["title"],
                          "published": parse_dt(pub)})
        token = data.get("nextPageToken")
        if not token or not page:
            break
        if limit and len(items) >= limit:
            break
        if since and min(parse_dt(it["contentDetails"].get("videoPublishedAt")
                                  or it["snippet"]["publishedAt"]) for it in page) < since:
            break
    items.sort(key=lambda x: x["published"], reverse=True)
    if since:
        items = [x for x in items if x["published"] >= since]
    return items[:limit] if limit else items


def video_details(ids):
    out = {}
    for batch in chunks(list(ids)):
        data = api("videos", part="snippet,contentDetails,statistics", id=",".join(batch))
        for v in data.get("items", []):
            out[v["id"]] = v
    return out


def write_csv(path, header, rows):
    # utf-8-sig + ';' — чтобы русский Excel открыл файл двойным щелчком без «кракозябр»
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(header)
        w.writerows(rows)


# ---------------------------------------------------------------- этап 1
def stage1():
    queries = [q.strip() for q in (HERE / "queries.txt").read_text(encoding="utf-8").splitlines()
               if q.strip()]
    after = (NOW - timedelta(days=365 * SEARCH_YEARS)).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"Поиск: {len(queries)} запросов × 2 длительности (medium, long)")
    channel_hits = {}
    for q in queries:
        for dur in ("medium", "long"):
            data = cached(f"search_{q}_{dur}", lambda: api(
                "search", cost=100, part="snippet", q=q, type="video", relevanceLanguage="ru",
                videoDuration=dur, publishedAfter=after, maxResults=50))
            for it in data.get("items", []):
                cid = it["snippet"]["channelId"]
                channel_hits[cid] = channel_hits.get(cid, 0) + 1
        print(f"  «{q}»: уникальных каналов всего {len(channel_hits)}")

    channels = get_channels(channel_hits)
    stats = {"подписчики вне 5–150 тыс.": 0, "страна UA": 0, "нет видео за 6 мес.": 0,
             "украинские буквы": 0, "запрещённые слова": 0, "мало Европы/Турции": 0}
    rows, rejected = [], []
    active_since = NOW - timedelta(days=ACTIVE_DAYS)

    for cid, ch in channels.items():
        name = ch["snippet"]["title"]
        st = ch.get("statistics", {})
        if st.get("hiddenSubscriberCount"):
            stats["подписчики вне 5–150 тыс."] += 1
            continue
        subs = int(st.get("subscriberCount", 0))
        if not (SUBS_MIN <= subs <= SUBS_MAX):
            stats["подписчики вне 5–150 тыс."] += 1
            continue
        if ch["snippet"].get("country") == "UA":
            stats["страна UA"] += 1
            continue

        pl = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        vids = recent_uploads(pl, limit=LAST_N)
        reason = None
        if not vids or vids[0]["published"] < active_since:
            reason = "нет видео за 6 мес."
        else:
            titles = [norm(v["title"]) for v in vids]
            joined = " ".join(titles)
            if UKR_LETTERS & set(joined):
                reason = "украинские буквы"
            elif BANNED_RE.search(joined):
                reason = "запрещённые слова"
            else:
                eu = sum(1 for t in titles if EUROPE_RE.search(t))
                if eu * 2 <= len(titles):
                    reason = "мало Европы/Турции"
        if reason:
            stats[reason] += 1
            rejected.append([name, f"https://www.youtube.com/channel/{cid}", subs, reason])
            continue

        eu = sum(1 for v in vids if EUROPE_RE.search(norm(v["title"])))
        rows.append([
            name,
            f"https://www.youtube.com/channel/{cid}",
            subs,
            int(st.get("videoCount", 0)),
            *[v["title"] for v in vids[:5]] + [""] * (5 - len(vids[:5])),
            f"{eu}/{len(vids)}",
            vids[0]["published"].strftime("%Y-%m-%d"),
            ch["snippet"].get("country", ""),
            cid,
        ])

    rows.sort(key=lambda r: r[2], reverse=True)
    write_csv(HERE / "candidates.csv",
              ["канал", "ссылка", "подписчики", "число видео",
               "видео 1 (последнее)", "видео 2", "видео 3", "видео 4", "видео 5",
               "про Европу/Турцию из последних", "дата последнего видео", "страна", "id канала"],
              rows)
    write_csv(HERE / "rejected.csv", ["канал", "ссылка", "подписчики", "причина отсева"],
              sorted(rejected, key=lambda r: r[3]))

    print(f"\nНайдено уникальных каналов: {len(channels)}")
    for k, v in stats.items():
        print(f"  отсеяно — {k}: {v}")
    print(f"\nПрошли фильтр: {len(rows)} каналов → candidates.csv\n")
    for i, r in enumerate(rows, 1):
        print(f"{i:>3}. {r[0]} — {r[2]:,} подп., {r[3]} видео, Европа/Турция {r[9]}".replace(",", " "))
        print(f"     {r[1]}")
        for t in r[4:9]:
            if t:
                print(f"       • {t}")
    print(f"\nИзрасходовано единиц квоты (без кэша): ~{UNITS['n']}")


# ---------------------------------------------------------------- этап 2
def selected_channel_ids():
    sel = HERE / "selected.txt"
    ids = []
    if sel.exists():
        lines = [l.strip() for l in sel.read_text(encoding="utf-8").splitlines() if l.strip()
                 and not l.strip().startswith("#")]
        handles = []
        for l in lines:
            m = re.search(r"(UC[\w-]{22})", l)
            if m:
                ids.append(m.group(1))
            else:
                h = re.search(r"@([\w.\-]+)", l)
                if h:
                    handles.append(h.group(1))
        for h in handles:
            data = api("channels", part="id", forHandle="@" + h)
            if data.get("items"):
                ids.append(data["items"][0]["id"])
            else:
                print(f"  не найден канал @{h}")
    else:
        with open(HERE / "candidates.csv", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f, delimiter=";"):
                ids.append(row["id канала"])
    return list(dict.fromkeys(ids))


def safe_name(s, n=40):
    s = re.sub(r"[^\w\- ]+", "", s, flags=re.UNICODE).strip().replace(" ", "_")
    return s[:n] or "video"


def stage2():
    ids = selected_channel_ids()
    if not ids:
        sys.exit("Нет каналов для этапа 2 (selected.txt / candidates.csv пусты).")
    channels = get_channels(ids)
    since = NOW - timedelta(days=STAGE2_DAYS)
    thumbs = HERE / "thumbnails"
    thumbs.mkdir(exist_ok=True)
    rows, summary = [], []

    for cid in ids:
        ch = channels.get(cid)
        if not ch:
            print(f"  канал {cid} не найден")
            continue
        name = ch["snippet"]["title"]
        subs = int(ch.get("statistics", {}).get("subscriberCount", 0))
        uploads = recent_uploads(ch["contentDetails"]["relatedPlaylists"]["uploads"], since=since)
        det = video_details([u["id"] for u in uploads])
        vids = []
        for u in uploads:
            v = det.get(u["id"])
            if not v:
                continue
            sec = parse_duration(v["contentDetails"].get("duration"))
            if sec <= MIN_DURATION_SEC or "viewCount" not in v.get("statistics", {}):
                continue
            if v["snippet"].get("liveBroadcastContent") in ("live", "upcoming"):
                continue
            vids.append((v, sec, int(v["statistics"]["viewCount"])))
        if not vids:
            print(f"• {name}: нет подходящих видео за 12 месяцев")
            summary.append([name, subs, 0, 0, 0])
            continue
        med = statistics.median(x[2] for x in vids)
        outs = [x for x in vids if med > 0 and x[2] >= OUTLIER_X * med]
        print(f"• {name}: видео >3 мин за год — {len(vids)}, медиана {int(med):,} просм., "
              f"аутлайеров {len(outs)}".replace(",", " "))
        summary.append([name, subs, len(vids), int(med), len(outs)])

        for v, sec, views in sorted(outs, key=lambda x: x[2], reverse=True):
            th = v["snippet"]["thumbnails"]
            best = next((th[k]["url"] for k in ("maxres", "standard", "high", "medium", "default")
                         if k in th), "")
            date = v["snippet"]["publishedAt"][:10]
            ratio = round(views / med, 1)
            if best:
                fn = thumbs / f"{safe_name(name, 25)}_{ratio}x_{v['id']}.jpg"
                if not fn.exists():
                    try:
                        r = SESSION.get(best, timeout=30)
                        if r.ok:
                            fn.write_bytes(r.content)
                    except requests.RequestException as e:
                        print(f"    превью не скачалось: {e}")
            rows.append([name, subs, v["snippet"]["title"], views, ratio, date,
                         fmt_duration(sec), best, f"https://www.youtube.com/watch?v={v['id']}",
                         int(med)])

    rows.sort(key=lambda r: r[4], reverse=True)
    write_csv(HERE / "outliers.csv",
              ["канал", "подписчики", "название", "просмотры", "во сколько раз выше медианы",
               "дата", "длительность", "ссылка на превью", "ссылка на видео", "медиана канала"],
              rows)
    write_csv(HERE / "channels_summary.csv",
              ["канал", "подписчики", "видео >3 мин за 12 мес.", "медиана просмотров",
               "аутлайеров"], summary)
    print(f"\nАутлайеров всего: {len(rows)} → outliers.csv, превью → thumbnails/")
    print(f"Израсходовано единиц квоты: ~{UNITS['n']}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "stage1":
        stage1()
    elif cmd == "stage2":
        stage2()
    else:
        print(__doc__)
