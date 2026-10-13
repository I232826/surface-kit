#!/usr/bin/env python3
"""List and decode records of an Intel AIQB / CPFF tuning file (Windows
IPU4 drivers). Record header: u32 size, u8 format, u8 key, u16 name_id
(cmc_name_id in Intel's ia_cmc_types.h for the CMC part).
usage: aiqb-dump.py file.aiqb [name_id ...]   (decode only those)"""
import struct, sys

CMC = ["reserved", "comment", "general_data", "black_level", "black_level_spatial",
       "saturation_level", "dyn_range_linearity", "module_sensitivity", "defect_pixels",
       "noise", "lsc", "lsc_ratio", "gdc", "optics_mechanics", "spectral_response",
       "chromaticity_response", "flash_chromaticity", "nvm_info", "color_matrices",
       "analog_gain_conversion", "digital_gain", "sensor_metadata", "gdc2", "exposure_range",
       "multi_led_flash", "advanced_color_matrices", "hdr", "ir_correction", "lsc_4x4",
       "lca", "phase_difference", "black_level_global", "valid_image_area", "lsc_4x4_ratio",
       "multi_gain_conv", "pipe_comp_decomp", "sensor_decomp", "media_format", "cbd"]

def cct(x, y):  # McCamy
    n = (x - 0.3320) / (0.1858 - y)
    return 449 * n**3 + 3525 * n**2 + 6823.3 * n + 5520.33

d = open(sys.argv[1], "rb").read()
want = {int(x, 0) for x in sys.argv[2:]}
if d[:4] == b"CPFF":            # CPF container: AIQB block inside
    d = d[d.index(b"AIQB"):]
assert d[:4] == b"AIQB", d[:4]

def records(start, end):
    o = start
    while o + 8 <= end:
        size, fmt, key, nid = struct.unpack_from("<IBBH", d, o)
        if size < 8 or o + size > end:
            print(f"  ?? bad record at {o:#x} size {size:#x}"); return
        yield o, size, fmt, key, nid
        o += size

def decode(o, size, nid):
    p = o + 8
    if nid == 2:
        w, h, bd, co, bdp = struct.unpack_from("<5H", d, p)
        print(f"    {w}x{h} bit_depth {bd} color_order {co} packed {bdp}")
    elif nid == 3:
        n, = struct.unpack_from("<I", d, p); p += 4
        for i in range(n):
            e, g, *c = struct.unpack_from("<II4H", d, p + 16 * i)
            print(f"    exp {e:6d} gain {g} BL " + " ".join(f"{x/1024:.2f}" for x in c))
    elif nid == 5:
        print("    sat", struct.unpack_from("<4H", d, p))
    elif nid == 15:
        nl, nn = struct.unpack_from("<HH", d, p); p += 4
        print(f"    {nl} avg light sources, {nn} nvm")
        for i in range(nl * 3 + nn):
            t, rg, bg, x, y = struct.unpack_from("<H4H", d, p + 10 * i)
            print(f"    src {t:3d} R/G {rg/1024:.3f} B/G {bg/1024:.3f}  cie {x/65536*4:.4f},{y/65536*4:.4f}")
    elif nid == 18:
        n, = struct.unpack_from("<H", d, p); p += 2
        for i in range(n):
            t, rg, bg, x, y = struct.unpack_from("<H4H", d, p)
            acc = struct.unpack_from("<9i", d, p + 10); pref = struct.unpack_from("<9i", d, p + 46)
            print(f"    src {t} R/G {rg/1024:.3f} B/G {bg/1024:.3f}")
            for name, m in (("accurate", acc), ("preferred", pref)):
                rows = [" ".join(f"{v/65536:+.4f}" for v in m[r*3:r*3+3]) for r in range(3)]
                print(f"      {name:9s} " + " | ".join(rows))
            p += 84
    elif nid == 25:
        nl, ns = struct.unpack_from("<HH", d, p); p += 4
        hues = struct.unpack_from(f"<{ns}I", d, p); p += 4 * ns
        print(f"    {nl} light sources, {ns} hue sectors")
        for i in range(nl):
            t, rg, bg, x, y = struct.unpack_from("<I4f", d, p); p += 20
            m = struct.unpack_from("<9f", d, p); p += 36 + 36 * ns
            print(f"    src {t:2d} CCT {cct(x, y):5.0f}K R/G {rg:.3f} B/G {bg:.3f} cie {x:.4f},{y:.4f}")
            print("      ccm " + " | ".join(" ".join(f"{v:+.4f}" for v in m[r*3:r*3+3]) for r in range(3)))
    else:
        blob = d[p:o + size]
        print("    " + blob[:48].hex(" ") + (" ..." if len(blob) > 48 else ""))

total, = struct.unpack_from("<I", d, 4)
print(f"AIQB size {total:#x}")
# top-level: AIQB header (24 bytes) then sub-blocks with their own header
o = 0x18
for ro, size, fmt, key, nid in records(o, len(d)):
    name = CMC[nid] if nid < len(CMC) else f"id{nid}"
    print(f"{ro:#08x} size {size:7d} fmt {fmt:#04x} key {key} name {nid:4d} {name}")
    if not want or nid in want:
        try: decode(ro, size, nid)
        except Exception as e: print("    decode error", e)
