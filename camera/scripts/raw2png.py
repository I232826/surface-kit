#!/usr/bin/env python3
"""Turn the last frame of a V4L2 BG10 capture into a quick-look PNG.

BG10 = 10-bit Bayer BGGR, one sample per little-endian 16-bit word. Each
2x2 BGGR cell becomes one RGB pixel (half resolution, no interpolation),
with a percentile auto-stretch and per-channel gray-world balance. Meant to
prove "real image", not to look good: that's libcamera's soft ISP's job.

usage: raw2png.py capture.raw WIDTH HEIGHT out.png
"""
import sys
from array import array

from PIL import Image


def main():
    raw, w, h, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
    frame_bytes = w * h * 2
    data = open(raw, "rb").read()
    nframes = len(data) // frame_bytes
    if nframes == 0:
        sys.exit(f"{raw}: {len(data)} bytes, smaller than one {w}x{h} frame")
    px = array("H")
    px.frombytes(data[(nframes - 1) * frame_bytes:nframes * frame_bytes])
    if sys.byteorder != "little":
        px.byteswap()

    hw, hh = w // 2, h // 2
    r, g, b = array("H", bytes(hw * hh * 2)), array("H", bytes(hw * hh * 2)), array("H", bytes(hw * hh * 2))
    for y in range(hh):
        row0, row1, o = 2 * y * w, (2 * y + 1) * w, y * hw
        for x in range(hw):
            b[o + x] = px[row0 + 2 * x]
            g[o + x] = (px[row0 + 2 * x + 1] + px[row1 + 2 * x]) >> 1
            r[o + x] = px[row1 + 2 * x + 1]

    lo, hi = min(px), max(px)
    print(f"{nframes} frame(s); last frame sample range {lo}..{hi} (10-bit max 1023)")

    def sample(ch):
        return sorted(ch[:: max(1, len(ch) // 20000)])

    def mean(s):
        return (sum(s) / len(s)) or 1

    # Gray world: scale R and B so their means match G, then stretch all
    # three over G's 1st..99th percentile.
    gs = sample(g)
    p_lo, p_hi = gs[len(gs) // 100], gs[-len(gs) // 100 - 1]
    span = max(1, p_hi - p_lo)

    def stretch(ch, gain):
        return bytes(min(255, max(0, int((v * gain - p_lo) * 255 / span))) for v in ch)

    gains = [mean(gs) / mean(sample(c)) for c in (r, g, b)]
    print("gray-world gains R/G/B: " + " ".join(f"{k:.2f}" for k in gains))
    img = Image.merge("RGB", [Image.frombytes("L", (hw, hh), stretch(c, k))
                              for c, k in zip((r, g, b), gains)])
    img.save(out)
    print(f"wrote {out} ({hw}x{hh})")


if __name__ == "__main__":
    main()
