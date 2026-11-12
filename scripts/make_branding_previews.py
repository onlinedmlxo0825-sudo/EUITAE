"""Channel branding previews: 3 scene-transition bumpers + 3 end screens (clean white tone).

Renders 1920x1080 30fps mp4 previews into branding/previews/. Nothing goes into CapCut yet;
the user picks first. Frames are drawn with PIL and piped to ffmpeg; short synth SFX from sfx/.

usage: python -I make_branding_previews.py <repo_root> [name ...]
"""
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(sys.argv[1])
ONLY = set(sys.argv[2:])
W, H, FPS = 1920, 1080, 30
WHITE, INK, GRAY, LINE, ACCENT = (255, 255, 255), (17, 17, 17), (138, 138, 138), (226, 226, 226), (255, 74, 43)
FONTS = ROOT / 'fonts'
OUT = ROOT / 'branding' / 'previews'
FR = ROOT / 'branding' / 'frames'
SFX = ROOT / 'sfx'
FF = next((Path.home() / 'AppData/Local/Microsoft/WinGet/Packages').rglob('ffmpeg.exe'))


def font(weight, size):
    return ImageFont.truetype(str(FONTS / f'GothicA1-{weight}.ttf'), size)


def clamp(x):
    return max(0.0, min(1.0, x))


def seg(t, a, b):
    return clamp((t - a) / (b - a)) if b > a else float(t >= a)


def out_cubic(x):
    return 1 - (1 - x) ** 3


def in_out(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def back(x):          # small overshoot pop
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def load(name):
    return Image.open(FR / name).convert('RGB').resize((W, H))


def tracked_width(d, text, f, tracking):
    return sum(d.textlength(ch, font=f) for ch in text) + tracking * (len(text) - 1)


def text(layer, s, f, cx, cy, fill, alpha=1.0, tracking=0, anchor='mm'):
    """Draw text centred at (cx, cy) on an RGBA layer with opacity and letter spacing."""
    if alpha <= 0:
        return
    d = ImageDraw.Draw(layer)
    col = fill + (int(255 * alpha),)
    if not tracking:
        d.text((cx, cy), s, font=f, fill=col, anchor=anchor)
        return
    w = tracked_width(d, s, f, tracking)
    x = cx - w / 2 if anchor == 'mm' else cx
    for ch in s:
        d.text((x, cy), ch, font=f, fill=col, anchor='lm')
        x += d.textlength(ch, font=f) + tracking


def pill(layer, cx, cy, label, f, filled, alpha=1.0, scale=1.0, fill=INK, txt=None, pad=46, h=84):
    if alpha <= 0:
        return
    d = ImageDraw.Draw(layer)
    w = (d.textlength(label, font=f) + pad * 2) * scale
    hh = h * scale
    box = [cx - w / 2, cy - hh / 2, cx + w / 2, cy + hh / 2]
    a = int(255 * alpha)
    if filled:
        d.rounded_rectangle(box, radius=hh / 2, fill=fill + (a,))
        tc = txt or WHITE
    else:
        d.rounded_rectangle(box, radius=hh / 2, outline=fill + (a,), width=max(2, int(3 * scale)))
        tc = txt or fill
    fs = ImageFont.truetype(f.path, max(8, int(f.size * scale)))
    d.text((cx, cy), label, font=fs, fill=tc + (a,), anchor='mm')
    return box


def cursor(layer, x, y, alpha=1.0, press=0.0):
    if alpha <= 0:
        return
    s = 1.0 - 0.12 * press
    pts = [(0, 0), (0, 44), (11, 33), (19, 52), (27, 48), (19, 30), (34, 30)]
    pts = [(x + px * s * 1.3, y + py * s * 1.3) for px, py in pts]
    d = ImageDraw.Draw(layer)
    d.polygon(pts, fill=(255, 255, 255, int(255 * alpha)), outline=(17, 17, 17, int(255 * alpha)), width=3)


def check(layer, cx, cy, size, col, alpha=1.0):
    d = ImageDraw.Draw(layer)
    a = int(255 * alpha)
    d.line([(cx - size, cy), (cx - size * 0.3, cy + size * 0.7), (cx + size, cy - size * 0.8)], fill=col + (a,), width=6, joint='curve')


def blend(a, b, k):
    return Image.blend(a, b, clamp(k)) if 0 < k < 1 else (b if k >= 1 else a)


# ── transition bumpers (prev scene → logo → next scene) ──────────────────────
PREV, NEXT = load('prev_gym.png'), load('next_fish.png')
WHITE_IMG = Image.new('RGB', (W, H), WHITE)


def bumper_minimal(t):
    """A. 미니멀 워드마크: 흰 화면에 '의태' + 주황 밑줄 + EUITAE VLOG."""
    base = blend(PREV, WHITE_IMG, out_cubic(seg(t, 0, 0.35)))
    base = blend(base, NEXT, in_out(seg(t, 2.0, 2.4)))
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    out = 1 - seg(t, 1.75, 2.0)
    k = out_cubic(seg(t, 0.3, 0.9))
    text(lay, '의태', font('Black', 176), W / 2, H / 2 - 40 + 26 * (1 - k), INK, k * out)
    lw = 230 * out_cubic(seg(t, 0.55, 1.05))
    if lw > 1 and out > 0:
        ImageDraw.Draw(lay).rectangle([W / 2 - lw / 2, H / 2 + 72, W / 2 + lw / 2, H / 2 + 78], fill=ACCENT + (int(255 * out),))
    text(lay, 'EUITAE  VLOG', font('Medium', 30), W / 2, H / 2 + 128, GRAY, seg(t, 0.75, 1.15) * out, tracking=14)
    return Image.alpha_composite(base.convert('RGBA'), lay)


def bumper_wipe(t):
    """B. 슬라이드 패널: 흰 판이 왼쪽에서 밀고 들어와 로고를 보여 주고 오른쪽으로 빠진다."""
    x_in = -W + W * in_out(seg(t, 0, 0.45))
    x_out = W * in_out(seg(t, 1.6, 2.1))
    px = x_in if t < 1.6 else x_out
    frame = (PREV if t < 1.0 else NEXT).copy().convert('RGBA')
    panel = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(panel)
    d.rectangle([0, 0, W, H], fill=WHITE + (255,))
    k = out_cubic(seg(t, 0.35, 0.8))
    text(panel, '의태', font('Black', 168), W / 2, H / 2 - 30 + 60 * (1 - k), INK, k)
    text(panel, 'EUITAE', font('Bold', 34), W / 2, H / 2 + 92, ACCENT, out_cubic(seg(t, 0.55, 0.95)), tracking=22)
    frame.alpha_composite(panel, (int(px), 0))
    edge = ImageDraw.Draw(frame)                       # orange leading edge
    ex = int(px + W) if t < 1.6 else int(px)
    edge.rectangle([ex - 14, 0, ex, H], fill=ACCENT + (255,))
    return frame


def bumper_dot(t):
    """C. 점(●) 아이리스: 흰 원이 퍼져 덮고, '의태.' 의 주황 점으로 다시 모여 다음 장면이 열린다."""
    diag = math.hypot(W, H) / 2
    dot_xy = (W / 2 + 150, H / 2 + 52)
    if t < 1.7:
        r = diag * out_cubic(seg(t, 0, 0.5))
        cx, cy = W / 2, H / 2
        under = PREV
    else:
        k = in_out(seg(t, 1.7, 2.35))
        r = (diag + 200) * (1 - k)
        cx, cy = W / 2 + (dot_xy[0] - W / 2) * k, H / 2 + (dot_xy[1] - H / 2) * k
        under = NEXT
    frame = under.copy().convert('RGBA')
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    if r > 0:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE + (255,))
    fade = 1 - seg(t, 1.6, 1.8)
    text(lay, '의태', font('Black', 160), W / 2 - 22, H / 2 - 10, INK, out_cubic(seg(t, 0.6, 0.95)) * fade)
    p = seg(t, 0.5, 0.78)
    if p > 0 and t < 2.35:
        s = back(p) if t < 1.7 else 1.0
        rr = 19 * s
        d.ellipse([dot_xy[0] - rr, dot_xy[1] - rr, dot_xy[0] + rr, dot_xy[1] + rr], fill=ACCENT + (255,))
    frame.alpha_composite(lay)
    return frame


# ── end screens (last scene → 10 s card) ─────────────────────────────────────
LAST = load('last_scene.png')
FROST = Image.blend(LAST.filter(ImageFilter.GaussianBlur(28)), WHITE_IMG, 0.8)


def end_editorial(t):
    """A. 에디토리얼: 왼쪽에 인사말, 오른쪽에 유튜브 최종 화면 요소(다음 영상·구독) 자리."""
    base = blend(LAST, WHITE_IMG, out_cubic(seg(t, 0, 0.6)))
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    a = out_cubic(seg(t, 0.6, 1.0))
    d.rectangle([150, 300, 158, 352], fill=ACCENT + (int(255 * a),))
    for i, (s, f, y) in enumerate([('오늘도 끝까지 봐주셔서', font('Bold', 62), 405), ('감사합니다', font('Black', 104), 505)]):
        k = out_cubic(seg(t, 0.7 + i * 0.18, 1.2 + i * 0.18))
        text(lay, s, f, 150, y + 24 * (1 - k), INK, k, anchor='lm')
    text(lay, '좋아요와 구독은 큰 힘이 됩니다', font('Light', 38), 150, 615, GRAY, out_cubic(seg(t, 1.2, 1.6)), anchor='lm')
    text(lay, '의태   EUITAE', font('Medium', 26), 150, 960, GRAY, seg(t, 1.5, 1.9), tracking=6, anchor='lm')
    k = out_cubic(seg(t, 1.0, 1.5))
    box = [1060, 230, 1760, 624]
    d.rounded_rectangle(box, radius=22, fill=(246, 246, 246, int(255 * k)), outline=LINE + (int(255 * k),), width=3)
    text(lay, '다음 영상', font('Medium', 34), (box[0] + box[2]) / 2, (box[1] + box[3]) / 2, GRAY, k)
    k2 = out_cubic(seg(t, 1.2, 1.7))
    c, r = (1410, 815), 118
    d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=(246, 246, 246, int(255 * k2)), outline=LINE + (int(255 * k2),), width=3)
    text(lay, '구독', font('Medium', 34), c[0], c[1], GRAY, k2)
    return Image.alpha_composite(base.convert('RGBA'), lay)


def end_buttons(t):
    """B. 버튼 클릭: 가운데 인사말, 커서가 '구독' → '좋아요'를 차례로 누른다."""
    base = blend(LAST, WHITE_IMG, out_cubic(seg(t, 0, 0.6)))
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    k0 = out_cubic(seg(t, 0.6, 1.0))
    text(lay, '의태', font('Black', 58), W / 2 - 10, 300, INK, k0)
    d.ellipse([W / 2 + 52, 316, W / 2 + 64, 328], fill=ACCENT + (int(255 * k0),))
    k1 = out_cubic(seg(t, 0.8, 1.3))
    text(lay, '끝까지 봐주셔서 고마워요!', font('Black', 84), W / 2, 440 + 24 * (1 - k1), INK, k1)
    kp = out_cubic(seg(t, 1.3, 1.8))
    fb = font('Bold', 40)
    like_x, sub_x, py = W / 2 - 170, W / 2 + 170, 610
    sub_on = t >= 3.55
    like_on = t >= 5.15
    press_s = 1 - 0.07 * math.sin(math.pi * seg(t, 3.45, 3.7))
    press_l = 1 - 0.07 * math.sin(math.pi * seg(t, 5.05, 5.3))
    pill(lay, like_x, py, '좋아요', fb, filled=like_on, alpha=kp, scale=press_l)
    if sub_on:
        pill(lay, sub_x, py, '구독중', fb, filled=True, alpha=kp, scale=press_s, fill=(236, 236, 236), txt=(80, 80, 80), pad=70)
        check(lay, sub_x - 92, py, 13, (80, 80, 80), kp)
    else:
        pill(lay, sub_x, py, '구독', fb, filled=True, alpha=kp, scale=press_s, fill=ACCENT, pad=70)
    text(lay, '알림 설정도 잊지 마세요', font('Light', 34), W / 2, 735, GRAY, out_cubic(seg(t, 5.6, 6.1)))
    # cursor path: enter → 구독 (click 3.5) → 좋아요 (click 5.1) → leave
    if 2.4 <= t < 6.6:
        if t < 3.4:
            k = in_out(seg(t, 2.4, 3.4)); x, y = 1500 + (sub_x + 10 - 1500) * k, 900 + (py + 8 - 900) * k
        elif t < 4.3:
            x, y = sub_x + 10, py + 8
        elif t < 5.0:
            k = in_out(seg(t, 4.3, 5.0)); x, y = sub_x + 10 + (like_x + 10 - sub_x - 10) * k, py + 8
        else:
            k = in_out(seg(t, 5.8, 6.6)); x, y = like_x + 10 + 300 * k, py + 8 + 300 * k
        press = math.sin(math.pi * seg(t, 3.45, 3.7)) + math.sin(math.pi * seg(t, 5.05, 5.3))
        cursor(lay, x, y, alpha=1 - seg(t, 6.2, 6.6), press=press)
    return Image.alpha_composite(base.convert('RGBA'), lay)


def end_frosted(t):
    """C. 프로스트: 마지막 장면을 뿌옇게 흐리고 그 위에 인사말과 버튼 세 개."""
    k = out_cubic(seg(t, 0, 0.9))
    base = blend(LAST, FROST, k)
    lay = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    k1 = out_cubic(seg(t, 0.7, 1.2))
    text(lay, '다음 영상에서 또 만나요', font('Black', 92), W / 2, 450 + 28 * (1 - k1), INK, k1)
    lw = 160 * out_cubic(seg(t, 1.0, 1.4))
    if lw > 1:
        ImageDraw.Draw(lay).rectangle([W / 2 - lw / 2, 532, W / 2 + lw / 2, 538], fill=ACCENT + (255,))
    fb = font('Bold', 36)
    for i, (lab, x) in enumerate([('좋아요', W / 2 - 290), ('구독', W / 2), ('알림 설정', W / 2 + 300)]):
        p = seg(t, 1.4 + i * 0.22, 1.75 + i * 0.22)
        if p > 0:
            pill(lay, x, 660, lab, fb, filled=(lab == '구독'), alpha=min(1, p * 2), scale=back(p) if p < 1 else 1.0,
                 fill=ACCENT if lab == '구독' else INK, pad=40, h=76)
    text(lay, '의태   EUITAE', font('Medium', 26), W / 2, 965, GRAY, seg(t, 2.2, 2.6), tracking=6)
    return Image.alpha_composite(base.convert('RGBA'), lay)


JOBS = {
    'transition_A_minimal': (bumper_minimal, 2.4, [('whoosh', 0.0, -10), ('click', 0.6, -12)]),
    'transition_B_wipe': (bumper_wipe, 2.2, [('whoosh', 0.0, -8), ('whoosh', 1.6, -10)]),
    'transition_C_dot': (bumper_dot, 2.4, [('whoosh', 0.0, -10), ('pop', 0.55, -8), ('whoosh', 1.7, -12)]),
    'ending_A_editorial': (end_editorial, 10.0, [('ding', 0.8, -14)]),
    'ending_B_buttons': (end_buttons, 10.0, [('click', 3.5, -6), ('click', 5.1, -6), ('ding', 5.2, -14)]),
    'ending_C_frosted': (end_frosted, 10.0, [('pop', 1.45, -10), ('pop', 1.67, -10), ('pop', 1.89, -10)]),
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
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', str(out)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(int(round(dur * FPS))):
        p.stdin.write(fn(i / FPS).convert('RGB').tobytes())
    p.stdin.close()
    p.wait()
    print(f'{name}: {dur}s -> {out}')


for name, (fn, dur, sounds) in JOBS.items():
    if not ONLY or name in ONLY:
        render(name, fn, dur, sounds)
