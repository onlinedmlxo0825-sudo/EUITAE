"""Thumbnail drafts for the 1108 vlog (1280x720), in the channel's style and two variations.

Channel style (seen on @xuitae vlogs): left half = gym physique shot, right half = the catch close-up,
one line of big white text with a thick black outline at the bottom.
usage: python -I make_thumbnails.py <repo_root>
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = Path(sys.argv[1])
PROJ = ROOT / '1108_낚시_등운동_브이로그' / '04_thumbnail'
SRC = PROJ / 'src'
W, H = 1280, 720
BHS = str(ROOT / 'fonts' / 'BlackHanSans-Regular.ttf')
GOTHIC = str(ROOT / 'fonts' / 'GothicA1-Black.ttf')
YELLOW, ORANGE, WHITE, BLACK = (255, 222, 40), (255, 74, 43), (255, 255, 255), (0, 0, 0)


def cover(img, w, h, cx=0.5, cy=0.5, zoom=1.0):
    """Crop img to aspect w:h around (cx, cy) (0..1), optionally zoomed in, and resize to w x h."""
    iw, ih = img.size
    scale = max(w / iw, h / ih) * zoom
    cw, ch = w / scale, h / scale
    x0 = min(max(cx * iw - cw / 2, 0), iw - cw)
    y0 = min(max(cy * ih - ch / 2, 0), ih - ch)
    return img.resize((w, h), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch))


def pop(img, sat=1.15, con=1.08, sharp=1.2):
    img = ImageEnhance.Color(img).enhance(sat)
    img = ImageEnhance.Contrast(img).enhance(con)
    return ImageEnhance.Sharpness(img).enhance(sharp)


def outlined(canvas, xy, parts, size, stroke=10, anchor='ms', font=BHS, shadow=True):
    """parts: [(text, color), ...] drawn as one line with a thick black outline and a soft drop shadow."""
    f = ImageFont.truetype(font, size)
    d = ImageDraw.Draw(canvas)
    widths = [d.textlength(t, font=f) for t, _ in parts]
    total = sum(widths)
    x = xy[0] - (total / 2 if anchor[0] == 'm' else 0)
    if shadow:
        sh = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        xx = x
        for (t, _), w in zip(parts, widths):
            sd.text((xx + 6, xy[1] + 8), t, font=f, fill=(0, 0, 0, 170), anchor='l' + anchor[1], stroke_width=stroke, stroke_fill=(0, 0, 0, 170))
            xx += w
        canvas.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)))
    for (t, col), w in zip(parts, widths):
        d.text((x, xy[1]), t, font=f, fill=col, anchor='l' + anchor[1], stroke_width=stroke, stroke_fill=BLACK)
        x += w


def bottom_fade(canvas, h=260, a=170):
    g = Image.new('L', (1, h))
    for y in range(h):
        g.putpixel((0, y), int(a * (y / h) ** 1.6))
    g = g.resize((W, h))
    shade = Image.new('RGBA', (W, h), (0, 0, 0, 255))
    shade.putalpha(g)
    canvas.alpha_composite(shade, (0, H - h))


back = pop(Image.open(SRC / 'back_70.0.jpg').convert('RGB'))
fish = pop(Image.open(ROOT / 'assets' / 'gamseongdom.jpg').convert('RGB'), sat=1.1, con=1.12)
rod = pop(Image.open(SRC / 'rod_136.2.jpg').convert('RGB'), sat=1.25, con=1.1)

# ── A: channel style (half / half + one line) ──
a = Image.new('RGBA', (W, H))
a.paste(cover(back, W // 2, H, cx=0.5, cy=0.42), (0, 0))
a.paste(cover(fish, W // 2, H, cx=0.62, cy=0.45, zoom=1.55), (W // 2, 0))
ImageDraw.Draw(a).rectangle([W // 2 - 3, 0, W // 2 + 3, H], fill=WHITE)
bottom_fade(a)
outlined(a, (W / 2, H - 52), [('등 운동 후 ', WHITE), ('감성돔', YELLOW), (' 낚음', WHITE)], 92)

# ── B: curiosity (bent rod full bleed, circle on the tip) ──
b = Image.new('RGBA', (W, H))
b.paste(cover(rod, W, H, cx=0.42, cy=0.45, zoom=1.12), (0, 0))
d = ImageDraw.Draw(b)
tip = (560, 92)                                    # where the bent rod tip is
d.ellipse([tip[0] - 78, tip[1] - 62, tip[0] + 78, tip[1] + 62], outline=(255, 30, 30), width=11)
# small physique inset, right side, with a white border
ins = cover(back, 300, 300, cx=0.5, cy=0.4, zoom=1.15)
mask = Image.new('L', (300, 300), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, 299, 299], radius=28, fill=255)
bd = Image.new('RGBA', (316, 316), (0, 0, 0, 0))
ImageDraw.Draw(bd).rounded_rectangle([0, 0, 315, 315], radius=34, fill=WHITE)
b.alpha_composite(bd, (W - 316 - 40, 150))
b.paste(ins, (W - 300 - 48, 158), mask)
bottom_fade(b, h=320, a=200)
tag = ImageFont.truetype(GOTHIC, 34)
db = ImageDraw.Draw(b)
tw = db.textlength('서해 겨울 원투낚시', font=tag)
db.rounded_rectangle([W / 2 - tw / 2 - 22, H - 232, W / 2 + tw / 2 + 22, H - 178], radius=27, fill=ORANGE)
db.text((W / 2, H - 205), '서해 겨울 원투낚시', font=tag, fill=WHITE, anchor='mm')
outlined(b, (W / 2, H - 52), [('이거 ', WHITE), ('뭐 걸린 거임??', YELLOW)], 108, stroke=11)

# ── C: upgraded split (diagonal accent, two-line title) ──
c = Image.new('RGBA', (W, H))
c.alpha_composite(cover(back, 720, H, cx=0.5, cy=0.42).convert('RGBA'), (0, 0))
right = Image.new('RGBA', (W, H), (0, 0, 0, 0))
right.paste(cover(fish, 760, H, cx=0.58, cy=0.45, zoom=1.45), (520, 0))
m = Image.new('L', (W, H), 0)
ImageDraw.Draw(m).polygon([(700, 0), (W, 0), (W, H), (560, H)], fill=255)
right.putalpha(m)
c.alpha_composite(right)
ImageDraw.Draw(c).line([(700, 0), (560, H)], fill=ORANGE, width=14)
bottom_fade(c, h=330, a=200)
tag = ImageFont.truetype(GOTHIC, 34)
dd = ImageDraw.Draw(c)
tw = dd.textlength('헬스인의 단백질 자급자족', font=tag)
dd.rounded_rectangle([W / 2 - tw / 2 - 22, H - 232, W / 2 + tw / 2 + 22, H - 178], radius=27, fill=ORANGE)
dd.text((W / 2, H - 205), '헬스인의 단백질 자급자족', font=tag, fill=WHITE, anchor='mm')
outlined(c, (W / 2, H - 52), [('겨울 ', WHITE), ('감성돔', YELLOW), (' 잡았다', WHITE)], 112, stroke=11)

# ── B2: the user's pick — bent rod + mosaic fish in a circle, blue tag, 3 titles ──
SEA = (22, 112, 205)


def mosaic_circle(img, d, block=16):
    """Pixelated circle crop of the fish so viewers can't tell what it is."""
    sq = cover(img, d, d, cx=0.62, cy=0.44, zoom=1.75)
    small = sq.resize((d // block, d // block), Image.BILINEAR)
    pix = small.resize((d, d), Image.NEAREST)
    m = Image.new('L', (d, d), 0)
    ImageDraw.Draw(m).ellipse([0, 0, d - 1, d - 1], fill=255)
    return pix, m


def b2(title):
    t = Image.new('RGBA', (W, H))
    t.paste(cover(rod, W, H, cx=0.42, cy=0.45, zoom=1.12), (0, 0))
    dr = ImageDraw.Draw(t)
    tip = (560, 92)
    dr.ellipse([tip[0] - 78, tip[1] - 62, tip[0] + 78, tip[1] + 62], outline=(255, 30, 30), width=11)
    D_ = 300
    cx, cy = W - 210, 250
    sh = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([cx - D_ / 2 - 6, cy - D_ / 2 + 6, cx + D_ / 2 + 14, cy + D_ / 2 + 26], fill=(0, 0, 0, 150))
    t.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))
    dr = ImageDraw.Draw(t)
    dr.ellipse([cx - D_ / 2 - 9, cy - D_ / 2 - 9, cx + D_ / 2 + 9, cy + D_ / 2 + 9], fill=WHITE)
    pix, m = mosaic_circle(fish, D_, block=23)
    t.paste(pix, (int(cx - D_ / 2), int(cy - D_ / 2)), m)
    outlined(t, (cx + 92, cy + 132), [('?', YELLOW)], 150, stroke=10)
    bottom_fade(t, h=320, a=200)
    tag = ImageFont.truetype(GOTHIC, 34)
    dt = ImageDraw.Draw(t)
    tw = dt.textlength('헬스인의 단백질 자급자족', font=tag)
    ty = H - 178                                                   # tag centre (lowered, just above the title)
    dt.rounded_rectangle([W / 2 - tw / 2 - 22, ty - 27, W / 2 + tw / 2 + 22, ty + 27], radius=27, fill=SEA)
    dt.text((W / 2, ty), '헬스인의 단백질 자급자족', font=tag, fill=WHITE, anchor='mm')
    size = 104
    while ImageDraw.Draw(t).textlength(''.join(p for p, _ in title), font=ImageFont.truetype(BHS, size)) > W - 120:
        size -= 4
    outlined(t, (W / 2, H - 52), title, size, stroke=11)
    return t


B2 = {
    'thumb_B2_1': [('서해 루어낚시 중 ', WHITE), ('잡힌 고기?', YELLOW)],
    'thumb_B2_2': [('서해 루어낚시에 ', WHITE), ('찾아온 손님', YELLOW)],
    'thumb_B2_3': [('서해에서 루어로 ', WHITE), ('이게 잡힌다고?', YELLOW)],
}

PROJ.mkdir(parents=True, exist_ok=True)
for name, title in B2.items():
    b2(title).convert('RGB').save(PROJ / f'{name}.jpg', quality=92)
    print(PROJ / f'{name}.jpg')
for name, img in (('thumb_A_channel', a), ('thumb_B_curiosity', b), ('thumb_C_upgrade', c)):
    img.convert('RGB').save(PROJ / f'{name}.jpg', quality=92)
    print(PROJ / f'{name}.jpg')
