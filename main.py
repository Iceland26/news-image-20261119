#!/usr/bin/env python3
"""news-image-20261119 — "THE WORLD TODAY": one image that sums up the world
news of Wednesday 19 November 2026, drawn entirely in code.

Pure Python 3 standard library — no PIL, no font files. The type is a
constructed outline typeface: every glyph is a set of filled polygon
contours on a 1000-unit em grid — sampled arcs and beziers, bracketed
serifs, real stroke contrast — in three cuts (serif display, serif
bold, sans), rasterised by a nonzero-winding scanline filler with 2x
supersampling and a hand-rolled PNG encoder.

The page mirrors a broadsheet front page: utility bar, date block and
masthead, a strap line, region tally chips, a four-number stat band, nine
numbered story cards with small drawn illustration strips, a 24-story
"also" column strip, and a date-check footer. 33 real stories of the day,
every one of them reported on 19 November 2026.

Deterministic: no randomness, no clock, no network. Two runs write the same
bytes. Output: $MAKEFUN_OUTPUT_DIR/entry.png (default /output/entry.png).
"""

import math
import os
import struct
import zlib

W, H = 1024, 1024
SS = 4                      # supersampling factor
SW, SH = W * SS, H * SS

# --------------------------------------------------------------------------
# PNG encoder (filter 0 rows, zlib level 9)
# --------------------------------------------------------------------------

def write_png(path, w, h, rgb):
    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)

# --------------------------------------------------------------------------
# Canvas: RGB framebuffer at supersampled resolution
# --------------------------------------------------------------------------

class Canvas:
    def __init__(self):
        self.buf = bytearray(SW * SH * 3)

    def _set_span(self, x0, x1, y, col):
        if y < 0 or y >= SH:
            return
        x0 = max(0, x0); x1 = min(SW - 1, x1)
        if x1 < x0:
            return
        i = (y * SW + x0) * 3
        n = (x1 - x0 + 1) * 3
        self.buf[i:i + n] = bytes(col) * (x1 - x0 + 1)

    def rect(self, x, y, w, h, col):
        """Filled rect in output (1024) coordinates."""
        X0, Y0 = int(x * SS), int(y * SS)
        X1, Y1 = int((x + w) * SS) - 1, int((y + h) * SS) - 1
        for yy in range(Y0, Y1 + 1):
            self._set_span(X0, X1, yy, col)

    def disc(self, cx, cy, r, col):
        """Filled circle in output coordinates (centre, radius)."""
        CX, CY, R = cx * SS, cy * SS, r * SS
        y0 = int(CY - R); y1 = int(CY + R)
        for yy in range(y0, y1 + 1):
            dy = yy - CY
            dx = max(0.0, R * R - dy * dy) ** 0.5
            self._set_span(int(CX - dx), int(CX + dx), yy, col)

    def line(self, x0, y0, x1, y1, thick, col):
        """Thick line with round caps, output coordinates."""
        steps = max(2, int(max(abs(x1 - x0), abs(y1 - y0)) * SS * 1.6))
        r = thick / 2.0
        for i in range(steps + 1):
            t = i / steps
            self.disc(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, r, col)

    def poly(self, pts, col):
        """Filled polygon, output coordinates (scanline, even-odd)."""
        P = [(x * SS, y * SS) for x, y in pts]
        ys = [p[1] for p in P]
        y0, y1 = int(min(ys)), int(max(ys))
        n = len(P)
        for yy in range(y0, y1 + 1):
            yc = yy + 0.5
            xs = []
            for i in range(n):
                xa, ya = P[i]; xb, yb = P[(i + 1) % n]
                if (ya <= yc < yb) or (yb <= yc < ya):
                    xs.append(xa + (yc - ya) * (xb - xa) / (yb - ya))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self._set_span(int(xs[i]), int(xs[i + 1]), yy, col)

    def downsample(self):
        """Box-average the supersampled buffer to W x H."""
        out = bytearray(W * H * 3)
        b = self.buf
        n = SS * SS
        for y in range(H):
            for x in range(W):
                o = (y * W + x) * 3
                base = ((y * SS) * SW + x * SS) * 3
                for c in range(3):
                    s = 0
                    for dy in range(SS):
                        i = base + dy * SW * 3 + c
                        for dx in range(SS):
                            s += b[i + dx * 3]
                    out[o + c] = s // n
        return bytes(out)

# --------------------------------------------------------------------------
# Constructed outline typeface (v3).
#
# Every glyph is a set of filled polygon contours on a 1000-unit em grid
# (baseline y=0, cap height 680, x-height 480, ascender 695, descender
# -215), drawn as true outlines: sampled elliptical arcs and cubic
# beziers, straight stems with bracketed serifs, and real stroke contrast
# (heavy verticals, light horizontals) in the serif cuts. Contours are
# wound CCW for outers and CW for counters (y-up); a nonzero-winding
# scanline rasteriser fills them, so overlapping parts union and
# counters cut out. v4 (foundry pass): digits and symbols rebuilt as
# explicit measured outlines, tabular figures, 4x supersampling.
# Three cuts share one set of glyph builders, driven by face parameters:
#   'disp'  serif display — masthead, big numerals
#   'bold'  serif bold    — headlines, labels, stat figures
#   'reg'   sans          — body text
# size everywhere means cap height in output px, as before.
# --------------------------------------------------------------------------

CAPU = 680.0          # cap height in font units
XHU = 480.0           # x-height
ASCU = 695.0          # lowercase ascender
DESCU = -215.0        # descender
OVU = 14.0            # overshoot for round glyphs

_FACES = {
    'disp': dict(S=104.0, T=34.0, SW=48.0, SH=32.0, BR=34.0,
                 BV=100.0, BH=46.0, SER=1),
    'bold': dict(S=158.0, T=56.0, SW=36.0, SH=44.0, BR=24.0,
                 BV=148.0, BH=66.0, SER=1),
    'reg':  dict(S=94.0,  T=80.0, SW=0.0,  SH=0.0,  BR=0.0,
                 BV=94.0,  BH=80.0, SER=0),
}

_KERN = {('T', 'h'): -22, ('T', 'o'): -16, ('T', 'e'): -12,
         ('T', 'a'): -14, ('W', 'o'): -14, ('W', 'a'): -12,
         ('Y', 'o'): -14, ('Y', 'a'): -10, ('V', 'a'): -10,
         ('A', 'v'): -12, ('A', 'w'): -10, ('L', 'y'): -8,
         ('r', ','): -10, ('r', '.'): -10, ('f', '.'): -8,
         ('f', ','): -8, ('T', '.'): -8, ('T', ','): -8}


def _star(cx, cy, r_out, r_in):
    pts = []
    for i in range(10):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(90 + i * 36)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


# ---- outline geometry helpers -------------------------------------------

def _arc(cx, cy, rx, ry, a0, a1):
    """Sampled elliptical arc, degrees, CCW in y-up space."""
    n = max(4, int(abs(a1 - a0) / 6.0))
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n)))
            for i in range(n + 1)]


def _bez(p0, p1, p2, p3, n=16):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        pts.append((u * u * u * p0[0] + 3 * u * u * t * p1[0]
                    + 3 * u * t * t * p2[0] + t * t * t * p3[0],
                    u * u * u * p0[1] + 3 * u * u * t * p1[1]
                    + 3 * u * t * t * p2[1] + t * t * t * p3[1]))
    return pts


def _quad(p0, p1, p2, n=6):
    pts = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        pts.append((u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
                    u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]))
    return pts


def _join(*parts):
    out = []
    for part in parts:
        for pt in part:
            if (not out or abs(pt[0] - out[-1][0]) > 0.01
                    or abs(pt[1] - out[-1][1]) > 0.01):
                out.append(pt)
    if (len(out) > 1 and abs(out[0][0] - out[-1][0]) < 0.01
            and abs(out[0][1] - out[-1][1]) < 0.01):
        out.pop()
    return out


def _area(pts):
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def _O(pts):
    """Normalise a contour to CCW (outer) in y-up space."""
    return pts if _area(pts) > 0 else pts[::-1]


def _I(pts):
    """Normalise a contour to CW (counter/hole) in y-up space."""
    return pts if _area(pts) < 0 else pts[::-1]


def _rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def _stem(cx, y0, y1, P, top=True, bot=True):
    """Vertical stem centred cx with bracketed serifs (serif faces)."""
    S = P['S']
    SW = P['SW']
    SH = P['SH']
    BR = P['BR']
    hw = S / 2.0
    x0 = cx - hw
    x1 = cx + hw
    if not SW:
        return [_rect(x0, y0, x1, y1)]
    pts = []
    if bot:
        pts += [(x0 - SW, y0), (x1 + SW, y0), (x1 + SW, y0 + SH)]
        pts += _quad((x1 + SW, y0 + SH), (x1 + 6, y0 + SH),
                     (x1, y0 + SH + BR))[1:]
    else:
        pts += [(x0, y0), (x1, y0)]
    if top:
        pts += [(x1, y1 - SH - BR)]
        pts += _quad((x1, y1 - SH - BR), (x1 + 6, y1 - SH),
                     (x1 + SW, y1 - SH))[1:]
        pts += [(x1 + SW, y1), (x0 - SW, y1), (x0 - SW, y1 - SH)]
        pts += _quad((x0 - SW, y1 - SH), (x0 - 6, y1 - SH),
                     (x0, y1 - SH - BR))[1:]
    else:
        pts += [(x1, y1), (x0, y1)]
    if bot:
        pts += [(x0, y0 + SH + BR)]
        pts += _quad((x0, y0 + SH + BR), (x0 - 6, y0 + SH),
                     (x0 - SW, y0 + SH))[1:]
    return [_O(pts)]


def _bowl(cx, cy, rx, ry, P):
    """Closed bowl: outer ellipse CCW + inner ellipse CW (a counter).
    Stroke thickness is clamped so small bowls keep a real counter."""
    bv = min(P['BV'], rx * 0.74)
    bh = min(P['BH'], ry * 0.74)
    return [_arc(cx, cy, rx, ry, 0, 360),
            _I(_arc(cx, cy, rx - bv, ry - bh, 0, 360))]


def _band(cx, cy, rx, ry, bv, bh, a0, a1):
    """Open arc band (a curved stroke) from angle a0 to a1, CCW.
    Stroke thickness is clamped so small radii keep a real counter."""
    bv = min(bv, rx * 0.72)
    bh = min(bh, ry * 0.72)
    outer = _arc(cx, cy, rx, ry, a0, a1)
    inner = _arc(cx, cy, rx - bv, ry - bh, a1, a0)
    return [_O(_join(outer, inner))]


def _diag(x0, y0, x1, y1, w):
    """Straight stroke between two points, flat perpendicular caps."""
    dx, dy = x1 - x0, y1 - y0
    ln = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / ln * w / 2.0, dx / ln * w / 2.0
    return [_O([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)])]


def _foot(cx, P, wmul=1.0):
    """Serif foot slab centred cx on the baseline (empty for sans)."""
    if not P['SER']:
        return []
    hw = (P['S'] / 2.0 + P['SW']) * wmul
    return [_rect(cx - hw, 0, cx + hw, P['SH'])]


def _sx(P, lb=40.0):
    """Centre x of a left stem whose serif foot starts at lb."""
    return lb + P['SW'] + P['S'] / 2.0


# ---- glyph builders: each takes face params P, returns (advance, contours)

def _gA(P):
    cs = []
    cs += _diag(96, 0, 278, 692, P['S'] * 0.86)
    cs += _diag(470, 0, 288, 692, P['S'] * 1.0)
    cs.append(_rect(196, 216, 370, 216 + P['T']))
    cs += _foot(96, P, 0.8)
    cs += _foot(470, P, 0.8)
    return 566, cs


def _gB(P):
    sx = _sx(P)
    cxb = sx + 150
    cs = _stem(sx, 0, CAPU, P)
    cs.append(_rect(sx - P['S'] / 2, CAPU - P['T'], cxb + 90, CAPU))
    cs.append(_rect(sx - P['S'] / 2, 0, cxb + 90, P['T']))
    cs.append(_rect(sx - P['S'] / 2, 348 - P['T'] / 2, cxb + 40,
                    348 + P['T'] / 2))
    cs += _bowl(cxb, 512, 210, 168, P)
    cs += _bowl(cxb, 173, 222, 179, P)
    return 566, cs


def _gC(P):
    cs = _band(310, 340, 252, 354, P['BV'], P['BH'], 52, 308)
    if P['SER']:
        cs.append(_rect(446, 600, 514, 600 + P['T']))
        cs.append(_rect(446, 80 - P['T'], 514, 80))
    return 596, cs


def _gD(P):
    """D = stem + top/bottom bars + a right-half arc band whose ends
    land inside the bars (v3's full bowl bulged left of the stem and
    left a hairline gap where its ring passed the stem's inner face)."""
    sx = _sx(P)
    cs = _stem(sx, 0, CAPU, P)
    cx = sx + P['S'] * 0.9
    rx = 556 - cx
    cs.append(_rect(sx - P['S'] / 2, CAPU - P['T'], cx + rx * 0.45, CAPU))
    cs.append(_rect(sx - P['S'] / 2, 0, cx + rx * 0.45, P['T']))
    cs += _band(cx, 340, rx, 340, P['BV'], P['BH'], -90, 90)
    return 612, cs


def _gE(P):
    sx = _sx(P)
    x0 = sx - P['S'] / 2
    cs = _stem(sx, 0, CAPU, P)
    cs.append(_rect(x0, CAPU - P['T'], 500, CAPU))
    cs.append(_rect(x0, 344 - P['T'] / 2, 452, 344 + P['T'] / 2))
    cs.append(_rect(x0, 0, 506, P['T']))
    if P['SER']:
        cs.append(_rect(500 - P['SH'], CAPU - P['T'] - 30, 500, CAPU))
        cs.append(_rect(506 - P['SH'], 0, 506, P['T'] + 30))
    return 546, cs


def _gF(P):
    sx = _sx(P)
    x0 = sx - P['S'] / 2
    cs = _stem(sx, 0, CAPU, P)
    cs.append(_rect(x0, CAPU - P['T'], 494, CAPU))
    cs.append(_rect(x0, 350 - P['T'] / 2, 430, 350 + P['T'] / 2))
    if P['SER']:
        cs.append(_rect(494 - P['SH'], CAPU - P['T'] - 30, 494, CAPU))
    return 540, cs


def _gG(P):
    cs = _band(318, 340, 258, 354, P['BV'], P['BH'], 50, 310)
    cs.append(_rect(328, 300, 560, 300 + P['T']))
    cs += _stem(512, 0, 318, P, top=False, bot=True)
    if P['SER']:
        cs.append(_rect(446, 600, 514, 600 + P['T']))
    return 616, cs


def _gH(P):
    sx1 = _sx(P)
    sx2 = 626 - 40 - P['SW'] - P['S'] / 2.0
    cs = _stem(sx1, 0, CAPU, P)
    cs += _stem(sx2, 0, CAPU, P)
    cs.append(_rect(sx1 - P['S'] / 2, 330, sx2 + P['S'] / 2, 330 + P['T']))
    return 626, cs


def _gI(P):
    return 296, _stem(148, 0, CAPU, P)


def _gJ(P):
    cs = _stem(300, 120, CAPU, P, top=True, bot=False)
    cs += _band(150, 120, 150, 120, P['BV'], P['BH'], 180, 360)
    return 436, cs


def _gK(P):
    sx = _sx(P)
    cs = _stem(sx, 0, CAPU, P)
    cs += _diag(sx + P['S'] * 0.30, 356, 534, CAPU, P['S'] * 0.72)
    cs += _diag(sx + P['S'] * 0.55, 322, 528, 0, P['S'] * 0.95)
    cs += _foot(512, P, 0.62)
    return 586, cs


def _gL(P):
    sx = _sx(P)
    cs = _stem(sx, 0, CAPU, P)
    cs.append(_rect(sx - P['S'] / 2, 0, 480, P['T']))
    if P['SER']:
        cs.append(_rect(480 - P['SH'], 0, 480, P['T'] + 30))
    return 526, cs


def _gM(P):
    sx1 = _sx(P)
    sx2 = 786 - 40 - P['SW'] - P['S'] / 2.0
    cs = _stem(sx1, 0, CAPU, P)
    cs += _stem(sx2, 0, CAPU, P)
    cs += _diag(sx1, CAPU, 393, 268, P['S'] * 0.9)
    cs += _diag(393, 268, sx2, CAPU, P['S'] * 0.9)
    return 786, cs


def _gN(P):
    sx1 = _sx(P)
    sx2 = 646 - 40 - P['SW'] - P['S'] / 2.0
    cs = _stem(sx1, 0, CAPU, P)
    cs += _stem(sx2, 0, CAPU, P)
    cs += _diag(sx1, CAPU, sx2, 0, P['S'] * 0.92)
    return 646, cs


def _gO(P):
    return 646, _bowl(323, 340, 268, 354, P)


def _gP(P):
    sx = _sx(P)
    cxb = sx + 150
    cs = _stem(sx, 0, CAPU, P)
    cs.append(_rect(sx - P['S'] / 2, CAPU - P['T'], cxb + 80, CAPU))
    cs.append(_rect(sx - P['S'] / 2, 336, cxb + 40, 336 + P['T']))
    cs += _bowl(cxb, 508, 566 - 70 - cxb, 172, P)
    return 566, cs


def _gQ(P):
    cs = _bowl(323, 340, 268, 354, P)
    cs += _diag(400, 130, 612, -60, P['S'] * 0.8)
    return 646, cs


def _gR(P):
    sx = _sx(P)
    cxb = sx + 150
    cs = _stem(sx, 0, CAPU, P)
    cs.append(_rect(sx - P['S'] / 2, CAPU - P['T'], cxb + 80, CAPU))
    cs.append(_rect(sx - P['S'] / 2, 336, cxb + 40, 336 + P['T']))
    cs += _bowl(cxb, 508, 566 - 70 - cxb, 172, P)
    cs += _diag(330, 330, 520, 0, P['S'] * 0.95)
    cs += _foot(505, P, 0.6)
    return 580, cs


def _gS(P):
    cs = _band(272, 496, 196, 190, P['BV'], P['BH'], 25, 215)
    cs += _band(264, 182, 204, 196, P['BV'], P['BH'], 200, 400)
    cs += _diag(150, 405, 395, 300, P['BV'] * 0.9)
    if P['SER']:
        cs.append(_rect(404, 566, 478, 566 + P['T'] * 0.85))
        cs.append(_rect(52, 60, 128, 60 + P['T'] * 0.85))
    return 536, cs


def _gT(P):
    cs = [_rect(36, CAPU - P['T'], 530, CAPU)]
    if P['SER']:
        cs.append(_rect(36, CAPU - P['T'] - 34, 36 + P['SH'],
                        CAPU - P['T']))
        cs.append(_rect(530 - P['SH'], CAPU - P['T'] - 34, 530,
                        CAPU - P['T']))
    cs += _stem(283, 0, CAPU - P['T'] / 2, P, top=False, bot=True)
    return 566, cs


def _gU(P):
    """Stems sit on the bowl stroke's centreline (inset BV/2 from the
    bowl's outer tangents) and run down into the bowl, so the union
    has no step where stem meets curve (v3 centred the stems on the
    band endpoints: flat stem bottoms notched the counter)."""
    lx = 88 + P['BV'] / 2.0
    rx = 538 - P['BV'] / 2.0
    cs = _stem(lx, 130, CAPU, P, top=True, bot=False)
    cs += _stem(rx, 130, CAPU, P, top=True, bot=False)
    cs += _band(313, 200, 225, 200, P['BV'], P['BH'], 180, 360)
    return 626, cs


def _gV(P):
    cs = _diag(40, CAPU, 283, 0, P['S'] * 0.98)
    cs += _diag(546, CAPU, 303, 0, P['S'] * 0.9)
    if P['SER']:
        cs.append(_rect(16, CAPU - P['SH'], 124, CAPU))
    return 586, cs


def _gW(P):
    cs = _diag(36, CAPU, 150, 0, P['S'] * 0.9)
    cs += _diag(150, 0, 283, 430, P['S'] * 0.8)
    cs += _diag(283, 430, 416, 0, P['S'] * 0.8)
    cs += _diag(416, 0, 770, CAPU, P['S'] * 0.9)
    return 806, cs


def _gX(P):
    cs = _diag(52, 0, 524, CAPU, P['S'] * 0.88)
    cs += _diag(52, CAPU, 524, 0, P['S'] * 0.88)
    return 576, cs


def _gY(P):
    cs = _diag(40, CAPU, 288, 352, P['S'] * 0.95)
    cs += _diag(536, CAPU, 288, 352, P['S'] * 0.9)
    cs += _stem(288, 0, 352, P, top=False, bot=True)
    return 576, cs


def _gZ(P):
    cs = [_rect(44, CAPU - P['T'], 512, CAPU), _rect(44, 0, 512, P['T'])]
    cs += _diag(512, CAPU, 44, 0, P['S'] * 0.85)
    if P['SER']:
        cs.append(_rect(44, CAPU - P['T'] - 30, 44 + P['SH'],
                        CAPU - P['T']))
        cs.append(_rect(512 - P['SH'], P['T'], 512, P['T'] + 30))
    return 556, cs


def _ga(P):
    sx = 500 - 52 - P['SW'] - P['S'] / 2.0
    cs = _bowl(240, 372, 178, 112, P)
    cs += _bowl(246, 172, 208, 180, P)
    cs += _stem(sx, 0, XHU, P)
    return 500, cs


def _gb(P):
    sx = _sx(P)
    cs = _stem(sx, 0, ASCU, P)
    cs += _bowl(302, 238, 196, 248, P)
    return 536, cs


def _gc(P):
    cs = _band(248, 240, 192, 252, P['BV'], P['BH'], 52, 308)
    if P['SER']:
        cs.append(_rect(326, 424, 398, 424 + P['T'] * 0.8))
    return 470, cs


def _gd(P):
    sx = 536 - 40 - P['SW'] - P['S'] / 2.0
    cs = _bowl(234, 238, 196, 248, P)
    cs += _stem(sx, 0, ASCU, P)
    return 536, cs


def _ge(P):
    """'e' = an open band (like 'c' with a wider sweep) plus a
    separate bar rect that overlaps the band on both sides: the eye
    is enclosed by band + bar, the lower counter stays open."""
    cx, cy, rx, ry = 252.0, 240.0, 198.0, 252.0
    ybar = 262.0
    t2 = P['T'] / 2.0
    a_out = math.degrees(math.asin(max(-1.0, min(1.0,
                                                 (ybar + t2 - cy) / ry))))
    cs = _band(cx, cy, rx, ry, P['BV'], P['BH'], a_out, 322)
    cs.append(_rect(118, ybar - t2, 428, ybar + t2))
    return 496, cs


def _gf(P):
    """'f': one contour — stem whose top bends right into a hook."""
    cx = 118.0
    S = P['S']
    x0, x1 = cx - S / 2.0, cx + S / 2.0
    pts = [(x0, 0), (x1, 0), (x1, 460)]
    pts += _bez((x1, 460), (x1 + 6, 580), (x1 + 48, 648), (x1 + 98, 648),
                12)[1:]
    pts += _bez((x1 + 98, 648), (x1 + 118, 648), (x1 + 112, 596),
                (x1 + 100, 552), 8)[1:]
    pts += _bez((x1 + 100, 552), (x1 + 40, 500), (x0 + 28, 452),
                (x0, 428), 10)[1:]
    cs = [_O(pts)]
    cs += _foot(cx, P)
    cs.append(_rect(38, 380, 268, 380 + P['T']))
    return 300, cs


def _gg(P):
    sx = 530 - 40 - P['SW'] - P['S'] / 2.0
    cs = _bowl(234, 238, 196, 248, P)
    cs += _bowl(240, -50, 180, 142, P)
    cs += _stem(sx, DESCU, XHU, P, top=True, bot=False)
    if P['SER']:
        cs.append(_rect(sx - P['S'] / 2, DESCU, sx + P['S'] / 2 + 44,
                        DESCU + P['SH']))
    return 530, cs


def _gh(P):
    sx = _sx(P)
    cs = _stem(sx, 0, ASCU, P)
    cs += _band(280, 325, 155, 155, P['BV'], P['BH'], -38, 168)
    cs += _stem(399, 0, 235, P, top=False, bot=True)
    return 540, cs


def _gi(P):
    cs = _stem(130, 0, XHU, P)
    cs.append(_O(_arc(130, 605, 47, 52, 0, 360)))
    return 260, cs


def _gj(P):
    sx = 190.0
    cs = _stem(sx, -10, XHU, P, top=True, bot=False)
    cs += _band(118, -10, 118, 190, P['BV'], P['BH'], 175, 360)
    cs.append(_O(_arc(190, 605, 47, 52, 0, 360)))
    return 280, cs


def _gk(P):
    sx = _sx(P)
    cs = _stem(sx, 0, ASCU, P)
    cs += _diag(430, XHU, sx + P['S'] * 0.6, 240, P['S'] * 0.7)
    cs += _diag(sx + P['S'] * 0.85, 215, 452, 0, P['S'] * 0.92)
    cs += _foot(445, P, 0.5)
    return 500, cs


def _gl(P):
    return 260, _stem(130, 0, ASCU, P)


def _gm(P):
    sx1 = _sx(P)
    cs = _stem(sx1, 0, XHU, P, top=True, bot=True)
    cs += _band(235, 325, 125, 155, P['BV'], P['BH'], -38, 168)
    cs += _stem(360, 0, 235, P, top=False, bot=True)
    cs += _band(485, 325, 125, 155, P['BV'], P['BH'], -38, 168)
    cs += _stem(610, 0, 235, P, top=False, bot=True)
    return 740, cs


def _gn(P):
    sx = _sx(P)
    cs = _stem(sx, 0, XHU, P, top=True, bot=True)
    cs += _band(280, 325, 155, 155, P['BV'], P['BH'], -38, 168)
    cs += _stem(399, 0, 235, P, top=False, bot=True)
    return 540, cs


def _go(P):
    return 520, _bowl(260, 240, 205, 252, P)


def _gp(P):
    sx = _sx(P)
    cs = _stem(sx, DESCU, XHU, P, top=True, bot=False)
    cs += _bowl(302, 238, 196, 248, P)
    return 530, cs


def _gq(P):
    sx = 530 - 40 - P['SW'] - P['S'] / 2.0
    cs = _bowl(234, 238, 196, 248, P)
    cs += _stem(sx, DESCU, XHU, P, top=True, bot=False)
    if P['SER']:
        cs.append(_rect(sx - P['S'] / 2, DESCU, sx + P['S'] / 2 + 44,
                        DESCU + P['SH']))
    return 530, cs


def _gr(P):
    sx = _sx(P)
    cs = _stem(sx, 0, XHU, P, top=True, bot=True)
    cs += _band(205, 315, 148, 168, P['BV'], P['BH'], -42, 92)
    return 360, cs


def _gs(P):
    cs = _band(225, 345, 160, 140, P['BV'], P['BH'], 25, 215)
    cs += _band(218, 130, 166, 142, P['BV'], P['BH'], 200, 400)
    cs += _diag(105, 290, 330, 195, P['BV'] * 0.9)
    if P['SER']:
        cs.append(_rect(330, 392, 392, 392 + P['T'] * 0.8))
        cs.append(_rect(48, 36, 110, 36 + P['T'] * 0.8))
    return 440, cs


def _gt(P):
    sx = 150.0
    cs = _stem(sx, 0, 565, P, top=False, bot=False)
    cs.append(_rect(56, 330, 262, 330 + P['T']))
    cs += _band(232, 96, 96, 96, 62, 62, 180, 295)
    return 320, cs


def _gu(P):
    cs = _stem(90, 150, XHU, P, top=True, bot=False)
    cs += _stem(450, 0, XHU, P)
    cs += _band(270, 150, 180, 150, P['BV'], P['BH'], 180, 360)
    return 540, cs


def _gv(P):
    cs = _diag(36, XHU, 232, 0, P['S'])
    cs += _diag(444, XHU, 248, 0, P['S'] * 0.92)
    return 480, cs


def _gw(P):
    cs = _diag(28, XHU, 140, 0, P['S'] * 0.95)
    cs += _diag(140, 0, 265, 340, P['S'] * 0.8)
    cs += _diag(265, 340, 390, 0, P['S'] * 0.8)
    cs += _diag(390, 0, 652, XHU, P['S'] * 0.9)
    return 680, cs


def _gx(P):
    cs = _diag(44, 0, 426, XHU, P['S'] * 0.9)
    cs += _diag(44, XHU, 426, 0, P['S'] * 0.9)
    return 470, cs


def _gy(P):
    cs = _diag(36, XHU, 240, 140, P['S'])
    cs += _diag(444, XHU, 240, 140, P['S'] * 0.9)
    cs += _diag(240, 140, 168, DESCU, P['S'] * 0.85)
    return 480, cs


def _gz(P):
    cs = [_rect(25, XHU - P['T'], 425, XHU), _rect(25, 0, 425, P['T'])]
    cs += _diag(425, XHU, 25, 0, P['S'] * 0.85)
    return 450, cs


def _g0(P):
    return 520, _bowl(260, 340, 185, 352, P)


def _g1(P):
    cs = _stem(300, 0, CAPU, P, top=False, bot=True)
    cs += _diag(300, 640, 205, 520, P['S'] * 0.85)
    return 520, cs


def _g2(P):
    cs = _band(258, 470, 185, 195, P['BV'] * 0.55, P['BH'], -21, 205)
    cs += _diag(138, 428, 405, 28, P['S'] * 0.66)
    cs.append(_rect(70, 0, 452, P['T']))
    if P['SER']:
        cs.append(_rect(452 - P['SH'], 0, 452, P['T'] + 30))
    return 520, cs


def _g3(P):
    cs = _band(255, 490, 175, 185, P['BV'], P['BH'], -95, 180)
    cs += _diag(95, 480, 215, 350, P['BV'] * 0.8)
    cs += _band(255, 185, 190, 197, P['BV'], P['BH'], 180, 460)
    if P['SER']:
        cs.append(_rect(66, 462, 128, 462 + P['T'] * 0.8))
    return 520, cs


def _g4(P):
    cs = _stem(370, 0, CAPU, P, top=False, bot=True)
    cs += _diag(90, 120, 370, CAPU, P['S'] * 0.95)
    cs.append(_rect(60, 120, 470, 120 + P['T']))
    return 520, cs


def _g5(P):
    sx = _sx(P)
    cs = [_rect(sx - P['S'] / 2, CAPU - P['T'], 440, CAPU)]
    if P['SER']:
        cs.append(_rect(440 - P['SH'], CAPU - P['T'] - 30, 440, CAPU))
    cs += _stem(sx, 330, CAPU, P, top=False, bot=False)
    mb = 330 + P['T'] * 0.38
    cs.append(_rect(sx - P['S'] / 2, mb - P['T'] * 0.38, 362,
                    mb + P['T'] * 0.38))
    cs += _band(268, 196, 202, 182, P['BV'] * 0.62, P['BH'], 100, 385)
    return 520, cs


def _g6(P):
    cs = _diag(420, CAPU, 180, 300, P['S'] * 0.9)
    cs += _bowl(258, 235, 200, 248, P)
    return 520, cs


def _g7(P):
    cs = [_rect(70, CAPU - P['T'], 460, CAPU)]
    if P['SER']:
        cs.append(_rect(70, CAPU - P['T'] - 30, 70 + P['SH'],
                        CAPU - P['T']))
    cs += _diag(460, CAPU, 215, 0, P['S'] * 0.95)
    return 520, cs


def _g8(P):
    cs = _bowl(258, 492, 158, 182, P)
    cs += _bowl(258, 182, 188, 194, P)
    return 520, cs


def _g9(P):
    sx = 530 - 40 - P['SW'] - P['S'] / 2.0
    cs = _bowl(258, 445, 200, 248, P)
    cs += _stem(sx, 120, CAPU, P, top=True, bot=False)
    cs += _band(258, 130, 168, 130, P['BV'], P['BH'], 270, 395)
    return 520, cs


def _gdot(P):
    return 250, [_O(_arc(125, 42, 46, 46, 0, 360))]


def _gcomma(P):
    cs = [_O(_arc(130, 62, 48, 48, 0, 360))]
    cs.append(_O([(178, 110), (200, 66), (152, -92), (94, -92),
                  (142, 32), (122, 96)]))
    return 250, cs


def _gapos(P):
    return 190, [_O([(95, 690), (152, 690), (128, 520), (86, 520)])]


def _gaposl(P):
    return 190, [_O([(55, 690), (112, 690), (136, 520), (94, 520)])]


def _gquote(P):
    cs = [_O([(80, 690), (137, 690), (113, 520), (71, 520)]),
          _O([(240, 690), (297, 690), (273, 520), (231, 520)])]
    return 330, cs


def _ghyph(P):
    return 300, [_rect(30, 250, 270, 250 + P['T'] * 0.8)]


def _gendash(P):
    return 420, [_rect(25, 250, 395, 250 + P['T'] * 0.8)]


def _gemdash(P):
    return 640, [_rect(20, 250, 620, 250 + P['T'] * 0.8)]


def _gcolon(P):
    cs = [_O(_arc(125, 468, 44, 44, 0, 360)),
          _O(_arc(125, 42, 44, 44, 0, 360))]
    return 250, cs


def _gsemi(P):
    cs = [_O(_arc(128, 468, 44, 44, 0, 360))]
    cs += _gcomma(P)[1]
    return 250, cs


def _gexcl(P):
    cs = [_O([(100, 690), (154, 690), (147, 195), (107, 195)]),
          _O(_arc(127, 42, 46, 46, 0, 360))]
    return 250, cs


def _gquest(P):
    cs = _band(250, 520, 165, 160, P['BV'], P['BH'], -60, 190)
    cs.append(_rect(224, 180, 276, 330))
    cs.append(_O(_arc(250, 42, 46, 46, 0, 360)))
    return 470, cs


def _gdollar(P):
    cs = _band(262, 490, 170, 180, P['BV'], P['BH'], 25, 215)
    cs += _band(258, 185, 180, 190, P['BV'], P['BH'], 200, 400)
    cs += _diag(150, 405, 395, 300, P['BV'] * 0.85)
    cs.append(_rect(244, -40, 276, 730))
    return 520, cs


def _gpercent(P):
    cs = _bowl(140, 520, 105, 115, P)
    cs += _bowl(610, 180, 105, 115, P)
    cs += _diag(640, 700, 110, 0, 60)
    return 750, cs


def _gamp(P):
    cs = _bowl(275, 525, 125, 135, P)
    cs += _bowl(282, 178, 198, 192, P)
    cs += _diag(215, 645, 362, 428, 50)
    cs += _diag(195, 345, 462, 0, 54)
    cs += _foot(462, P, 0.8)
    return 590, cs


def _gslash(P):
    return 320, _diag(60, -30, 260, 710, 58)


def _glparen(P):
    return 300, _band(330, 340, 290, 430, 54, 54, 100, 260)


def _grparen(P):
    return 300, _band(-30, 340, 290, 430, 54, 54, -80, 80)


def _gmiddot(P):
    return 200, [_O(_arc(100, 250, 40, 40, 0, 360))]


def _gbullet(P):
    return 260, [_O(_arc(130, 330, 62, 62, 0, 360))]


def _gup(P):
    cs = [_rect(192, 0, 268, 470),
          _O([(230, 705), (70, 455), (390, 455)])]
    return 460, cs


def _gdown(P):
    cs = [_rect(192, 230, 268, 700),
          _O([(230, -5), (70, 245), (390, 245)])]
    return 460, cs


def _gtriup(P):
    return 480, [_O([(240, 640), (460, 60), (20, 60)])]


def _gtridn(P):
    return 480, [_O([(20, 640), (460, 640), (240, 60)])]


def _gstar(P):
    return 560, [_O(_star(280, 330, 270, 110))]


def _gplus(P):
    return 460, [_rect(30, 300, 430, 362), _rect(197, 130, 263, 532)]


def _geq(P):
    return 460, [_rect(30, 354, 430, 406), _rect(30, 194, 430, 246)]


def _gellip(P):
    cs = [_O(_arc(x, 42, 40, 40, 0, 360)) for x in (80, 320, 560)]
    return 640, cs


def _gpound(P):
    sx = _sx(P)
    cs = _stem(sx, 0, 545, P, top=False, bot=True)
    cs += _band(238, 545, 92, 108, P['BV'] * 0.8, P['BH'] * 0.8, -20, 180)
    cs.append(_rect(88, 318, 402, 318 + P['T']))
    cs.append(_rect(sx - P['S'] / 2, 0, 472, P['T']))
    if P['SER']:
        cs.append(_rect(472 - P['SH'], 0, 472, P['T'] + 30))
    return 540, cs


def _geuro(P):
    cs = _band(300, 340, 230, 350, P['BV'], P['BH'], 55, 305)
    cs.append(_rect(58, 382, 382, 382 + P['T'] * 0.7))
    cs.append(_rect(58, 262, 362, 262 + P['T'] * 0.7))
    return 580, cs


def _gspace(P):
    return 235, []


_BUILD = {
    'A': _gA, 'B': _gB, 'C': _gC, 'D': _gD, 'E': _gE, 'F': _gF,
    'G': _gG, 'H': _gH, 'I': _gI, 'J': _gJ, 'K': _gK, 'L': _gL,
    'M': _gM, 'N': _gN, 'O': _gO, 'P': _gP, 'Q': _gQ, 'R': _gR,
    'S': _gS, 'T': _gT, 'U': _gU, 'V': _gV, 'W': _gW, 'X': _gX,
    'Y': _gY, 'Z': _gZ,
    'a': _ga, 'b': _gb, 'c': _gc, 'd': _gd, 'e': _ge, 'f': _gf,
    'g': _gg, 'h': _gh, 'i': _gi, 'j': _gj, 'k': _gk, 'l': _gl,
    'm': _gm, 'n': _gn, 'o': _go, 'p': _gp, 'q': _gq, 'r': _gr,
    's': _gs, 't': _gt, 'u': _gu, 'v': _gv, 'w': _gw, 'x': _gx,
    'y': _gy, 'z': _gz,
    '0': _g0, '1': _g1, '2': _g2, '3': _g3, '4': _g4, '5': _g5,
    '6': _g6, '7': _g7, '8': _g8, '9': _g9,
    '.': _gdot, ',': _gcomma, "'": _gapos, '\u2019': _gapos,
    '\u2018': _gaposl, '"': _gquote, '\u201c': _gquote,
    '\u201d': _gquote, '-': _ghyph, '\u2013': _gendash,
    '\u2014': _gemdash, ':': _gcolon, ';': _gsemi, '!': _gexcl,
    '?': _gquest, '$': _gdollar, '%': _gpercent, '&': _gamp,
    '/': _gslash, '(': _glparen, ')': _grparen, '\u00b7': _gmiddot,
    '\u2022': _gbullet, '\u2191': _gup, '\u2193': _gdown,
    '\u25b2': _gtriup, '\u25bc': _gtridn, '\u2605': _gstar,
    '+': _gplus, '=': _geq, '\u2026': _gellip, '\u00a3': _gpound,
    '\u20ac': _geuro, ' ': _gspace,
}

_BUILT = {}
_SPANS = {}


def _glyph(ch, weight):
    key = (ch, weight)
    got = _BUILT.get(key)
    if got is None:
        fn = _BUILD.get(ch)
        if fn is None and ch.lower() != ch:
            fn = _BUILD.get(ch.lower())
        if fn is None:
            fn = _BUILD['?']
        got = fn(_FACES[weight])
        _BUILT[key] = got
    return got


def _glyph_spans(ch, weight, size):
    """Rasterise one glyph: returns (advance_px, spans) where spans are
    (dy, x0, x1) in device px relative to pen x and baseline y."""
    key = (ch, weight, int(size * 4))
    got = _SPANS.get(key)
    if got is not None:
        return got
    adv_u, contours = _glyph(ch, weight)
    f = size / CAPU
    d = f * SS
    edges = []
    ys = []
    for c in contours:
        pts = [(x * d, -y * d) for x, y in c]
        ys += [p[1] for p in pts]
        n = len(pts)
        for i in range(n):
            edges.append((pts[i], pts[(i + 1) % n]))
    spans = []
    if ys:
        y_lo = int(math.floor(min(ys)))
        y_hi = int(math.ceil(max(ys)))
        for yy in range(y_lo, y_hi + 1):
            yc = yy + 0.5
            xs = []
            for (xa, ya), (xb, yb) in edges:
                if (ya <= yc < yb) or (yb <= yc < ya):
                    xs.append((xa + (yc - ya) * (xb - xa) / (yb - ya),
                               1 if yb > ya else -1))
            if not xs:
                continue
            xs.sort()
            w = 0
            prev = None
            for xint, dirn in xs:
                if prev is not None and w != 0 and xint > prev:
                    spans.append((yy, prev, xint))
                w += dirn
                prev = xint
    got = (adv_u * f, spans)
    _SPANS[key] = got
    return got


def text_width(s, size, weight='reg', tracking=0.0):
    """Width in output px of string s at cap-height `size` px."""
    f = size / CAPU
    w = 0.0
    prev = None
    for ch in s:
        w += _glyph(ch, weight)[0]
        if prev is not None and weight != 'reg':
            w += _KERN.get((prev, ch), 0)
        prev = ch
    w *= f
    if len(s) > 1:
        w += tracking * (len(s) - 1)
    return w


def draw_text(cv, x, y_base, s, size, col, weight='reg', tracking=0.0,
              align='left'):
    """Draw string s with baseline at y_base (output px). Returns end x."""
    w = text_width(s, size, weight, tracking)
    if align == 'center':
        x -= w / 2
    elif align == 'right':
        x -= w
    f = size / CAPU
    pen = x
    prev = None
    for ch in s:
        if prev is not None and weight != 'reg':
            pen += _KERN.get((prev, ch), 0) * f
        adv_px, spans = _glyph_spans(ch, weight, size)
        if spans:
            bx = pen * SS
            by = y_base * SS
            for dy, x0, x1 in spans:
                cv._set_span(int(bx + x0), int(bx + x1), int(by) + dy,
                             col)
            # note: span x1 is the far edge; _set_span is inclusive, and
            # neighbouring spans never share a pixel row segment.
        pen += adv_px + tracking
        prev = ch
    return pen


def wrap_text(s, size, weight, max_w, tracking=0.0):
    """Greedy word wrap; honours explicit newlines. Returns list of lines."""
    lines = []
    for para in s.split('\n'):
        words = para.split()
        if not words:
            lines.append('')
            continue
        cur = words[0]
        for wd in words[1:]:
            trial = cur + ' ' + wd
            if text_width(trial, size, weight, tracking) <= max_w:
                cur = trial
            else:
                lines.append(cur)
                cur = wd
        lines.append(cur)
    return lines


def draw_block(cv, x, y_top, s, size, col, weight, max_w, leading,
               tracking=0.0, align='left'):
    """Wrap and draw a paragraph; y_top is the top of the cap height of
    the first line. Returns the y just below the last line's baseline."""
    lines = wrap_text(s, size, weight, max_w, tracking)
    yb = y_top + size
    for ln in lines:
        draw_text(cv, x, yb, ln, size, col, weight, tracking, align)
        yb += leading
    return yb - leading


# --------------------------------------------------------------------------
# Page layout — "THE WORLD TODAY", Wednesday 19 November 2026
# --------------------------------------------------------------------------

PAPER = (247, 243, 233)
CARD = (255, 253, 244)
INK = (23, 32, 42)
INK2 = (52, 50, 44)
GREY = (110, 102, 88)
HAIR = (203, 195, 172)
RED = (176, 42, 36)
WHITE = (255, 255, 255)

REG_EUROPE = (61, 84, 120)
REG_AMERICAS = (156, 56, 72)
REG_ASIA = (31, 122, 109)
REG_MIDEAST = (166, 118, 43)
REG_AFRICA = (109, 76, 65)
REG_OCEANIA = (74, 124, 155)
REG_WORLD = (91, 117, 83)
REG_SPORT = (34, 110, 52)

MX = 12                 # page margin
CW = W - 2 * MX         # content width = 1000

def hline(cv, x, y, w, col=HAIR, thick=1.0):
    cv.rect(x, y, w, thick, col)

# ---- card illustration strips: layered flat-illustration scenes ---------
# Every strip is drawn from code primitives only (rects, discs, polygons,
# lines, vertical gradients) — layered silhouettes, lit windows, glows and
# small true details. Deterministic: the only randomness is a fixed-seed
# LCG, so reruns are byte-identical.

def _lerp(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def _grad(cv, x, y, w, h, stops):
    """Vertical gradient through (pos, colour) stops."""
    for yy in range(int(h)):
        t = yy / max(1.0, h - 1)
        col = stops[-1][1]
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                col = _lerp(c0, c1, (t - p0) / max(1e-6, p1 - p0))
                break
        cv.rect(x, y + yy, w, 1, col)


def _lcg(seed):
    s = [seed & 0x7fffffff]

    def nxt():
        s[0] = (s[0] * 1103515245 + 12345) & 0x7fffffff
        return s[0] / 0x7fffffff
    return nxt


def _glow(cv, cx, cy, r, col, base):
    """Soft disc: two blended halos under a solid core."""
    cv.disc(cx, cy, r * 1.9, _lerp(base, col, 0.28))
    cv.disc(cx, cy, r * 1.4, _lerp(base, col, 0.55))
    cv.disc(cx, cy, r, col)


def _windows(cv, x, y, w, h, seed, col=(243, 205, 120), density=0.42):
    rnd = _lcg(seed)
    yy = y + 3
    while yy < y + h - 3:
        xx = x + 3
        while xx < x + w - 3:
            if rnd() < density:
                cv.rect(xx, yy, 1.6, 2.2, col)
            xx += 4.5
        yy += 5


def _arcpts(cx, cy, rx, ry, a0, a1, step=6):
    pts = []
    n = max(2, int(abs(a1 - a0) / step))
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((cx + rx * math.cos(a), cy - ry * math.sin(a)))
    return pts


def _ln(cv, x0, y0, x1, y1, col, thick):
    """Art-section line helper (colour first, like the other helpers)."""
    cv.line(x0, y0, x1, y1, thick, col)


def art_skyline(cv, x, y, w, h):
    """Shenzhen at dusk: layered towers, lit windows, three flags."""
    _grad(cv, x, y, w, h, [(0, (13, 22, 44)), (0.55, (23, 44, 66)),
                           (0.82, (64, 62, 58)), (1, (150, 96, 52))])
    _glow(cv, x + w * 0.72, y + h * 0.66, 6, (240, 180, 100), (120, 84, 56))
    back = (36, 52, 74)
    for bx, bh in ((0, 14), (26, 20), (54, 11), (84, 24), (118, 16),
                   (150, 22), (186, 13), (216, 19), (250, 15), (282, 21),
                   (310, 12)):
        cv.rect(x + bx, y + h - bh, 24, bh, back)
    front = (9, 14, 24)
    towers = ((6, 26, 30), (44, 32, 32), (88, 24, 30), (128, 34, 34),
              (176, 27, 30), (220, 31, 32), (262, 25, 28), (300, 30, 28))
    for bx, bh, bw in towers:
        cv.rect(x + bx, y + h - bh, bw, bh, front)
    _windows(cv, x + 44, y + h - 32, 32, 32, 11)
    _windows(cv, x + 128, y + h - 34, 34, 34, 23)
    _windows(cv, x + 220, y + h - 31, 32, 31, 37)
    for bx, bh, col in ((59, 32, (198, 42, 40)), (145, 34, (62, 96, 205)),
                        (236, 31, (232, 182, 62))):
        _ln(cv, x + bx, y + h - bh, x + bx, y + h - bh - 6, (200, 205, 210), 1)
        cv.rect(x + bx, y + h - bh - 6, 6.5, 3.6, col)
    cv.rect(x, y + h - 4, w, 4, (6, 10, 18))
    for dx in (30, 90, 150, 205, 262, 305):
        cv.rect(x + dx, y + h - 2.6, 9, 1.1, (110, 140, 165))


def art_sea(cv, x, y, w, h):
    """Hormuz at sunset: a warship silhouetted on a glowing sea."""
    _grad(cv, x, y, w, h * 0.68, [(0, (58, 44, 84)), (0.45, (148, 74, 84)),
                                  (0.75, (226, 128, 72)), (1, (240, 164, 92))])
    _glow(cv, x + w * 0.66, y + h * 0.64, 5.5, (248, 196, 110), (200, 110, 70))
    _grad(cv, x, y + h * 0.68, w, h * 0.32 + 1,
          [(0, (110, 64, 56)), (1, (12, 20, 34))])
    for i, dx in enumerate((0, -9, 7, -16, 14, -24)):
        cv.rect(x + w * 0.66 + dx - 6 + i * 2, y + h * 0.78 + i * 2.8,
                12 - i * 1.4, 1.1, (196, 138, 88))
    ship = (13, 19, 31)
    cv.poly([(x + 18, y + 31), (x + 62, y + 31), (x + 57, y + 35.5),
             (x + 24, y + 35.5)], ship)
    cv.rect(x + 34, y + 28.5, 14, 2.8, ship)
    hull = [(x + 74, y + 29.5), (x + 258, y + 29.5), (x + 242, y + 37.5),
            (x + 92, y + 37.5)]
    cv.poly(hull, ship)
    cv.rect(x + 118, y + 23.5, 62, 6, ship)
    cv.rect(x + 138, y + 17.5, 26, 6, ship)
    cv.rect(x + 146, y + 13.5, 10, 4, ship)
    cv.rect(x + 198, y + 19.5, 10, 10, ship)
    cv.rect(x + 198, y + 19.5, 10, 2.4, (40, 30, 26))
    _ln(cv, x + 106, y + 29.5, x + 106, y + 9, ship, 1.6)
    _ln(cv, x + 106, y + 14, x + 92, y + 19, ship, 1)
    _ln(cv, x + 106, y + 14, x + 120, y + 19, ship, 1)
    _ln(cv, x + 224, y + 29.5, x + 224, y + 15, ship, 1.4)
    _ln(cv, x + 224, y + 18, x + 212, y + 22, ship, 1)
    _ln(cv, x + 224, y + 18, x + 236, y + 22, ship, 1)
    for dx in (0, 7, 14):
        cv.rect(x + 250 - dx * 2.2, y + 36.6, 5 - dx * 0.12, 1.1,
                (205, 214, 224))


def art_chart(cv, x, y, w, h):
    """Nasdaq: rising bars, a trend line and an arrow breaking out."""
    _grad(cv, x, y, w, h, [(0, (8, 22, 15)), (1, (5, 12, 9))])
    for fy in (0.28, 0.52, 0.76):
        cv.rect(x + 4, y + h * fy, w - 8, 0.8, (26, 58, 40))
    for fx in (0.27, 0.52, 0.77):
        cv.rect(x + w * fx, y + 3, 0.8, h - 6, (26, 58, 40))
    base = y + h - 5
    heights = (8, 12, 10, 16, 14, 20, 26, 31)
    cols = [(30, 130, 74)] * 6 + [(232, 150, 44), (232, 96, 44)]
    tops = []
    for i, (bh, col) in enumerate(zip(heights, cols)):
        bx = x + 16 + i * 38
        cv.rect(bx, base - bh, 17, bh, col)
        cv.rect(bx, base - bh, 17, 2, _lerp(col, (255, 255, 255), 0.25))
        tops.append((bx + 8.5, base - bh - 3))
    for i in range(len(tops) - 1):
        _ln(cv, tops[i][0], tops[i][1], tops[i + 1][0], tops[i + 1][1],
                (74, 226, 130), 1.7)
    for tx, ty in tops:
        cv.disc(tx, ty, 1.5, (235, 250, 240))
    ex, ey = tops[-1]
    cv.poly([(ex + 2, ey - 6), (ex + 11, ey - 3.5), (ex + 4, ey + 3)],
            (74, 226, 130))


def art_scales(cv, x, y, w, h):
    """The golden scales of The Hague on a dark ground."""
    _grad(cv, x, y, w, h, [(0, (26, 19, 10)), (1, (12, 9, 5))])
    cx = x + w / 2
    _glow(cv, cx, y + 20, 11, (232, 190, 90), (30, 23, 12))
    dark, mid, bright = (146, 106, 38), (206, 158, 62), (240, 206, 110)
    cv.rect(cx - 88, y + 7, 176, 3, mid)
    cv.rect(cx - 88, y + 7, 176, 1.2, bright)
    cv.disc(cx - 88, y + 8.5, 2.6, bright)
    cv.disc(cx + 88, y + 8.5, 2.6, bright)
    cv.disc(cx, y + 5.5, 3.2, bright)
    cv.rect(cx - 2.2, y + 8, 4.4, 23, mid)
    cv.rect(cx, y + 8, 2.2, 23, dark)
    cv.poly([(cx - 14, y + 41), (cx + 14, y + 41), (cx + 4, y + 30),
             (cx - 4, y + 30)], mid)
    cv.rect(cx - 17, y + 40.4, 34, 2.4, dark)
    for sgn in (-1, 1):
        px = cx + sgn * 84
        _ln(cv, cx + sgn * 84, y + 10, px - 11, y + 27, bright, 0.9)
        _ln(cv, cx + sgn * 84, y + 10, px + 11, y + 27, bright, 0.9)
        cv.poly(_arcpts(px, y + 27, 15, 9, 180, 360), dark)
        rim = _arcpts(px, y + 27, 15, 9, 180, 360, 4)
        for i in range(len(rim) - 1):
            _ln(cv, rim[i][0], rim[i][1], rim[i + 1][0], rim[i + 1][1],
                    bright, 1.1)


def art_bridge(cv, x, y, w, h):
    """The Kerch Bridge lit at night, arch and cables over dark water."""
    _grad(cv, x, y, w, h * 0.62, [(0, (8, 14, 30)), (0.7, (16, 28, 48)),
                                  (1, (22, 38, 58))])
    _glow(cv, x + w * 0.82, y + 9, 3, (220, 228, 240), (24, 36, 56))
    _grad(cv, x, y + h * 0.62, w, h * 0.38 + 1,
          [(0, (14, 24, 40)), (1, (6, 10, 20))])
    cx = x + w / 2
    deck = y + 24
    arch = _arcpts(cx, deck + 3, 92, 17, 180, 360, 4)
    for i in range(len(arch) - 1):
        _ln(cv, arch[i][0], arch[i][1], arch[i + 1][0], arch[i + 1][1],
                (84, 112, 140), 2.4)
    for i in range(0, len(arch), 3):
        cv.disc(arch[i][0], arch[i][1], 1.05, (246, 214, 140))
    for sgn in (-1, 1):
        cv.rect(cx + sgn * 58 - 2, y + 9, 4, 16, (24, 40, 62))
    cable = []
    for i in range(25):
        t = i / 24
        px = cx - 58 + 116 * t
        py = y + 9 + 13 * (1 - (2 * t - 1) ** 2) * 0.72 + 9.5 * (2 * t - 1) ** 2
        cable.append((px, py))
    for i in range(len(cable) - 1):
        _ln(cv, cable[i][0], cable[i][1], cable[i + 1][0], cable[i + 1][1],
                (140, 168, 192), 1.1)
    for fx in (-40, -20, 0, 20, 40):
        _ln(cv, cx + fx, y + 20.5 - abs(fx) * 0.06, cx + fx, deck,
                (80, 105, 130), 0.8)
    cv.rect(x, deck, w, 3.4, (20, 32, 50))
    cv.rect(x, deck - 1.4, w, 1, (90, 120, 150))
    rnd = _lcg(7)
    for lx in range(10, int(w) - 6, 15):
        cv.disc(x + lx, deck + 1.2, 1.15, (246, 214, 140))
        if rnd() < 0.7:
            cv.rect(x + lx - 2.5, deck + 6 + rnd() * 6, 5, 1,
                    (110, 100, 74))


def art_climate(cv, x, y, w, h):
    """Smokestacks at dusk: plumes drifting over a factory silhouette."""
    _grad(cv, x, y, w, h, [(0, (74, 44, 54)), (0.55, (150, 78, 62)),
                           (0.85, (216, 128, 74)), (1, (228, 150, 84))])
    _glow(cv, x + w * 0.2, y + h * 0.72, 7, (246, 206, 140), (190, 110, 70))
    rnd = _lcg(41)
    stacks = ((140, 8), (168, 4), (205, 12))
    for sx, stop in stacks:
        for i in range(6):
            px = x + sx + 6 + i * 9 + rnd() * 3
            py = y + stop - 2 - i * 2.6
            r = 2.6 + i * 0.85
            cv.disc(px, py, r, _lerp((96, 86, 84), (168, 138, 122),
                                     i / 5))
    sil = (26, 18, 16)
    cv.rect(x + 118, y + 26, 132, 17, sil)
    for i in range(3):
        bx = x + 126 + i * 40
        cv.poly([(bx, y + 26), (bx + 12, y + 20), (bx + 24, y + 26)], sil)
    for sx, stop in stacks:
        cv.rect(x + sx, y + stop, 9 if sx != 168 else 11, 43 - stop, sil)
        cv.rect(x + sx + (9 if sx != 168 else 11) - 1.6, y + stop, 1.6,
                43 - stop, (122, 82, 60))
    cv.rect(x, y + h - 5, w, 5, (20, 14, 12))
    _windows(cv, x + 124, y + 28, 120, 12, 53, (240, 180, 100), 0.3)


def art_drought(cv, x, y, w, h):
    """El Nino: cracked earth, a hard sun and one green sprout."""
    _grad(cv, x, y, w, h * 0.52, [(0, (168, 198, 224)), (0.55, (232, 220, 178)),
                                  (1, (246, 214, 150))])
    sx, sy = x + w * 0.8, y + 10
    for i in range(8):
        a = math.radians(i * 45)
        _ln(cv, sx + 9 * math.cos(a), sy - 9 * math.sin(a),
                sx + 12.5 * math.cos(a), sy - 12.5 * math.sin(a),
                (246, 200, 110), 1.2)
    _glow(cv, sx, sy, 6, (250, 226, 150), (240, 210, 150))
    _grad(cv, x, y + h * 0.52, w, h * 0.48 + 1,
          [(0, (196, 156, 98)), (1, (148, 108, 62))])
    cv.poly([(x, y + h * 0.52), (x + 60, y + h * 0.47), (x + 130, y + h * 0.52),
             (x + 210, y + h * 0.485), (x + 280, y + h * 0.52),
             (x + w, y + h * 0.5), (x + w, y + h * 0.56), (x, y + h * 0.56)],
            (170, 128, 78))
    crack = (96, 66, 34)
    pts = [(8, 36), (34, 33.5), (58, 37), (86, 34.5), (112, 38), (140, 35.5)]
    for i in range(len(pts) - 1):
        _ln(cv, x + pts[i][0], y + pts[i][1], x + pts[i + 1][0],
                y + pts[i + 1][1], crack, 1.1)
    _ln(cv, x + 58, y + 37, x + 74, y + 41.5, crack, 0.9)
    _ln(cv, x + 240, y + 38, x + 262, y + 35, crack, 1)
    _ln(cv, x + 262, y + 35, x + 282, y + 38.5, crack, 1)
    _ln(cv, x + 262, y + 35, x + 270, y + 30.5, crack, 0.9)
    gx, gy = x + w * 0.42, y + 34.5
    _ln(cv, gx, gy, gx, gy - 7.5, (74, 146, 62), 1.5)
    cv.poly([(gx, gy - 6), (gx - 8.5, gy - 10.5), (gx - 9.5, gy - 5.5),
             (gx - 3, gy - 4)], (96, 178, 84))
    cv.poly([(gx, gy - 6.5), (gx + 8.5, gy - 11.5), (gx + 9.5, gy - 6),
             (gx + 3, gy - 4.5)], (58, 128, 50))


def art_columns(cv, x, y, w, h):
    """A white palace facade: pediment, six columns, two flags."""
    _grad(cv, x, y, w, h, [(0, (146, 186, 224)), (1, (218, 234, 246))])
    for dx in (18, 70, 250, 300):
        cv.disc(x + dx, y + h * 0.6, 7, (122, 144, 118))
    cv.rect(x, y + h * 0.62, w, 3, (110, 134, 108))
    cx = x + w / 2
    cream, shade, dark = (240, 232, 212), (206, 196, 172), (96, 88, 76)
    cv.rect(cx - 95, y + h - 3.4, 190, 3.4, shade)
    cv.rect(cx - 84, y + h - 6.4, 168, 3, cream)
    cv.rect(cx - 74, y + h - 9.4, 148, 3, shade)
    for i in range(6):
        cxx = cx - 62 + i * 25
        cv.rect(cxx, y + 16, 7.5, h - 25.4, cream)
        cv.rect(cxx + 5.5, y + 16, 2, h - 25.4, shade)
        if i < 5:
            cv.rect(cxx + 11, y + 19, 8, 12, dark)
    cv.rect(cx - 4.5, y + 22, 9, h - 31.4, (70, 62, 54))
    cv.rect(cx - 80, y + 11.6, 160, 4.6, cream)
    cv.rect(cx - 80, y + 15.4, 160, 1.4, shade)
    cv.poly([(cx - 86, y + 11.6), (cx + 86, y + 11.6), (cx, y + 2.6)], cream)
    cv.disc(cx, y + 8.6, 2.2, shade)
    for sgn in (-1, 1):
        px = cx + sgn * 96
        _ln(cv, px, y + 5, px, y + 27, (90, 84, 76), 1.1)
        cv.rect(px, y + 5, sgn * 9, 2.8, (198, 48, 48))
        cv.rect(px, y + 7.8, sgn * 9, 2.8, (244, 244, 244))


def art_football(cv, x, y, w, h):
    """A floodlit stadium at night, the ball waiting on the pitch."""
    _grad(cv, x, y, w, h, [(0, (10, 18, 34)), (1, (18, 32, 50))])
    for fx in (x + 42, x + w - 42):
        _glow(cv, fx, y + 8, 3.4, (225, 238, 255), (24, 38, 58))
        for r_ in range(2):
            for c_ in range(3):
                cv.disc(fx - 3 + c_ * 3, y + 6 + r_ * 3.4, 1, (245, 250, 255))
    cv.poly([(x + 8, y + 30), (x + 30, y + 15), (x + w - 30, y + 15),
             (x + w - 8, y + 30), (x + w - 18, y + 34.5), (x + 18, y + 34.5)],
            (16, 26, 42))
    cv.rect(x + 30, y + 15, w - 60, 1.6, (52, 76, 104))
    rnd = _lcg(97)
    for i in range(46):
        cv.rect(x + 22 + rnd() * (w - 44), y + 19 + rnd() * 9, 1.3, 1.3,
                (96, 116, 144))
    _grad(cv, x, y + 31, w, h - 31, [(0, (36, 124, 54)), (1, (24, 92, 40))])
    cv.rect(x + w / 2 - 0.7, y + 31.5, 1.4, h - 32, (205, 228, 205))
    ell = _arcpts(x + w / 2, y + 37.5, 17, 4.6, 0, 360, 10)
    for i in range(len(ell) - 1):
        _ln(cv, ell[i][0], ell[i][1], ell[i + 1][0], ell[i + 1][1],
                (205, 228, 205), 0.9)
    bx, by = x + w * 0.68, y + 34.5
    cv.disc(bx, by, 8.6, (242, 244, 246))
    cv.disc(bx, by, 2.7, (22, 26, 32))
    for dx, dy in ((-5.6, -3.4), (5.6, -3.4), (-3.6, 5), (3.6, 5)):
        cv.disc(bx + dx, by + dy, 1.8, (22, 26, 32))

ART = [art_skyline, art_sea, art_chart, art_scales, art_bridge,
       art_climate, art_drought, art_columns, art_football]


CARDS = [
    ("SHENZHEN · SUMMIT", "AP", REG_ASIA,
     "Trump, Xi and Putin hold first three-way summit",
     "The first US-China-Russia summit, at APEC in Shenzhen, ends with a "
     "peace declaration and a call to reform the UN."),
    ("HORMUZ · WAR", "REUTERS", REG_MIDEAST,
     "Iran widens war: Kuwait, Bahrain hit",
     "Tehran answers US strikes on Qeshm Island as tankers are mined near "
     "Hormuz; Trump warns of a dirty-bomb red line."),
    ("NASDAQ · MARKETS", "CNBC", REG_AMERICAS,
     "Anthropic's $81.3bn IPO smashes the record",
     "Priced at $83 a share, the debut tops SpaceX's $75bn; trading opens "
     "today on Nasdaq as ANT, valued near $1.5tn."),
    ("THE HAGUE · LAW", "REUTERS", REG_EUROPE,
     "World Court: Myanmar committed genocide",
     "The ICJ rules Myanmar's campaign against the Rohingya was "
     "state-sponsored genocide — a first ruling of its kind."),
    ("CRIMEA · WAR", "AP", REG_EUROPE,
     "Ukraine strikes the Kerch Bridge again",
     "A third strike in four days halts rail traffic on Russia's Crimea "
     "bridge; Putin vows a response."),
    ("CLIMATE · TALKS", "REUTERS", REG_WORLD,
     "COP31 split over fossil-fuel phase-out",
     "Climate talks enter their final stage still split over phase-out "
     "wording and finance, with Friday's close nearing."),
    ("FIJI · DISASTER", "WIRE", REG_OCEANIA,
     "Fiji declares disaster in El Nino drought",
     "A national state of disaster is declared as El Nino drought grips "
     "the Pacific islands."),
    ("JAKARTA · LAW", "REUTERS", REG_ASIA,
     "Indonesia can now seize crime assets",
     "Parliament passes an asset-forfeiture law letting the state seize "
     "crime-linked assets without a prior conviction."),
    ("FOOTBALL · SPORT", "WIRE", REG_SPORT,
     "Pochettino takes charge at Man United",
     "The former Spurs boss succeeds the sacked Michael Carrick; his first "
     "match is away at Liverpool on Sunday."),
]

ALSO = [
    ("GAZA", "Tanks enter central Gaza past truce line"),
    ("RIYADH", "Houthi missile damages the PIF Tower"),
    ("MOGADISHU", "UAE envoy given 72 hours to leave Somalia"),
    ("TOKYO", "Takaichi and Putin agree to keep talking"),
    ("WASHINGTON", "Court asked to end migrant protections"),
    ("DHAKA", "Opposition shutdown grips Bangladesh"),
    ("MOSCOW", "Military plane crash kills all 19 aboard"),
    ("BLACK SEA", "Tanker Gas Husky sinks off Bulgaria"),
    ("GAZA AID", "Peace plan scores just 4 of 26 points"),
    ("CEPU", "Refinery blast kills one worker in Java"),
    ("PYONGYANG", "North Korea unveils first AI chatbot"),
    ("LONDON", "Britain launches new renewables auction"),
    ("DISCLOSURE", "Trump bought $265,000 of Nvidia stock"),
    ("OIL", "Brent near $92 as Hormuz attacks bite"),
    ("WALL ST", "S&P falls a fifth day; Dow off 1.11%"),
    ("PANGUNA", "Rio Tinto puts $250m in mine fund"),
    ("EMISSIONS", "Data centres: carbon up 70% by 2030"),
    ("MANILA", "US defence loan package tops $2bn"),
    ("FOOTBALL", "Chelsea top group, 1-0 over PSG"),
    ("CRICKET", "England win ODI series 2-1 over Australia"),
    ("TENNIS", "Alcaraz beats Medvedev 6-2 6-4 in Turin"),
    ("CRICKET", "South Africa rout Bangladesh, 9 wickets"),
    ("TENNIS", "Barty for the Hall of Fame"),
    ("RANKINGS", "Morocco up to record fifth in world"),
]

def draw_card(cv, x, y, w, h, idx):
    cat, src, col, head, summ = CARDS[idx]
    cv.rect(x, y, w, h, HAIR)
    cv.rect(x + 1, y + 1, w - 2, h - 2, CARD)
    ART[idx](cv, x + 1, y + 1, w - 2, 43)
    cv.disc(x + 17, y + 59, 9.5, col)
    draw_text(cv, x + 17, y + 64.5, str(idx + 1), 13.5, WHITE, 'bold',
              align='center')
    draw_text(cv, x + 33, y + 63.5, cat, 10.5, col, 'bold', tracking=0.7)
    draw_text(cv, x + w - 11, y + 63.5, src, 9.5, GREY, 'bold',
              tracking=0.5, align='right')
    last = draw_block(cv, x + 11, y + 70, head, 19.5, INK, 'bold',
                      w - 22, 23.5)
    draw_block(cv, x + 11, last + 8, summ, 11.6, INK2, 'reg', w - 22, 15.2)

def draw_also_item(cv, x, y_top, label, text, colw):
    """One ALSO one-liner: red bold label, then body words, wrapped as one
    token flow across the full column width. Returns y below the item."""
    size, lh = 9.4, 11.2
    space_w = 2.4 * size / 7.0
    tokens = [(label, 'bold', RED)]
    tokens += [(wd, 'reg', INK2) for wd in text.split()]
    lines = [[]]
    cur_w = 0.0
    for tok in tokens:
        tw = text_width(tok[0], size, tok[1])
        add = tw if not lines[-1] else tw + space_w
        if lines[-1] and cur_w + add > colw:
            lines.append([tok])
            cur_w = tw
        else:
            lines[-1].append(tok)
            cur_w += add
    for i, line in enumerate(lines):
        lx = x
        yb = y_top + size + i * lh
        for wd, wt, col in line:
            draw_text(cv, lx, yb, wd, size, col, wt)
            lx += text_width(wd, size, wt) + space_w
    return y_top + size + (len(lines) - 1) * lh + 3.5

def render():
    cv = Canvas()
    cv.rect(0, 0, W, H, PAPER)

    # ---- utility bar -----------------------------------------------------
    cv.rect(0, 0, W, 26, INK)
    draw_text(cv, 16, 18, "THE WORLD TODAY", 11, WHITE, 'bold',
              tracking=1.5)
    draw_text(cv, W - 16, 18, "33 STORIES · 7 GROUPS · ONE PAGE", 11,
              WHITE, 'bold', tracking=1.5, align='right')

    # ---- masthead ---------------------------------------------------------
    cv.rect(MX, 36, 96, 84, RED)
    draw_text(cv, MX + 48, 53, "NOV", 12, WHITE, 'bold', tracking=2,
              align='center')
    draw_text(cv, MX + 48, 94, "19", 38, WHITE, 'disp', align='center')
    draw_text(cv, MX + 48, 113, "WED 2026", 10, WHITE, 'bold',
              tracking=1.5, align='center')
    draw_text(cv, 124, 104, "The World Today", 66, INK, 'disp')
    # right info box
    bx, bw = 836, 176
    cv.rect(bx, 40, bw, 76, HAIR)
    cv.rect(bx + 1, 41, bw - 2, 74, CARD)
    draw_text(cv, bx + bw / 2, 66, "WEDNESDAY", 13, INK, 'bold',
              tracking=1, align='center')
    draw_text(cv, bx + bw / 2, 86, "19 NOVEMBER 2026", 13, INK, 'bold',
              tracking=0.5, align='center')
    draw_text(cv, bx + bw / 2, 106, "VOL. I — NO. 19", 11, GREY, 'reg',
              align='center')
    hline(cv, MX, 128, CW, INK, 3)
    hline(cv, MX, 134, CW, INK, 1)

    # ---- strap line -------------------------------------------------------
    draw_text(cv, W / 2, 160,
              "Three-way summit in Shenzhen · War widens in the Gulf · "
              "A genocide verdict · The biggest IPO ever",
              15, INK, 'reg', align='center')

    # ---- region tally chips ----------------------------------------------
    chips = [("EUROPE 8", REG_EUROPE), ("AMERICAS 4", REG_AMERICAS),
             ("ASIA-PACIFIC 7", REG_ASIA), ("MIDDLE EAST 4", REG_MIDEAST),
             ("AFRICA 3", REG_AFRICA), ("OCEANIA 4", REG_OCEANIA),
             ("WORLD 3", REG_WORLD)]
    widths = [text_width(t, 11.5, 'bold', 0.5) + 20 for t, _ in chips]
    gap = (CW - sum(widths)) / (len(chips) - 1)
    cx = MX
    for (label, col), cwd in zip(chips, widths):
        cv.rect(cx, 172, cwd, 24, col)
        draw_text(cv, cx + cwd / 2, 189, label, 11.5, WHITE, 'bold',
                  tracking=0.5, align='center')
        cx += cwd + gap

    # ---- stat band ---------------------------------------------------------
    hline(cv, MX, 208, CW, HAIR, 1)
    stats = [("$81.3bn", "raised by Anthropic — the largest IPO on record"),
             ("589m", "children lived in war zones in 2025, a record"),
             ("109-0", "Denmark's vote to back the Greenland pact"),
             ("$250m", "Rio Tinto fund for Panguna mine harm in PNG")]
    for i, (num, cap) in enumerate(stats):
        sx = MX + i * 250
        if i:
            cv.rect(sx - 8, 216, 1, 48, HAIR)
        draw_text(cv, sx + 6, 240, num, 27, RED, 'bold')
        draw_block(cv, sx + 6, 246, cap, 11, INK2, 'reg', 224, 13.5)
    hline(cv, MX, 274, CW, HAIR, 1)

    # ---- story cards -------------------------------------------------------
    cw3 = (CW - 16) / 3
    for i in range(9):
        cxp = MX + (i % 3) * (cw3 + 8)
        cyp = 284 + (i // 3) * 174
        draw_card(cv, cxp, cyp, cw3, 168, i)

    # ---- ALSO strip ---------------------------------------------------------
    hline(cv, MX, 806, CW, INK, 1.6)
    draw_text(cv, MX, 824, "ALSO ON WEDNESDAY 19 NOVEMBER", 13, INK,
              'bold', tracking=1)
    aw = text_width("ALSO ON WEDNESDAY 19 NOVEMBER", 13, 'bold', 1)
    draw_text(cv, MX + aw + 10, 824, "— 24 MORE STORIES", 13, RED, 'bold',
              tracking=1)
    colw = (CW - 5 * 13) / 6
    for c in range(6):
        yy = 832
        for it in ALSO[c * 4:(c + 1) * 4]:
            yy = draw_also_item(cv, MX + c * (colw + 13), yy, it[0], it[1],
                                colw)

    # ---- footer --------------------------------------------------------------
    cv.rect(MX, 958, CW, 32, RED)
    cv.rect(MX + 1.5, 959.5, CW - 3, 29, CARD)
    draw_text(cv, MX + 12, 979, "DATE CHECK", 11, RED, 'bold',
              tracking=0.8)
    dw = text_width("DATE CHECK", 11, 'bold', 0.8)
    draw_text(cv, MX + 12 + dw + 8, 979,
              "Every story here was reported on Wednesday 19 November 2026 "
              "— nothing carried over from earlier days.",
              11, INK2, 'reg')
    draw_text(cv, MX + 12, 1013,
              "Sources: Reuters · Associated Press · Just Security · "
              "Save the Children · 38 North · FIFA",
              9.5, GREY, 'reg')
    draw_text(cv, W - MX, 1013, "DRAWN ENTIRELY IN CODE · NO PHOTOGRAPHS",
              9.5, GREY, 'bold', tracking=0.8, align='right')

    return cv.downsample()

def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    rgb = render()
    write_png(os.path.join(out_dir, "entry.png"), W, H, rgb)

if __name__ == "__main__":
    main()
