#!/usr/bin/env python3
"""Prototype of grey-candidate AWB on a raw SBGGR10 frame (16-bit LE words).
Cells whose sensor chromaticity lies near the calibrated grey locus (the
sensor's R/G, B/G for neutral grey under known lights, from the Windows
tuning file) vote; everything else (saturated surfaces) is ignored.
usage: awb-proto.py raw.bin W H out_prefix [gainR gainB]"""
import array, math, sys
from PIL import Image

BL = 16.0
# rear ov8865 (OV8865_MSHW0191): sensor R/G, B/G of grey per light source
PLANCK = [(0.880, 0.363), (0.528, 0.572), (0.454, 0.679), (0.456, 0.731)]  # A, D50, D65, D75
FLUO = [(0.787, 0.364), (0.691, 0.476), (0.526, 0.448)]                     # TL83, F3, TL84
BAND = 0.15   # log2 units

raw = array.array("H"); raw.frombytes(open(sys.argv[1], "rb").read())
W, H = int(sys.argv[2]), int(sys.argv[3]); out = sys.argv[4]
L = lambda p: (math.log2(p[0]), math.log2(p[1]))
pl = [L(p) for p in PLANCK]; fl = [L(p) for p in FLUO]

def seg_dist(p, a, b):
    ax, ay = a; bx, by = b; px, py = p
    dx, dy = bx - ax, by - ay
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    qx, qy = ax + t * dx, ay + t * dy
    return math.hypot(px - qx, py - qy), (qx, qy)

def locus_dist(p):
    d = min(seg_dist(p, pl[i], pl[i + 1])[0] for i in range(len(pl) - 1))
    return min([d] + [math.hypot(p[0] - f[0], p[1] - f[1]) for f in fl])

cells = []
sr = sg = sb = 0.0; nacc = 0; ar = ag = ab = 0.0
for y in range(0, H, 2):
    o0 = y * W; o1 = o0 + W
    for x in range(0, W, 2):
        b = raw[o0 + x] - BL; g = (raw[o0 + x + 1] + raw[o1 + x]) / 2 - BL; r = raw[o1 + x + 1] - BL
        cells.append((r, g, b))
        if g < 24 or max(raw[o0 + x], raw[o1 + x + 1], raw[o0 + x + 1]) >= 1000 or r <= 0 or b <= 0:
            continue
        sr += r; sg += g; sb += b
        p = (math.log2(r / g), math.log2(b / g))
        if locus_dist(p) < BAND:
            ar += r; ag += g; ab += b; nacc += 1
ncell = len(cells)
gw = (sg / sr, sg / sb)
grey = (ag / ar, ag / ab) if nacc > 0.01 * ncell else gw
print(f"grey world gains R {gw[0]:.3f} B {gw[1]:.3f}")
print(f"grey-candidate gains R {grey[0]:.3f} B {grey[1]:.3f}  ({100 * nacc / ncell:.1f}% of cells voted)")

def est_cct(rg, bg):
    m = ((-0.14282, 1.54924, -0.95641), (-0.32466, 1.57837, -0.73191), (-0.68202, 0.77073, 0.56332))
    xyz = [r[0] * rg + r[1] + r[2] * bg for r in m]; s = sum(xyz); x, y = xyz[0] / s, xyz[1] / s
    n = (x - 0.3320) / (0.1858 - y); return 449 * n**3 + 3525 * n**2 + 6823.3 * n + 5520.33
CCMS = [(3130, (1.7509, -0.1451, -0.6058, -0.7199, 2.2316, -0.5117, -0.6516, -2.0728, 3.7244)),
        (4900, (1.8115, -0.5750, -0.2365, -0.3398, 1.8446, -0.5047, -0.0435, -0.8334, 1.8769)),
        (6030, (1.8887, -0.7241, -0.1646, -0.3123, 1.8719, -0.5596, -0.0246, -0.7024, 1.7270)),
        (6610, (1.8390, -0.7159, -0.1231, -0.2844, 1.7659, -0.4816, -0.0345, -0.5874, 1.6219))]
def ccm_for(ct):
    if ct <= CCMS[0][0]: return CCMS[0][1]
    if ct >= CCMS[-1][0]: return CCMS[-1][1]
    for (c0, m0), (c1, m1) in zip(CCMS, CCMS[1:]):
        if c0 <= ct <= c1:
            t = (ct - c0) / (c1 - c0); return tuple(a + (b - a) * t for a, b in zip(m0, m1))

def render(gains, name):
    ct = est_cct(1 / gains[0], 1 / gains[1]); M = ccm_for(ct)
    # exposure: put the median green at 0.18 linear
    gs = sorted(c[1] for c in cells[::7]); k = 0.18 / max(gs[len(gs) // 2], 1)
    img = Image.new("RGB", (W // 2, H // 2)); px = []
    for r, g, b in cells:
        r, g, b = r * gains[0] * k, g * k, b * gains[1] * k
        R = M[0] * r + M[1] * g + M[2] * b; G = M[3] * r + M[4] * g + M[5] * b; B = M[6] * r + M[7] * g + M[8] * b
        px.append(tuple(int(255 * min(1, max(0, v)) ** (1 / 2.2)) for v in (R, G, B)))
    img.putdata(px); img = img.rotate(180); img.save(f"{out}-{name}.png")
    print(f"  {name}: CT estimate {ct:.0f} K")

render(gw, "greyworld"); render(grey, "greycand")
if len(sys.argv) > 6:
    render((float(sys.argv[5]), float(sys.argv[6])), "manual")
