"""Print word timings for clip ranges. usage: python words_in.py <asr_root> <stem>:<from>-<to> ..."""
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
for spec in sys.argv[2:]:
    stem, rng = spec.split(':')
    a, b = (float(x) for x in rng.split('-'))
    W = json.loads((root / stem / 'words.json').read_text('utf-8'))
    ws = [w for w in W if a <= w[0] <= b]
    print(f'== {stem} {a}-{b}')
    print(' '.join(f'{w[2].strip()}@{w[0]:.1f}' for w in ws))
