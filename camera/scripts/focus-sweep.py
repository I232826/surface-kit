#!/usr/bin/env python3
"""Find a good fixed focus position for the rear camera's VCM (dw9719).

libcamera's simple pipeline has no autofocus, so the lens sits wherever it
is left. Step the lens through a range of positions, grab a frame through
libcamera at each, and score sharpness (variance of a Laplacian over the
centre of the image). Point the camera at something with detail at the
distance you care about before running it.

usage: focus-sweep.py [start stop step]      (default 0 1023 64)
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

from PIL import Image, ImageFilter, ImageStat

CAMID = r"\_SB_.PCI0.I2C3.CAMR"
MEDIA = "/dev/media0"


def lens_subdev():
    graph = subprocess.run(["media-ctl", "-d", MEDIA, "-p"], capture_output=True,
                           text=True, check=True).stdout
    m = re.search(r"^- entity \d+: (dw9719[^(]*?) \(", graph, re.M)
    if not m:
        sys.exit("no dw9719 entity in the media graph (is the patched dw9719 loaded?)")
    name = m.group(1).strip()
    dev = subprocess.run(["media-ctl", "-d", MEDIA, "-e", name], capture_output=True,
                         text=True, check=True).stdout.strip()
    return name, dev


VIDIOC_S_CTRL = 0xC008561C
V4L2_CID_FOCUS_ABSOLUTE = 0x009A090A


def set_focus(fd, pos):
    # through a held-open fd: the dw9719 powers down (and the lens drops) when
    # its subdev is closed, so a v4l2-ctl one-shot wouldn't stick
    fcntl.ioctl(fd, VIDIOC_S_CTRL, struct.pack("Ii", V4L2_CID_FOCUS_ABSOLUTE, pos))
    time.sleep(0.3)


ISYS = "/sys/bus/intel-ipu4-bus/devices/intel-ipu60/power/runtime_status"


def wait_idle():
    """A failed stream latches reset_needed until the isys powers down."""
    for _ in range(40):
        try:
            if open(ISYS).read().strip() == "suspended":
                return
        except OSError:
            return
        time.sleep(0.25)


def grab(tmp, tries=3):
    for attempt in range(tries):
        img = grab_once(tmp)
        if img is not None:
            return img
        print(f"    (no frames, retry {attempt + 1}/{tries})")
    return None


def grab_once(tmp):
    wait_idle()
    for f in glob.glob(os.path.join(tmp, "*.ppm")):
        os.unlink(f)
    # 90 frames: let auto exposure settle so frames are comparable
    subprocess.run(["timeout", "40", "cam", f"--camera={CAMID}", "--capture=90",
                    "--stream=width=1280,height=960,pixelformat=RGB888",
                    f"--file={tmp}/f-#.ppm"], capture_output=True)
    frames = sorted(glob.glob(os.path.join(tmp, "*.ppm")), key=os.path.getmtime)
    return Image.open(frames[-1]).convert("L") if frames else None


def sharpness(img):
    w, h = img.size
    centre = img.crop((w // 4, h // 4, 3 * w // 4, 3 * h // 4))
    edges = centre.filter(ImageFilter.Kernel((3, 3), (0, 1, 0, 1, -4, 1, 0, 1, 0), 1, 128))
    return ImageStat.Stat(edges).var[0]


def main():
    start, stop, step = (int(a) for a in sys.argv[1:4]) if len(sys.argv) == 4 else (0, 1023, 64)
    if subprocess.run(["pgrep", "-x", "pipewire"], capture_output=True).returncode == 0:
        sys.exit("pipewire is running; stop it first (it keeps the isys powered, so one "
                 "failed start poisons every later one)")
    name, dev = lens_subdev()
    print(f"lens: {name} ({dev})")
    fd = os.open(dev, os.O_RDWR)
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for pos in range(start, stop + 1, step):
            set_focus(fd, pos)
            img = grab(tmp)
            if img is None:
                print(f"  {pos:5d}: no frame")
                continue
            s = sharpness(img)
            results.append((s, pos))
            print(f"  {pos:5d}: sharpness {s:9.1f}  mean {ImageStat.Stat(img).mean[0]:5.1f}")
    if results:
        best = max(results)
        print(f"best: focus_absolute={best[1]} (sharpness {best[0]:.1f})")
    os.close(fd)


if __name__ == "__main__":
    main()
