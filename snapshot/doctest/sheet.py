#!/usr/bin/env python3
"""Contact sheet: each photo with the detected outline, next to its scan.
usage: sheet.py run.log out.jpg"""
import re, sys
from PIL import Image, ImageDraw
rows = []
for name, c in re.findall(r'^(\S+\.jpg): corners \[(.*?)\]', open(sys.argv[1]).read(), re.M):
    pts = [tuple(map(int, p)) for p in re.findall(r'\((-?\d+), (-?\d+)\)', c)]
    im = Image.open(name).convert("RGB"); d = ImageDraw.Draw(im)
    d.line(pts + [pts[0]], fill=(0, 255, 0), width=max(4, im.width // 200))
    im.thumbnail((360, 270))
    sc = Image.open(name[:-4] + " (scan).jpeg").convert("RGB"); sc.thumbnail((360, 270))
    rows.append((im, sc, name.rsplit("/", 1)[-1]))
cols = 2
g = Image.new("RGB", (cols * 740, 280 * ((len(rows) + cols - 1) // cols)), (255, 255, 255))
for i, (a, b, n) in enumerate(rows):
    x, y = (i % cols) * 740, (i // cols) * 280
    g.paste(a, (x, y)); g.paste(b, (x + 365, y)); ImageDraw.Draw(g).text((x + 4, y + 4), n, fill=(255, 0, 0))
g.save(sys.argv[2], quality=80)
