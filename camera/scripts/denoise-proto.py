#!/usr/bin/env python3
"""Prototype of the GPU denoise pass on a processed (gamma) RGB image:
5x5 cross-bilateral, luma smoothed with weights from luma similarity
(sigma S), chroma averaged with a 3x wider luma tolerance so colour
speckles go but colours don't bleed across edges.
usage: denoise-proto.py in.png x0 y0 w h out.png sigma[,sigma...] [chroma_step]
chroma_step spreads the chroma taps (3: 5x5 taps over 13x13 pixels), as
chroma noise at high gain comes in clumps larger than 5x5."""
import math, sys
from PIL import Image, ImageDraw

im = Image.open(sys.argv[1]).convert("RGB")
x0, y0, w, h = map(int, sys.argv[2:6]); out = sys.argv[6]
sigmas = [float(s) for s in sys.argv[7].split(",")]
cs = int(sys.argv[8]) if len(sys.argv) > 8 else 1
M = 2 * cs
c = im.crop((x0 - M, y0 - M, x0 + w + M, y0 + h + M)); W = w + 2 * M
px = list(c.get_flattened_data()) if hasattr(c, 'get_flattened_data') else list(c.getdata())
Y = [0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px]
Cb = [b - y for (r, g, b), y in zip(px, Y)]; Cr = [r - y for (r, g, b), y in zip(px, Y)]
sp = {(dx, dy): math.exp(-(dx * dx + dy * dy) / (2 * 1.5 ** 2)) for dx in range(-2, 3) for dy in range(-2, 3)}
tiles = [(im.crop((x0, y0, x0 + w, y0 + h)), "now")]
for s in sigmas:
    res = []
    kl, kc = -1 / (2 * s * s), -1 / (2 * (3 * s) ** 2)
    for y in range(M, h + M):
        for x in range(M, w + M):
            i = y * W + x; yc = Y[i]
            sl = wl = sb = sr = wc = 0.0
            for (dx, dy), ws in sp.items():
                j = i + dy * W + dx; d = Y[j] - yc
                a = ws * math.exp(kl * d * d); sl += a * Y[j]; wl += a
                j = i + cs * (dy * W + dx); d = Y[j] - yc
                b = ws * math.exp(kc * d * d); sb += b * Cb[j]; sr += b * Cr[j]; wc += b
            yy = sl / wl; cb = sb / wc; cr = sr / wc
            r = yy + cr; b_ = yy + cb; g = (yy - 0.299 * r - 0.114 * b_) / 0.587
            res.append(tuple(max(0, min(255, int(round(v)))) for v in (r, g, b_)))
    t = Image.new("RGB", (w, h)); t.putdata(res); tiles.append((t, f"sigma {s:g}"))
g = Image.new("RGB", (w * 2 + 10, h * ((len(tiles) + 1) // 2) + 10 * (len(tiles) // 2)), (255, 255, 255))
for k, (t, lab) in enumerate(tiles):
    t = t.copy(); d = ImageDraw.Draw(t); d.rectangle((0, 0, len(lab) * 7 + 10, 18), fill=(0, 0, 0)); d.text((5, 4), lab, fill=(255, 255, 255))
    g.paste(t, ((k % 2) * (w + 10), (k // 2) * (h + 10)))
g.save(out)
