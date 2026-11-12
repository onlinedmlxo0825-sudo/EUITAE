"""Channel branding previews v2 — same 3 transitions + 3 end screens, polished.

Upgrades over v1: 2x supersampled drawing (smooth edges), per-letter reveals, gentle zoom on the
scenes behind, soft shadows, Material icons (Apache-2.0), click ripples, an end-screen countdown bar.
Output: branding/previews/*_v2.mp4 (1920x1080, 30fps). Not added to CapCut.

usage: python -I make_branding_v2.py <repo_root> [name ...]
"""
import math
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(sys.argv[1])
ONLY = set(sys.argv[2:])
W, H, FPS, S = 1920, 1080, 30, 2                     # S = supersampling factor
WW, HH = W * S, H * S
WHITE, INK, GRAY, LIGHT, LINE, ACCENT = (255, 255, 255), (17, 17, 17), (130, 130, 130), (246, 246, 246), (228, 228, 228), (255, 74, 43)
FONTS, OUT, FR, SFX = ROOT / 'fonts', ROOT / 'branding' / 'previews', ROOT / 'branding' / 'frames', ROOT / 'sfx'
FF = next((Path.home() / 'AppData/Local/Microsoft/WinGet/Packages').rglob('ffmpeg.exe'))
IC = dict(thumb=0xE8DC, bell=0xE7F4, person=0xE7FD, add=0xE7FE, play=0xE1C4, check=0xE5CA)


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


def bounce(x):
    n, d = 7.5625, 2.75
    if x < 1 / d: return n * x * x
    if x < 2 / d: x -= 1.5 / d; return n * x * x + 0.75
    if x < 2.5 / d: x -= 2.25 / d; return n * x * x + 0.9375
    x -= 2.625 / d; return n * x * x + 0.984375


# ── images ──
def load(name):
    return Image.open(FR / name).convert('RGB').resize((WW, HH), Image.LANCZOS)


def zoomed(img, z):
    """Centre zoom (z >= 1) of a canvas-sized image."""
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
    if a <= 0:
        return
    x0, y0, x1, y1 = [v * S for v in box]
    m = int(blur * S * 2.5)
    pw, ph = int(x1 - x0) + 2 * m, int(y1 - y0) + 2 * m
    patch = Image.new('RGBA', (pw, ph), (0, 0, 0, 0))
    dd = ImageDraw.Draw(patch)
    shape = [m, m, m + (x1 - x0), m + (y1 - y0)]
    if ellipse:
        dd.ellipse(shape, fill=(0, 0, 0, int(255 * a)))
    else:
        dd.rounded_rectangle(shape, radius=radius * S, fill=(0, 0, 0, int(255 * a)))
    patch = patch.filter(ImageFilter.GaussianBlur(blur * S))
    lay.alpha_composite(patch, (int(x0 - m), int(y0 - m + dy * S)))


def pill(lay, cx, cy, label, f, style, a=1.0, sc=1.0, ic=None, ic_filled=False, h=86, pad=44, shadow_a=0.08):
    """style: 'outline' | 'ink' | 'accent' | 'soft'. Returns the box in 1920 space."""
    if a <= 0:
        return None
    d = ImageDraw.Draw(lay)
    tw = d.textlength(label, font=f) / S
    iw = (h * 0.42 + 14) if ic else 0
    w, hh = (tw + iw + pad * 2) * sc, h * sc
    box = (cx - w / 2, cy - hh / 2, cx + w / 2, cy + hh / 2)
    if shadow_a and style != 'outline':
        shadow(lay, box, hh / 2, a=shadow_a * a, blur=14, dy=8)
    fill, fg, outline = {'outline': (None, INK, INK), 'ink': (INK, WHITE, None), 'accent': (ACCENT, WHITE, None),
                         'soft': ((236, 236, 236), (70, 70, 70), None)}[style]
    al = int(255 * clamp(a))
    if style == 'outline':
        d.rounded_rectangle(P(*box), radius=hh / 2 * S, fill=WHITE + (al,), outline=outline + (al,), width=int(3 * S * sc))
    else:
        d.rounded_rectangle(P(*box), radius=hh / 2 * S, fill=fill + (al,))
    x = cx - (tw + iw) * sc / 2
    if ic:
        isz = h * 0.42 * sc
        icon(lay, ic, x + isz / 2, cy, isz, fg, a, filled=ic_filled)
        x += iw * sc
    fs = font_from(f, sc)
    d.text((x * S, cy * S), label, font=fs, fill=fg + (al,), anchor='lm')
    return box


@lru_cache(None)
def _scaled(path, size):
    return ImageFont.truetype(path, size)


def font_from(f, sc):
    return f if abs(sc - 1) < 1e-3 else _scaled(f.path, max(8, int(f.size * sc)))


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
    shadow(lay, (x, y, x + 34 * s, y + 52 * s), 6, a=0.12 * a, blur=6, dy=4)
    ImageDraw.Draw(lay).polygon(pts, fill=WHITE + (int(255 * a),), outline=INK + (int(255 * a),), width=int(3 * S))


def logo(lay, x, y, size, a=1.0, dot_k=1.0):
    """'의태.' wordmark with the orange dot."""
    f = font('Black', size)
    d = ImageDraw.Draw(lay)
    w = d.textlength('의태', font=f) / S
    text(lay, '의태', f, x - 8, y, INK, a)
    r = size * 0.075 * dot_k
    cx, cy = x - 8 + w / 2 + size * 0.16, y + size * 0.3
    if r > 0 and a > 0:
        d.ellipse(P(cx - r, cy - r, cx + r, cy + r), fill=ACCENT + (int(255 * a),))


# ── scenes ──
PREV, NEXT, LAST = load('prev_gym.png'), load('next_fish.png'), load('last_scene.png')
WHITE_IMG = Image.new('RGB', (WW, HH), WHITE)
FROST = Image.blend(LAST.resize((W // 4, H // 4)).filter(ImageFilter.GaussianBlur(6)).resize((WW, HH), Image.BICUBIC), WHITE_IMG, 0.72)


def tA(t):
    """A+ 미니멀 워드마크: 한 글자씩 올라오는 '의태', 왼쪽부터 그어지는 밑줄과 점, 자간이 좁혀지며 나타나는 EUITAE VLOG."""
    if t < 1.0:
        base = blend(zoomed(PREV, 1 + 0.05 * out_cubic(seg(t, 0, 0.45))), WHITE_IMG, out_cubic(seg(t, 0, 0.4)))
    else:
        base = blend(WHITE_IMG, zoomed(NEXT, 1.06 - 0.06 * out_cubic(seg(t, 2.1, 2.6))), in_out(seg(t, 2.1, 2.55)))
    lay = blank()
    letters(lay, '의태', font('Black', 180), W / 2, H / 2 - 40, INK, t, 0.32, step=0.09, exit_at=1.85)
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
    base = base.convert('RGBA')
    base.alpha_composite(lay)
    return finish(base)


def tB(t):
    """B+ 더블 슬라이드: 회색 판과 흰 판이 시차를 두고 밀고 들어오고, 로고가 한 박자 늦게 따라온다."""
    under = zoomed(PREV, 1 + 0.03 * seg(t, 0, 0.5)) if t < 1.0 else zoomed(NEXT, 1.05 - 0.05 * out_cubic(seg(t, 1.55, 2.4)))
    frame = under.convert('RGBA')
    if t < 1.55:
        gx = -W + W * in_out(seg(t, 0.0, 0.42))
        wx = -W + W * in_out(seg(t, 0.07, 0.5))
    else:
        wx = W * in_out(seg(t, 1.55, 2.0))
        gx = W * in_out(seg(t, 1.63, 2.08))
    d = ImageDraw.Draw(frame)
    d.rectangle(P(gx, 0, gx + W, H), fill=(238, 238, 238, 255))
    panel = blank()
    pd = ImageDraw.Draw(panel)
    pd.rectangle([0, 0, WW, HH], fill=WHITE + (255,))
    k = out_quint(seg(t, 0.38, 0.85))
    ox = -140 * (1 - k) + (90 * in_out(seg(t, 1.55, 2.0)))
    text(panel, '의태', font('Black', 172), W / 2 + ox, H / 2 - 30, INK, k)
    tr = 46 - 24 * out_cubic(seg(t, 0.55, 1.1))
    text(panel, 'EUITAE', font('Bold', 34), W / 2 + ox * 0.6, H / 2 + 96, ACCENT, seg(t, 0.55, 0.95), tracking=tr)
    frame.alpha_composite(panel, (int(wx * S), 0))
    edge = (wx + W) if t < 1.55 else wx
    d.rectangle(P(edge - 12, 0, edge, H), fill=ACCENT + (255,))
    return finish(frame)


def tC(t):
    """C+ 점 아이리스: 원이 퍼져 덮고, 주황 점이 떨어져 튕기며 물결이 번지고, 화면이 그 점으로 모여 다음 장면이 열린다."""
    diag = math.hypot(W, H) / 2 + 40
    dot = (W / 2 + 158, H / 2 + 50)
    if t < 1.75:
        r = diag * out_cubic(seg(t, 0, 0.5))
        cx, cy = W / 2, H / 2
        frame = zoomed(PREV, 1 + 0.04 * seg(t, 0, 0.5)).convert('RGBA')
    else:
        k = in_out(seg(t, 1.75, 2.35))
        r = (diag + 260) * (1 - k)
        cx, cy = W / 2 + (dot[0] - W / 2) * k, H / 2 + (dot[1] - H / 2) * k
        frame = zoomed(NEXT, 1.08 - 0.08 * out_cubic(seg(t, 1.75, 2.6))).convert('RGBA')
    lay = blank()
    d = ImageDraw.Draw(lay)
    if r > 0:
        d.ellipse(P(cx - r, cy - r, cx + r, cy + r), fill=WHITE + (255,))
    letters(lay, '의태', font('Black', 164), W / 2 - 24, H / 2 - 12, INK, t, 0.62, step=0.08, exit_at=1.62)
    p = seg(t, 0.48, 0.95)
    if p > 0 and t < 2.5:
        y = dot[1] - 140 * (1 - bounce(p))
        squash = 1 + 0.35 * max(0, math.sin(math.pi * seg(t, 0.68, 0.78)))
        rr = 19 * (1 - seg(t, 2.3, 2.5))
        d.ellipse(P(dot[0] - rr * squash, y - rr / squash, dot[0] + rr * squash, y + rr / squash), fill=ACCENT + (255,))
    for st in (0.8, 0.98):
        ripple(lay, dot[0], dot[1], seg(t, st, st + 0.65), maxr=150, width=2.5)
    frame.alpha_composite(lay)
    return finish(frame)


def eA(t):
    """A+ 에디토리얼: 인사말, 아이콘 줄, 그림자 있는 '다음 영상'·'구독' 자리, 아래 남은 시간 막대."""
    base = blend(zoomed(LAST, 1 + 0.04 * seg(t, 0, 0.6)), WHITE_IMG, out_cubic(seg(t, 0, 0.6))).convert('RGBA')
    lay = blank()
    d = ImageDraw.Draw(lay)
    logo(lay, 206, 150, 46, a=seg(t, 0.5, 0.9), dot_k=back(seg(t, 0.7, 1.0)))
    ka = out_cubic(seg(t, 0.6, 1.0))
    d.rounded_rectangle(P(150, 318 + 40 * (1 - ka), 158, 370), radius=4 * S, fill=ACCENT + (int(255 * ka),))
    k = out_quint(seg(t, 0.7, 1.15))
    text(lay, '오늘도 끝까지 봐주셔서', font('Bold', 60), 150, 420 + 26 * (1 - k), INK, k, anchor='lm')
    letters(lay, '감사합니다', font('Black', 108), 146, 522, INK, t, 0.85, step=0.06, anchor='l')
    for i, (ic, lab) in enumerate([('thumb', '좋아요'), ('add', '구독'), ('bell', '알림 설정')]):
        kk = out_cubic(seg(t, 1.35 + i * 0.15, 1.75 + i * 0.15))
        x = 150 + i * 196
        icon(lay, ic, x + 18, 650 + 14 * (1 - kk), 36, ACCENT, kk)
        text(lay, lab, font('Medium', 32), x + 46, 650 + 14 * (1 - kk), GRAY, kk, anchor='lm')
    text(lay, '여러분의 좋아요와 구독이 큰 힘이 됩니다', font('Light', 32), 150, 730, GRAY, out_cubic(seg(t, 1.8, 2.2)), anchor='lm')
    kc = out_cubic(seg(t, 1.0, 1.5))
    sc = 0.96 + 0.04 * kc
    cx, cy, cw, ch = 1410, 427, 700 * sc, 394 * sc
    box = (cx - cw / 2, cy - ch / 2 + 20 * (1 - kc), cx + cw / 2, cy + ch / 2 + 20 * (1 - kc))
    shadow(lay, box, 24, a=0.10 * kc, blur=26, dy=14)
    d.rounded_rectangle(P(*box), radius=24 * S, fill=WHITE + (int(255 * kc),), outline=LINE + (int(255 * kc),), width=2 * S)
    icon(lay, 'play', cx, cy - 18 + 20 * (1 - kc), 96, (190, 190, 190), kc)
    text(lay, '다음 영상', font('Medium', 30), cx, cy + 66 + 20 * (1 - kc), GRAY, kc)
    kk = out_cubic(seg(t, 1.25, 1.75))
    c, r = (1410, 830), 118 * (0.96 + 0.04 * kk)
    shadow(lay, (c[0] - r, c[1] - r, c[0] + r, c[1] + r), 0, a=0.10 * kk, blur=24, dy=12, ellipse=True)
    d.ellipse(P(c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=WHITE + (int(255 * kk),), outline=LINE + (int(255 * kk),), width=2 * S)
    icon(lay, 'add', c[0], c[1] - 16, 64, (190, 190, 190), kk)
    text(lay, '구독', font('Medium', 28), c[0], c[1] + 50, GRAY, kk)
    kb = seg(t, 0.6, 1.0)
    d.rectangle(P(0, H - 6, W, H), fill=(240, 240, 240, int(255 * kb)))
    d.rectangle(P(0, H - 6, W * clamp(t / 10), H), fill=ACCENT + (int(255 * kb),))
    base.alpha_composite(lay)
    return finish(base)


def eB(t):
    """B+ 버튼 클릭: 구독 → 알림(종이 흔들림) → 좋아요(+1) 순서로 눌리고, 누를 때마다 물결이 번진다."""
    base = blend(zoomed(LAST, 1 + 0.04 * seg(t, 0, 0.6)), WHITE_IMG, out_cubic(seg(t, 0, 0.6))).convert('RGBA')
    lay = blank()
    logo(lay, W / 2, 290, 60, a=seg(t, 0.5, 0.9), dot_k=back(seg(t, 0.7, 1.0)))
    letters(lay, '끝까지 봐주셔서 고마워요!', font('Black', 84), W / 2, 432, INK, t, 0.8, step=0.035)
    kp = out_cubic(seg(t, 1.5, 1.95))
    fb = font('Bold', 38)
    py = 610 + 20 * (1 - kp)
    like_x, sub_x, bell_x = W / 2 - 300, W / 2 + 10, W / 2 + 270
    C_SUB, C_BELL, C_LIKE = 3.45, 4.65, 5.85
    def press(c): return 1 - 0.07 * math.sin(math.pi * seg(t, c - 0.05, c + 0.2))
    pill(lay, like_x, py, '좋아요', fb, 'ink' if t >= C_LIKE + 0.05 else 'outline', kp, press(C_LIKE), ic='thumb',
         ic_filled=t >= C_LIKE + 0.05)
    if t >= C_SUB + 0.05:
        pill(lay, sub_x, py, '구독중', fb, 'soft', kp, press(C_SUB), ic='check', pad=56)
    else:
        pill(lay, sub_x, py, '구독', fb, 'accent', kp, press(C_SUB), pad=64, shadow_a=0.16)
    # bell: round button, swings after the click
    bs = press(C_BELL)
    on = t >= C_BELL + 0.05
    r = 43 * bs
    if kp > 0:
        shadow(lay, (bell_x - r, py - r, bell_x + r, py + r), 0, a=0.08 * kp, blur=14, dy=8, ellipse=True)
        dd = ImageDraw.Draw(lay)
        if on:
            dd.ellipse(P(bell_x - r, py - r, bell_x + r, py + r), fill=INK + (int(255 * kp),))
        else:
            dd.ellipse(P(bell_x - r, py - r, bell_x + r, py + r), fill=WHITE + (int(255 * kp),), outline=INK + (int(255 * kp),), width=3 * S)
        sw = seg(t, C_BELL, C_BELL + 1.1)
        rot = 22 * math.sin(sw * math.pi * 6) * (1 - sw) if 0 < sw < 1 else 0
        icon(lay, 'bell', bell_x, py, 40 * bs, WHITE if on else INK, kp, filled=on, rot=rot)
    for c, x in ((C_SUB, sub_x), (C_BELL, bell_x), (C_LIKE, like_x)):
        ripple(lay, x, py, seg(t, c, c + 0.6), color=ACCENT, maxr=140)
    kpl = seg(t, C_LIKE + 0.05, C_LIKE + 1.0)
    if 0 < kpl < 1:
        text(lay, '+1', font('Black', 40), like_x + 40, py - 70 - 60 * out_cubic(kpl), ACCENT, 1 - kpl ** 2)
    text(lay, '알림 설정까지 해 주시면 완벽!', font('Light', 34), W / 2, 740, GRAY, out_cubic(seg(t, 6.3, 6.8)))
    text(lay, 'EUITAE', font('Medium', 24), W / 2, 980, GRAY, seg(t, 1.8, 2.3), tracking=12)
    if 2.4 <= t < 7.0:
        pts = [(2.4, (1560, 930)), (3.35, (sub_x + 8, py + 10)), (4.0, (sub_x + 8, py + 10)), (4.55, (bell_x + 6, py + 12)),
               (5.2, (bell_x + 6, py + 12)), (5.75, (like_x + 12, py + 12)), (6.3, (like_x + 12, py + 12)), (7.0, (like_x + 380, py + 380))]
        for (ta, pa), (tb, pb) in zip(pts, pts[1:]):
            if ta <= t < tb:
                k = in_out(seg(t, ta, tb))
                x, y = pa[0] + (pb[0] - pa[0]) * k, pa[1] + (pb[1] - pa[1]) * k
                break
        pr = sum(math.sin(math.pi * seg(t, c - 0.05, c + 0.2)) for c in (C_SUB, C_BELL, C_LIKE))
        cursor(lay, x, y, a=1 - seg(t, 6.6, 7.0), press=pr)
    base.alpha_composite(lay)
    return finish(base)


def eC(t):
    """C+ 프로스트 카드: 흐려진 마지막 장면이 천천히 확대되고, 그 위로 흰 카드가 떠오른다."""
    z = 1 + 0.08 * (t / 10)
    base = blend(zoomed(LAST, z), zoomed(FROST, z), out_cubic(seg(t, 0, 0.9))).convert('RGBA')
    lay = blank()
    d = ImageDraw.Draw(lay)
    kc = out_cubic(seg(t, 0.55, 1.1))
    sc = 0.94 + 0.06 * kc
    cw, ch = 1160 * sc, 560 * sc
    box = (W / 2 - cw / 2, H / 2 - ch / 2 + 24 * (1 - kc), W / 2 + cw / 2, H / 2 + ch / 2 + 24 * (1 - kc))
    shadow(lay, box, 36, a=0.14 * kc, blur=34, dy=18)
    d.rounded_rectangle(P(*box), radius=36 * S, fill=(255, 255, 255, int(235 * kc)))
    logo(lay, W / 2, 352, 44, a=seg(t, 0.9, 1.3), dot_k=back(seg(t, 1.0, 1.3)))
    letters(lay, '다음 영상에서 또 만나요', font('Black', 80), W / 2, 470, INK, t, 1.0, step=0.04)
    lw = 150 * out_cubic(seg(t, 1.5, 1.9))
    if lw > 1:
        d.rounded_rectangle(P(W / 2 - lw / 2, 532, W / 2 + lw / 2, 538), radius=3 * S, fill=ACCENT + (255,))
    fb = font('Bold', 34)
    for i, (lab, x, st, ic) in enumerate([('좋아요', W / 2 - 300, 'outline', 'thumb'), ('구독', W / 2, 'accent', 'add'),
                                          ('알림 설정', W / 2 + 310, 'outline', 'bell')]):
        p = seg(t, 1.9 + i * 0.22, 2.3 + i * 0.22)
        if p > 0:
            pill(lay, x, 652, lab, fb, st, min(1, p * 2), back(p) if p < 1 else 1.0, ic=ic, h=78, pad=36,
                 shadow_a=0.12 if st == 'accent' else 0)
    ripple(lay, W / 2, 652, seg(t, 2.15, 2.85), maxr=150)
    text(lay, 'EUITAE', font('Medium', 24), W / 2, 1000, (110, 110, 110), seg(t, 2.6, 3.0), tracking=12)
    base.alpha_composite(lay)
    return finish(base)


JOBS = {
    'transition_A_minimal_v2': (tA, 2.6, [('whoosh', 0.0, -10), ('click', 0.62, -14), ('pop', 0.95, -16)]),
    'transition_B_wipe_v2': (tB, 2.4, [('whoosh', 0.0, -8), ('whoosh', 1.55, -10)]),
    'transition_C_dot_v2': (tC, 2.6, [('whoosh', 0.0, -10), ('pop', 0.62, -8), ('whoosh', 1.75, -12)]),
    'ending_A_editorial_v2': (eA, 10.0, [('ding', 0.85, -14)]),
    'ending_B_buttons_v2': (eB, 10.0, [('click', 3.45, -6), ('ding', 4.7, -14), ('click', 5.85, -6), ('pop', 5.95, -12)]),
    'ending_C_frosted_v2': (eC, 10.0, [('pop', 1.95, -10), ('pop', 2.17, -10), ('pop', 2.39, -10), ('ding', 2.2, -16)]),
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


for name, (fn, dur, sounds) in JOBS.items():
    if not ONLY or name in ONLY:
        render(name, fn, dur, sounds)
