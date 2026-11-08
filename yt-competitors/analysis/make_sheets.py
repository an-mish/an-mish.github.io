import csv, glob, os
from PIL import Image, ImageDraw, ImageFont
rows = list(csv.DictReader(open('outliers.csv', encoding='utf-8-sig'), delimiter=';'))
allf = glob.glob('thumbnails/*.jpg')
files = {}
for r0 in rows:
    v0 = r0['ссылка на видео'].split('v=')[1]
    m = [f for f in allf if f.endswith('x_' + v0 + '.jpg')]
    if m: files[v0] = m[0]
W, H, C = 512, 288, 3
try:
    font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 26)
except Exception:
    font = ImageFont.load_default()
missing = 0
for s in range(0, len(rows), 9):
    sheet = Image.new('RGB', (W * C, H * 3), 'white')
    d = ImageDraw.Draw(sheet)
    for k, r in enumerate(rows[s:s + 9]):
        vid = r['ссылка на видео'].split('v=')[1]
        f = files.get(vid)
        x, y = (k % C) * W, (k // C) * H
        if f:
            im = Image.open(f).convert('RGB')
            im = im.resize((W, int(im.height * W / im.width)))
            if im.height > H:  # 4:3 -> crop to 16:9
                t = (im.height - H) // 2; im = im.crop((0, t, W, t + H))
            sheet.paste(im, (x, y))
        else:
            missing += 1
        n = str(s + k + 1)
        d.rectangle([x, y, x + 18 * len(n) + 12, y + 34], fill='yellow')
        d.text((x + 6, y + 2), n, fill='black', font=font)
    sheet.save(f'analysis/sheets/sheet_{s // 9 + 1:02d}.jpg', quality=85)
print('sheets', (len(rows) + 8) // 9, 'missing', missing)
