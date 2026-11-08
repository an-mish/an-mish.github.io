"""Анализ аутлайеров: ВИСП, шаблоны названий, темы, длительность, превью.
Запуск из папки yt-competitors:  python3 analysis/analyze.py
"""
import csv
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)


def read(p):
    with open(p, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f, delimiter=";"))


def write(name, header, rows):
    with open(OUT / name, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(header)
        w.writerows(rows)


def norm(s):
    return s.lower().replace("ё", "е")


def secs(d):
    p = [int(x) for x in d.split(":")]
    return p[0] * 3600 + p[1] * 60 + p[2] if len(p) == 3 else p[0] * 60 + p[1]


rows = read(ROOT / "outliers.csv")
for i, r in enumerate(rows, 1):
    r["n"] = i
    r["x"] = float(r["во сколько раз выше медианы"])
    r["t"] = norm(r["название"])
    r["ru"] = bool(re.search(r"[а-я]", r["t"]))
    r["sec"] = secs(r["длительность"])

# Каналы не на русском: их названия в разбор шаблонов не берём (но считаем отдельно)
NON_RU_CHANNELS = {"Europe Visa News", "Spanish Property Choice ", "Turkey Travel Planner",
                   "Stuffed Cabbage Adventures", "Travel Time - Dj0rdje1", "TraverseXP by AJ"}
for r in rows:
    r["ru_channel"] = r["канал"] not in NON_RU_CHANNELS


# ------------------------------------------------------------------ ВИСП
VISP = {
    "Выгода": [
        r"что посмотреть", r"куда (поехать|пойти|сходить|уехать|переехать)", r"маршрут",
        r"\bгид\b", r"гид по", r"путеводител", r"\bкак\b", r"где (вкусно|поесть|покушать|остановиться)", r"сам(ый|ое|ая|ые) красив", r"\bтоп\b", r"лучш",
        r"что (надо|нужно) знать", r"инструкц", r"обзор", r"секрет", r"советы", r"лайфхак",
        r"ошибк", r"сколько (стоит|нужно)", r"цены", r"за (1|один|2|два|три|3) (день|дня|дней)",
        r"какой источник что лечит", r"things to do", r"guide", r"how to", r"itinerary",
        r"mistakes", r"scams", r"must.know", r"to avoid", r"best", r"top \d", r"\d+ причин",
        r"полный", r"подробн", r"чтобы увидеть больше",
    ],
    "Интрига": [
        r"\?", r"не ожидал", r"шок", r"тайн", r"секрет", r"скрыт", r"никто не", r"никому",
        r"правда", r"почему", r"что происходит", r"неизвестн", r"не такая", r"удивил",
        r"ужас", r"невозможн", r"о котор(ой|ом) никто", r"которого не должно", r"чуть не",
        r"не все", r"\.\.\.|…", r"не только", r"не расскажут", r"не покажет", r"вот это",
        r"самое страшное", r"смертельн", r"крови|кровав|мертв", r"lies", r"dangerous",
        r"need to talk", r"reality", r"\bsach\b", r"не доходят", r"заблуждени", r"хватит",
        r"не существует", r"сюрприз", r"началось", r"не хочу", r"изменит все", r"а ведь",
    ],
    "Срочность (призыв)": [
        r"обязательно", r"\bнадо\b", r"нужно знать", r"внимание", r"осторожн", r"будьте", r"срочно",
        r"сейчас", r"не ходите", r"смотри", r"перед поездкой", r"before you", r"avoid",
        r"apply now", r"отдыхай", r"наслаждайся", r"решили .* тогда", r"хотя бы раз",
        r"must", r"не потеря", r"не опоздать", r"вам сюда", r"сегодня", r"не грустите", r"хватит",
    ],
    "Причастность": [
        r"\bвы\b", r"\bвас\b", r"\bвам\b", r"\bваш", r"\bты\b", r"\bтебя\b", r"туристы",
        r"туристов", r"пенсионер", r"на пенси", r"эмигра", r"соотечественник", r"переезд",
        r"родился в ссср", r"нашу пенсию", r"наши(ми)? грек", r"для тех", r"\byou\b", r"\byour\b",
        r"like a local", r"\blocal", r"for pakistanis", r"иностран", r"на двоих", r"с любимой",
        r"товарищ", r"60\+|64\+|шестой десяток", r"из россии", r"экспат",
    ],
}
VISP_RE = {k: [re.compile(p) for p in v] for k, v in VISP.items()}
YEAR_RE = re.compile(r"\b20(25|26|27)\b|январ|феврал|март|апрел|ма[яй]\b|июн|июл|август|сентябр|октябр|ноябр|декабр")

visp_rows = []
for r in rows:
    marks = {}
    for k, pats in VISP_RE.items():
        found = []
        for p in pats:
            m = p.search(r["t"])
            if m:
                found.append(m.group(0).strip())
        marks[k] = sorted(set(found))
    year = YEAR_RE.search(r["t"])
    r["visp"] = marks
    r["year"] = bool(year)
    r["score"] = sum(1 for k in marks if marks[k])
    visp_rows.append([r["n"], r["канал"], r["название"], r["x"]] +
                     [("да: " + ", ".join(marks[k])) if marks[k] else "нет" for k in VISP] +
                     [("да: " + year.group(0)) if year else "нет", r["score"]])
write("visp_titles.csv",
      ["№", "канал", "название", "x медианы", "Выгода", "Интрига", "Срочность (призыв)",
       "Причастность", "Дата/год (актуальность)", "сколько элементов ВИСП"], visp_rows)


def agg(sub):
    xs = [r["x"] for r in sub]
    if not xs:
        return 0, 0, 0, 0
    return len(xs), len({r["канал"] for r in sub}), round(st.mean(xs), 1), round(st.median(xs), 1)


ru = [r for r in rows if r["ru_channel"]]
print("ВСЕГО", len(rows), "из них русскоязычных каналов", len(ru))
print("\n== ВИСП (русскоязычные каналы) ==")
for k in VISP:
    yes = [r for r in ru if r["visp"][k]]
    no = [r for r in ru if not r["visp"][k]]
    print(f"{k:22} есть {agg(yes)}  нет {agg(no)}")
print("Год/дата", agg([r for r in ru if r["year"]]), "нет", agg([r for r in ru if not r["year"]]))
for s in range(5):
    print("элементов", s, agg([r for r in ru if r["score"] == s]))

# ------------------------------------------------------------------ шаблоны
PATTERNS = [
    ("«Что посмотреть / куда пойти / things to do»", r"что посмотреть|куда (пойти|сходить)|things to do|what to see"),
    ("«За N дней / 1 день / 72 часа»", r"за (1|один|одн|2|два|три|3)\s*(день|дня|дней)|\b\d+ дн(я|ей)\b|72 часа|\d+ days|один день"),
    ("Число-список в названии: «Топ-5», «10 ошибок», «7 причин», «101 Things»", r"\bтоп[ -]?\d|\b\d+ (причин|мест|ошибок|направлен|вещ|отел|lies|things|big|must|tourist)|\btop \d"),
    ("«Почему …»", r"\bпочему\b|\bwhy\b"),
    ("Вопрос в названии (знак «?»)", r"\?"),
    ("«Не ожидал(а) / удивил / не такая, как вы думали»", r"не ожидал|удивил|не такая|такого (я )?не|вы не поверите|сам в шоке"),
    ("«Честно / правда / реальность / без прикрас»", r"честн|правд|реальн|без прикрас|reality|truth|\bsach\b|как есть"),
    ("«Шок / ужас / жесть / кошмар» (эмоция-страх)", r"шок|ужас|жесть|кошмар|страшн|катастроф|ад\b|ад в"),
    ("«Стоит ли / оно того стоит / worth it»", r"стоит ли|того стоит|стоит ехать|worth"),
    ("Сравнение: «или», «vs», «лучше чем», «как X»", r"\bили\b|\bvs\b|лучше чем|больше, чем|больше чем|греческая венеция|рублевк|ривьера|\bкак [а-я]+ов\b"),
    ("Скрытое: «секрет / тайна / никто не знает / неизвестн / туристы не доходят»", r"секрет|тайн|скрыт|никто не|неизвестн|не доход|не знаете|не покажет|не расскажут|о которой никто|hidden"),
    ("Ошибки и ловушки туриста: «ошибки / обман / как не потеряться / осторожно / scams»", r"ошибк|обман|ловушк|как не|осторожн|теряете|scam|mistake|trap|avoid|не потеря"),
    ("«Что надо знать / полный гид / инструкция»", r"что надо знать|надо знать|нужно знать|гид|инструкц|guide|must.know|explained|everything you"),
    ("Маршрут / прогулка / пешком", r"маршрут|прогулк|пешком|walking|itinerary|идем по"),
    ("Личный опыт: «я / мы / мой / N лет жизни»", r"\bя\b|\bмы\b|\bмой\b|\bмоя\b|\bмое\b|\bмои\b|\bнаш|личный опыт|\d+ лет|спустя"),
    ("Цены / «сколько стоит» / бюджет", r"цен[аыуе]|сколько стоит|сколько нужно|бюджет|дешев|недорог|за копейки|сколько потрат|salary|€|\$"),
    ("Превосходная степень: «самый / лучший / best»", r"сам(ый|ая|ое|ые|ой|ом)|лучш|best|идеальн"),
    ("Сезон / месяц в названии", r"январ|феврал|март|апрел|\bма[яй]\b|июн|июл|август|сентябр|октябр|ноябр|декабр|зимой|летом|рождеств|новый год|новогодн|christmas|осен"),
    ("Город + сезон: «в ноябре», «зимой», «рождественская»", r"\b(в|на) (январе|феврале|марте|апреле|мае|июне|июле|августе|сентябре|октябре|ноябре|декабре)\b|зимой|осенью|рождеств|новогодн|christmas"),
    ("Год в названии (2025/2026)", r"\b20(25|26|27)\b"),
    ("Флаг-эмодзи в названии", r"[\U0001F1E6-\U0001F1FF]{2}"),
]
pat_rows = []
print("\n== ШАБЛОНЫ (русскоязычные каналы | все каналы) ==")
for name, rx in PATTERNS:
    c = re.compile(rx)
    sub = [r for r in ru if c.search(r["t"]) or (name.startswith("Флаг") and c.search(r["название"]))]
    suball = [r for r in rows if c.search(r["t"]) or (name.startswith("Флаг") and c.search(r["название"]))]
    n, ch, mean, med = agg(sub)
    na, cha, meana, meda = agg(suball)
    ex = sorted(sub, key=lambda r: -r["x"])[:6]
    chans = Counter(r["канал"] for r in sub).most_common(3)
    print(f"{name[:60]:60} RU n={n} кан={ch} ср={mean} мед={med} | ВСЕ n={na} кан={cha} ср={meana} мед={meda} | топ-каналы {chans}")
    pat_rows.append([name, n, ch, mean, med, na, cha, meana, meda,
                     " || ".join(f"{r['название'].strip()} (x{r['x']}, {r['канал'].strip()})" for r in ex),
                     ", ".join(f"{k.strip()}: {v}" for k, v in chans)])
write("patterns.csv", ["шаблон", "RU: видео", "RU: каналов", "RU: средний x", "RU: медианный x",
                       "все: видео", "все: каналов", "все: средний x", "все: медианный x",
                       "лучшие примеры (RU)", "каналы, где чаще всего"], pat_rows)
print("База RU:", agg(ru), "ВСЕ:", agg(rows))

# ------------------------------------------------------------------ темы и жанры
GENRES = [
    ("Новости / политика / «Европа на грани»", r"мигрант|сеут|войн|кризис|погром|бунт|гор(ит|ят)|диктатор|санчес|революц|конец европы|граница|депорт|эль-ниньо|cash banned|ждет нас"),
    ("Королевская семья и биографии", r"леонор|летиси|софия испанская|инфант|кабалье|королев|принцесс|франко|гауди|шевчук|ддт|магомаев|елизаветы"),
    ("Визы / работа / иммиграция", r"visa|work permit|jobs|trc|immigration|nulla osta|pr 20|ausbildung|салари|salary|виз[аы]|внж|гражданств"),
    ("Недвижимость / дом / дача", r"villa|apartment|penthouse|duplex|cortijo|for sale|купил[аи]? (дом|квартир)|дом в турции|дач[уаи]|ремонт|окна|ипотек|квартир|недвижим|рублевк|цена моего дома|сада"),
    ("Погода / море / пляж «сегодня» (Аланья)", r"погод|температур[аеу] воды|ливн|дожд|шторм|жара|лето|град|молни|наводнен|подтоплен|пляж клеопатр|пустые пляжи|полные пляжи|море и пляжи|волны|что с морем|затапл"),
    ("Шопинг / рынки / цены на продукты", r"рынок|базар|магазин|обувь|кож[аи]|мех|сумки|duty free|дьюти|цены на|супермаркет|шоппинг|распродаж|\bdm\b|закупк|что едят|продукт|злотых|сыр, мед"),
    ("Отели / пакетный отдых", r"отел|hotel|resort|все включено|ультра|5\*|5 \*|4★|crystal|justiniano|calido|concordia|club hotel|maldives"),
    ("Жизнь / переезд / пенсия / эмиграция", r"пенси|жизнь в|жизни в|переезд|переех|эмиграц|уехал|адаптац|соотечественник|год в испании|живут|живу|прожила|бизнес в|полгода в|лет прожив|после \d+ лет|комфортно|выживал|стоит ли переезжать"),
    ("Автопутешествие / автодом", r"автодом|караван|трейлер|tundra|на авто|на своем авто|на машине|оффгрид|км за|фаркоп|аренда авто"),
    ("Город-гид: что посмотреть / маршрут / за N дней", r"что посмотреть|маршрут|за (1|один|2|два) (день|дня)|things to do|travel guide|guide to|itinerary|топ мест|прогулка по|walking tour|куда пойти|где остановиться|принцевы|за два дня|за один день|must visit|большой влог"),
    ("Скрытые и необычные места / природа", r"скрыт|неизвестн|о которой никто|каньон|пещер|пляж|остров|озер|ущель|термальн|источник|ванны|мост|мыс|деревн|село|некропол|город мертв|замок|крепост|дорога|рафтинг|виндсерф|не доходят|вулкан|альп|горы"),
    ("Ошибки туриста / аэропорт / практические советы", r"ошибк|scam|mistake|аэропорт|пересадк|как не|теряете|что надо знать|must-know|things to know|lies|tips|revolut|банк|безопасност"),
    ("Праздники / сезонные события", r"рождеств|новый год|новогодн|christmas|ярмарк|фестивал|концерт"),
]
def genre(r):
    for g, rx in GENRES:
        if re.search(rx, r["t"]):
            return g
    return "Прочее / влог"
for r in rows:
    r["genre"] = genre(r)
g_rows = []
print("\n== ЖАНРЫ (все каналы) ==")
for g in [x[0] for x in GENRES] + ["Прочее / влог"]:
    sub = [r for r in rows if r["genre"] == g]
    n, ch, mean, med = agg(sub)
    ex = sorted(sub, key=lambda r: -r["x"])[:4]
    print(f"{g:55} n={n} кан={ch} ср={mean} мед={med} | {Counter(r['канал'].strip() for r in sub).most_common(3)}")
    g_rows.append([g, n, ch, mean, med, " || ".join(f"{r['название'].strip()} (x{r['x']}, {r['канал'].strip()})" for r in ex),
                   ", ".join(f"{k}: {v}" for k, v in Counter(r['канал'].strip() for r in sub).most_common(3))])
write("genres.csv", ["жанр", "видео", "каналов", "средний x", "медианный x", "лучшие примеры", "каналы"], g_rows)

PLACES = {
    "Греция": r"греци|греческ|🇬🇷|афин|левкад|лефкад|мани|эпир|парг|касторь|самотрак|тасос|кими|янин|нафплион|викос|коринф|метан|эгремни|айтолико|кефалон|sivota|argostoli|kefalonia|пелопоннес|каламат|портохилион|василики",
    "Турция (вся)": r"турц|турец|turkey|turkiye|стамбул|istanbul|аланья|алания|alanya|анталь|антали|кемер|каш\b|сиде|принцевы|буюкада|сабиха",
    "  из них Аланья": r"аланья|алания|alanya|клеопатр|\bоба\b|махмутлар",
    "  из них Стамбул": r"стамбул|istanbul|принцевы|буюкада|сабиха",
    "Испания": r"испани|барселон|сеут|майорк|малаг|марбель|каталон|almer|spain|саграда|леонор|летиси|франко|кабалье|санчес",
    "Болгария": r"болгар|бургас|варн|родоп|старозагор|сарафов|пловдив",
    "Италия": r"итали|сицили|палермо|катани|чефалу|тоскан|бергамо|лекко|генуя|милан|italy|рим\b",
    "Чехия (Карловы Вары)": r"карловы вары|karlovy|чехи|czech|прага",
    "Великобритания": r"лондон|london|эдинбург|англи|uk\b|букингем|хайгейт|хэмпстед",
    "Венгрия (Будапешт)": r"будапешт|budapest|венгр",
    "Германия / Австрия": r"германи|germany|бавари|берлин|berlin|вен[аые]\b|vienna|австри|розенкруг",
    "Румыния / Сербия / Балканы": r"румын|romania|бухарест|трансильван|серби|serbia|белград|belgrade|черногор|македони|скопье|словени|slovenia|албани|albania",
    "Польша / Прибалтика": r"польш|poland|краков|литв|латви|эстони|прибалт|latvia",
    "Не Европа (Египет, Баку, Москва, Беларусь и др.)": r"египет|хургад|баку|азербайдж|москв|пинск|брест|гомел|беларус|иордани|тунис|мальдив|кабо|коста-рик|алматы|казахстан|ереван|екатеринбург|сингапур|australia|vanuatu|dubai",
}
p_rows = []
print("\n== МЕСТА ==")
for p, rx in PLACES.items():
    sub = [r for r in rows if re.search(rx, r["t"] + " " + r["название"])]
    n, ch, mean, med = agg(sub)
    print(f"{p:45} n={n} кан={ch} ср={mean} мед={med} {Counter(r['канал'].strip() for r in sub).most_common(3)}")
    p_rows.append([p, n, ch, mean, med, ", ".join(f"{k}: {v}" for k, v in Counter(r['канал'].strip() for r in sub).most_common(4))])
write("places.csv", ["место", "видео", "каналов", "средний x", "медианный x", "каналы"], p_rows)

# ------------------------------------------------------------------ длительность
allv = read(HERE / "all_videos.csv")
BUCKETS = [("до 10 мин", 0, 600), ("10–20 мин", 600, 1200), ("20–40 мин", 1200, 2400), ("больше 40 мин", 2400, 10**9)]
d_rows = []
print("\n== ДЛИТЕЛЬНОСТЬ ==")
for name, lo, hi in BUCKETS:
    o = [r for r in rows if lo <= r["sec"] < hi]
    o_ru = [r for r in ru if lo <= r["sec"] < hi]
    a = [v for v in allv if lo <= int(v["секунд"]) < hi]
    a_out = [v for v in a if float(v["x_медианы"]) >= 3]
    n, ch, mean, med = agg(o)
    nr, chr_, meanr, medr = agg(o_ru)
    rate = round(100 * len(a_out) / len(a), 1) if a else 0
    print(f"{name:14} аутлайеров {n} ({round(100*n/len(rows))}%) ср={mean} мед={med} | RU {nr} ср={meanr} мед={medr} | всего видео {len(a)} ({round(100*len(a)/len(allv))}%), доля аутлайеров {rate}%")
    d_rows.append([name, n, f"{round(100*n/len(rows))}%", mean, med, nr, meanr, medr, len(a), f"{round(100*len(a)/len(allv))}%", f"{rate}%"])
write("duration.csv", ["длительность", "аутлайеров", "доля среди аутлайеров", "средний x", "медианный x",
                       "RU-аутлайеров", "RU средний x", "RU медианный x", "все видео каналов", "доля среди всех видео",
                       "шанс стать аутлайером"], d_rows)
# связь длительности и множителя
xs = [r["sec"] for r in rows]; ys = [r["x"] for r in rows]
def spearman(a, b):
    ra = {v: i for i, v in enumerate(sorted(range(len(a)), key=lambda k: a[k]))}
    rb = {v: i for i, v in enumerate(sorted(range(len(b)), key=lambda k: b[k]))}
    n = len(a)
    d2 = sum((ra[i] - rb[i]) ** 2 for i in range(n))
    return 1 - 6 * d2 / (n * (n * n - 1))
print("Spearman длительность~множитель (аутлайеры):", round(spearman(xs, ys), 3))
# Внутри каналов: доля аутлайеров по бакетам для каналов, у которых есть видео в разных бакетах
per = defaultdict(lambda: defaultdict(lambda: [0, 0]))
for v in allv:
    s = int(v["секунд"])
    b = next(nm for nm, lo, hi in BUCKETS if lo <= s < hi)
    per[v["канал"]][b][0] += 1
    per[v["канал"]][b][1] += float(v["x_медианы"]) >= 3
print("Каналы: доля аутлайеров по длительности (видео/аутлайеры)")
for ch, d in per.items():
    print(" ", ch.strip()[:28], {b: f"{d[b][1]}/{d[b][0]}" for b, _, _ in BUCKETS if d[b][0]})

# ------------------------------------------------------------------ превью
notes = {}
for line in (HERE / "thumbs_notes.txt").read_text(encoding="utf-8").splitlines():
    if line.startswith("#") or not line.strip():
        continue
    p = line.split("|")
    notes[int(p[0])] = dict(face=p[1], text=p[2], words=p[3], dup=p[4], obj=p[5], colors=p[6], plan=p[7], gfx=p[8])

def face_cat(f):
    if f == "0":
        return "нет людей"
    if "мелко" in f or "со спины" in f:
        return "люди мелко / со спины"
    if f.startswith("автор"):
        return "лицо автора"
    return "лицо другого человека"

def words_n(w):
    m = re.match(r"(\d+)", w)
    return int(m.group(1)) if m else 0

def wcat(n):
    return "0" if n == 0 else "1–3" if n <= 3 else "4–7" if n <= 7 else "8–12" if n <= 12 else "13+"

for r in rows:
    nt = notes[r["n"]]
    r["face"] = face_cat(nt["face"])
    r["wn"] = words_n(nt["words"])
    r["wc"] = wcat(r["wn"])
    r["dup"] = nt["dup"]
    r["plan"] = nt["plan"]
    g = nt["gfx"].lower()
    r["g_flag"] = "флаг" in g
    r["g_num"] = bool(re.search(r"\d|цифр", g))
    r["g_arrow"] = bool(re.search(r"стрел|палец|указат", g))
    r["g_circle"] = "круг" in g
    r["g_collage"] = "коллаж" in g or "коллаж" in nt["obj"]
    r["g_price"] = "цена" in g or "цены" in g or "€" in g
    r["g_ai"] = "AI" in nt["obj"] or "AI" in nt["colors"]
    r["obj"] = nt["obj"]; r["colors"] = nt["colors"]

def show(title, key, subset, order=None):
    c = defaultdict(list)
    for r in subset:
        c[key(r)].append(r)
    print(f"-- {title}")
    out = []
    for k in (order or sorted(c, key=lambda k: -len(c[k]))):
        if k in c:
            n, ch, mean, med = agg(c[k])
            print(f"   {str(k):28} {n:4} ({round(100*n/len(subset))}%) кан={ch} ср={mean} мед={med}")
            out.append([title, k, n, f"{round(100*n/len(subset))}%", ch, mean, med])
    return out

print("\n== ПРЕВЬЮ (все 363) ==")
th = []
th += show("Лицо", lambda r: r["face"], rows)
th += show("Слов на превью", lambda r: r["wc"], rows, ["0", "1–3", "4–7", "8–12", "13+"])
th += show("Текст дублирует название", lambda r: r["dup"], [r for r in rows if r["wn"] > 0])
th += show("План", lambda r: r["plan"], rows)
for nm, k in [("флаг", "g_flag"), ("цифры/год", "g_num"), ("стрелка/палец/указатель", "g_arrow"),
              ("круг", "g_circle"), ("коллаж", "g_collage"), ("цена крупно", "g_price"), ("AI-картинка", "g_ai")]:
    th += show(f"Есть {nm}", lambda r, k=k: "да" if r[k] else "нет", rows, ["да", "нет"])
print("\n== ПРЕВЬЮ: только русскоязычные тревел-каналы (без Ромки, визовых, недвижимости, новостей) ==")
EXCL = NON_RU_CHANNELS | {"Romka roker", "Artur Yarilo ", "Сергей Захаров гид в Барселоне "}
core = [r for r in rows if r["канал"] not in EXCL]
print("core n=", len(core))
th += show("CORE Лицо", lambda r: r["face"], core)
th += show("CORE Слов", lambda r: r["wc"], core, ["0", "1–3", "4–7", "8–12", "13+"])
th += show("CORE Дублирует", lambda r: r["dup"], [r for r in core if r["wn"] > 0])
th += show("CORE План", lambda r: r["plan"], core)
for nm, k in [("флаг", "g_flag"), ("цифры/год", "g_num"), ("стрелка/палец", "g_arrow"), ("коллаж", "g_collage"), ("AI", "g_ai")]:
    th += show(f"CORE {nm}", lambda r, k=k: "да" if r[k] else "нет", core, ["да", "нет"])
write("thumbs_summary.csv", ["признак", "значение", "превью", "доля", "каналов", "средний x", "медианный x"], th)

# Каждое превью — строкой
write("thumbs_each.csv", ["№", "канал", "название", "x", "лицо", "текст", "слов", "дублирует название",
                          "главный объект", "цвета", "план", "графика"],
      [[r["n"], r["канал"].strip(), r["название"].strip(), r["x"], notes[r["n"]]["face"], "да" if notes[r["n"]]["text"] == "1" else "нет",
        notes[r["n"]]["words"], notes[r["n"]]["dup"], notes[r["n"]]["obj"], notes[r["n"]]["colors"], notes[r["n"]]["plan"],
        notes[r["n"]]["gfx"]] for r in rows])

print("\n== Превью без людей (core + все RU), по убыванию x ==")
for r in sorted([r for r in rows if r["face"] in ("нет людей", "люди мелко / со спины") and r["ru_channel"]], key=lambda r: -r["x"])[:40]:
    nt = notes[r["n"]]
    print(f" #{r['n']} x{r['x']} {r['канал'].strip()[:18]} | {nt['obj']} | {nt['colors']} | слов {nt['words']} | {nt['gfx']}")

print("\n== Каналы: число аутлайеров ==")
for ch, n in Counter(r["канал"].strip() for r in rows).most_common():
    print(" ", ch, n)
