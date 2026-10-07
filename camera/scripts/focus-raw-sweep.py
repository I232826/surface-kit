#!/usr/bin/env python3
"""Rear focus sweep on raw full-resolution frames.

Like focus-sweep.py, but scores the sensor's raw 3264x2448 Bayer data
(no soft ISP, no downscale) and normalises sharpness by brightness, so the
auto exposure settling at slightly different levels doesn't swamp the focus
signal. Each 2x2 Bayer cell is averaged into one luma pixel first, so the
colour filter pattern doesn't count as "detail". Stop PipeWire first.

usage: focus-raw-sweep.py [start stop step]      (default 0 1023 64)
"""
import fcntl
import glob
import os
import struct
import subprocess
import sys
import tempfile
import time

from PIL import Image, ImageFilter, ImageStat

CAMID = r"\_SB_.PCI0.I2C3.CAMR"
MEDIA = "/dev/media0"
W, H = 3264, 2448
VIDIOC_S_CTRL = 0xC008561C
V4L2_CID_FOCUS_ABSOLUTE = 0x009A090A
ISYS = "/sys/bus/intel-ipu4-bus/devices/intel-ipu60/power/runtime_status"


def subdev(entity_re):
    import re
    graph = subprocess.run(["media-ctl", "-d", MEDIA, "-p"], capture_output=True,
                           text=True, check=True).stdout
    name = re.search(rf"^- entity \d+: ({entity_re}[^(]*?) \(", graph, re.M).group(1).strip()
    return subprocess.run(["media-ctl", "-d", MEDIA, "-e", name], capture_output=True,
                          text=True, check=True).stdout.strip()


def wait_idle():
    for _ in range(80):
        if open(ISYS).read().strip() == "suspended":
            return
        time.sleep(0.25)


def grab(tmp):
    wait_idle()
    for f in glob.glob(os.path.join(tmp, "*.bin")):
        os.unlink(f)
    subprocess.run(["timeout", "40", "cam", f"--camera={CAMID}", "--capture=40",
                    f"--stream=width={W},height={H},role=raw", f"--file={tmp}/f-#.bin"],
                   capture_output=True)
    frames = sorted(glob.glob(os.path.join(tmp, "*.bin")), key=os.path.getmtime)
    if not frames:
        return None
    raw = Image.frombytes("I;16", (W, H), open(frames[-1], "rb").read())
    return raw.convert("I").reduce(2)          # 2x2 Bayer cell -> luma


def score(luma):
    w, h = luma.size
    c = luma.crop((w // 4, h // 4, 3 * w // 4, 3 * h // 4))
    # raw is linear, so scaling to a fixed mean cancels exposure differences
    mean = ImageStat.Stat(c).mean[0]
    l8 = c.point(lambda v: v * 64 / max(mean, 1)).convert("L")
    lap = l8.filter(ImageFilter.Kernel((3, 3), (0, 1, 0, 1, -4, 1, 0, 1, 0), 1, 128))
    return ImageStat.Stat(lap).var[0], mean


def main():
    start, stop, step = (int(a) for a in sys.argv[1:4]) if len(sys.argv) == 4 else (0, 1023, 64)
    if subprocess.run(["pgrep", "-x", "pipewire"], capture_output=True).returncode == 0:
        sys.exit("pipewire is running; stop it first")
    fd = os.open(subdev("dw9719"), os.O_RDWR)
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for pos in range(start, stop + 1, step):
            fcntl.ioctl(fd, VIDIOC_S_CTRL, struct.pack("Ii", V4L2_CID_FOCUS_ABSOLUTE, pos))
            time.sleep(0.3)
            luma = grab(tmp)
            if luma is None:
                print(f"  {pos:5d}: no frame", flush=True)
                continue
            s, mean = score(luma)
            results.append((s, pos))
            print(f"  {pos:5d}: sharpness {s:7.2f}  {'#' * int(s / 10)}", flush=True)
    os.close(fd)
    if results:
        best = max(results)
        print(f"best: focus_absolute={best[1]} (sharpness {best[0]:.2f})")


if __name__ == "__main__":
    main()
