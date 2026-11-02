#!/usr/bin/env python3
"""Which sites of the 2x2 Bayer cell are green? They match in brightness and
detail. Reads one raw 16-bit frame from `cam --stream role=raw --file=...`.
usage: bayer-sites.py frame.bin [width height]"""
import sys
from array import array

W = int(sys.argv[2]) if len(sys.argv) > 2 else 2592
H = int(sys.argv[3]) if len(sys.argv) > 3 else 1944
BLACK = 16
a = array("H")
a.frombytes(open(sys.argv[1], "rb").read())
print("max", max(a), "mean %.1f" % (sum(a) / len(a)))
cells = []
for y in range(0, H - 16, 16):
    r0, r1 = y * W, (y + 1) * W
    for x in range(0, W - 2, 8):
        c = (a[r0 + x], a[r0 + x + 1], a[r1 + x], a[r1 + x + 1])
        if max(c) < 900:
            cells.append(c)
n = len(cells)
names = ["p00", "p01", "p10", "p11"]
m = [sum(c[i] for c in cells) / n - BLACK for i in range(4)]
for i in range(4):
    print(names[i], "mean-black %.1f" % m[i])
d = [[cells[k + 1][i] - cells[k][i] for k in range(n - 1)] for i in range(4)]


def corr(u, v):
    mu, mv = sum(u) / len(u), sum(v) / len(v)
    su = sum((x - mu) ** 2 for x in u)
    sv = sum((y - mv) ** 2 for y in v)
    return sum((x - mu) * (y - mv) for x, y in zip(u, v)) / (su * sv) ** 0.5


for i in range(4):
    for j in range(i + 1, 4):
        print(names[i], names[j], "corr %.4f ratio %.3f" % (corr(d[i], d[j]), m[i] / m[j]))
