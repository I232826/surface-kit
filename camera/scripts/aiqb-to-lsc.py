#!/usr/bin/env python3
"""Fit a libcamera simple-IPA 'Lsc' block (radial gain 1 + k1 r^2 + k2 r^4 per
channel, r relative to half the image width) to the lens shading tables in a
Windows AIQB/CPF tuning file (lsc_4x4 record: one 63x47 grid per channel for
each light source).  usage: aiqb-to-lsc.py FILE"""
import struct
import sys

d = open(sys.argv[1], "rb").read()
d = d[d.index(b"AIQB"):]
o = 0x18
while True:
    size, fmt, key, nid = struct.unpack_from("<IBBH", d, o)
    if nid == 28:
        break
    o += size
p = o + 8 + 16
ngrids, chans, W, H = struct.unpack_from("<4H", d, p)
p += 8
print(f"{ngrids} light sources, {chans} channels, {W}x{H}")


def fit(xs, ys):
    """least squares y - 1 = k1 x + k2 x^2"""
    a = sum(x * x for x in xs); b = sum(x ** 3 for x in xs); c = sum(x ** 4 for x in xs)
    e = sum(x * (y - 1) for x, y in zip(xs, ys)); f = sum(x * x * (y - 1) for x, y in zip(xs, ys))
    det = a * c - b * b
    return (e * c - f * b) / det, (a * f - b * e) / det


results = []
for g in range(ngrids):
    src, rg, bg = struct.unpack_from("<I2f", d, p)
    t = p + 22
    tables = []
    for ch in range(chans):
        tables.append(struct.unpack_from(f"<{W * H}H", d, t + ch * W * H * 2))
    p += 22 + chans * W * H * 2
    cx, cy = (W - 1) / 2, (H - 1) / 2
    out = []
    # channels R, Gr, Gb, B: normalise to the table's own centre
    for ch in range(chans):
        tb = tables[ch]
        c = sum(tb[int(cy + dy) * W + int(cx + dx)] for dy in (-1, 0, 1) for dx in (-1, 0, 1)) / 9
        xs, ys = [], []
        for y in range(H):
            for x in range(W):
                r2 = ((x - cx) ** 2 + (y - cy) ** 2) / cx ** 2
                xs.append(r2)
                ys.append(tb[y * W + x] / c)
        out.append((c, tb[0] / c, fit(xs, ys)))
    print(f"source {src} R/G {rg:.3f} B/G {bg:.3f}  centre " + " ".join(f"{x[0]:.0f}" for x in out)
          + "  corner " + " ".join(f"{x[1]:.2f}" for x in out))
    results.append((rg, bg, out))
names = ["R", "Gr", "Gb", "B"]
for rg, bg, out in results:
    print(f"R/G {rg:.3f}: " + "  ".join(f"{n} k1 {x[2][0]:+.3f} k2 {x[2][1]:+.3f}" for n, x in zip(names, out)))
