#!/usr/bin/env python3
"""Show the PCH camera clock registers ICLK CLK1..CLK5 that the
ACPI methods CLKC/CLKF write: bit 1 = clock on, bit 0 = frequency select
(per Intel's DDK: 0 = 24 MHz, 1 = 19.2 MHz). Base = SBRG + 0xAD8000; SBRG
(sideband base, 16 MiB aligned) is found from the GPIO controller's
communities, which lie inside it (DSDT GBAS). Root.

  imgclk.py                  show all
  imgclk.py set INDEX VALUE  write one (INDEX 0-4 as in CLDB clock_source;
                             VALUE 3 = on at 19.2 MHz, 1 = off at 19.2 MHz)"""
import mmap, os, re, struct, sys

iomem = open("/proc/iomem", errors="replace").read()
# the GPIO controller (INT3455 on Ice Lake-LP, INT34C5 on others): its
# communities sit in the 16 MiB sideband window at SBRG
addrs = [int(a, 16) for a in re.findall(r"^\s*([0-9a-f]+)-[0-9a-f]+ : (?:INT3455|INT34C5)", iomem, re.M)]
addrs = [a for a in addrs if a]
if not addrs:
    sys.exit("GPIO controller not found in /proc/iomem (run as root)")
sbrg = min(addrs) & ~0xFFFFFF
base = sbrg + 0xAD8000
print(f"GPIO communities at {', '.join(hex(a) for a in sorted(set(addrs)))} -> SBRG {sbrg:#x}, ICLK at {base:#x}")
OFFSETS = (0x00, 0x0C, 0x18, 0x24, 0x30)
write = len(sys.argv) == 4 and sys.argv[1] == "set"
fd = os.open("/dev/mem", (os.O_RDWR if write else os.O_RDONLY) | os.O_SYNC)
page = base & ~0xFFF
mm = mmap.mmap(fd, 0x1000, mmap.MAP_SHARED,
               mmap.PROT_READ | (mmap.PROT_WRITE if write else 0), offset=page)
if write:
    i, v = int(sys.argv[2]), int(sys.argv[3], 0)
    o = base - page + OFFSETS[i]
    mm[o:o + 4] = struct.pack("<I", v)
    print(f"CLK{i + 1} <- {v:#x}")
for i, off in enumerate(OFFSETS):
    (v,) = struct.unpack("<I", mm[base - page + off: base - page + off + 4])
    print(f"CLK{i + 1} (index {i}): {v:#010x}  on={(v >> 1) & 1}  "
          f"freq={'19.2 MHz' if v & 1 else '24 MHz'}")
