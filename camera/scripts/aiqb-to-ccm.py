#!/usr/bin/env python3
"""Print a libcamera simple-IPA 'Ccm' tuning block from the colour matrices
in a Windows AIQB/CPF tuning file (advanced_color_matrices record, the
'traditional' matrix per light source).  usage: aiqb-to-ccm.py FILE"""
import struct, sys

def cct(x, y):  # McCamy
    n = (x - 0.3320) / (0.1858 - y)
    return 449 * n**3 + 3525 * n**2 + 6823.3 * n + 5520.33

def ipa_cct(rg, bg):
    """CT libcamera's simple AWB reports for this light (libipa estimateCCT
    on the inverse gains = the sensor's R/G, 1, B/G). Keying the matrices by
    it, not by the true CT, makes the IPA pick the right one despite its
    generic RGB->XYZ guess (off by ~850 K under tungsten on the ov8865)."""
    m = ((-0.14282, 1.54924, -0.95641), (-0.32466, 1.57837, -0.73191),
         (-0.68202, 0.77073, 0.56332))
    xyz = [r[0] * rg + r[1] + r[2] * bg for r in m]
    return cct(xyz[0] / sum(xyz), xyz[1] / sum(xyz))

d = open(sys.argv[1], "rb").read()
d = d[d.index(b"AIQB"):]
o = 0x18
while o + 8 <= len(d):
    size, fmt, key, nid = struct.unpack_from("<IBBH", d, o)
    if size < 8: break
    if nid == 25: break
    o += size
else:
    sys.exit("no advanced_color_matrices record")
p = o + 8
nl, ns = struct.unpack_from("<HH", d, p); p += 4 + 4 * ns
mats = []
for _ in range(nl):
    t, rg, bg, x, y = struct.unpack_from("<I4f", d, p); p += 20
    m = struct.unpack_from("<9f", d, p); p += 36 + 36 * ns
    # skip fluorescent references (cmc_light_source f1..f12 = 9..20): they
    # sit off the Planckian locus, and the IPA blends matrices by CT only
    if x > 0 and y > 0 and not 9 <= t <= 20:
        mats.append((round(ipa_cct(rg, bg) / 10) * 10, t, m, round(cct(x, y))))
mats.sort()
print("  # colour matrices from the Windows driver's tuning file")
print(f"  # ({sys.argv[1].rsplit('/', 1)[-1]}), daylight/tungsten light sources")
print("  - Ccm:")
print("      ccms:")
seen = set()
for ct, t, m, true_ct in mats:
    if ct in seen: continue
    seen.add(ct)
    print(f"        - ct: {ct}   # source {t}, true {true_ct} K")
    print("          ccm: [ " + ",\n                 ".join(", ".join(f"{v:7.4f}" for v in m[r*3:r*3+3]) for r in range(3)) + " ]")
