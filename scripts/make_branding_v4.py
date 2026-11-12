"""Channel branding previews v4 — transition A (ivory) and ending A (black), the user's picks.

Changes from v3:
- A small YouTube icon (red rounded rectangle with a white play triangle) pops in next to '의태'
  in the transition, and sits next to the small '의태.' logo on the end screen.
- Ending A in a black theme with white text (same layout, cursor clicks and sounds as v3).
- (v5 output) bigger YouTube icon in the transition; end-screen logo is '의태' + YouTube icon with no dot.
Output: branding/previews/<job>_v5_<theme>.mp4 (1920x1080, 30fps). The user approved these on 2026-11-11;
copies live in branding/final/ (transition_A_ivory.mp4, ending_A_dark.mp4). Not added to CapCut.

usage: python -I make_branding_v4.py <repo_root> [job_theme ...]   e.g. transition_A_ivory ending_A_dark
"""
import math
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(sys.argv[1])
CLEAN = '--clean' in sys.argv          # CapCut versions: start/end on black instead of the sample scene frames
ONLY = set(a for a in sys.argv[2:] if a != '--clean')
W, H, FPS, S = 1920, 1080, 30, 2                     # S = supersampling factor
WW, HH = W * S, H * S
WHITE, ACCENT = (255, 255, 255), (255, 74, 43)
FONTS, OUT, FR, SFX = ROOT / 'fonts', ROOT / 'branding' / 'previews', ROOT / 'branding' / 'frames', ROOT / 'sfx'
FF = next((Path.home() / 'AppData/Local/Microsoft/WinGet/Packages').rglob('ffmpeg.exe'))
IC = dict(thumb=0xE8DC, bell=0xE7F4, person=0xE7FD, add=0xE7FE, play=0xE1C4, check=0xE5CA)

THEMES = {
    # BG background, CARD card/button, INK main text, GRAY secondary text, LINE hairline, SOFT pressed button,
    # PH placeholder icons, SHA shadow strength multiplier
    'ivory':  dict(BG=(242, 238, 230), CARD=(250, 248, 243), INK=(44, 41, 38), GRAY=(134, 126, 116), LINE=(222, 215, 203),
                   SOFT=(229, 223, 212), PH=(222, 215, 203), SHA=1.0),
    'greige': dict(BG=(230, 228, 224), CARD=(241, 240, 237), INK=(42, 42, 42), GRAY=(122, 120, 116), LINE=(212, 209, 203),
                   SOFT=(218, 215, 209), PH=(212, 209, 203), SHA=1.0),
    'dark':   dict(BG=(18, 18, 19), CARD=(32, 32, 34), INK=(244, 242, 238), GRAY=(150, 148, 144), LINE=(56, 56, 58),
                   SOFT=(52, 52, 55), PH=(92, 92, 96), SHA=3.0),
}
BG = CARD = INK = GRAY = LINE = SOFT = PH = None
SHA = 1.0
BG_IMG = None
YT_RED = (255, 0, 0)


def set_theme(name):
    global BG, CARD, INK, GRAY, LINE, SOFT, PH, SHA, BG_IMG
    th = THEMES[name]
    BG, CARD, INK, GRAY, LINE, SOFT, PH, SHA = (th[k] for k in ('BG', 'CARD', 'INK', 'GRAY', 'LINE', 'SOFT', 'PH', 'SHA'))
    BG_IMG = Image.new('RGB', (WW, HH), BG)


@lru_cache(None)
def font(weight, size):
    return ImageFont.truetype(str(FONTS / f'GothicA1-{weight}.ttf'), int(size * S))


@lru_cache(None)
def icon_font(size, filled=False):
    name = 'MaterialIcons-Regular.ttf' if filled else 'MaterialIconsOutlined-Regular.otf'
    return ImageFont.truetype(str(FONTS / name), int(size * S))


# ── easing ──
def clamp(x): return max(0.0, min(1.0, x))
def seg(t, a, b): return clamp((t - a) / (b - a)) if b > a else float(t >= a)
def out_cubic(x): return 1 - (1 - x) ** 3
def out_quint(x): return 1 - (1 - x) ** 5
def in_out(x): return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2
def back(x, c1=1.70158): c3 = c1 + 1; return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


# ── images ──
def load(name):
    return Image.open(FR / name).convert('RGB').resize((WW, HH), Image.LANCZOS)


def zoomed(img, z):
    if abs(z - 1) < 1e-3:
        return img
    w, h = WW / z, HH / z
    box = ((WW - w) / 2, (HH - h) / 2, (WW + w) / 2, (HH + h) / 2)
    return img.resize((WW, HH), Image.BILINEAR, box=box)


def blend(a, b, k):
    return a if k <= 0 else (b if k >= 1 else Image.blend(a, b, k))


def blank():
    return Image.new('RGBA', (WW, HH), (0, 0, 0, 0))


def finish(img):
    return img.convert('RGB').resize((W, H), Image.LANCZOS)


# ── drawing helpers (all coordinates in 1920x1080 space) ──
def P(*v):
    return [x * S for x in v]


_MEASURE = ImageDraw.Draw(Image.new('RGBA', (8, 8)))


def tlen(s, f):
    return _MEASURE.textlength(s, font=f) / S


def text(lay, s, f, x, y, fill, a=1.0, anchor='mm', tracking=0):
    if a <= 0:
        return
    d = ImageDraw.Draw(lay)
    col = fill + (int(255 * clamp(a)),)
    if not tracking:
        d.text((x * S, y * S), s, font=f, fill=col, anchor=anchor)
        return
    ws = [d.textlength(ch, font=f) for ch in s]
    total = sum(ws) + tracking * S * (len(s) - 1)
    cx = x * S - (total / 2 if anchor[0] == 'm' else 0)
    for ch, w in zip(s, ws):
        d.text((cx, y * S), ch, font=f, fill=col, anchor='l' + anchor[1])
        cx += w + tracking * S


def letters(lay, s, f, x, y, fill, t, start, step=0.07, dur=0.45, rise=38, exit_at=None, anchor='m'):
    """Per-letter reveal: each glyph rises and fades in, staggered; optional staggered exit upward."""
    d = ImageDraw.Draw(lay)
    ws = [d.textlength(ch, font=f) for ch in s]
    total = sum(ws)
    cx = x * S - (total / 2 if anchor == 'm' else 0)
    for i, (ch, w) in enumerate(zip(s, ws)):
        k = out_quint(seg(t, start + i * step, start + i * step + dur))
        dy = rise * (1 - k)
        a = k
        if exit_at is not None:
            e = in_out(seg(t, exit_at + i * 0.05, exit_at + i * 0.05 + 0.28))
            dy -= 30 * e
            a *= 1 - e
        if a > 0 and ch.strip():
            d.text((cx, (y + dy) * S), ch, font=f, fill=fill + (int(255 * a),), anchor='lm')
        cx += w


def icon(lay, name, x, y, size, fill, a=1.0, filled=False, rot=0.0):
    if a <= 0:
        return
    f = icon_font(size, filled)
    if not rot:
        ImageDraw.Draw(lay).text((x * S, y * S), chr(IC[name]), font=f, fill=fill + (int(255 * a),), anchor='mm')
        return
    n = int(size * S * 1.6)
    g = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    ImageDraw.Draw(g).text((n / 2, n / 2), chr(IC[name]), font=f, fill=fill + (int(255 * a),), anchor='mm')
    g = g.rotate(rot, resample=Image.BICUBIC, center=(n / 2, n * 0.18))       # swing from the top, like a bell
    lay.alpha_composite(g, (int(x * S - n / 2), int(y * S - n / 2)))


def shadow(lay, box, radius, a=0.10, blur=22, dy=12, ellipse=False):
    """Soft drop shadow drawn on a local patch (cheap)."""
    a = min(0.6, a * SHA)
    if a <= 0:
        return
    x0, y0, x1, y1 = [v * S for v in box]
    m = int(blur * S * 2.5)
    pw, ph = int(x1 - x0) + 2 * m, int(y1 - y0) + 2 * m
    patch = Image.new('RGBA', (pw, ph), (0, 0, 0, 0))
    dd = ImageDraw.Draw(patch)
    shape = [m, m, m + (x1 - x0), m + (y1 - y0)]
    if ellipse:
        dd.ellipse(shape, fill=(40, 30, 20, int(255 * a)))
    else:
        dd.rounded_rectangle(shape, radius=radius * S, fill=(40, 30, 20, int(255 * a)))
    patch = patch.filter(ImageFilter.GaussianBlur(blur * S))
    lay.alpha_composite(patch, (int(x0 - m), int(y0 - m + dy * S)))


@lru_cache(None)
def _scaled(path, size):
    return ImageFont.truetype(path, size)


def font_from(f, sc):
    return f if abs(sc - 1) < 1e-3 else _scaled(f.path, max(8, int(f.size * sc)))


def pill_w(label, f, ic, h, pad):
    return tlen(label, f) + ((h * 0.42 + 14) if ic else 0) + pad * 2


def pill(lay, cx, cy, label, f, style, a=1.0, sc=1.0, ic=None, ic_filled=False, ic_rot=0.0, h=86, pad=44, shadow_a=0.08):
    """style: 'outline' | 'ink' | 'accent' | 'soft'. Returns the box in 1920 space."""
    if a <= 0:
        return None
    d = ImageDraw.Draw(lay)
    tw = tlen(label, f)
    iw = (h * 0.42 + 14) if ic else 0
    w, hh = (tw + iw + pad * 2) * sc, h * sc
    box = (cx - w / 2, cy - hh / 2, cx + w / 2, cy + hh / 2)
    if shadow_a:
        shadow(lay, box, hh / 2, a=shadow_a * a, blur=14, dy=8)
    fill, fg = {'outline': (CARD, INK), 'ink': (INK, CARD), 'accent': (ACCENT, WHITE), 'soft': (SOFT, INK)}[style]
    al = int(255 * clamp(a))
    if style == 'outline':
        d.rounded_rectangle(P(*box), radius=hh / 2 * S, fill=fill + (al,), outline=INK + (al,), width=int(3 * S * sc))
    else:
        d.rounded_rectangle(P(*box), radius=hh / 2 * S, fill=fill + (al,))
    x = cx - (tw + iw) * sc / 2
    if ic:
        isz = h * 0.42 * sc
        icon(lay, ic, x + isz / 2, cy, isz, fg, a, filled=ic_filled, rot=ic_rot)
        x += iw * sc
    d.text((x * S, cy * S), label, font=font_from(f, sc), fill=fg + (al,), anchor='lm')
    return box


def ripple(lay, x, y, p, color=ACCENT, maxr=120, width=3):
    if not 0 < p < 1:
        return
    r = maxr * out_cubic(p)
    a = int(255 * (1 - p) * 0.8)
    ImageDraw.Draw(lay).ellipse(P(x - r, y - r, x + r, y + r), outline=color + (a,), width=int(width * S))


def cursor(lay, x, y, a=1.0, press=0.0):
    if a <= 0:
        return
    s = (1.0 - 0.12 * press) * 1.35
    pts = [(0, 0), (0, 44), (11, 33), (19, 52), (27, 48), (19, 30), (34, 30)]
    pts = [((x + px * s) * S, (y + py * s) * S) for px, py in pts]
    shadow(lay, (x, y, x + 34 * s, y + 52 * s), 6, a=0.14 * a, blur=6, dy=4)
    ImageDraw.Draw(lay).polygon(pts, fill=WHITE + (int(255 * a),), outline=(17, 17, 17, int(255 * a)), width=int(3 * S))


def yt_icon(lay, cx, cy, h, a=1.0, k=1.0):
    """YouTube icon: red rounded rectangle (about 1.42:1) with a white play triangle. k scales it (pop-in)."""
    if a <= 0 or k <= 0:
        return
    h *= k
    w = h * 1.42
    al = int(255 * clamp(a))
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle(P(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), radius=h * 0.28 * S, fill=YT_RED + (al,))
    th = h * 0.42
    tx = cx - th * 0.36
    d.polygon([((tx) * S, (cy - th / 2) * S), ((tx) * S, (cy + th / 2) * S), ((tx + th * 0.87) * S, cy * S)], fill=WHITE + (al,))


def logo(lay, x, y, size, a=1.0, dot_k=1.0, yt_k=None):
    """'의태.' wordmark with the orange dot. With yt_k (the icon's pop-in scale) it is '의태' + YouTube icon, no dot."""
    f = font('Black', size)
    d = ImageDraw.Draw(lay)
    w = d.textlength('의태', font=f) / S
    text(lay, '의태', f, x - 8, y, INK, a)
    if yt_k is not None:
        yh = size * 0.74
        yt_icon(lay, x - 8 + w / 2 + size * 0.2 + yh * 0.71, y - size * 0.02, yh, a, yt_k)
        return
    r = size * 0.075 * dot_k
    cx, cy = x - 8 + w / 2 + size * 0.16, y + size * 0.3
    if r > 0 and a > 0:
        d.ellipse(P(cx - r, cy - r, cx + r, cy + r), fill=ACCENT + (int(255 * a),))


# ── scenes ──
if CLEAN:
    PREV = NEXT = LAST = Image.new('RGB', (WW, HH), (0, 0, 0))
else:
    PREV, NEXT, LAST = load('prev_gym.png'), load('next_fish.png'), load('last_scene.png')


def tA(t):
    """A 미니멀 워드마크 (부드러운 종이 톤): 한 글자씩 올라오는 '의태', 밑줄과 점, 자간이 좁혀지는 EUITAE VLOG."""
    if t < 1.0:
        base = blend(zoomed(PREV, 1 + 0.05 * out_cubic(seg(t, 0, 0.45))), BG_IMG, out_cubic(seg(t, 0, 0.4)))
    else:
        base = blend(BG_IMG, zoomed(NEXT, 1.06 - 0.06 * out_cubic(seg(t, 2.1, 2.6))), in_out(seg(t, 2.1, 2.55)))
    lay = blank()
    fl = font('Black', 180)
    wl, yh, gap = tlen('의태', fl), 86, 34
    left = W / 2 - (wl + gap + yh * 1.42) / 2                     # centre '의태' + YouTube icon as one group
    letters(lay, '의태', fl, left + wl / 2, H / 2 - 40, INK, t, 0.32, step=0.09, exit_at=1.85)
    yk = back(seg(t, 0.55, 0.85)) * (1 - in_out(seg(t, 1.95, 2.15)))
    yt_icon(lay, left + wl + gap + yh * 0.71, H / 2 - 54, yh, seg(t, 0.55, 0.68) * (1 - seg(t, 1.95, 2.15)), yk)
    d = ImageDraw.Draw(lay)
    x0 = W / 2 - 120
    grow = out_cubic(seg(t, 0.62, 1.0)) * 240
    shrink = in_out(seg(t, 1.85, 2.1)) * 240
    if grow - shrink > 1:
        d.rounded_rectangle(P(x0 + shrink, H / 2 + 74, x0 + grow, H / 2 + 80), radius=3 * S, fill=ACCENT + (255,))
    dk = back(seg(t, 0.95, 1.2)) * (1 - seg(t, 1.85, 2.0))
    if dk > 0:
        r = 7 * dk
        d.ellipse(P(x0 + 252 - r, H / 2 + 77 - r, x0 + 252 + r, H / 2 + 77 + r), fill=ACCENT + (255,))
    tr = 40 - 26 * out_cubic(seg(t, 0.8, 1.45))
    text(lay, 'EUITAE  VLOG', font('Medium', 30), W / 2, H / 2 + 132, GRAY, seg(t, 0.8, 1.2) * (1 - seg(t, 1.8, 2.0)), tracking=tr)
    # small 좋아요 / 구독 / 알림 설정 row under the English name (v6)
    fr, rh, rp, gap = font('Bold', 24), 50, 22, 16
    row = [('좋아요', 'outline', 'thumb'), ('구독', 'accent', 'add'), ('알림 설정', 'outline', 'bell')]
    ws = [pill_w(lab, fr, ic, rh, rp) for lab, _, ic in row]
    x = W / 2 - (sum(ws) + gap * (len(ws) - 1)) / 2
    out_k = 1 - seg(t, 1.8, 2.0)
    for i, ((lab, st, ic), w) in enumerate(zip(row, ws)):
        p = seg(t, 1.0 + i * 0.08, 1.3 + i * 0.08)
        if p > 0 and out_k > 0:
            pill(lay, x + w / 2, H / 2 + 205, lab, fr, st, min(1, p * 2) * out_k, back(p) if p < 1 else 1.0, ic=ic,
                 h=rh, pad=rp, shadow_a=0.10 if st == 'accent' else 0)
        x += w + gap
    base = base.convert('RGBA')
    base.alpha_composite(lay, source=(0, 30 * S))                  # lift the whole group 30px to keep it centred
    return finish(base)


# ending A: button row + cursor
ROW_Y, ROW_H, ROW_PAD, ROW_X0, ROW_GAP = 664, 76, 32, 150, 22
C_LIKE, C_SUB, C_BELL = 3.2, 4.3, 5.4


def row_slots():
    """Fixed slot centres so the row doesn't shift when a label changes (구독 -> 구독중)."""
    fb = font('Bold', 32)
    widths = [max(pill_w('좋아요', fb, 'thumb', ROW_H, ROW_PAD), 0),
              max(pill_w('구독', fb, 'add', ROW_H, ROW_PAD), pill_w('구독중', fb, 'check', ROW_H, ROW_PAD)),
              pill_w('알림 설정', fb, 'bell', ROW_H, ROW_PAD)]
    xs, x = [], ROW_X0
    for w in widths:
        xs.append(x + w / 2)
        x += w + ROW_GAP
    return xs


def eA(t):
    """A 에디토리얼 + 커서: 인사말, 좋아요·구독·알림 버튼을 커서가 차례로 누르고, 오른쪽에 '다음 영상'·'구독' 자리, 아래 남은 시간 막대."""
    base = blend(zoomed(LAST, 1 + 0.04 * seg(t, 0, 0.6)), BG_IMG, out_cubic(seg(t, 0, 0.6))).convert('RGBA')
    lay = blank()
    d = ImageDraw.Draw(lay)
    logo(lay, 206, 150, 46, a=seg(t, 0.5, 0.9), dot_k=back(seg(t, 0.7, 1.0)), yt_k=back(seg(t, 0.85, 1.15)))
    ka = out_cubic(seg(t, 0.6, 1.0))
    d.rounded_rectangle(P(150, 318 + 40 * (1 - ka), 158, 370), radius=4 * S, fill=ACCENT + (int(255 * ka),))
    k = out_quint(seg(t, 0.7, 1.15))
    text(lay, '오늘도 끝까지 봐주셔서', font('Bold', 60), 150, 420 + 26 * (1 - k), INK, k, anchor='lm')
    letters(lay, '감사합니다', font('Black', 108), 146, 522, INK, t, 0.85, step=0.06, anchor='l')

    # buttons: appear one by one, then get clicked left to right
    fb = font('Bold', 32)
    like_x, sub_x, bell_x = row_slots()
    def press(c): return 1 - 0.07 * math.sin(math.pi * seg(t, c - 0.05, c + 0.2))
    def appear(i): return out_cubic(seg(t, 1.35 + i * 0.15, 1.75 + i * 0.15))
    def ry(i): return ROW_Y + 16 * (1 - appear(i))
    liked, subbed, belled = t >= C_LIKE + 0.05, t >= C_SUB + 0.05, t >= C_BELL + 0.05
    pill(lay, like_x, ry(0), '좋아요', fb, 'ink' if liked else 'outline', appear(0), press(C_LIKE), ic='thumb', ic_filled=liked,
         h=ROW_H, pad=ROW_PAD, shadow_a=0.07)
    if subbed:
        pill(lay, sub_x, ry(1), '구독중', fb, 'soft', appear(1), press(C_SUB), ic='check', h=ROW_H, pad=ROW_PAD, shadow_a=0.05)
    else:
        pill(lay, sub_x, ry(1), '구독', fb, 'accent', appear(1), press(C_SUB), ic='add', h=ROW_H, pad=ROW_PAD, shadow_a=0.14)
    sw = seg(t, C_BELL, C_BELL + 1.1)
    rot = 22 * math.sin(sw * math.pi * 6) * (1 - sw) if 0 < sw < 1 else 0
    pill(lay, bell_x, ry(2), '알림 설정', fb, 'ink' if belled else 'outline', appear(2), press(C_BELL), ic='bell',
         ic_filled=belled, ic_rot=rot, h=ROW_H, pad=ROW_PAD, shadow_a=0.07)
    for c, x in ((C_LIKE, like_x), (C_SUB, sub_x), (C_BELL, bell_x)):
        ripple(lay, x, ROW_Y, seg(t, c, c + 0.6), color=ACCENT, maxr=130)
    kpl = seg(t, C_LIKE + 0.05, C_LIKE + 1.0)
    if 0 < kpl < 1:
        text(lay, '+1', font('Black', 40), like_x + 30, ROW_Y - 62 - 60 * out_cubic(kpl), ACCENT, 1 - kpl ** 2)
    text(lay, '여러분의 좋아요와 구독이 큰 힘이 됩니다', font('Light', 32), 150, 760, GRAY, out_cubic(seg(t, 1.8, 2.2)), anchor='lm')

    # right column: end-screen placeholders (YouTube end-screen elements go here)
    kc = out_cubic(seg(t, 1.0, 1.5))
    sc = 0.96 + 0.04 * kc
    cx, cy, cw, ch = 1410, 427, 700 * sc, 394 * sc
    box = (cx - cw / 2, cy - ch / 2 + 20 * (1 - kc), cx + cw / 2, cy + ch / 2 + 20 * (1 - kc))
    shadow(lay, box, 24, a=0.09 * kc, blur=26, dy=14)
    d.rounded_rectangle(P(*box), radius=24 * S, fill=CARD + (int(255 * kc),), outline=LINE + (int(255 * kc),), width=2 * S)
    icon(lay, 'play', cx, cy - 18 + 20 * (1 - kc), 96, PH, kc)
    text(lay, '다음 영상', font('Medium', 30), cx, cy + 66 + 20 * (1 - kc), GRAY, kc)
    kk = out_cubic(seg(t, 1.25, 1.75))
    c, r = (1410, 830), 118 * (0.96 + 0.04 * kk)
    shadow(lay, (c[0] - r, c[1] - r, c[0] + r, c[1] + r), 0, a=0.09 * kk, blur=24, dy=12, ellipse=True)
    d.ellipse(P(c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=CARD + (int(255 * kk),), outline=LINE + (int(255 * kk),), width=2 * S)
    icon(lay, 'add', c[0], c[1] - 16, 64, PH, kk)
    text(lay, '구독', font('Medium', 28), c[0], c[1] + 50, GRAY, kk)

    kb = seg(t, 0.6, 1.0)
    d.rectangle(P(0, H - 6, W, H), fill=LINE + (int(255 * kb),))
    d.rectangle(P(0, H - 6, W * clamp(t / 10), H), fill=ACCENT + (int(255 * kb),))

    # cursor: comes in from below, clicks 좋아요 -> 구독 -> 알림 설정, then drifts away
    if 2.3 <= t < 6.7:
        tip = lambda x: (x + 10, ROW_Y + 8)
        pts = [(2.3, (720, 1010)), (3.1, tip(like_x)), (3.6, tip(like_x)), (4.2, tip(sub_x)), (4.7, tip(sub_x)),
               (5.3, tip(bell_x)), (5.85, tip(bell_x)), (6.7, (bell_x + 300, ROW_Y + 330))]
        x, y = pts[-1][1]
        for (ta, pa), (tb, pb) in zip(pts, pts[1:]):
            if ta <= t < tb:
                k = in_out(seg(t, ta, tb))
                x, y = pa[0] + (pb[0] - pa[0]) * k, pa[1] + (pb[1] - pa[1]) * k
                break
        pr = sum(math.sin(math.pi * seg(t, c - 0.05, c + 0.2)) for c in (C_LIKE, C_SUB, C_BELL))
        cursor(lay, x, y, a=seg(t, 2.3, 2.5) * (1 - seg(t, 6.3, 6.7)), press=pr)
    base.alpha_composite(lay)
    return finish(base)


JOBS = {
    'transition_A': (tA, 2.6, [('whoosh', 0.0, -10), ('click', 0.62, -14), ('pop', 0.95, -16), ('tick', 0.58, -16),
                               ('tick', 1.08, -18)]),
    'ending_A': (eA, 10.0, [('ding', 0.85, -16), ('whoosh', 2.3, -22),
                            ('click', C_LIKE, -6), ('pop', C_LIKE + 0.08, -12),
                            ('click', C_SUB, -6), ('tick', C_SUB + 0.1, -12),
                            ('click', C_BELL, -6), ('ding', C_BELL + 0.05, -14)]),
}


def render(name, fn, dur, sounds):
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f'{name}.mp4'
    cmd = [str(FF), '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-']
    fc, labels = [], []
    for i, (snd, at, db) in enumerate(sounds):
        cmd += ['-i', str(SFX / f'{snd}.wav')]
        ms = int(at * 1000)
        fc.append(f'[{i + 1}:a]adelay={ms}|{ms},volume={db}dB[s{i}]')
        labels.append(f'[s{i}]')
    fc.append(f'anullsrc=r=48000:cl=stereo,atrim=0:{dur}[sil]')
    fc.append(''.join(labels) + f'[sil]amix=inputs={len(labels) + 1}:normalize=0,atrim=0:{dur}[a]')
    cmd += ['-filter_complex', ';'.join(fc), '-map', '0:v', '-map', '[a]', '-t', str(dur),
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(round(dur * FPS))):
        p.stdin.write(fn(i / FPS).tobytes())
    p.stdin.close()
    p.wait()
    print(f'{name}: {dur}s -> {out}', flush=True)


PICKS = [('transition_A', 'ivory'), ('ending_A', 'dark')]

for job, theme in PICKS:
    if ONLY and f'{job}_{theme}' not in ONLY:
        continue
    set_theme(theme)
    fn, dur, sounds = JOBS[job]
    if CLEAN:
        OUT = ROOT / 'branding' / 'final'
        render(f'{job}_{theme}_capcut', fn, dur, sounds)
    else:
        render(f'{job}_v6_{theme}', fn, dur, sounds)
