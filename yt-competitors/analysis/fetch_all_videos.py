"""Все видео >3 мин за 12 мес. по выбранным каналам — база для сравнения с аутлайерами."""
import sys, statistics
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import yt_competitors as y

ids = y.selected_channel_ids()
chs = y.get_channels(ids)
since = y.NOW - y.timedelta(days=y.STAGE2_DAYS)
rows = []
for cid in ids:
    ch = chs[cid]
    ups = y.recent_uploads(ch['contentDetails']['relatedPlaylists']['uploads'], since=since)
    det = y.video_details([u['id'] for u in ups])
    vids = []
    for u in ups:
        v = det.get(u['id'])
        if not v or 'viewCount' not in v.get('statistics', {}):
            continue
        sec = y.parse_duration(v['contentDetails'].get('duration'))
        if sec <= y.MIN_DURATION_SEC or v['snippet'].get('liveBroadcastContent') in ('live', 'upcoming'):
            continue
        vids.append((v, sec, int(v['statistics']['viewCount'])))
    if not vids:
        continue
    med = statistics.median(x[2] for x in vids)
    for v, sec, views in vids:
        rows.append([ch['snippet']['title'], v['snippet']['title'], views, sec,
                     round(views / med, 2) if med else 0, v['snippet']['publishedAt'][:10], v['id']])
y.write_csv(Path(__file__).parent / 'all_videos.csv',
            ['канал', 'название', 'просмотры', 'секунд', 'x_медианы', 'дата', 'id'], rows)
print(len(rows), 'видео; квота ~', y.UNITS['n'])
