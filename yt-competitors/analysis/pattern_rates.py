"""Шанс стать аутлайером для названий с шаблоном и без него (по ВСЕМ видео каналов за год)."""
import csv, re, sys
from pathlib import Path
from collections import Counter
sys.argv = ['x']
HERE = Path(__file__).resolve().parent
src = (HERE / 'analyze.py').read_text(encoding='utf-8')
ns = {'__file__': str(HERE / 'analyze.py')}
# берём из analyze.py только списки правил
exec(src.split('# ------------------------------------------------------------------ ВИСП')[0], ns)
exec('import re\n' + src.split('# ------------------------------------------------------------------ ВИСП')[1].split('visp_rows = []')[0], ns)
pat_src = src.split('PATTERNS = [')[1].split(']\npat_rows')[0]
PATTERNS = eval('[' + pat_src + ']')
NON = ns['NON_RU_CHANNELS']
allv = list(csv.DictReader(open(HERE / 'all_videos.csv', encoding='utf-8-sig'), delimiter=';'))
for v in allv:
    v['t'] = v['название'].lower().replace('ё', 'е')
    v['out'] = float(v['x_медианы']) >= 3
EXCL_ROMKA = len(sys.argv) > 1
def rate(s):
    return (len(s), sum(v['out'] for v in s), round(100 * sum(v['out'] for v in s) / len(s), 1) if s else 0)
rows = []
for label, base in [('RU-каналы', [v for v in allv if v['канал'] not in NON]),
                    ('RU без Romka и Sablin23', [v for v in allv if v['канал'] not in NON | {'Romka roker', 'ПУТЕШЕСТВЕННИК Sablin23'}])]:
    print(f'\n=== {label}: видео {len(base)}, аутлайеров {sum(v["out"] for v in base)}, базовый шанс {rate(base)[2]}%')
    for k, pats in ns['VISP_RE'].items():
        yes = [v for v in base if any(p.search(v['t']) for p in pats)]
        no = [v for v in base if not any(p.search(v['t']) for p in pats)]
        print(f'  ВИСП {k:20} с: {rate(yes)}  без: {rate(no)}')
        rows.append([label, 'ВИСП: ' + k, *rate(yes), *rate(no)])
    yr = ns['YEAR_RE']
    yes = [v for v in base if yr.search(v['t'])]; no = [v for v in base if not yr.search(v['t'])]
    print(f'  ВИСП дата/год            с: {rate(yes)}  без: {rate(no)}')
    rows.append([label, 'ВИСП: дата/год', *rate(yes), *rate(no)])
    def score(v):
        return sum(1 for pats in ns['VISP_RE'].values() if any(p.search(v['t']) for p in pats))
    for n in range(4):
        s = [v for v in base if score(v) == n] if n < 3 else [v for v in base if score(v) >= 3]
        print(f'  элементов ВИСП {n}{"+" if n==3 else ""}: {rate(s)}')
        rows.append([label, f'элементов ВИСП: {n}{"+" if n==3 else ""}', *rate(s), '', '', ''])
    for name, rx in PATTERNS:
        c = re.compile(rx)
        yes = [v for v in base if c.search(v['t']) or (name.startswith('Флаг') and c.search(v['название']))]
        no = [v for v in base if v not in yes]
        print(f'  {name[:58]:58} с: {rate(yes)}  без: {rate(no)[2]}%  каналов {len({v["канал"] for v in yes if v["out"]})}')
        rows.append([label, name, *rate(yes), *rate(no)])
with open(HERE / 'out' / 'pattern_rates.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f, delimiter=';')
    w.writerow(['выборка', 'признак', 'видео с признаком', 'из них аутлайеров', 'шанс, %', 'видео без', 'аутлайеров без', 'шанс без, %'])
    w.writerows(rows)
