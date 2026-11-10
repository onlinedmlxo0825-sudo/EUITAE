"""Find which stage crashes: usage python -I -X faulthandler asr_probe.py <wav> <model> <stage>"""
import sys
import soundfile as sf
import numpy as np

wav, model_name, stage = sys.argv[1], sys.argv[2], sys.argv[3]
audio, sr = sf.read(wav, dtype='float32')
audio = audio[: sr * 30]
print('audio', audio.shape, sr, flush=True)
if stage == 'vad':
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    ts = get_speech_timestamps(audio, VadOptions())
    print('VAD OK', len(ts), flush=True)
    sys.exit(0)
from faster_whisper import WhisperModel
m = WhisperModel(model_name, device='cpu', compute_type='int8', cpu_threads=int(sys.argv[4]) if len(sys.argv) > 4 else 0)
print('load ok', flush=True)
segs, info = m.transcribe(audio, language='ko', beam_size=1, vad_filter=False, word_timestamps=(stage == 'words'))
for s in segs:
    print(round(s.start, 1), s.text, flush=True)
print('DECODE OK', flush=True)
