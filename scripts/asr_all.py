"""Transcribe every clip in a recordings folder with one Whisper model load.

usage: python -I asr_all.py <skill_scripts_dir> <recordings_root> <out_root> [model]
Writes <out_root>/<clip stem>/{audio16k.wav, words.json, segments.json, transcript.txt}
"""
import json
import sys
import time
from pathlib import Path

skill, root, out_root = map(Path, sys.argv[1:4])
model_name = sys.argv[4] if len(sys.argv) > 4 else 'large-v3-turbo'
sys.dont_write_bytecode = True
sys.path.insert(0, str(skill))
import _common as C  # noqa: E402

C.setup_console()
C.need_ffmpeg()
clips = sorted(p for p in root.rglob('*') if p.suffix.lower() == '.mp4' and '편집' not in p.parts)
clips = [p for p in clips if p.stem != 'GH010064']   # stray 6s clip from 11/3
print(f'{len(clips)} clips', flush=True)

model, dev = C.load_whisper(model_name, 'cpu')
T0 = time.time()
for i, media in enumerate(clips, 1):
    out = out_root / media.stem
    if (out / 'words.json').exists():
        print(f'[{i}/{len(clips)}] skip {media.name}', flush=True)
        continue
    out.mkdir(parents=True, exist_ok=True)
    wav = C.extract_wav16k(media, out / 'audio16k.wav')
    t0 = time.time()
    segs, _ = model.transcribe(str(wav), language='ko', word_timestamps=True, beam_size=5,
                               condition_on_previous_text=False, vad_filter=True,
                               vad_parameters=dict(min_silence_duration_ms=400, speech_pad_ms=150))
    S, W = [], []
    for s in segs:
        text = s.text.strip()
        if C.is_hallucination(text, '', exact_too=False):
            continue
        if C.norm_text(text) in C.HALLU_EXACT and (s.no_speech_prob > 0.3 or s.avg_logprob < -0.7):
            continue
        if s.no_speech_prob > 0.6 and s.avg_logprob < -0.8:
            continue
        S.append(dict(start=round(s.start, 3), end=round(s.end, 3), text=text,
                      no_speech=round(s.no_speech_prob, 3), logprob=round(s.avg_logprob, 3)))
        for w in (s.words or []):
            W.append([round(w.start, 3), round(w.end, 3), w.word])
    C.write_json(out / 'segments.json', S)
    C.write_json(out / 'words.json', W, compact=True)
    (out / 'transcript.txt').write_text(
        '\n'.join(f'[{C.mmss(s["start"])}-{C.mmss(s["end"])}] {s["text"]}' for s in S) + '\n', 'utf-8')
    (out / 'meta.json').write_text(json.dumps(dict(media=str(media), model=model_name), ensure_ascii=False), 'utf-8')
    print(f'[{i}/{len(clips)}] {media.name} · {len(S)} sentences · {time.time() - t0:.0f}s (total {time.time() - T0:.0f}s)',
          flush=True)
print('ALL DONE', flush=True)
