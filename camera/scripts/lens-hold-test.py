#!/usr/bin/env python3
"""Rear camera: does streaming survive with the lens held open at a position?

Holds the dw9719 subdev open (as PipeWire does) at each focus position and
runs a few libcamera captures per sensor mode, waiting for the isys to power
down in between so a failed run can't poison the next one. Stop PipeWire
first, or the isys never powers down.

usage: lens-hold-test.py [positions...]      (default 0 300 600)
"""
import fcntl
import glob
import os
import re
import struct
import subprocess
import sys
import tempfile
import time

CAMID = r"\_SB_.PCI0.I2C3.CAMR"
MEDIA = "/dev/media0"
ISYS = "/sys/bus/intel-ipu4-bus/devices/intel-ipu60/power/runtime_status"
VIDIOC_S_CTRL = 0xC008561C
V4L2_CID_FOCUS_ABSOLUTE = 0x009A090A
TRIES = 3
# libcamera picks the sensor mode from the stream size
MODES = {"binned 1632x1224": "width=1632,height=1224",
         "full 3264x2448": "width=3264,height=2448"}


def lens_subdev():
    graph = subprocess.run(["media-ctl", "-d", MEDIA, "-p"], capture_output=True,
                           text=True, check=True).stdout
    name = re.search(r"^- entity \d+: (dw9719[^(]*?) \(", graph, re.M).group(1).strip()
    return subprocess.run(["media-ctl", "-d", MEDIA, "-e", name], capture_output=True,
                          text=True, check=True).stdout.strip()


def wait_idle():
    for _ in range(80):
        if open(ISYS).read().strip() == "suspended":
            return True
        time.sleep(0.25)
    return False


def grab(stream, tmp):
    for f in glob.glob(os.path.join(tmp, "*")):
        os.unlink(f)
    subprocess.run(["timeout", "30", "cam", f"--camera={CAMID}", "--capture=30",
                    f"--stream={stream},role=raw", f"--file={tmp}/f-#.bin"],
                   capture_output=True)
    return len(glob.glob(os.path.join(tmp, "*.bin")))


def main():
    positions = [int(a) for a in sys.argv[1:]] or [0, 300, 600]
    if subprocess.run(["pgrep", "-x", "pipewire"], capture_output=True).returncode == 0:
        sys.exit("pipewire is running; stop it first (it keeps the isys powered)")
    fd = os.open(lens_subdev(), os.O_RDWR)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for pos in positions:
                fcntl.ioctl(fd, VIDIOC_S_CTRL,
                            struct.pack("Ii", V4L2_CID_FOCUS_ABSOLUTE, pos))
                time.sleep(0.5)
                for label, stream in MODES.items():
                    res = []
                    for _ in range(TRIES):
                        if not wait_idle():
                            res.append("busy")
                            continue
                        res.append(str(grab(stream, tmp)))
                    print(f"focus {pos:4d}  {label:17s} frames per run: {' '.join(res)}",
                          flush=True)
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
