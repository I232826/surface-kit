#!/usr/bin/env python3
"""Score AWB methods on raw SBGGR10 frames against a known illuminant.
usage: awb-eval.py TRUE_RG TRUE_BG raw.bin [raw.bin ...]"""
import array, math, sys
W, H, BL = 1632, 1224, 16.0
PLANCK = [(0.880, 0.363), (0.528, 0.572), (0.454, 0.679), (0.456, 0.731)]
FLUO = [(0.787, 0.364), (0.691, 0.476), (0.526, 0.448)]
L = lambda p: (math.log2(p[0]), math.log2(p[1]))
pl = [L(p) for p in PLANCK]; fl = [L(p) for p in FLUO]

def seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    q = (a[0] + t * dx, a[1] + t * dy); return math.hypot(p[0] - q[0], p[1] - q[1]), q

def project(p):            # nearest point on the Planckian polyline
    return min((seg(p, pl[i], pl[i + 1]) for i in range(len(pl) - 1)))[1]

def ldist(p):
    return min([min(seg(p, pl[i], pl[i + 1])[0] for i in range(len(pl) - 1))] +
               [math.hypot(p[0] - f[0], p[1] - f[1]) for f in fl])

def cells(fn):
    raw = array.array("H"); raw.frombytes(open(fn, "rb").read()); out = []
    for y in range(0, H, 4):            # every other cell row/col, like SwStats
        o0 = y * W; o1 = o0 + W
        for x in range(0, W, 4):
            if max(raw[o0 + x], raw[o0 + x + 1], raw[o1 + x], raw[o1 + x + 1]) >= 1000: continue
            b = raw[o0 + x] - BL; g = (raw[o0 + x + 1] + raw[o1 + x]) / 2 - BL; r = raw[o1 + x + 1] - BL
            if g >= 8 and r > 0 and b > 0: out.append((r, g, b))
    return out

def m_greyworld(c):
    R = sum(x[0] for x in c); G = sum(x[1] for x in c); B = sum(x[2] for x in c)
    return L((R / G, B / G))

def m_greycand(c, band=0.15, wpow=0):
    R = G = B = 0
    for r, g, b in c:
        if ldist(L((r / g, b / g))) < band:
            w = (r + g + b) ** wpow; R += r * w; G += g * w; B += b * w
    return L((R / G, B / G)) if G else m_greyworld(c)

def m_bright(c, frac=0.02):
    s = sorted(c, key=lambda x: -(x[0] + x[1] + x[2]))[:max(1, int(len(c) * frac))]
    return L((sum(x[0] for x in s) / sum(x[1] for x in s), sum(x[2] for x in s) / sum(x[1] for x in s)))

def m_bright_cand(c, frac=0.10, band=0.15):
    """brightest grey candidates: highlights that could be grey"""
    cand = [x for x in c if ldist(L((x[0] / x[1], x[2] / x[1]))) < band]
    return m_bright(cand, frac) if cand else m_greyworld(c)

true = L((float(sys.argv[1]), float(sys.argv[2])))
methods = {
    "greyworld": m_greyworld,
    "greycand": m_greycand,
    "greycand w=Y^2": lambda c: m_greycand(c, wpow=2),
    "bright 2%": m_bright,
    "bright 2% ->locus": lambda c: project(m_bright(c)),
    "bright cand 10%": m_bright_cand,
    "bright cand 10% ->locus": lambda c: project(m_bright_cand(c)),
    "bright cand 3% ->locus": lambda c: project(m_bright_cand(c, 0.03)),
}
data = [(fn.rsplit("/", 2)[-2], cells(fn)) for fn in sys.argv[3:]]
print(f"{'method':26s}" + "".join(f"{n:>22s}" for n, _ in data) + "   (error in % of colour, gains R/B)")
for name, f in methods.items():
    row = f"{name:26s}"
    for _, c in data:
        e = f(c); err = 100 * (2 ** math.hypot(e[0] - true[0], e[1] - true[1]) - 1)
        row += f"   {err:5.1f}% {2**-e[0]:4.2f}/{2**-e[1]:4.2f}"
    print(row)
