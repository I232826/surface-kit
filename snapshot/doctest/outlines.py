#!/usr/bin/env python3
"""Photos with the detected outline, several per row (no scans).
usage: outlines.py run.log out.jpg"""
import re, sys
from PIL import Image, ImageDraw
log = open(sys.argv[1]).read()
items = re.findall(r'^(\S+\.jpg): corners \[(.*?)\]', log, re.M)
cols, tw, th = 4, 360, 270
g = Image.new("RGB", (cols * (tw + 5), (th + 5) * ((len(items) + cols - 1) // cols)), (255, 255, 255))
for i, (name, c) in enumerate(items):
    pts = [tuple(map(int, p)) for p in re.findall(r'\((-?\d+), (-?\d+)\)', c)]
    im = Image.open(name).convert("RGB"); d = ImageDraw.Draw(im)
    d.line(pts + [pts[0]], fill=(0, 255, 0), width=max(4, im.width // 150))
    im.thumbnail((tw, th))
    x, y = (i % cols) * (tw + 5), (i // cols) * (th + 5)
    g.paste(im, (x, y)); ImageDraw.Draw(g).text((x + 4, y + 4), name.rsplit("/", 1)[-1], fill=(255, 0, 0))
g.save(sys.argv[2], quality=80)
