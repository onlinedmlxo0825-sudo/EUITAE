"""Multi-clip vlog -> CapCut project, reusing the smartdaddy skill's Builder.

usage: python -I vlog_build.py <skill_scripts_dir> <plan.json> [--install]

plan.json:
{
  "name": "project name", "template": "<CapCut project folder>", "asr_root": "D:/.../01_asr",
  "staging": "D:/.../03_capcut", "sub_scale": 0.62,
  "segments": [{"file": "D:/.../clip.mp4", "in": 12.3, "out": 18.0, "subs": true, "label": "why"}],
  "texts": [{"at": 3.0, "dur": 2.0, "text": "caption", "x": 0.5, "y": 0.2, "size": 1.4}],
  "replace": {"wrong": "right"},
  "sub_max": [20, 26, 22],
  "cap_scale": 0.6,
  "cap_style": {"font": "C:/Windows/Fonts/Hancom Gothic Bold.ttf", "color": [1, 0.86, 0.2], "stroke": [0, 0, 0], "stroke_width": 0.1}
}
"""
import copy
import json
import sys
import time
from pathlib import Path

skill = Path(sys.argv[1])
plan_path = Path(sys.argv[2]).resolve()
do_install = '--install' in sys.argv
sys.dont_write_bytecode = True
sys.path.insert(0, str(skill))
import _common as C  # noqa: E402
import capcut_build as CB  # noqa: E402

C.setup_console()
C.need_ffmpeg()
P = json.loads(plan_path.read_text('utf-8'))
name = P['name']
tpl_dir = Path(P['template'])
tpl = CB.Template(tpl_dir)
if not tpl.vid or not tpl.txt:
    C.die('template needs a video clip and a text clip')


def synth_audio_template(tpl):
    """Template has no audio clip: derive a local-file audio clip (type extract_music) from the video clip.
    Only audio-relevant refs are kept; library ids stay empty so CapCut can't swap the sound."""
    seg = copy.deepcopy(tpl.vid[0])
    refs = {r: v for r, v in tpl.vid[2].items()
            if v[0] in ('speeds', 'sound_channel_mappings', 'vocal_separations', 'placeholder_infos', 'beats')}
    seg.update(clip=None, uniform_scale=None, hdr_settings=None, extra_material_refs=list(refs))
    mat = dict(app_id=0, category_id='', category_name='local', check_flag=1, copyright_limit_type='none', duration=0,
               effect_id='', formula_id='', id='', intensifies_path='', is_ai_clone_tone=False, is_text_edit_overdub=False,
               is_ugc=False, local_material_id='', music_id='', name='', path='', query='', request_id='',
               resource_id='', search_id='', source_from='', source_platform=0, team_id='', text_id='',
               third_resource_id='', tone_category_id='', tone_category_name='', tone_effect_id='', tone_effect_name='',
               tone_platform='', tone_second_category_id='', tone_second_category_name='', tone_speaker='', tone_type='',
               type='extract_music', video_id='', wave_points=[])
    return seg, mat, refs


if not tpl.aud and (P.get('sfx_dir') or any(s.get('sfx') or s.get('cap_sfx') for s in P['segments'])):
    tpl.aud = synth_audio_template(tpl)
sfx_dir = Path(P.get('sfx_dir', '.'))
b = CB.Builder(tpl)
D = b.D
cv = D.get('canvas_config', {})
asr_root = Path(P['asr_root'])
replace = P.get('replace') or {}
sub_scale = P.get('sub_scale')
if P.get('sub_max'):          # [split target, hard max, keep-one-line max] characters per subtitle
    CB.MAXC, CB.HARD, CB.ONE_LINE = P['sub_max']

words_cache = {}


def words_for(f):
    stem = Path(f).stem
    if stem not in words_cache:
        wp = asr_root / stem / 'words.json'
        words_cache[stem] = CB.load_words(wp) if wp.exists() else []
    return words_cache[stem]


def fade_kf(src0_us, dur_us, fin, fout):
    """Alpha keyframes: fade in over fin s, out over fout s. Offsets are source-based (src0 + t)."""
    pts = [(0, 0.0 if fin else 1.0)]
    if fin:
        pts.append((C.us(fin), 1.0))
    if fout:
        pts += [(dur_us - C.us(fout), 1.0), (dur_us, 0.0)]
    else:
        pts.append((dur_us, 1.0))
    return [CB.kf('KFTypeAlpha', [(src0_us + o, v) for o, v in pts])]


t = 0.0
timeline, cues_all, scales, sfx_all, seg_starts = [], [], {}, [], {}
photo_files = set()
for i, s in enumerate(P['segments']):
    f = Path(s['file'])
    info = C.media_info(f)
    is_photo = info['kind'] == 'photo'
    if is_photo:                      # still picture on the main track: {"file": "x.jpg", "dur": 4.0}
        src_in, src_out = 0.0, float(s['dur'])
    else:
        src_in = max(0.0, float(s['in']))
        src_out = min(float(s['out']), info['duration'])
    if src_out - src_in < 0.1:
        print(f'[skip] {f.name} {src_in}-{src_out}')
        continue
    if f not in scales:
        scales[f] = CB.cover_scale(info, cv) if info['width'] >= info['height'] else 1.0
    st_us, en_us = C.us(t), C.us(t + (src_out - src_in))
    # one material per clip, like CapCut itself: when many clips share one material, CapCut splits it on open
    # and resets some clips' source start to 0 (seen in v008: 10 GoPro clips played from the file start)
    b.mats.pop((f.resolve().as_posix(), 'video'), None)
    vs = b.put_video('메인', f, st_us, en_us - st_us, C.us(src_in), scales[f], float(s.get('vol', 1.0)))
    if is_photo:
        b.mats[(f.resolve().as_posix(), 'video')][0].update(type='photo', duration=10800000000, has_audio=False)
        photo_files.add(f.resolve().as_posix())
    if s.get('fade'):                 # [fade-in s, fade-out s] through black
        vs['common_keyframes'] = fade_kf(C.us(src_in), en_us - st_us, *s['fade'])
    if s.get('black'):                # hold on black (clip fully transparent, silent)
        vs['common_keyframes'] = [CB.kf('KFTypeAlpha', [(C.us(src_in), 0.0), (C.us(src_in) + en_us - st_us, 0.0)])]
        vs['volume'] = 0.0
    seg_starts.setdefault(s.get('label', ''), t)
    seg_end = en_us / C.US
    for x in s.get('titles') or []:   # title texts tied to this clip: {"text","at","dur","y","size","scale","style","fade"}
        P.setdefault('texts', []).append(dict(x, at=round(t + float(x.get('at', 0.0)), 3),
                                              dur=float(x.get('dur', src_out - src_in)), track='타이틀'))
    for x in s.get('notes') or []:    # extra captions anywhere on screen: {"text","src"|"at","dur","x","y","scale","style"}
        off = float(x['src']) - src_in if 'src' in x else float(x.get('at', 0.0))
        P.setdefault('texts', []).append(dict(x, at=round(t + off, 3), dur=float(x.get('dur', 2.5)),
                                              scale=x.get('scale', P.get('cap_scale')), track='강조 글자'))
        if x.get('sfx'):
            sfx_all.append(dict(at=t + off, name=x['sfx'], db=float(x.get('sfx_db', -20)), label=x['text']))
    if s.get('subs', True):
        ws = [(t + max(0.0, w0 - src_in), t + min(src_out - src_in, max(0.05, w1 - src_in)), w)
              for w0, w1, w in words_for(f) if src_in <= (w0 + w1) / 2 < src_out]
        for c0, c1, txt in CB.make_cues(ws, replace):
            if c0 < seg_end - 0.3:
                cues_all.append([c0, min(c1, seg_end - 0.02), txt])
    if s.get('caption'):
        cd = float(s.get('cap_dur', 2.5))
        cat = (seg_end - cd) if s.get('cap_end') else t + float(s.get('cap_offset', 0.2))
        P.setdefault('texts', []).append(dict(at=round(cat, 3), dur=cd, text=s['caption'], x=s.get('cap_x', 0.5),
                                              y=s.get('cap_y', 0.12), size=s.get('cap_size', 1.0),
                                              scale=s.get('cap_scale', P.get('cap_scale')),
                                              style=P.get('cap_styles', {}).get(s.get('cap_kind', ''))))
        if s.get('cap_sfx'):          # sound on the caption's first frame
            sfx_all.append(dict(at=cat, name=s['cap_sfx'], db=float(s.get('cap_sfx_db', -20)), label=s['caption']))
    for x in s.get('sfx') or []:      # {"name": "ding", "at": seconds into this clip | "src": source seconds, "db": -20}
        off = float(x['src']) - src_in if 'src' in x else float(x.get('at', 0.0))
        if 0 <= off < src_out - src_in:
            sfx_all.append(dict(at=t + off, name=x['name'], db=float(x.get('db', -20)), label=s.get('label', '')))
    timeline.append(dict(n=len(timeline) + 1, start=round(t, 3), dur=round(src_out - src_in, 3), file=f.name,
                         src_in=round(src_in, 3), src_out=round(src_out, 3), label=s.get('label', '')))
    t = seg_end
total = t

def text_mat(seg):
    return next(x for x in D['materials']['texts'] if x['id'] == seg['material_id'])


def apply_box(m, box):
    """Rectangle behind the text (CapCut text background). box = {"color": "#000000", "alpha": 0.55, "radius": 0.2}"""
    m.update(background_style=1, background_color=box.get('color', '#000000'),
             background_alpha=float(box.get('alpha', 0.55)), background_round_radius=float(box.get('radius', 0.0)),
             background_width=float(box.get('pad_x', 0.14)), background_height=float(box.get('pad_y', 0.14)),
             background_horizontal_offset=0.0, background_vertical_offset=0.0,
             check_flag=m.get('check_flag', 7) | 16)


for c0, c1, txt in cues_all:
    seg = b.put_text('자막', txt, C.us(c0), C.us(c1) - C.us(c0))
    if sub_scale:
        seg.setdefault('clip', {})['scale'] = dict(x=sub_scale, y=sub_scale)
    if P.get('sub_y') is not None:    # vertical position, CapCut transform units (-1 = bottom edge)
        seg.setdefault('clip', {}).setdefault('transform', {'x': 0.0, 'y': 0.0})['y'] = float(P['sub_y'])
    if P.get('sub_box'):
        apply_box(text_mat(seg), P['sub_box'])

def hexcol(rgb):
    return '#' + ''.join(f'{round(v * 255):02X}' for v in rgb)


def style_caption(seg, cs):
    """Give an emphasis text its own look (font, fill, outline) instead of the subtitle preset.
    cs = {"font": "<ttf/otf path>", "color": [r,g,b], "stroke": [r,g,b], "stroke_width": 0.1}"""
    m = next(x for x in D['materials']['texts'] if x['id'] == seg['material_id'])
    c = json.loads(m['content'])
    fill, stroke, sw = cs.get('color', [1, 1, 1]), cs.get('stroke', [0, 0, 0]), float(cs.get('stroke_width', 0.1))
    for st in c['styles']:
        st.pop('effectStyle', None)                      # the subtitle preset would override fill/outline
        st['fill'] = dict(alpha=1.0, content=dict(render_type='solid', solid=dict(alpha=1.0, color=fill)))
        st['strokes'] = [dict(alpha=1.0, content=dict(render_type='solid', solid=dict(alpha=1.0, color=stroke)),
                              width=sw)]
        if cs.get('font'):
            st['font'] = dict(path=Path(cs['font']).as_posix(), id='')
    # accent: some characters in another color, e.g. {"chars": "[]", "color": [1, 0.29, 0.17]} → "[" "]" coloured
    acc = cs.get('accent')
    if acc and c['styles']:
        base, text, runs = c['styles'][0], c['text'], []
        for i, ch in enumerate(text):        # Korean/ASCII are 1 UTF-16 unit each
            on = ch in acc['chars']
            if runs and runs[-1][0] == on:
                runs[-1][2] = i + 1
            else:
                runs.append([on, i, i + 1])
        styles = []
        for on, a, z in runs:
            st = copy.deepcopy(base)
            st['range'] = [a, z]
            if on:
                st['fill'] = dict(alpha=1.0, content=dict(render_type='solid', solid=dict(alpha=1.0, color=acc['color'])))
            styles.append(st)
        c['styles'] = styles
    m['content'] = json.dumps(c, ensure_ascii=False)
    m.update(text_color=hexcol(fill), border_color=hexcol(stroke), border_width=sw, border_alpha=1.0,
             use_effect_default_color=False, check_flag=m.get('check_flag', 7) | 8)
    if cs.get('font'):
        m.update(font_path=Path(cs['font']).as_posix(), font_id='', font_resource_id='', font_title='none',
                 font_name=Path(cs['font']).stem)


for o in P.get('texts', []):
    seg = b.put_text(o.get('track', '강조 글자'), o['text'], C.us(o['at']), C.us(o['dur']),
                     emphasis=(o.get('x', 0.5), o.get('y', 0.5), o.get('size', 1.0)))
    if o.get('scale'):
        seg.setdefault('clip', {})['scale'] = dict(x=o['scale'], y=o['scale'])
    if o.get('style') or P.get('cap_style'):
        cs = dict(P.get('cap_style') or {}, **(o.get('style') or {}))
        style_caption(seg, cs)
        if cs.get('box'):
            apply_box(text_mat(seg), cs['box'])
    if o.get('fade'):
        seg['common_keyframes'] = fade_kf(0, C.us(o['dur']), *o['fade'])

# picture overlays spanning labelled clips, e.g. the highlight letterbox:
# {"file": "x.png", "from_label": "...", "to_label": "...", "track": "하이라이트 표시"}
for ov in P.get('overlays', []):
    f = Path(ov['file']).resolve()
    st = seg_starts[ov['from_label']]
    en = seg_starts[ov['to_label']] if ov.get('to_label') else total
    m, info = b.material(f, 'video')
    m.update(type='photo', duration=10800000000, has_audio=False)
    b.put_video(ov.get('track', '하이라이트 표시'), f, C.us(st), C.us(en) - C.us(st), 0, 1.0, 0.0)
    photo_files.add(f.as_posix())

# background music over labelled ranges, looped: {"file": mp3, "from_label", "to_label", "db": -32, "from": src start s}
bgm_files = set()
for bg in P.get('bgm', []):
    f = Path(bg['file']).resolve()
    fdur = C.media_info(f)['duration']
    st = seg_starts[bg['from_label']]
    en = seg_starts[bg['to_label']] if bg.get('to_label') else total
    s0, tt = float(bg.get('from', 0.0)), st
    chunks = []
    while en - tt > 0.05:
        du = min(fdur - s0, en - tt)
        b.mats.pop((f.as_posix(), 'audio'), None)
        chunks.append(b.put_audio(b.free_track('BGM', 'audio', C.us(tt), C.us(du)), f, C.us(tt), C.us(du), C.us(s0),
                                  round(10 ** (float(bg.get('db', -32)) / 20), 4)))
        tt += du
        s0 = 0.0
    # fade the music in where the scene starts and out where it ends (CapCut audio_fades)
    fin, fout = C.us(float(bg.get('fade_in', 1.5))), C.us(float(bg.get('fade_out', 2.0)))
    for k, seg in enumerate(chunks):
        a_in = fin if k == 0 else 0
        a_out = fout if k == len(chunks) - 1 else 0
        if a_in or a_out:
            fm = dict(id=CB.uid(), fade_in_duration=a_in, fade_out_duration=a_out, fade_type=0, type='audio_fade')
            D['materials'].setdefault('audio_fades', []).append(fm)
            seg['extra_material_refs'].append(fm['id'])
    bgm_files.add(f)

sfx_files = set()
for x in sorted(sfx_all, key=lambda x: x['at']):
    f = (sfx_dir / f"{x['name']}.wav").resolve()
    if not f.exists():
        C.die(f'sound file not found: {f}')
    du = min(C.media_info(f)['duration'], total - x['at'])
    if du <= 0.02:
        continue
    st_us = C.us(x['at'])
    b.mats.pop((f.as_posix(), 'audio'), None)
    b.put_audio(b.free_track('효과음', 'audio', st_us, C.us(du)), f, st_us, C.us(du), 0, round(10 ** (x['db'] / 20), 4))
    sfx_files.add(f)
    x['at'] = round(x['at'], 3)

for x in D['tracks']:
    x['segments'].sort(key=lambda s: s['target_timerange']['start'])
order = {'video': 0, 'text': 1, 'audio': 2}
D['tracks'].sort(key=lambda x: (order.get(x['type'], 9), x['name'] != '자막'))
for i, x in enumerate(D['tracks']):
    for s in x['segments']:
        s['track_render_index'] = i
        s['render_index'] = i if x['type'] in ('video', 'text') else 0

cc = C.find_capcut_dir(None, required=True)
dest = cc / name
now = int(time.time())
D.update(id=CB.uid(), name=name, duration=C.us(total), path=dest.as_posix(), create_time=now, update_time=now,
         static_cover_image_path='', keyframe_graph_list=[], time_marks=None, relationships=[], group_container=None,
         cover=None, retouch_cover=None)
D['keyframes'] = {k: [] for k in D.get('keyframes', {})} if isinstance(D.get('keyframes'), dict) else D.get('keyframes')
fai = D.get('function_assistant_info')
if isinstance(fai, dict):
    for k, v in fai.items():
        if isinstance(v, list):
            fai[k] = []

stage_root = Path(P['staging'])
stage_root.mkdir(parents=True, exist_ok=True)
stage = stage_root / name
media_paths = sorted({Path(s['file']) for s in P['segments']} | sfx_files | bgm_files)
cover = P.get('cover') or [P['segments'][0]['file'], P['segments'][0]['in'] + 0.5]
CB.write_staging(b, tpl, stage, name, dest, media_paths, (Path(cover[0]), float(cover[1])))
if photo_files:                      # media list: mark pictures as photos, not videos
    mp = stage / 'draft_meta_info.json'
    meta = C.read_json(mp)
    for g in meta.get('draft_materials', []):
        for it in g.get('value', []):
            if Path(it.get('file_Path', '')).as_posix() in photo_files:
                it.update(metetype='photo', duration=10800000000)
    C.write_json(mp, meta, compact=True)
(stage_root / f'{name}.srt').write_text('\n'.join(f'{k + 1}\n{CB.srt_time(c0)} --> {CB.srt_time(c1)}\n{txt}\n'
                                                  for k, (c0, c1, txt) in enumerate(cues_all)), 'utf-8-sig')
C.write_json(stage_root / f'{name}_timeline.json', dict(name=name, total=round(total, 3), clips=timeline,
                                                         subtitles=[[round(x, 3), round(y, 3), z] for x, y, z in cues_all],
                                                         texts=P.get('texts', []), sfx=sfx_all))
ntr = {x['name']: len(x['segments']) for x in D['tracks']}
print(f'built: {name} · {C.mmss(total)} · tracks {ntr} · canvas {cv.get("width")}x{cv.get("height")}')
print(f'  staging: {stage}')
if do_install:
    sys.exit(CB.install(stage, cc, name, stage_root / 'backups'))
