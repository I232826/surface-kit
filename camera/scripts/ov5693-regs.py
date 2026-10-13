#!/usr/bin/env python3
"""Dump the front ov5693's clock (PLL) and timing registers over I2C.

Powers the sensor through runtime PM for the read and lets it suspend
again afterwards. Uses I2C_RDWR on /dev/i2c-N, which works while the
ov5693 driver owns the address. Run as root.

usage: ov5693-regs.py [REG | START:COUNT ...]    (hex, e.g. 4837 3000:100)
       with no arguments, dumps the known clock and timing registers
"""
import ctypes
import fcntl
import os
import sys
import time

DEV = "/sys/bus/i2c/devices/i2c-INT33BE:00"
ADDR = 0x36
I2C_RDWR = 0x0707
I2C_M_RD = 0x0001

RANGES = {
    "PLL 0x0300-0x0313": (0x0300, 0x14),
    "sys clk 0x3020-0x3022": (0x3020, 3),
    "0x3106": (0x3106, 1),
    "HTS/VTS 0x380c-0x380f": (0x380C, 4),
    "MIPI 0x4837 (pclk period)": (0x4837, 1),
}


class Msg(ctypes.Structure):
    _fields_ = [("addr", ctypes.c_uint16), ("flags", ctypes.c_uint16),
                ("len", ctypes.c_uint16), ("buf", ctypes.c_void_p)]


class RdWr(ctypes.Structure):
    _fields_ = [("msgs", ctypes.c_void_p), ("nmsgs", ctypes.c_uint32)]


def read(fd, reg, n):
    wbuf = (ctypes.c_uint8 * 2)(reg >> 8, reg & 0xFF)
    rbuf = (ctypes.c_uint8 * n)()
    msgs = (Msg * 2)(Msg(ADDR, 0, 2, ctypes.addressof(wbuf)),
                     Msg(ADDR, I2C_M_RD, n, ctypes.addressof(rbuf)))
    fcntl.ioctl(fd, I2C_RDWR, RdWr(ctypes.addressof(msgs), 2))
    return bytes(rbuf)


def main():
    bus = os.path.basename(os.path.dirname(os.path.realpath(DEV)))   # i2c-N
    os.system("modprobe i2c-dev")
    ctrl = os.path.join(DEV, "power/control")
    old = open(ctrl).read().strip()
    open(ctrl, "w").write("on")
    time.sleep(0.3)
    try:
        fd = os.open(f"/dev/{bus}", os.O_RDWR)
        ranges = dict(RANGES) if len(sys.argv) == 1 else {}
        for a in sys.argv[1:]:
            start, _, count = a.partition(":")
            ranges[a] = (int(start, 16), int(count, 16) if count else 1)
        for name, (reg, n) in ranges.items():
            for off in range(0, n, 16):
                vals = read(fd, reg + off, min(16, n - off))
                print(f"{reg + off:04x}: " + " ".join(f"{v:02x}" for v in vals))
        os.close(fd)
    finally:
        open(ctrl, "w").write(old)


if __name__ == "__main__":
    main()
