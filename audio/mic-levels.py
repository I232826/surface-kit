#!/usr/bin/env python3
"""Peak, clipping, speech and noise levels of mic test recordings.
usage: mic-levels.py file.wav ..."""
import math, struct, sys, wave
for f in sys.argv[1:]:
    w = wave.open(f)
    n, ch = w.getnframes(), w.getnchannels()
    data = struct.unpack("<%dh" % (n * ch), w.readframes(n))
    x = [data[i] for i in range(0, len(data), ch)]  # left
    x = x[len(x) // 10:]  # skip start
    peak = max(abs(v) for v in x) or 1
    clip = sum(1 for v in x if abs(v) >= 32700)
    blk = 960  # 20 ms
    rms = sorted(math.sqrt(sum(v * v for v in x[i:i + blk]) / blk) + 1e-9
                 for i in range(0, len(x) - blk, blk))
    db = lambda v: 20 * math.log10(v / 32768)
    print(f"{f.rsplit('/', 1)[-1]:12} peak {db(peak):6.1f} dBFS  clipped {clip:5d}  "
          f"speech(90%) {db(rms[len(rms) * 9 // 10]):6.1f}  noise(10%) {db(rms[len(rms) // 10]):6.1f}  "
          f"SNR {db(rms[len(rms) * 9 // 10]) - db(rms[len(rms) // 10]):5.1f} dB")
