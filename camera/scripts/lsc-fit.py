#!/usr/bin/env python3
"""Fit the radial lens shading model for libcamera's Lsc algorithm.

Takes a raw full-resolution BGGR10 frame (16-bit unpacked, as written by
`cam --stream=width=3264,height=2448,role=raw`) of a flat white field, e.g.
white paper held against the lens with light behind it, and fits per
channel the gain 1 + k1 r^2 + k2 r^4 that flattens it, with r the distance
from the centre over half the image width (the convention Lsc uses).

usage: lsc-fit.py frame.bin [width height [ORDER]]   (default 3264 2448 BGGR;
       GBRG is the Surface Pro 7 front camera with mirror=1)
"""
import math
import sys
from array import array

BLACK = 16           # ov8865 black level, 10-bit (measured; the driver sets 16)
GRID = 24            # blocks across the width


def main():
    path = sys.argv[1]
    w, h = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) >= 4 else (3264, 2448)
    order = sys.argv[4] if len(sys.argv) >= 5 else "BGGR"
    a = array("H")
    a.frombytes(open(path, "rb").read())
    if len(a) < w * h:
        sys.exit(f"short frame: {len(a)} samples, want {w * h}")

    bw = (w // GRID) & ~1
    bh = bw
    half = w / 2.0
    sites = {"r": [], "g": [], "b": []}
    for site, ch in zip([(0, 0), (0, 1), (1, 0), (1, 1)], order.lower()):
        sites[ch].append(site)
    planes = sites
    blocks = []      # (r^2, {ch: mean})
    for by in range(0, h - bh + 1, bh):
        for bx in range(0, w - bw + 1, bw):
            means = {}
            for ch, offs in planes.items():
                total = n = 0
                for oy, ox in offs:
                    for y in range(by + oy, by + bh, 2 * 4):      # every 4th pair of rows
                        row = y * w
                        for x in range(bx + ox, bx + bw, 2 * 4):
                            total += a[row + x] - BLACK
                            n += 1
                means[ch] = total / max(n, 1)
            cx, cy = bx + bw / 2 - w / 2, by + bh / 2 - h / 2
            blocks.append(((cx * cx + cy * cy) / (half * half), means))

    peak = max(m["g"] for _, m in blocks) + BLACK
    if peak > 1000:
        print("warning: some of the frame is clipped; use less light", file=sys.stderr)

    out = {}
    for ch in "rgb":
        centre = sorted(blocks, key=lambda b: b[0])[:4]
        c = sum(m[ch] for _, m in centre) / len(centre)
        # least squares for gain - 1 = k1 x + k2 x^2, x = r^2
        sxx = sxx2 = sx2x2 = sxy = sx2y = 0.0
        for x, m in blocks:
            if m[ch] <= 1:
                continue
            y = c / m[ch] - 1.0
            sxx += x * x
            sxx2 += x * x * x
            sx2x2 += x ** 4
            sxy += x * y
            sx2y += x * x * y
        det = sxx * sx2x2 - sxx2 * sxx2
        k1 = (sxy * sx2x2 - sx2y * sxx2) / det
        k2 = (sxx * sx2y - sxx2 * sxy) / det
        worst = max(c / m[ch] for _, m in blocks if m[ch] > 1)
        out[ch] = (k1, k2)
        print(f"{ch}: centre {c:6.1f}  corner falloff x{worst:4.2f}  k1 {k1:+.4f}  k2 {k2:+.4f}")

    print("\n  - Lsc:")
    print(f"      k1: [ {out['r'][0]:.4f}, {out['g'][0]:.4f}, {out['b'][0]:.4f} ]")
    print(f"      k2: [ {out['r'][1]:.4f}, {out['g'][1]:.4f}, {out['b'][1]:.4f} ]")


if __name__ == "__main__":
    main()
