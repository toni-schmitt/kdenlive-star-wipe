#!/usr/bin/env python3
"""
Render an animated GIF preview of a luma wipe file, the same way MLT uses it:
a threshold sweeps from black to white and everything below it has already
switched to the incoming clip.  A soft edge is added to mimic Kdenlive's
"Softness" slider.

Usage:  python3 make_preview.py lumas/HD/star_wipe.pgm preview/star_wipe.gif
"""

import sys
import os

from PIL import Image, ImageDraw


def read_pgm(path):
    with open(path, "rb") as fh:
        data = fh.read()
    if not data.startswith(b"P5"):
        raise ValueError("%s is not a binary (P5) PGM" % path)
    pos = 2
    fields = []
    while len(fields) < 3:
        while pos < len(data) and data[pos : pos + 1].isspace():
            pos += 1
        if data[pos : pos + 1] == b"#":
            pos = data.index(b"\n", pos) + 1
            continue
        start = pos
        while pos < len(data) and not data[pos : pos + 1].isspace():
            pos += 1
        fields.append(int(data[start:pos]))
    pos += 1  # single whitespace byte after maxval
    width, height, maxval = fields
    raw = data[pos:]
    if maxval > 255:
        img = Image.frombytes("I;16B", (width, height), raw[: width * height * 2])
        img = img.point(lambda v: v >> 8, "L")
    else:
        img = Image.frombytes("L", (width, height), raw[: width * height])
    return img


def demo_pair(size):
    """Two easily distinguishable 'clips' to wipe between."""
    w, h = size
    a = Image.new("RGB", size)
    da = ImageDraw.Draw(a)
    for y in range(h):
        t = y / max(1, h - 1)
        da.line([(0, y), (w, y)], fill=(int(20 + 30 * t), int(40 + 60 * t), int(90 + 70 * t)))
    for x in range(0, w, 40):
        da.line([(x, 0), (x, h)], fill=(255, 255, 255), width=1)
    for y in range(0, h, 40):
        da.line([(0, y), (w, y)], fill=(255, 255, 255), width=1)

    b = Image.new("RGB", size)
    db = ImageDraw.Draw(b)
    for y in range(h):
        t = y / max(1, h - 1)
        db.line([(0, y), (w, y)], fill=(int(230 - 40 * t), int(120 + 40 * t), int(30 + 20 * t)))
    for i in range(-h, w, 60):
        db.line([(i, 0), (i + h, h)], fill=(255, 235, 200), width=6)
    return a, b


def render(luma_path, out_path, width=480, frames=36, softness=0.06, hold=6):
    luma = read_pgm(luma_path)
    height = max(1, round(width * luma.height / luma.width))
    luma = luma.resize((width, height), Image.BILINEAR)
    clip_a, clip_b = demo_pair((width, height))

    soft = max(1e-6, softness) * 255.0
    out = []
    for i in range(frames + 1):
        t = i / frames
        # threshold travels a little past both ends so the wipe fully clears
        thr = t * (255.0 + 2 * soft) - soft
        mask = luma.point(
            lambda v, thr=thr: 0 if v > thr + soft
            else 255 if v < thr - soft
            else int(255 * (thr + soft - v) / (2 * soft))
        )
        out.append(Image.composite(clip_b, clip_a, mask).convert("P", palette=Image.ADAPTIVE))

    durations = [40] * len(out)
    durations[0] = durations[-1] = hold * 40
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    out[0].save(
        out_path, save_all=True, append_images=out[1:],
        duration=durations, loop=0, optimize=True,
    )
    print("wrote %s (%dx%d, %d frames)" % (out_path, width, height, len(out)))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    render(sys.argv[1], sys.argv[2])
