"""Copyright-free vlog sound effects, synthesized from scratch (48 kHz mono WAV).

Writes the smartdaddy skill's 7 basic sounds (snap, click, pop, whoosh, ding, tick, buzz)
plus two comic ones for vlogs:
  boing.wav   띠용  — 웃긴 순간(가루가 코로, 표정)
  wahwah.wav  빠밤빠~ (내려가는 트롬본) — 실패·허탈(바닥 걸림, 채비 날아감)
  cricket.wav 찌르르 (귀뚜라미) — 어색한 정적·머쓱한 순간

usage: python -I make_vlog_sfx.py <skill_scripts_dir> <out_dir>
"""
import sys
from pathlib import Path

import numpy as np

skill, out = Path(sys.argv[1]), Path(sys.argv[2])
sys.dont_write_bytecode = True
sys.path.insert(0, str(skill))
import make_sfx as M  # noqa: E402

SR = M.SR


def boing():
    d = 0.6
    t = M.t_(d)
    f = 180 + 260 * np.exp(-t / 0.12) * (1 + 0.35 * np.sin(2 * np.pi * 14 * t))   # wobbling spring
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.3 * np.sin(4 * np.pi * np.cumsum(f) / SR)
    return x * M.env(d, 0.004, 0.22)


def wahwah():
    out_ = []
    for f0, d in ((392.0, 0.28), (370.0, 0.28), (349.0, 0.28), (330.0, 0.9)):          # G4 F#4 F4 E4
        t = M.t_(d)
        vib = 1 + (0.012 * np.sin(2 * np.pi * 6 * t) if d > 0.5 else 0)
        ph = 2 * np.pi * np.cumsum(f0 * vib) / SR
        tone = sum(np.sin(k * ph) / k ** 0.8 for k in range(1, 7))                     # brassy harmonics
        wah = 0.55 + 0.45 * np.sin(np.pi * np.clip(t / d, 0, 1))                         # mute opening
        out_.append(tone * wah * np.clip(t / 0.02, 0, 1) * np.clip((d - t) / 0.05, 0, 1))
    return M.band(np.concatenate(out_), 120, 4000)


def cricket():
    """귀뚜라미 '찌르르 찌르르' — 어색한 정적·머쓱한 순간."""
    d = 1.6
    t = M.t_(d)
    x = np.zeros(len(t))
    for start in (0.05, 0.75):                      # two chirps
        for k in range(4):                          # each chirp = 4 quick pulses
            t0 = start + k * 0.055
            m = (t >= t0) & (t < t0 + 0.04)
            tt = t[m] - t0
            x[m] += np.sin(2 * np.pi * 4300 * tt) * np.sin(np.pi * tt / 0.04)
    return x


out.mkdir(parents=True, exist_ok=True)
sounds = dict(M.SOUNDS, boing=boing, wahwah=wahwah, cricket=cricket)
for name, fn in sounds.items():
    M.write(out / f'{name}.wav', fn())
print(f'{len(sounds)} sounds -> {out}: ' + ', '.join(sounds))
