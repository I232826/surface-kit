#!/usr/bin/env python3
"""Dump sensor register tables from a Windows Intel IPU4 sensor driver (.sys).
Entries are 16 bytes: u32 type, u32 reg, u32 value, u32 0. Prints each run of
>= MIN entries as a table.  usage: win-regtables.py ov5693.sys"""
import struct, sys
MIN = 8
d = open(sys.argv[1], "rb").read()

def ok(o):
    if o + 16 > len(d): return False
    t, r, v, z = struct.unpack_from("<IIII", d, o)
    return t <= 4 and z == 0 and r <= 0xffff and v <= 0xffff and (r or v or t)

o, n = 0, 0
while o < len(d) - 16:
    if not ok(o):
        o += 4; continue
    e = o
    while ok(e): e += 16
    cnt = (e - o) // 16
    if cnt >= MIN:
        n += 1
        print(f"## table {n} @ {o:#x} ({cnt} entries)")
        for p in range(o, e, 16):
            t, r, v, _ = struct.unpack_from("<IIII", d, p)
            print(f"{t} {r:#06x} {v:#04x}")
        o = e
    else:
        o += 4
