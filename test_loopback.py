import numpy as np

_original_fromstring = np.fromstring
def _patched_fromstring(string, dtype=float, count=-1, sep=''):
    if sep == '':
        return np.frombuffer(string, dtype=dtype, count=count)
    return _original_fromstring(string, dtype=dtype, count=count, sep=sep)
np.fromstring = _patched_fromstring

import soundcard as sc

try:
    mic = sc.default_speaker()
    print("Speaker found:", mic.name)
    loopback = sc.get_microphone(id=str(mic.name), include_loopback=True)
    print("Loopback found:", loopback.name)
    with loopback.recorder(samplerate=16000, channels=1) as rec:
        print("Successfully opened! Reading 1000 frames...")
        data = rec.record(1000)
        print("Data shape:", data.shape)
except Exception as e:
    print("ERROR:", e)
