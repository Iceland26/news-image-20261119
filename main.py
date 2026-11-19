#!/usr/bin/env python3
"""news-image-20261119 — "THE WORLD TODAY": one image that sums up the world
news of Wednesday 19 November 2026, drawn entirely in code.

Pure Python 3 standard library — no PIL, no font files. The type is a
constructed filled-glyph system: every letter is built from bars, diagonals
and ring segments on a 7-unit cap grid, in three weights (regular, bold, and
a slab-footed display cut for the masthead). A scanline rasteriser with 2x
supersampling and a hand-rolled PNG encoder do the rest.

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
SS = 2                      # supersampling factor
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
        for y in range(H):
            for x in range(W):
                i = ((y * SS) * SW + x * SS) * 3
                o = (y * W + x) * 3
                for c in range(3):
                    s = (b[i + c] + b[i + 3 + c]
                         + b[i + SW * 3 + c] + b[i + SW * 3 + 3 + c])
                    out[o + c] = s >> 2
        return bytes(out)

# --------------------------------------------------------------------------
# Constructed filled-glyph typeface.
#
# Glyph space: y UP, baseline y=0, cap height 7, x-height 4.9, descender -2.
# Each glyph is (advance, [primitive, ...]); primitives are built around a
# centreline and take their thickness from the weight's stem width S:
#   ('V', x, y0, y1, feet)  vertical bar; feet is '' or any of 'b','t'
#                           (slab feet are drawn only in the display cut)
#   ('H', y, x0, x1)        horizontal bar
#   ('D', x0, y0, x1, y1)   diagonal bar, flat caps
#   ('A', cx, cy, rx, ry, start_deg, sweep_deg)  ring segment (sweep may be
#                           negative for clockwise); 357 deg = closed ring
#   ('C', cx, cy, r)        filled disc
#   ('P', [(x, y), ...])    filled polygon
# --------------------------------------------------------------------------

def _star(cx, cy, r_out, r_in):
    pts = []
    for i in range(10):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(90 + i * 36)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts

GLYPHS = {
    # ---- capitals -------------------------------------------------------
    'A': (5.5, [('D', 0.35, 0, 2.75, 7), ('D', 5.15, 0, 2.75, 7),
                ('H', 2.35, 1.5, 4.0)]),
    'B': (5.3, [('V', 0.6, 0, 7, 'bt'), ('H', 7, 0.6, 3.7),
                ('H', 3.42, 0.6, 4.0), ('H', 0, 0.6, 4.0),
                ('A', 2.45, 5.21, 2.0, 1.79, -88, 176),
                ('A', 2.45, 1.71, 2.15, 1.71, -88, 176)]),
    'C': (5.5, [('A', 2.95, 3.5, 2.6, 3.5, 48, 264)]),
    'D': (5.7, [('V', 0.6, 0, 7, 'bt'), ('H', 7, 0.6, 3.4),
                ('H', 0, 0.6, 3.4), ('A', 2.35, 3.5, 2.95, 3.5, -87, 174)]),
    'E': (4.9, [('V', 0.6, 0, 7, 'bt'), ('H', 7, 0.6, 4.55),
                ('H', 3.5, 0.6, 3.95), ('H', 0, 0.6, 4.55)]),
    'F': (4.7, [('V', 0.6, 0, 7, 'bt'), ('H', 7, 0.6, 4.45),
                ('H', 3.6, 0.6, 3.7)]),
    'G': (5.7, [('A', 2.95, 3.5, 2.6, 3.5, 50, 262),
                ('H', 2.55, 3.1, 5.45), ('V', 5.15, 0, 2.55, '')]),
    'H': (5.7, [('V', 0.6, 0, 7, 'bt'), ('V', 5.1, 0, 7, 'bt'),
                ('H', 3.5, 0.6, 5.1)]),
    'I': (1.7, [('V', 0.85, 0, 7, 'bt')]),
    'J': (4.3, [('V', 3.7, 1.75, 7, 't'),
                ('A', 2.05, 1.75, 1.65, 1.75, 180, 175)]),
    'K': (5.3, [('V', 0.6, 0, 7, 'bt'), ('D', 4.95, 7, 1.75, 3.1),
                ('D', 2.05, 2.8, 5.15, 0)]),
    'L': (4.7, [('V', 0.6, 0, 7, 'bt'), ('H', 0, 0.6, 4.55)]),
    'M': (6.6, [('V', 0.6, 0, 7, 'bt'), ('V', 6.0, 0, 7, 'bt'),
                ('D', 0.6, 7, 3.3, 2.7), ('D', 6.0, 7, 3.3, 2.7)]),
    'N': (5.9, [('V', 0.6, 0, 7, 'bt'), ('V', 5.3, 0, 7, 'bt'),
                ('D', 0.6, 7, 5.3, 0)]),
    'O': (5.9, [('A', 2.95, 3.5, 2.95, 3.5, 0, 357)]),
    'P': (5.3, [('V', 0.6, 0, 7, 'bt'), ('H', 7, 0.6, 3.7),
                ('H', 3.3, 0.6, 3.9),
                ('A', 2.45, 5.15, 2.0, 1.85, -88, 176)]),
    'Q': (5.9, [('A', 2.95, 3.5, 2.95, 3.5, 0, 357),
                ('D', 3.5, 1.3, 5.75, -0.5)]),
    'R': (5.3, [('V', 0.6, 0, 7, 'bt'), ('H', 7, 0.6, 3.7),
                ('H', 3.3, 0.6, 3.9),
                ('A', 2.45, 5.15, 2.0, 1.85, -88, 176),
                ('D', 2.8, 3.3, 5.15, 0)]),
    'S': (5.1, [('A', 2.55, 5.0, 2.0, 2.0, 32, 190),
                ('A', 2.55, 2.05, 2.15, 2.05, 130, -288)]),
    'T': (5.3, [('H', 7, 0.15, 5.15), ('V', 2.65, 0, 7, 'b')]),
    'U': (5.7, [('V', 0.6, 1.95, 7, 't'), ('V', 5.1, 1.95, 7, 't'),
                ('A', 2.85, 1.95, 2.25, 1.95, 180, 180)]),
    'V': (5.5, [('D', 0.25, 7, 2.75, 0), ('D', 5.25, 7, 2.75, 0)]),
    'W': (7.3, [('D', 0.25, 7, 1.8, 0), ('D', 1.8, 0, 3.65, 5.4),
                ('D', 3.65, 5.4, 5.5, 0), ('D', 5.5, 0, 7.05, 7)]),
    'X': (5.3, [('D', 0.35, 7, 4.95, 0), ('D', 0.35, 0, 4.95, 7)]),
    'Y': (5.5, [('D', 0.25, 7, 2.75, 3.3), ('D', 5.25, 7, 2.75, 3.3),
                ('V', 2.75, 0, 3.3, 'b')]),
    'Z': (5.1, [('H', 7, 0.25, 4.85), ('D', 4.85, 7, 0.25, 0),
                ('H', 0, 0.25, 4.85)]),
    # ---- lowercase ------------------------------------------------------
    'a': (4.7, [('A', 2.4, 2.45, 2.0, 2.45, 0, 357),
                ('V', 4.4, 0, 4.9, ''), ('H', 4.9, 1.3, 4.4)]),
    'b': (4.9, [('V', 0.6, 0, 7, 'bt'),
                ('A', 2.8, 2.45, 2.0, 2.45, 0, 357)]),
    'c': (4.5, [('A', 2.4, 2.45, 2.05, 2.45, 50, 262)]),
    'd': (4.9, [('A', 2.3, 2.45, 2.0, 2.45, 0, 357),
                ('V', 4.3, 0, 7, 'bt')]),
    'e': (4.7, [('A', 2.4, 2.45, 2.05, 2.45, 35, 305),
                ('H', 2.6, 0.55, 4.35)]),
    'f': (3.1, [('V', 1.15, 0, 6.55, ''),
                ('A', 2.0, 6.5, 0.9, 0.55, 0, 180),
                ('H', 3.85, 0.35, 2.95)]),
    'g': (4.9, [('A', 2.3, 2.45, 2.0, 2.45, 0, 357),
                ('V', 4.3, -0.8, 4.9, ''),
                ('A', 2.55, -0.8, 1.75, 0.95, 0, -235)]),
    'h': (5.0, [('V', 0.6, 0, 7, 'bt'),
                ('A', 2.85, 2.5, 1.85, 2.4, 175, -210),
                ('V', 4.62, 0, 2.4, '')]),
    'i': (1.6, [('V', 0.8, 0, 4.9, 'b'), ('C', 0.8, 6.35, 0.58)]),
    'j': (2.7, [('V', 2.05, -1.25, 4.9, ''),
                ('A', 1.0, -1.25, 1.05, 0.78, 0, -165),
                ('C', 2.05, 6.35, 0.58)]),
    'k': (4.7, [('V', 0.6, 0, 7, 'bt'), ('D', 4.35, 4.9, 1.8, 2.3),
                ('D', 2.05, 2.05, 4.55, 0)]),
    'l': (1.6, [('V', 0.8, 0, 7, 'bt')]),
    'm': (7.7, [('V', 0.6, 0, 4.9, 'b'),
                ('A', 2.4, 2.5, 1.6, 2.4, 175, -210),
                ('V', 3.98, 0, 2.4, ''),
                ('A', 5.78, 2.5, 1.6, 2.4, 175, -210),
                ('V', 7.35, 0, 2.4, '')]),
    'n': (5.0, [('V', 0.6, 0, 4.9, 'b'),
                ('A', 2.85, 2.5, 1.85, 2.4, 175, -210),
                ('V', 4.62, 0, 2.4, '')]),
    'o': (4.8, [('A', 2.4, 2.45, 2.05, 2.45, 0, 357)]),
    'p': (4.9, [('V', 0.6, -2.0, 4.9, 't'),
                ('A', 2.8, 2.45, 2.0, 2.45, 0, 357)]),
    'q': (4.9, [('A', 2.3, 2.45, 2.0, 2.45, 0, 357),
                ('V', 4.3, -2.0, 4.9, 't')]),
    'r': (3.5, [('V', 0.6, 0, 4.9, 'b'),
                ('A', 2.15, 3.4, 1.55, 1.5, 175, -215)]),
    's': (4.3, [('A', 2.15, 3.6, 1.7, 1.3, 32, 190),
                ('A', 2.15, 1.35, 1.8, 1.35, 130, -288)]),
    't': (3.3, [('V', 1.55, 0, 6.6, ''), ('H', 3.95, 0.3, 3.05),
                ('A', 2.4, 0.95, 0.85, 0.95, 180, 155)]),
    'u': (5.0, [('V', 0.6, 2.3, 4.9, 't'),
                ('A', 2.5, 2.3, 1.9, 2.3, 180, 180),
                ('V', 4.4, 0, 4.9, 'b')]),
    'v': (4.7, [('D', 0.25, 4.9, 2.35, 0), ('D', 4.45, 4.9, 2.35, 0)]),
    'w': (6.5, [('D', 0.25, 4.9, 1.6, 0), ('D', 1.6, 0, 3.25, 3.9),
                ('D', 3.25, 3.9, 4.9, 0), ('D', 4.9, 0, 6.25, 4.9)]),
    'x': (4.5, [('D', 0.3, 4.9, 4.2, 0), ('D', 0.3, 0, 4.2, 4.9)]),
    'y': (4.7, [('D', 0.25, 4.9, 2.35, 1.55), ('D', 4.45, 4.9, 1.0, -2.0)]),
    'z': (4.5, [('H', 4.9, 0.25, 4.25), ('D', 4.25, 4.9, 0.25, 0),
                ('H', 0, 0.25, 4.25)]),
    # ---- digits ---------------------------------------------------------
    '0': (5.3, [('A', 2.65, 3.5, 2.3, 3.5, 0, 357)]),
    '1': (4.4, [('D', 1.15, 5.35, 2.55, 7), ('V', 2.55, 0, 7, 'b'),
                ('H', 0, 0.95, 4.15)]),
    '2': (5.0, [('A', 2.5, 5.0, 2.05, 2.0, -55, 235),
                ('D', 3.85, 3.6, 0.45, 0), ('H', 0, 0.3, 4.6)]),
    '3': (5.0, [('A', 2.35, 5.15, 1.95, 1.85, -75, 215),
                ('A', 2.35, 2.25, 2.1, 2.25, -105, 215)]),
    '4': (5.1, [('V', 3.5, 0, 7, ''), ('D', 0.4, 2.5, 3.5, 7),
                ('H', 2.5, 0.2, 4.9)]),
    '5': (4.9, [('H', 7, 0.5, 4.45), ('V', 0.6, 4.2, 7, 't'),
                ('A', 2.45, 2.6, 2.05, 2.6, 115, -215)]),
    '6': (5.0, [('D', 4.35, 7, 1.5, 2.9),
                ('A', 2.5, 2.45, 2.05, 2.45, 0, 357)]),
    '7': (4.9, [('H', 7, 0.3, 4.6), ('D', 4.6, 7, 1.9, 0)]),
    '8': (5.0, [('A', 2.5, 5.2, 1.8, 1.8, 0, 357),
                ('A', 2.5, 2.3, 2.05, 2.3, 0, 357)]),
    '9': (5.0, [('A', 2.5, 4.55, 2.05, 2.45, 0, 357),
                ('V', 4.5, 1.55, 7, ''),
                ('A', 2.6, 1.55, 1.9, 1.55, 0, -170)]),
    # ---- punctuation and symbols ---------------------------------------
    '.': (1.6, [('C', 0.8, 0.55, 0.6)]),
    ',': (1.6, [('C', 0.85, 0.75, 0.58), ('D', 1.25, 0.6, 0.55, -0.9)]),
    "'": (1.5, [('D', 0.95, 7, 0.45, 5.5)]),
    '\u2019': (1.5, [('D', 0.95, 7, 0.45, 5.5)]),
    '\u2018': (1.5, [('D', 0.55, 7, 1.05, 5.5)]),
    '"': (2.6, [('D', 0.85, 7, 0.35, 5.5), ('D', 2.15, 7, 1.65, 5.5)]),
    '-': (2.8, [('H', 2.5, 0.25, 2.55)]),
    '\u2013': (3.6, [('H', 2.5, 0.2, 3.4)]),
    '\u2014': (5.2, [('H', 2.5, 0.15, 5.05)]),
    ':': (1.6, [('C', 0.8, 0.55, 0.58), ('C', 0.8, 4.7, 0.58)]),
    ';': (1.6, [('C', 0.85, 4.7, 0.58), ('C', 0.85, 0.75, 0.58),
                ('D', 1.25, 0.6, 0.55, -0.9)]),
    '!': (1.6, [('V', 0.8, 1.9, 7, ''), ('C', 0.8, 0.55, 0.6)]),
    '?': (4.4, [('A', 2.2, 5.15, 1.75, 1.85, -35, 245),
                ('V', 2.2, 1.85, 3.3, ''), ('C', 2.2, 0.55, 0.6)]),
    '$': (5.0, [('A', 2.5, 5.0, 1.95, 1.95, 32, 190),
                ('A', 2.5, 2.05, 2.1, 2.05, 130, -288),
                ('V', 2.5, -0.5, 7.5, '')]),
    '%': (7.6, [('A', 1.55, 5.6, 1.15, 1.3, 0, 330),
                ('A', 6.0, 1.4, 1.15, 1.3, 0, 330),
                ('D', 6.9, 7, 0.7, 0)]),
    '&': (5.6, [('A', 2.6, 5.3, 1.45, 1.55, 0, 357),
                ('A', 2.9, 2.1, 2.25, 2.1, 0, 357),
                ('D', 1.2, 3.9, 4.9, 0.1)]),
    '/': (3.2, [('D', 0.55, -0.25, 2.85, 7.25)]),
    '(': (3.0, [('A', 2.7, 3.5, 2.0, 3.6, 105, 150)]),
    ')': (3.0, [('A', 0.3, 3.5, 2.0, 3.6, -75, 150)]),
    '\u00b7': (1.8, [('C', 0.9, 2.6, 0.55)]),
    '\u2022': (2.2, [('C', 1.1, 3.0, 0.85)]),
    '\u2191': (4.4, [('V', 2.2, 0, 6.2, ''), ('D', 2.2, 7, 0.5, 4.9),
                     ('D', 2.2, 7, 3.9, 4.9)]),
    '\u2193': (4.4, [('V', 2.2, 0.8, 7, ''), ('D', 2.2, 0, 0.5, 2.1),
                     ('D', 2.2, 0, 3.9, 2.1)]),
    '\u25b2': (4.6, [('P', [(2.3, 7), (4.5, 0), (0.1, 0)])]),
    '\u25bc': (4.6, [('P', [(0.1, 7), (4.5, 7), (2.3, 0)])]),
    '\u2605': (5.4, [('P', _star(2.7, 3.3, 2.9, 1.18))]),
    '+': (4.4, [('H', 3.3, 0.6, 3.8), ('V', 2.2, 1.4, 5.2, '')]),
    '=': (4.4, [('H', 4.4, 0.6, 3.8), ('H', 2.2, 0.6, 3.8)]),
    '\u2026': (4.8, [('C', 0.7, 0.55, 0.55), ('C', 2.4, 0.55, 0.55),
                     ('C', 4.1, 0.55, 0.55)]),
    ' ': (2.4, []),
}

# Weights: name -> (stem width in glyph units, slab feet?)
WEIGHTS = {
    'reg': (0.88, False),
    'bold': (1.14, False),
    'disp': (1.24, True),
}

def _glyph(ch):
    g = GLYPHS.get(ch)
    if g is None:
        g = GLYPHS.get(ch.lower()) or GLYPHS['?']
    return g

def text_width(s, size, weight='reg', tracking=0.0):
    """Width in output px of string s at cap-height `size` px."""
    u = size / 7.0
    w = 0.0
    for ch in s:
        w += _glyph(ch)[0] * u
    if len(s) > 1:
        w += tracking * (len(s) - 1)
    return w

def _draw_prim(cv, prim, ox, oy, u, S, serif, col, adv=9.9):
    """Draw one primitive. (ox, oy) = pen origin in output px, oy = baseline."""
    kind = prim[0]
    if kind == 'V':
        _, x, y0, y1, feet = prim
        cx = ox + x * u
        cv.rect(cx - S * u / 2, oy - y1 * u, S * u, (y1 - y0) * u, col)
        if serif and feet:
            fw = min(S + 0.7, adv - 0.1) * u
            fh = 0.52 * u
            if 'b' in feet:
                cv.rect(cx - fw / 2, oy - y0 * u - fh, fw, fh, col)
            if 't' in feet:
                cv.rect(cx - fw / 2, oy - y1 * u, fw, fh, col)
    elif kind == 'H':
        _, y, x0, x1 = prim
        cv.rect(ox + x0 * u, oy - (y + S / 2) * u, (x1 - x0) * u, S * u, col)
    elif kind == 'D':
        _, x0, y0, x1, y1 = prim
        dx, dy = x1 - x0, y1 - y0
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln * S / 2, dx / ln * S / 2
        pts = [(ox + (x0 + nx) * u, oy - (y0 + ny) * u),
               (ox + (x1 + nx) * u, oy - (y1 + ny) * u),
               (ox + (x1 - nx) * u, oy - (y1 - ny) * u),
               (ox + (x0 - nx) * u, oy - (y0 - ny) * u)]
        cv.poly(pts, col)
    elif kind == 'A':
        _, cx, cy, rx, ry, start, sweep = prim
        steps = max(6, int(abs(sweep) / 6.0))
        irx = max(0.05, rx - S); iry = max(0.05, ry - S)
        pts = []
        for i in range(steps + 1):
            a = math.radians(start + sweep * i / steps)
            pts.append((ox + (cx + rx * math.cos(a)) * u,
                        oy - (cy + ry * math.sin(a)) * u))
        for i in range(steps, -1, -1):
            a = math.radians(start + sweep * i / steps)
            pts.append((ox + (cx + irx * math.cos(a)) * u,
                        oy - (cy + iry * math.sin(a)) * u))
        cv.poly(pts, col)
    elif kind == 'C':
        _, cx, cy, r = prim
        cv.disc(ox + cx * u, oy - cy * u, r * u, col)
    elif kind == 'P':
        pts = [(ox + x * u, oy - y * u) for x, y in prim[1]]
        cv.poly(pts, col)

def draw_text(cv, x, y_base, s, size, col, weight='reg', tracking=0.0,
              align='left'):
    """Draw string s with baseline at y_base (output px). Returns end x."""
    S, serif = WEIGHTS[weight]
    u = size / 7.0
    w = text_width(s, size, weight, tracking)
    if align == 'center':
        x -= w / 2
    elif align == 'right':
        x -= w
    pen = x
    for ch in s:
        adv, prims = _glyph(ch)
        for prim in prims:
            _draw_prim(cv, prim, pen, y_base, u, S, serif, col, adv)
        pen += adv * u + tracking
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
    """Wrap and draw a paragraph; y_top is the top of the cap height of the
    first line. Returns the y just below the last line's baseline."""
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

# ---- card illustration strips (flat shapes only) -------------------------

def art_skyline(cv, x, y, w, h):
    cv.rect(x, y, w, h, (24, 52, 66))
    cv.disc(x + w - 52, y + 15, 9, (240, 200, 120))
    base = y + h
    for bx, bw, bh in ((6, 34, 24), (46, 26, 33), (78, 40, 20), (124, 30, 38),
                       (160, 44, 26), (210, 28, 35), (244, 38, 22),
                       (288, 30, 30)):
        cv.rect(x + bx, base - bh, bw, bh, (13, 30, 40))
    for wx, wy in ((56, 22), (64, 28), (134, 16), (142, 24), (220, 20),
                   (252, 26), (296, 22), (16, 30), (92, 28), (176, 30)):
        cv.rect(x + wx, base - wy, 2.4, 3.2, (240, 214, 140))
    for px, col in ((70, (198, 52, 44)), (150, (52, 92, 178)),
                    (232, (232, 176, 64))):
        cv.rect(x + px, y + 8, 2, 12, (220, 220, 210))
        cv.poly([(x + px + 2, y + 8), (x + px + 13, y + 11),
                 (x + px + 2, y + 14)], col)

def art_sea(cv, x, y, w, h):
    cv.rect(x, y, w, h, (18, 42, 64))
    for r in range(3):
        for i in range(10):
            cv.rect(x + 12 + i * 32 + (r % 2) * 14, y + 9 + r * 12, 13, 2.4,
                    (110, 160, 195))
    cv.rect(x + 100, y + h - 12, 128, 7, (148, 158, 168))
    cv.rect(x + 118, y + h - 18, 30, 6, (148, 158, 168))
    cv.rect(x + 192, y + h - 21, 15, 9, (200, 208, 216))
    cv.rect(x + 204, y + h - 26, 3, 14, (148, 158, 168))
    pts = [(x + 272 + px, y + 18 + py) for px, py in _star(0, 0, 11, 4.2)]
    cv.poly(pts, (240, 130, 40))

def art_chart(cv, x, y, w, h):
    cv.rect(x, y, w, h, (16, 52, 44))
    base = y + h - 6
    for i, bh in enumerate((10, 15, 13, 21, 27)):
        cv.rect(x + 60 + i * 34, base - bh, 22, bh, (46, 160, 130))
    cv.rect(x + 60 + 5 * 34, base - 36, 22, 36, (240, 130, 40))
    cv.poly([(x + 52, y + 26), (x + 218, y + 8), (x + 206, y + 6),
             (x + 222, y + 2), (x + 224, y + 16), (x + 220, y + 5),
             (x + 66, y + 30)], (235, 240, 235))

def art_scales(cv, x, y, w, h):
    cv.rect(x, y, w, h, (38, 48, 58))
    gold = (206, 172, 92)
    cx = x + w / 2
    cv.rect(cx - 2, y + 10, 4, h - 16, gold)
    cv.rect(cx - 62, y + 12, 124, 4, gold)
    cv.disc(cx, y + 8, 4, gold)
    for sx in (-62, 62):
        cv.line(cx + sx, y + 16, cx + sx - 14, y + 29, 2, gold)
        cv.line(cx + sx, y + 16, cx + sx + 14, y + 29, 2, gold)
        cv.poly([(cx + sx - 16, y + 29), (cx + sx + 16, y + 29),
                 (cx + sx + 9, y + 35), (cx + sx - 9, y + 35)], gold)
    cv.rect(cx - 18, y + h - 6, 36, 3, gold)

def art_bridge(cv, x, y, w, h):
    cv.rect(x, y, w, h, (52, 74, 94))
    cv.rect(x, y + h - 9, w, 9, (30, 48, 66))
    for i in range(8):
        cv.rect(x + 20 + i * 38, y + h - 6, 14, 1.8, (110, 150, 180))
    deck = y + 24
    cv.rect(x + 8, deck, w - 16, 4, (16, 24, 32))
    for tx in (70, 226):
        cv.rect(x + tx, y + 5, 8, 23, (16, 24, 32))
        cv.line(x + tx + 4, y + 6, x + 16, deck, 1.6, (200, 210, 220))
        cv.line(x + tx + 4, y + 6, x + w - 16, deck, 1.6, (200, 210, 220))
    pts = [(x + 168 + px, y + 13 + py) for px, py in _star(0, 0, 8, 3.0)]
    cv.poly(pts, (240, 90, 50))

def art_climate(cv, x, y, w, h):
    cv.rect(x, y, w, h, (70, 120, 150))
    cv.disc(x + 42, y + 14, 10, (246, 206, 92))
    for cx, cy, r in ((120, 16, 9), (138, 13, 12), (158, 16, 9),
                      (236, 18, 8), (252, 15, 10)):
        cv.disc(x + cx, y + cy, r, (240, 244, 246))
    cv.poly([(x + 168, y + 8), (x + 180, y + 8), (x + 180, y + 24),
             (x + 190, y + 24), (x + 174, y + 38), (x + 158, y + 24),
             (x + 168, y + 24)], (198, 52, 44))

def art_drought(cv, x, y, w, h):
    cv.rect(x, y, w, h, (198, 142, 62))
    cv.disc(x + w - 58, y + 14, 11, (250, 224, 130))
    cv.disc(x + w - 58, y + 14, 15, (222, 172, 92))
    cv.disc(x + w - 58, y + 14, 11, (250, 224, 130))
    cv.rect(x, y + h - 13, w, 13, (110, 74, 40))
    for x0, zig in ((36, (0, 10, 18, 30)), (138, (0, 12, 20, 32)),
                    (240, (0, 9, 19, 28))):
        for i in range(3):
            cv.line(x + x0 + zig[i], y + h - 10 + (i % 2) * 4,
                    x + x0 + zig[i + 1], y + h - 4 - (i % 2) * 3, 1.9,
                    (246, 226, 182))

def art_columns(cv, x, y, w, h):
    cv.rect(x, y, w, h, (96, 32, 36))
    cream = (238, 228, 200)
    cx = x + w / 2
    cv.poly([(cx - 52, y + 14), (cx + 52, y + 14), (cx, y + 4)], cream)
    for dx in (-40, -14, 12):
        cv.rect(cx + dx, y + 17, 9, h - 24, cream)
    cv.rect(cx - 52, y + h - 6, 104, 3, cream)

def art_football(cv, x, y, w, h):
    cv.rect(x, y, w, h, (34, 110, 52))
    cv.rect(x + 14, y + 6, w - 28, 1.6, (235, 245, 235))
    cv.rect(x + 14, y + h - 8, w - 28, 1.6, (235, 245, 235))
    cv.rect(x + w / 2 - 1, y + 6, 1.6, h - 14, (235, 245, 235))
    cv.disc(x + w / 2, y + h / 2, 10, (34, 110, 52))
    cv.disc(x + w / 2, y + h / 2, 10.8, (235, 245, 235))
    cv.disc(x + w / 2, y + h / 2, 9.2, (34, 110, 52))
    bx, by = x + w - 74, y + h / 2
    cv.disc(bx, by, 9, (245, 245, 245))
    for dx, dy in ((0, 0), (-5, -4), (5, -4), (-4, 5), (5, 5)):
        cv.disc(bx + dx, by + dy, 1.8, (20, 24, 28))

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
    draw_text(cv, x + 17, y + 63.5, str(idx + 1), 12, WHITE, 'bold',
              align='center')
    draw_text(cv, x + 33, y + 63.5, cat, 10.5, col, 'bold', tracking=0.7)
    draw_text(cv, x + w - 11, y + 63.5, src, 9.5, GREY, 'bold',
              tracking=0.5, align='right')
    last = draw_block(cv, x + 11, y + 70, head, 19.5, INK, 'bold',
                      w - 22, 23.5)
    draw_block(cv, x + 11, last + 8, summ, 12, INK2, 'reg', w - 22, 15.2)

def draw_also_item(cv, x, y_top, label, text, colw):
    """One ALSO one-liner: red bold label, then body words, wrapped as one
    token flow across the full column width. Returns y below the item."""
    size, lh = 10.2, 12.0
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
    draw_text(cv, 124, 108, "The World Today", 74, INK, 'disp')
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
