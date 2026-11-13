"""Cut vertical Shorts (1080x1920) out of the finished CapCut draft, re-laying the text for vertical.

Layout (follows the @xuitae Shorts look, a bit upgraded):
  black background · title (2 lines, white + yellow keyword) at the top · landscape video enlarged to
  960px high with the sides cropped · subtitles in a black box at the bottom of the video ·
  yellow captions at the top of the video · light-blue inner voice just above the subtitles.
The bottom ~1/4 stays empty for the Shorts UI (channel name, description, buttons).
Audio = the clips' own sound + BGM/SFX from the draft, with the draft's volumes.

usage: python -I make_shorts.py <repo_root> <draft_content.json> <shorts.json> [name ...]
shorts.json: [{"name": "short1", "range": [428.6, 470.4], "title": [[["text", "white"|"yellow"], ...], [line2...]]}]
"""
import json, subprocess, sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT, DRAFT, SPEC = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
ONLY = set(sys.argv[4:])
OUT = ROOT / '1108_낚시_등운동_브이로그' / '05_shorts'
TMP = OUT / '_tmp'
FF = next((Path.home() / 'AppData/Local/Microsoft/WinGet/Packages').rglob('ffmpeg.exe'))
W, H, FPS = 1080, 1920, 30
VID_Y, VID_H = 420, 960                      # video band
BHS = str(ROOT / 'fonts' / 'BlackHanSans-Regular.ttf')
GOTH = str(ROOT / 'fonts' / 'GothicA1-Black.ttf')
COL = {'white': (255, 255, 255), 'yellow': (255, 222, 40), 'blue': (140, 216, 255)}
US = 1e6

D = json.loads(DRAFT.read_text('utf-8'))
M = D['materials']
vm = {m['id']: m for m in M['videos']}
am = {m['id']: m for m in M['audios']}
tm = {m['id']: m for m in M['texts']}
fades = {m['id']: m for m in M.get('audio_fades', [])}


def run(args):
    subprocess.run([str(FF), '-v', 'error', '-y'] + [str(a) for a in args], check=True)


def kind(m):
    c = json.loads(m['content'])
    col = c['styles'][0]['fill']['content']['solid']['color']
    if m.get('background_style') == 1:
        return 'sub'
    if col[2] < 0.5:
        return 'yellow'
    if col[0] < 0.7:
        return 'blue'
    return 'note'


def collect(t0, t1):
    vids, auds, txts = [], [], []
    for tr in D['tracks']:
        for s in tr['segments']:
            st = s['target_timerange']['start'] / US
            en = st + s['target_timerange']['duration'] / US
            a, b = max(st, t0), min(en, t1)
            if b - a < 0.05:
                continue
            if tr['type'] == 'video' and tr.get('name') == '메인':
                m = vm[s['material_id']]
                src = s['source_timerange']['start'] / US + (a - st)
                vids.append(dict(file=m['path'], photo=m.get('type') == 'photo', src=src, dur=b - a, at=a - t0,
                                 vol=float(s.get('volume', 1.0))))
            elif tr['type'] == 'audio':
                m = am[s['material_id']]
                src = s['source_timerange']['start'] / US + (a - st)
                fi = fo = 0.0
                for r in s.get('extra_material_refs', []):
                    if r in fades:
                        fi, fo = fades[r]['fade_in_duration'] / US, fades[r]['fade_out_duration'] / US
                # keep only the part of the fades that falls inside the cut
                fi_left = max(0.0, fi - (a - st))
                fo_start = (en - fo) - t0 if fo else None
                auds.append(dict(file=m['path'], src=src, dur=b - a, at=a - t0, vol=float(s.get('volume', 1.0)),
                                 fi=fi_left, fo_at=fo_start, fo=fo))
            elif tr['type'] == 'text':
                m = tm[s['material_id']]
                txts.append(dict(text=json.loads(m['content'])['text'], kind=kind(m), at=a - t0, dur=b - a))
    vids.sort(key=lambda v: v['at'])
    return vids, auds, txts


# ── text layers ──
def layer():
    return Image.new('RGBA', (W, H), (0, 0, 0, 0))


def fit(text, font_path, size, maxw):
    f = ImageFont.truetype(font_path, size)
    while f.getlength(text) > maxw and size > 24:
        size -= 2
        f = ImageFont.truetype(font_path, size)
    return f


def wrap(text, font, maxw):
    """Split into at most 2 lines at a space near the middle when too wide."""
    if font.getlength(text) <= maxw or ' ' not in text:
        return [text]
    words = text.split(' ')
    best = None
    for i in range(1, len(words)):
        a, b = ' '.join(words[:i]), ' '.join(words[i:])
        score = max(font.getlength(a), font.getlength(b))
        if best is None or score < best[0]:
            best = (score, [a, b])
    return best[1]


def draw_sub(text):
    im = layer()
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(GOTH, 50)
    lines = wrap(text, f, W - 140)
    f = fit(max(lines, key=f.getlength), GOTH, 50, W - 140)
    lh = 66
    y_bottom = VID_Y + VID_H - 46
    for i, ln in enumerate(reversed(lines)):
        cy = y_bottom - i * (lh + 10) - lh / 2
        tw = f.getlength(ln)
        d.rounded_rectangle([W / 2 - tw / 2 - 24, cy - lh / 2, W / 2 + tw / 2 + 24, cy + lh / 2], radius=12, fill=(0, 0, 0, 215))
        d.text((W / 2, cy + 2), ln, font=f, fill=(255, 255, 255), anchor='mm')
    return im, len(lines)


def draw_cap(text, color, y, size):
    im = layer()
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(BHS, size)
    lines = wrap(text, f, W - 120)
    f = fit(max(lines, key=f.getlength), BHS, size, W - 120)
    for i, ln in enumerate(lines):
        d.text((W / 2, y + i * (size + 12)), ln, font=f, fill=COL[color], anchor='mm', stroke_width=7, stroke_fill=(0, 0, 0))
    return im


def draw_title(lines):
    im = layer()
    d = ImageDraw.Draw(im)
    size = 86
    widths = lambda sz: [sum(ImageFont.truetype(BHS, sz).getlength(t) for t, _ in ln) for ln in lines]
    while max(widths(size)) > W - 100:
        size -= 4
    f = ImageFont.truetype(BHS, size)
    gap = size + 22
    y0 = (VID_Y - 30) / 2 - (len(lines) - 1) * gap / 2 + 20
    for i, ln in enumerate(lines):
        x = W / 2 - widths(size)[i] / 2
        for t, c in ln:
            d.text((x, y0 + i * gap), t, font=f, fill=COL[c], anchor='lm', stroke_width=5, stroke_fill=(0, 0, 0))
            x += f.getlength(t)
    return im


def draw_brand():
    """'의태' + YouTube icon, centred just under the video (fills the empty lower area, above the Shorts UI)."""
    im = layer()
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(GOTH, 60)
    cy = VID_Y + VID_H + 150                     # lowered (user: "조금만 더 내리면")
    tw = f.getlength('의태')
    ih, gap = 50, 18
    iw = ih * 1.42
    x0 = W / 2 - (tw + gap + iw) / 2
    d.text((x0, cy), '의태', font=f, fill=(255, 255, 255), anchor='lm')
    ix = x0 + tw + gap
    # white icon with a black play triangle (monochrome, matches the white text)
    d.rounded_rectangle([ix, cy - ih / 2, ix + iw, cy + ih / 2], radius=ih * 0.28, fill=(255, 255, 255))
    th = ih * 0.42
    tx = ix + iw / 2 - th * 0.36
    d.polygon([(tx, cy - th / 2), (tx, cy + th / 2), (tx + th * 0.87, cy)], fill=(0, 0, 0))
    ft = ImageFont.truetype(str(ROOT / 'fonts' / 'GothicA1-Bold.ttf'), 34)
    d.text((W / 2, cy + 64), '헬스인의 단백질 자급자족', font=ft, fill=(190, 190, 190), anchor='mm')
    return im


def brand_right():
    """x of the right edge of the '의태 + logo' group (same math as draw_brand)."""
    tw = ImageFont.truetype(GOTH, 60).getlength('의태')
    return W / 2 + (tw + 18 + 50 * 1.42) / 2


def draw_cta():
    """Last 2 seconds: '구독 꾹 👇' pill right of the YouTube logo, same row (white pill, black text)."""
    im = layer()
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(GOTH, 38)
    fe = ImageFont.truetype('C:/Windows/Fonts/seguiemj.ttf', 36)
    label = '구독 꾹 '
    tw, ew = f.getlength(label), 42
    cy = VID_Y + VID_H + 150
    x0 = brand_right() + 30 + 26
    # toned down to match the white logo: white pill, black text
    d.rounded_rectangle([x0 - 26, cy - 32, x0 + tw + ew + 22, cy + 32], radius=32, fill=(255, 255, 255))
    d.text((x0, cy + 2), label, font=f, fill=(0, 0, 0), anchor='lm')
    d.text((x0 + tw, cy + 4), '👇', font=fe, anchor='lm', embedded_color=True)
    return im


def build(spec):
    name = spec['name']
    work = TMP / name
    work.mkdir(parents=True, exist_ok=True)
    # one range, or several ranges joined back to back ("ranges": [[a, b], [c, d]])
    vids, auds, txts, dur = [], [], [], 0.0
    parts_spec = spec.get('parts') or [{'range': r} for r in (spec.get('ranges') or [spec['range']])]
    for part in parts_spec:
        if 'range' in part:                          # a stretch of the finished edit
            t0, t1 = part['range']
            v, au, tx = collect(t0, t1)
            plen = t1 - t0
        else:                                        # a raw source clip that isn't in the edit
            plen = part['out'] - part['in']
            v = [dict(file=part['file'], photo=False, src=part['in'], dur=plen, at=0.0, vol=part.get('vol', 1.0))]
            au = []
            if 'bgm_from' in part:                   # borrow the edit's music/SFX from a timeline spot
                _, au, _ = collect(part['bgm_from'], part['bgm_from'] + plen)
            tx = [dict(kind='sub', text=s['text'], at=s['at'], dur=s['dur']) for s in part.get('subs', [])]
        for x in v + au + tx:
            x['at'] += dur
        for x in au:
            if x['fo_at'] is not None:
                x['fo_at'] += dur
        vids += v; auds += au; txts += tx
        dur += plen
    for e in spec.get('extra_texts', []):          # captions that live outside the chosen ranges
        txts.append(dict(kind=e.get('kind', 'note'), text=e['text'], at=float(e['at']), dur=float(e['dur'])))

    # 1) base 16:9 video with clip audio
    parts = []
    for i, v in enumerate(vids):
        p = work / f'v{i:02d}.mp4'
        vf = 'scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=yuv420p,setsar=1'
        if v['photo']:
            run(['-loop', '1', '-t', f"{v['dur']:.3f}", '-i', v['file'], '-f', 'lavfi', '-t', f"{v['dur']:.3f}",
                 '-i', 'anullsrc=r=48000:cl=stereo', '-vf', vf, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16',
                 '-c:a', 'aac', '-ar', '48000', '-ac', '2', '-shortest', p])
        else:
            run(['-ss', f"{v['src']:.3f}", '-t', f"{v['dur']:.3f}", '-i', v['file'], '-vf', vf,
                 '-af', f"volume={v['vol']:.4f},aresample=48000", '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16',
                 '-c:a', 'aac', '-ar', '48000', '-ac', '2', p])
        parts.append(p)
    lst = work / 'list.txt'
    lst.write_text(''.join(f"file '{p.as_posix()}'\n" for p in parts), 'utf-8')
    base = work / 'base.mp4'
    run(['-f', 'concat', '-safe', '0', '-i', lst, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16',
         '-c:a', 'aac', '-ar', '48000', base])

    # 2) text layers
    layers = [(draw_title(spec['title']), 0.0, dur), (draw_brand(), 0.0, dur), (draw_cta(), dur - 2.0, dur)]
    subs = [t for t in txts if t['kind'] == 'sub']
    for t in txts:
        if t['kind'] == 'sub':
            im, n = draw_sub(t['text'])
        elif t['kind'] == 'yellow':
            im = draw_cap(t['text'], 'yellow', VID_Y + 90, 66)
        elif t['text'].startswith('['):                  # exercise name: white, top of the video like the main edit
            im = draw_cap(t['text'], 'white', VID_Y + 90, 70)
        else:                                            # inner voice / notes: just above the subtitles
            hi = max([1] + [2 for s in subs if s['at'] < t['at'] + t['dur'] and t['at'] < s['at'] + s['dur']
                           and len(wrap(s['text'], ImageFont.truetype(GOTH, 50), W - 140)) > 1])
            y = VID_Y + VID_H - 46 - hi * 76 - 60
            im = draw_cap(t['text'], 'blue' if t['kind'] == 'blue' else 'white', y, 54)
        layers.append((im, t['at'], t['at'] + t['dur']))
    pngs = []
    for i, (im, a, b) in enumerate(layers):
        p = work / f't{i:02d}.png'
        bb = im.getbbox() or (0, 0, 2, 2)
        im.crop(bb).save(p)
        pngs.append((p, bb[0], bb[1], a, b))

    # 3) composite + audio mix
    args = ['-i', base]
    for p, *_ in pngs:
        args += ['-i', p]
    na = 1 + len(pngs)
    for a in auds:
        args += ['-ss', f"{a['src']:.3f}", '-t', f"{a['dur']:.3f}", '-i', a['file']]
    vf = [f'[0:v]scale=-2:{VID_H},crop={W}:{VID_H},pad={W}:{H}:0:{VID_Y}:black[v0]']
    last = 'v0'
    for i, (p, x, y, a, b) in enumerate(pngs):
        en = '' if i < 2 else f":enable='between(t,{a:.3f},{b:.3f})'"
        vf.append(f'[{last}][{i + 1}:v]overlay={x}:{y}{en}[v{i + 1}]')
        last = f'v{i + 1}'
    mix = ['[0:a]']
    for k, a in enumerate(auds):
        ms = int(round(a['at'] * 1000))
        chain = f"[{na + k}:a]aresample=48000,volume={a['vol']:.4f}"
        if a['fi'] > 0.01:
            chain += f",afade=t=in:st=0:d={a['fi']:.3f}"
        if a['fo'] and a['fo_at'] is not None and a['fo_at'] < dur:
            st = max(0.0, a['fo_at'] - a['at'])
            chain += f",afade=t=out:st={st:.3f}:d={a['fo']:.3f}"
        chain += f',adelay={ms}|{ms}[a{k}]'
        vf.append(chain)
        mix.append(f'[a{k}]')
    vf.append(''.join(mix) + f'amix=inputs={len(mix)}:normalize=0:duration=first,'
              f'afade=t=in:st=0:d=0.15,afade=t=out:st={dur - 0.3:.3f}:d=0.3'
              + (',loudnorm=I=-15:TP=-1.5:LRA=11,aresample=48000' if spec.get('loudnorm', True) else '') + '[aout]')
    out = OUT / f'{name}.mp4'
    run(args + ['-filter_complex', ';'.join(vf), '-map', f'[{last}]', '-map', '[aout]', '-t', f'{dur:.3f}',
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', '30',
                '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', out])
    print(f'{name}: {dur:.1f}s, {len(vids)} clips, {len(txts)} texts, {len(auds)} audio -> {out}')


OUT.mkdir(parents=True, exist_ok=True)
for spec in json.loads(SPEC.read_text('utf-8')):
    if not ONLY or spec['name'] in ONLY:
        build(spec)
