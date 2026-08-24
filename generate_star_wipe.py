#!/usr/bin/env python3
"""
Generate star-shaped luma wipe files (.pgm) for Kdenlive / MLT.

A luma wipe in MLT is just a greyscale image: as the transition progresses,
MLT raises a threshold from black to white, and every pixel whose luma value
is below the threshold has already switched to the incoming clip.  So a
"growing star" wipe is simply an image whose brightness increases with the
distance from the centre, measured with a *star-shaped* distance metric
instead of the usual circular one.

The star metric used here is  d(p) = |p| / R(angle(p))  where R(theta) is the
radius of the star polygon in direction theta.  Level sets of d are therefore
scaled copies of the star -- exactly what a classic star wipe looks like.

Written for stdlib-only Python 3 (no numpy required).
"""

import argparse
import math
import os
import sys
from array import array

# --------------------------------------------------------------------------
# star geometry
# --------------------------------------------------------------------------


def pentagram_ratio(points: int) -> float:
    """Inner/outer radius of the 'classic' star with straight, un-broken arms.

    This is the ratio you get when the arms of an n-pointed star are formed by
    straight lines running from one vertex to the vertex two positions away
    (the {n/2} star polygon).  For 5 points it gives the familiar 0.382 of the
    pentagram used by every star wipe since the 1970s.
    """
    if points < 5:
        # 3 and 4 point stars have no {n/2} polygon; pick a pleasant default.
        return 0.38
    return math.cos(2.0 * math.pi / points) / math.cos(math.pi / points)


def star_radius_table(points: int, inner_ratio: float, samples: int = 16384):
    """Sample R(theta) over one wedge (2*pi/points) of the star.

    The star is built from an outer vertex at angle 0 (radius 1.0) and an
    inner vertex at angle pi/points (radius `inner_ratio`).  Within the wedge
    the outline is one straight segment, mirrored around the inner vertex, so
    a ray/segment intersection gives R exactly.
    """
    seg = 2.0 * math.pi / points
    half = seg / 2.0

    ax, ay = 1.0, 0.0                                        # outer vertex
    bx = inner_ratio * math.cos(half)                        # inner vertex
    by = inner_ratio * math.sin(half)
    dx, dy = bx - ax, by - ay                                # segment direction
    cross_ad = ax * dy - ay * dx                             # A x D

    table = array("d", bytes(8 * (samples + 1)))
    for i in range(samples + 1):
        phi = seg * i / samples
        # mirror the second half of the wedge onto the first half
        p = phi if phi <= half else seg - phi
        ux, uy = math.cos(p), math.sin(p)
        den = ux * dy - uy * dx
        table[i] = cross_ad / den if den != 0.0 else 1.0
    return table


# --------------------------------------------------------------------------
# luma rendering
# --------------------------------------------------------------------------


def render_star_luma(
    width: int,
    height: int,
    points: int = 5,
    inner_ratio: float = None,
    rotation: float = -90.0,
    spin: float = 0.0,
    gamma: float = 1.0,
    center=(0.5, 0.5),
    par: float = 1.0,
    bits: int = 8,
):
    """Render the star wipe and return (maxval, bytes) ready for a P5 payload.

    rotation  degrees; -90 puts one arm straight up (the classic look)
    spin      degrees of extra twist between the centre and the frame edge,
              which makes the star rotate while it grows
    gamma     <1 makes the star grow fast then slow, >1 the opposite;
              1.0 = constant radial speed (classic)
    par       pixel aspect ratio (storage), so anamorphic formats stay round
    """
    if inner_ratio is None:
        inner_ratio = pentagram_ratio(points)

    samples = 16384
    table = star_radius_table(points, inner_ratio, samples)
    seg = 2.0 * math.pi / points
    inv_seg = 1.0 / seg
    scale = samples / seg

    rot = math.radians(rotation)
    spin_rad = math.radians(spin)

    cx = center[0] * width
    cy = center[1] * height

    # Work in square-pixel space normalised to half the frame height, so the
    # star is geometrically correct rather than stretched by the frame ratio.
    unit = height / 2.0
    xs = array("d", bytes(8 * width))
    for x in range(width):
        xs[x] = ((x + 0.5) - cx) * par / unit
    # distance used to normalise the spin ramp
    diag = math.hypot(max(cx, width - cx) * par, max(cy, height - cy)) / unit

    dist = array("f", bytes(4 * width * height))
    peak = 0.0
    idx = 0
    atan2 = math.atan2
    hypot = math.hypot

    for y in range(height):
        ny = ((y + 0.5) - cy) / unit
        for x in range(width):
            nx = xs[x]
            r = hypot(nx, ny)
            if r == 0.0:
                dist[idx] = 0.0
                idx += 1
                continue
            theta = atan2(ny, nx) - rot
            if spin_rad:
                theta -= spin_rad * (r / diag)
            phi = theta - seg * math.floor(theta * inv_seg)   # theta mod seg
            v = r / table[int(phi * scale)]
            dist[idx] = v
            if v > peak:
                peak = v
            idx += 1

    # Normalise so the very last pixel to be revealed is pure white; without
    # this the wipe would finish before the frame corners are covered.
    maxval = (1 << bits) - 1
    inv_peak = 1.0 / peak if peak else 0.0
    lut_n = 4096
    lut = [0] * (lut_n + 1)
    for i in range(lut_n + 1):
        t = i / lut_n
        if gamma != 1.0:
            t = t ** gamma
        lut[i] = min(maxval, int(t * maxval + 0.5))

    if bits == 8:
        out = bytearray(width * height)
        for i in range(width * height):
            out[i] = lut[int(dist[i] * inv_peak * lut_n)]
    else:
        out = bytearray(2 * width * height)
        for i in range(width * height):
            v = lut[int(dist[i] * inv_peak * lut_n)]
            out[2 * i] = v >> 8          # PGM 16-bit is big endian
            out[2 * i + 1] = v & 0xFF
    return maxval, bytes(out)


def write_pgm(path, width, height, maxval, payload, comment=None):
    header = b"P5\n"
    if comment:
        for line in comment.splitlines():
            header += b"# " + line.encode("utf-8") + b"\n"
    header += b"%d %d\n%d\n" % (width, height, maxval)
    with open(path, "wb") as fh:
        fh.write(header)
        fh.write(payload)


# --------------------------------------------------------------------------


def parse_center(text):
    parts = text.split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("center must be given as x,y (0..1)")
    return (float(parts[0]), float(parts[1]))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Generate a star wipe luma (.pgm) for Kdenlive / MLT.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("-o", "--output", default="star_wipe.pgm", help="output .pgm file")
    ap.add_argument("-s", "--size", default="1920x1080", help="image size WxH")
    ap.add_argument("-p", "--points", type=int, default=5, help="number of star points")
    ap.add_argument(
        "-i",
        "--inner",
        type=float,
        default=None,
        help="inner/outer radius ratio (default: classic star polygon ratio)",
    )
    ap.add_argument(
        "-r", "--rotation", type=float, default=-90.0,
        help="star orientation in degrees (-90 = one arm pointing up)",
    )
    ap.add_argument(
        "--spin", type=float, default=0.0,
        help="degrees of twist between centre and edge (rotating star wipe)",
    )
    ap.add_argument(
        "-g", "--gamma", type=float, default=1.0,
        help="growth curve; <1 fast start, >1 slow start",
    )
    ap.add_argument(
        "-c", "--center", type=parse_center, default=(0.5, 0.5),
        help="star centre in normalised frame coordinates",
    )
    ap.add_argument(
        "--par", type=float, default=1.0,
        help="pixel aspect ratio of the target format (1.0 for square pixels)",
    )
    ap.add_argument("--bits", type=int, choices=(8, 16), default=8, help="bit depth")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    try:
        width, height = (int(v) for v in args.size.lower().split("x"))
    except ValueError:
        ap.error("--size must look like 1920x1080")

    inner = args.inner if args.inner is not None else pentagram_ratio(args.points)
    maxval, payload = render_star_luma(
        width, height,
        points=args.points,
        inner_ratio=inner,
        rotation=args.rotation,
        spin=args.spin,
        gamma=args.gamma,
        center=args.center,
        par=args.par,
        bits=args.bits,
    )
    comment = (
        "Star wipe luma for Kdenlive/MLT\n"
        "points=%d inner=%.4f rotation=%.1f spin=%.1f gamma=%.2f center=%.3f,%.3f"
        % (args.points, inner, args.rotation, args.spin, args.gamma,
           args.center[0], args.center[1])
    )
    outdir = os.path.dirname(os.path.abspath(args.output))
    if outdir:
        os.makedirs(outdir, exist_ok=True)
    write_pgm(args.output, width, height, maxval, payload, comment)
    if not args.quiet:
        print("wrote %s (%dx%d, %d-bit)" % (args.output, width, height, args.bits))
    return 0


if __name__ == "__main__":
    sys.exit(main())
