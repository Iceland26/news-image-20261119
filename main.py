#!/usr/bin/env python3
"""news-image-20261119 — "THE WORLD TODAY": one image that sums up the world
news of Wednesday 19 November 2026, drawn entirely in code.

Pure Python 3 standard library. A small vector stroke typeface, a scanline
rasteriser with 2x supersampling, and a hand-rolled PNG encoder render a
newspaper front page: masthead, date bar, market ticker, a lead story with a
dot-grid world map, a numbers rail, four top stories and briefs grids for
world, planet, society, Asia-Pacific, economy and sport — 30+ real stories
of the day, every one of them reported on 19 November 2026.

Deterministic: no randomness, no clock, no network. Two runs write the same
bytes. Output: $MAKEFUN_OUTPUT_DIR/entry.png (default /output/entry.png).
"""

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
        """Filled polygon, output coordinates (scanline)."""
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
# Stroke typeface. Glyphs live on a 7-unit cap height, y down, baseline y=7.
# Each glyph: (width, [stroke, ...]); a stroke is a list of (x, y) points.
# A stroke of the form ("poly", pts) is a filled polygon (for triangles).
# --------------------------------------------------------------------------

def _s(*pts):
    return list(pts)

GLYPHS = {
    'A': (4.5, [_s((0, 7), (2.25, 0), (4.5, 7)), _s((1.05, 4.7), (3.45, 4.7))]),
    'B': (4.3, [_s((0, 0), (0, 7)), _s((0, 0), (2.4, 0), (3.2, 0.9), (3.2, 2.3), (2.4, 3.3), (0, 3.3)),
                _s((0, 3.3), (2.6, 3.3), (3.4, 4.3), (3.4, 5.9), (2.5, 7), (0, 7))]),
    'C': (4.4, [_s((4.3, 1.3), (3.2, 0.2), (1.6, 0), (0.6, 0.9), (0.2, 2.2), (0.2, 4.8),
                  (0.6, 6.1), (1.6, 7), (3.2, 6.8), (4.3, 5.7))]),
    'D': (4.5, [_s((0, 0), (0, 7)), _s((0, 0), (2.7, 0), (3.9, 1.3), (4.4, 3.5), (3.9, 5.7), (2.7, 7), (0, 7))]),
    'E': (3.9, [_s((3.9, 0), (0, 0), (0, 7), (3.9, 7)), _s((0, 3.5), (3.1, 3.5))]),
    'F': (3.7, [_s((3.7, 0), (0, 0), (0, 7)), _s((0, 3.5), (2.9, 3.5))]),
    'G': (4.6, [_s((4.3, 1.3), (3.2, 0.2), (1.6, 0), (0.6, 0.9), (0.2, 2.2), (0.2, 4.8),
                  (0.6, 6.1), (1.6, 7), (3.3, 6.8), (4.4, 5.9), (4.4, 3.9), (2.7, 3.9))]),
    'H': (4.5, [_s((0, 0), (0, 7)), _s((4.5, 0), (4.5, 7)), _s((0, 3.5), (4.5, 3.5))]),
    'I': (1.7, [_s((0.85, 0), (0.85, 7)), _s((0, 0), (1.7, 0)), _s((0, 7), (1.7, 7))]),
    'J': (3.4, [_s((3.4, 0), (3.4, 5.3), (2.8, 6.6), (1.4, 7), (0.4, 6.2), (0.2, 5))]),
    'K': (4.3, [_s((0, 0), (0, 7)), _s((4.2, 0), (0.5, 3.5)), _s((1.7, 2.5), (4.3, 7))]),
    'L': (3.7, [_s((0, 0), (0, 7), (3.7, 7))]),
    'M': (5.4, [_s((0, 7), (0, 0), (2.7, 3.6), (5.4, 0), (5.4, 7))]),
    'N': (4.6, [_s((0, 7), (0, 0), (4.6, 7), (4.6, 0))]),
    'O': (4.6, [_s((2.3, 0), (3.8, 0.5), (4.5, 2), (4.6, 3.5), (4.5, 5), (3.8, 6.5),
                  (2.3, 7), (0.8, 6.5), (0.1, 5), (0, 3.5), (0.1, 2), (0.8, 0.5), (2.3, 0))]),
    'P': (4.2, [_s((0, 7), (0, 0), (2.9, 0), (3.9, 0.9), (3.9, 2.6), (2.9, 3.5), (0, 3.5))]),
    'Q': (4.6, [_s((2.3, 0), (3.8, 0.5), (4.5, 2), (4.6, 3.5), (4.5, 5), (3.8, 6.5),
                  (2.3, 7), (0.8, 6.5), (0.1, 5), (0, 3.5), (0.1, 2), (0.8, 0.5), (2.3, 0)),
                _s((2.8, 5.1), (4.8, 7.5))]),
    'R': (4.3, [_s((0, 7), (0, 0), (2.9, 0), (3.9, 0.9), (3.9, 2.6), (2.9, 3.5), (0, 3.5)),
                _s((2.1, 3.5), (4.3, 7))]),
    'S': (4.1, [_s((4, 1.2), (3, 0.1), (1.4, 0), (0.4, 0.9), (0.3, 2), (1.1, 2.9), (3, 3.6),
                  (3.9, 4.5), (3.8, 5.9), (2.9, 6.9), (1.2, 7), (0.2, 6))]),
    'T': (4.2, [_s((0, 0), (4.2, 0)), _s((2.1, 0), (2.1, 7))]),
    'U': (4.5, [_s((0, 0), (0, 4.7), (0.6, 6.3), (1.6, 7), (2.9, 7), (3.9, 6.3), (4.5, 4.7), (4.5, 0))]),
    'V': (4.5, [_s((0, 0), (2.25, 7), (4.5, 0))]),
    'W': (6.1, [_s((0, 0), (1.35, 7), (3.05, 2.7), (4.75, 7), (6.1, 0))]),
    'X': (4.2, [_s((0, 0), (4.2, 7)), _s((4.2, 0), (0, 7))]),
    'Y': (4.3, [_s((0, 0), (2.15, 3.3), (4.3, 0)), _s((2.15, 3.3), (2.15, 7))]),
    'Z': (4.2, [_s((0, 0), (4.2, 0), (0, 7), (4.2, 7))]),
    '0': (4.2, [_s((2.1, 0), (3.4, 0.5), (4.1, 2), (4.2, 3.5), (4.1, 5), (3.4, 6.5),
                  (2.1, 7), (0.8, 6.5), (0.1, 5), (0, 3.5), (0.1, 2), (0.8, 0.5), (2.1, 0))]),
    '1': (3.2, [_s((0.9, 1.5), (2.1, 0), (2.1, 7)), _s((0.7, 7), (3.1, 7))]),
    '2': (4.1, [_s((0.3, 1.3), (1, 0.2), (2.6, 0), (3.7, 0.9), (3.6, 2.2), (0.2, 7), (4, 7))]),
    '3': (4.1, [_s((0.4, 0.9), (1.4, 0), (2.8, 0.1), (3.6, 1.1), (3.3, 2.4), (2.1, 3.2)),
                _s((2.1, 3.2), (3.4, 3.9), (3.7, 5.4), (2.9, 6.7), (1.4, 7), (0.3, 6.1))]),
    '4': (4.4, [_s((2.9, 7), (2.9, 0), (0, 4.9), (4.4, 4.9))]),
    '5': (4.0, [_s((3.9, 0), (0.2, 0), (0.2, 3.1), (2.2, 2.8), (3.6, 3.8), (3.8, 5.4),
                  (2.9, 6.8), (1.2, 7), (0.2, 6.2))]),
    '6': (4.1, [_s((3.7, 1.1), (2.5, 0), (1.1, 0.9), (0.3, 3.2), (0.2, 5), (0.9, 6.6),
                  (2.2, 7), (3.4, 6.3), (3.8, 5), (3.3, 3.7), (2, 3.3), (0.6, 3.9))]),
    '7': (4.1, [_s((0.2, 0), (4.1, 0), (1.7, 7))]),
    '8': (4.1, [_s((2.05, 3.3), (1, 2.9), (0.4, 1.9), (0.7, 0.7), (1.9, 0), (3.2, 0.5),
                  (3.6, 1.6), (3.1, 2.8), (2.05, 3.3)),
                _s((2.05, 3.3), (0.9, 3.9), (0.3, 5.2), (0.9, 6.5), (2.05, 7), (3.2, 6.5),
                  (3.8, 5.2), (3.2, 3.9), (2.05, 3.3))]),
    '9': (4.1, [_s((0.4, 6), (1.6, 7), (3, 6.1), (3.8, 3.8), (3.9, 2), (3.1, 0.4),
                  (1.7, 0), (0.4, 0.7), (0.2, 2.1), (0.8, 3.3), (2.1, 3.7), (3.5, 3.1))]),
    '.': (1.6, [_s((0.8, 6.5), (0.8, 6.9))]),
    ',': (1.6, [_s((1.05, 6.1), (0.75, 7.7))]),
    "'": (1.6, [_s((0.8, 0.1), (0.8, 1.7))]),
    '\u2019': (1.6, [_s((0.8, 0.1), (0.8, 1.7))]),
    '"': (3.0, [_s((0.7, 0.1), (0.7, 1.7)), _s((2.2, 0.1), (2.2, 1.7))]),
    '-': (3.0, [_s((0.3, 3.5), (2.7, 3.5))]),
    '\u2013': (3.6, [_s((0.3, 3.5), (3.3, 3.5))]),
    '\u2014': (4.8, [_s((0.2, 3.5), (4.6, 3.5))]),
    ':': (1.6, [_s((0.8, 2), (0.8, 2.4)), _s((0.8, 5.4), (0.8, 5.8))]),
    ';': (1.6, [_s((0.8, 2), (0.8, 2.4)), _s((1.05, 6.1), (0.75, 7.7))]),
    '!': (1.6, [_s((0.8, 0), (0.8, 4.7)), _s((0.8, 6.5), (0.8, 6.9))]),
    '?': (3.9, [_s((0.4, 1.2), (1.2, 0.1), (2.7, 0), (3.5, 0.9), (3.3, 2.3), (2, 3.5), (2, 4.7)),
                _s((2, 6.5), (2, 6.9))]),
    '$': (4.1, [_s((4, 1.2), (3, 0.1), (1.4, 0), (0.4, 0.9), (0.3, 2), (1.1, 2.9), (3, 3.6),
                  (3.9, 4.5), (3.8, 5.9), (2.9, 6.9), (1.2, 7), (0.2, 6)),
                _s((2.05, -0.5), (2.05, 7.5))]),
    '%': (5.8, [_s((1.15, 0.15), (2, 0.6), (2.15, 1.6), (1.6, 2.5), (0.6, 2.3), (0.15, 1.4), (1.15, 0.15)),
                _s((4.7, 0), (1.1, 7)),
                _s((4.65, 4.5), (5.5, 4.95), (5.65, 5.95), (5.1, 6.85), (4.1, 6.65), (3.65, 5.75), (4.65, 4.5))]),
    '(': (2.8, [_s((2.4, 0.4), (1.2, 1.6), (0.7, 3.5), (1.2, 5.4), (2.4, 6.6))]),
    ')': (2.8, [_s((0.4, 0.4), (1.6, 1.6), (2.1, 3.5), (1.6, 5.4), (0.4, 6.6))]),
    '/': (3.4, [_s((3.4, -0.2), (0, 7.2))]),
    '+': (4.0, [_s((2, 1.7), (2, 5.3)), _s((0.2, 3.5), (3.8, 3.5))]),
    '=': (3.8, [_s((0.2, 2.6), (3.6, 2.6)), _s((0.2, 4.6), (3.6, 4.6))]),
    '\u00b7': (1.6, [_s((0.8, 3.4), (0.8, 3.8))]),
    '\u2026': (4.6, [_s((0.7, 6.5), (0.7, 6.9)), _s((2.3, 6.5), (2.3, 6.9)), _s((3.9, 6.5), (3.9, 6.9))]),
    '\u00b0': (2.6, [_s((1.3, 0.1), (2.2, 0.6), (2.4, 1.5), (1.9, 2.4), (1, 2.5), (0.35, 1.8), (0.45, 0.7), (1.3, 0.1))]),
    '\u25b2': (4.0, [("poly", [(2, 0.7), (3.9, 6.3), (0.1, 6.3)])]),
    '\u25bc': (4.0, [("poly", [(2, 6.3), (3.9, 0.7), (0.1, 0.7)])]),
    '&': (4.4, [_s((3.4, 0.7), (2.2, 1.9), (0.9, 3.4), (0.5, 4.9), (1.1, 6.4), (2.4, 7),
                   (3.5, 6.4)), _s((1.7, 3.6), (3.9, 6.9))]),
    ' ': (2.6, []),
}

def text_width(s, size, tracking=0.0):
    """Width in output px of string s at cap-height size (px)."""
    u = size / 7.0
    w = 0.0
    for ch in s.upper():
        g = GLYPHS.get(ch)
        w += (g[0] if g else 2.6) * u + tracking
    return w - (tracking if s else 0)

def draw_text(cv, x, y, s, size, col, weight=1.0, tracking=0.0, align="left"):
    """Draw s with cap top at y, left edge x (or centred/right per align)."""
    s = s.upper()
    w = text_width(s, size, tracking)
    if align == "center":
        x -= w / 2
    elif align == "right":
        x -= w
    u = size / 7.0
    thick = max(0.55, size * 0.115 * weight)
    cx = x
    for ch in s:
        g = GLYPHS.get(ch)
        if g is None:
            cx += 2.6 * u + tracking
            continue
        gw, strokes = g
        for st in strokes:
            if st and st[0] == "poly":
                pts = [(cx + px * u, y + py * u) for px, py in st[1]]
                cv.poly(pts, col)
            else:
                for i in range(len(st) - 1):
                    cv.line(cx + st[i][0] * u, y + st[i][1] * u,
                            cx + st[i + 1][0] * u, y + st[i + 1][1] * u, thick, col)
        cx += gw * u + tracking
    return w

def wrap(s, size, maxw, tracking=0.0):
    """Greedy word wrap; returns list of lines."""
    lines, cur = [], ""
    for word in s.split():
        trial = (cur + " " + word).strip()
        if text_width(trial, size, tracking) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines

def draw_wrapped(cv, x, y, s, size, col, maxw, leading=1.28, weight=1.0,
                 tracking=0.0, align="left", max_lines=None):
    lines = wrap(s, size, maxw, tracking)
    if max_lines:
        lines = lines[:max_lines]
    for i, ln in enumerate(lines):
        lx = x
        if align == "center":
            lx = x + maxw / 2
        draw_text(cv, lx, y + i * size * leading, ln, size, col, weight, tracking, align)
    return len(lines) * size * leading

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------

PAPER = (247, 243, 233)
PAPER_D = (238, 231, 214)
INK = (20, 21, 26)
INK_SOFT = (52, 54, 60)
GREY = (110, 112, 118)
RULE = (196, 188, 168)
RED = (176, 32, 24)
BLUE = (27, 74, 130)
GOLD = (178, 128, 20)
PANEL = (240, 234, 219)
PANEL_BLUE = (233, 237, 240)
WHITE = (252, 250, 245)

M = 34                      # page margin
CW = W - 2 * M              # content width

# --------------------------------------------------------------------------
# Motifs
# --------------------------------------------------------------------------

# Dot-grid world map: (row, first col, last col) land spans, 44 x 18 grid.
MAP_SPANS = [
    (1, 3, 9), (1, 21, 35),
    (2, 2, 10), (2, 19, 23), (2, 25, 38),
    (3, 2, 10), (3, 19, 24), (3, 26, 37), (3, 39, 39),
    (4, 3, 10), (4, 19, 23), (4, 26, 36), (4, 38, 39),
    (5, 3, 9), (5, 19, 22), (5, 25, 35), (5, 37, 38),
    (6, 3, 8), (6, 19, 26), (6, 28, 34),
    (7, 5, 7), (7, 19, 26), (7, 28, 30), (7, 32, 34),
    (8, 6, 7), (8, 20, 25), (8, 31, 33),
    (9, 9, 11), (9, 20, 25), (9, 32, 35),
    (10, 9, 12), (10, 20, 24), (10, 33, 35),
    (11, 10, 12), (11, 21, 24),
    (12, 10, 13), (12, 21, 24), (12, 34, 37),
    (13, 10, 12), (13, 22, 24), (13, 34, 38),
    (14, 10, 12), (14, 22, 23), (14, 35, 37),
    (15, 10, 11),
    (16, 10, 11),
]

def draw_map(cv, x, y, w, col=INK_SOFT, hot=RED):
    cols, rows = 44, 18
    step = w / cols
    r = step * 0.30
    land = set()
    for row, a, b in MAP_SPANS:
        for c in range(a, b + 1):
            land.add((row, c))
    for (row, c) in land:
        cv.disc(x + (c + 0.5) * step, y + (row + 0.5) * step, r, col)
    # Story hotspots: Shenzhen, Kyiv, Gaza/Hormuz, Riyadh, Washington, Hobart
    for (row, c) in [(6, 33), (3, 24), (6, 26), (7, 26), (5, 5), (14, 38)]:
        cv.disc(x + (c + 0.5) * step, y + (row + 0.5) * step, r * 1.9, hot)
    return rows * step

def hrule(cv, x, y, w, thick, col=INK):
    cv.rect(x, y, w, thick, col)

def section_head(cv, x, y, w, label, col=INK):
    cv.rect(x, y, w, 21, col)
    draw_text(cv, x + 8, y + 4.5, label, 12.5, WHITE, weight=1.15, tracking=1.2)
    return y + 21


def brief(cv, x, y, w, headline, size=13.0, col=INK):
    """A headline-only brief; returns height used."""
    return draw_wrapped(cv, x, y, headline, size, col, w, leading=1.22, weight=1.08)

def story(cv, x, y, w, head, deck, hsize=19, dsize=12):
    """Headline + short deck; returns height used."""
    hh = draw_wrapped(cv, x, y, head, hsize, INK, w, leading=1.15, weight=1.3)
    dh = draw_wrapped(cv, x, y + hh + 2, deck, dsize, INK_SOFT, w,
                      leading=1.25, weight=0.9)
    return hh + 2 + dh

# --------------------------------------------------------------------------
# The page
# --------------------------------------------------------------------------

def render():
    cv = Canvas()
    cv.rect(0, 0, W, H, PAPER)

    # ---- folio line ------------------------------------------------------
    draw_text(cv, M, 13, "VOL. I · No. 19", 11.5, INK_SOFT)
    draw_text(cv, W - M, 13, "DRAWN ENTIRELY IN CODE · NO PHOTOGRAPHS", 11.5,
              INK_SOFT, align="right")
    hrule(cv, M, 33, CW, 1.4, INK)

    # ---- masthead ---------------------------------------------------------
    draw_text(cv, W / 2, 44, "THE WORLD TODAY", 84, INK, weight=1.5,
              tracking=1.0, align="center")
    hrule(cv, M, 142, CW, 5, INK)
    hrule(cv, M, 150, CW, 1.6, INK)

    # ---- date bar ---------------------------------------------------------
    cv.rect(M, 160, CW, 40, INK)
    draw_text(cv, W / 2, 169, "WEDNESDAY 19 NOVEMBER 2026", 27, WHITE,
              weight=1.35, tracking=2.2, align="center")

    # ---- market ticker ----------------------------------------------------
    tick = ("MARKETS  BRENT $92.25 \u25b2 0.3% · WTI $83.46 · GOLD $3,740 \u25bc · "
            "S&P 500 7,324 \u25bc 0.2% · NASDAQ 24,430 \u25b2 0.4% · DOW 50,198 \u25bc 1.1%")
    draw_text(cv, W / 2, 212, tick, 14.5, INK, weight=1.05, align="center")
    hrule(cv, M, 236, CW, 1.4, INK)

    # ---- lead story (left) -------------------------------------------------
    LX, LW = M, 604
    y = 252
    draw_text(cv, LX, y, "SHENZHEN · APEC · DIPLOMACY", 14.5, RED, weight=1.3, tracking=1.6)
    y += 25
    y += draw_wrapped(cv, LX, y, "TRUMP, XI AND PUTIN HOLD FIRST THREE-WAY SUMMIT",
                      47, INK, LW, leading=1.16, weight=1.45)
    y += 5
    y += draw_wrapped(cv, LX, y,
                      "The leaders of the United States, China and Russia sit down "
                      "together in Shenzhen — a first in modern diplomacy — and "
                      "announce a \u201cpeace declaration\u201d.",
                      16.5, INK_SOFT, LW, leading=1.3, weight=0.95)
    y += 7
    y += draw_wrapped(cv, LX, y,
                      "JOINT STATEMENT PROMISES U.N. REFORM AND NUCLEAR TALKS — "
                      "UKRAINE, IRAN AND HORMUZ OIL ON THE TABLE",
                      15.5, INK, LW, leading=1.26, weight=1.2)
    y += 14
    map_h = draw_map(cv, LX + 2, y, 252)
    cap_h = draw_wrapped(cv, LX + 272, y + 2,
                         "THE DAY AT A GLANCE — RED DOTS MARK TODAY'S FRONT "
                         "PAGE, FROM SHENZHEN TO HOBART",
                         12.5, GREY, LW - 272, leading=1.3, weight=1.0)
    draw_wrapped(cv, LX + 272, y + 2 + cap_h + 8,
                 "INSIDE: WAR IN THE GULF · A GENOCIDE VERDICT · "
                 "THE BIGGEST IPO IN HISTORY",
                 12.5, GREY, LW - 272, leading=1.3, weight=1.0)

    # ---- right rail ---------------------------------------------------------
    RX, RW = 662, W - M - 662
    ry = 252
    cv.rect(RX, ry, RW, 178, PANEL)
    draw_text(cv, RX + 14, ry + 11, "THE DAY IN NUMBERS", 15.5, RED, weight=1.3, tracking=1.2)
    stats = [
        ("$81.3bn", "ANTHROPIC'S IPO — THE LARGEST EVER RAISED"),
        ("109–0", "DENMARK'S VOTE FOR THE GREENLAND PACT"),
        ("589m", "CHILDREN LIVING IN WAR ZONES — A RECORD"),
        ("72 hrs", "GIVEN TO THE UAE ENVOY TO QUIT SOMALIA"),
    ]
    sy = ry + 40
    for num, lab in stats:
        draw_text(cv, RX + 14, sy, num, 23, INK, weight=1.4)
        draw_wrapped(cv, RX + 112, sy + 2, lab, 11, INK_SOFT, RW - 124,
                     leading=1.2, weight=1.0)
        sy += 34.5
    ry += 192
    draw_text(cv, RX, ry, "BUSINESS · NEW YORK", 13, RED, weight=1.25, tracking=1.2)
    ry += 21
    ry += draw_wrapped(cv, RX, ry, "ANTHROPIC'S $81bn IPO SMASHES THE RECORD",
                       23.5, INK, RW, leading=1.18, weight=1.35)
    ry += 2
    ry += draw_wrapped(cv, RX, ry,
                       "Priced at $83 a share, the AI firm's offering tops "
                       "SpaceX's $75bn. Trading opens today on Nasdaq as ANT.",
                       13.5, INK_SOFT, RW, leading=1.27, weight=0.95)
    ry += 7
    bx, bw = RX + 2, RW - 88
    draw_text(cv, bx, ry, "SPACEX, JUN", 10, GREY)
    cv.rect(bx, ry + 14, bw * 75 / 81.3, 10, GREY)
    draw_text(cv, bx + bw * 75 / 81.3 + 7, ry + 13, "$75bn", 11, INK_SOFT, weight=1.1)
    draw_text(cv, bx, ry + 31, "ANTHROPIC", 10, RED, weight=1.1)
    cv.rect(bx, ry + 45, bw, 10, RED)
    draw_text(cv, bx + bw + 7, ry + 44, "$81.3bn", 11, RED, weight=1.15)

    # ---- lower columns -------------------------------------------------------
    hrule(cv, M, 646, CW, 2.2, INK)
    gcol_w = (CW - 2 * 22) / 3
    gy = 660
    for vx in (M + gcol_w + 11, M + 2 * gcol_w + 33):
        cv.rect(vx, gy + 2, 0.9, 272, RULE)

    # Column 1 — war & the court
    cx = M
    yy = gy
    draw_text(cv, cx, yy, "MIDDLE EAST", 12, RED, weight=1.25, tracking=1.3)
    yy += 15
    yy += story(cv, cx, yy, gcol_w, "IRAN WIDENS THE WAR: KUWAIT, BAHRAIN STRUCK",
                "Tehran answers U.S. strikes on Qeshm Island as tankers "
                "are mined near Hormuz.")
    yy += 5.5
    hrule(cv, cx, yy, gcol_w, 0.9, RULE); yy += 8
    draw_text(cv, cx, yy, "THE HAGUE", 12, RED, weight=1.25, tracking=1.3)
    yy += 15
    yy += story(cv, cx, yy, gcol_w, "WORLD COURT: MYANMAR COMMITTED GENOCIDE",
                "The ICJ rules the Rohingya campaign was genocide by "
                "the state — a first of its kind.")
    yy += 5.5
    hrule(cv, cx, yy, gcol_w, 0.9, RULE); yy += 8
    yy += brief(cv, cx, yy, gcol_w,
                "SOMALIA ORDERS UAE AMBASSADOR OUT IN 72 HOURS, CITING \u201cINVASION\u201d",
                size=12.5)
    yy += 5.5
    hrule(cv, cx, yy, gcol_w, 0.9, RULE); yy += 7
    yy += brief(cv, cx, yy, gcol_w,
                "BANGLADESH GRIPPED BY NATIONWIDE OPPOSITION SHUTDOWN", size=12.5)

    # Column 2 — Ukraine, Gaza, the Gulf
    cx = M + gcol_w + 22
    yy = gy
    draw_text(cv, cx, yy, "UKRAINE", 12, RED, weight=1.25, tracking=1.3)
    yy += 15
    yy += story(cv, cx, yy, gcol_w, "KYIV HITS KERCH BRIDGE FOR A THIRD TIME",
                "Rail traffic halted on Russia's Crimea bridge — "
                "third strike in four days.")
    yy += 5.5
    hrule(cv, cx, yy, gcol_w, 0.9, RULE); yy += 8
    draw_text(cv, cx, yy, "SAUDI ARABIA", 12, RED, weight=1.25, tracking=1.3)
    yy += 15
    yy += story(cv, cx, yy, gcol_w, "HOUTHI MISSILE DAMAGES RIYADH'S PIF TOWER",
                "The Saudi wealth fund's tower is damaged in an "
                "apparent Houthi missile attack.")
    yy += 5.5
    hrule(cv, cx, yy, gcol_w, 0.9, RULE); yy += 8
    yy += brief(cv, cx, yy, gcol_w,
                "ISRAELI TANKS PUSH INTO CENTRAL GAZA BEYOND CEASEFIRE LINE",
                size=12.5)
    yy += 5.5
    hrule(cv, cx, yy, gcol_w, 0.9, RULE); yy += 7
    yy += brief(cv, cx, yy, gcol_w,
                "LPG TANKER GAS HUSKY SINKS OFF BULGARIA AFTER PROJECTILE STRIKES",
                size=12.5)

    # Column 3 — planet, Asia-Pacific, economy briefs
    cx = M + 2 * (gcol_w + 22)
    yy = section_head(cv, cx, gy, gcol_w, "PLANET · ASIA · MONEY")
    yy += 9
    col3 = [
        "COP31 TALKS ENTER FINAL STAGE, SPLIT OVER FOSSIL-FUEL WORDS",
        "FIJI DECLARES NATIONAL DISASTER OVER EL NIÑO DROUGHT",
        "RIO TINTO PUTS $250M INTO PANGUNA MINE LEGACY FUND",
        "INDONESIA PASSES LAW TO SEIZE CRIME ASSETS WITHOUT A CONVICTION",
        "NORTH KOREA UNVEILS ITS FIRST AI CHATBOT, \u201cFOUNTAIN OF WISDOM\u201d",
        "OIL STEADIES NEAR $92 AS HORMUZ ATTACKS OFFSET SURPLUS",
        "DISCLOSURE: TRUMP BOUGHT UP TO $265,000 OF NVIDIA STOCK",
    ]
    for j, it in enumerate(col3):
        hh = brief(cv, cx, yy, gcol_w, it, size=12.5)
        yy += hh + 7
        if j < len(col3) - 1:
            hrule(cv, cx, yy - 3.5, gcol_w, 0.8, RULE)

    # ---- sport strip -----------------------------------------------------------
    sy = 946
    hrule(cv, M, sy, CW, 2.2, INK)
    draw_text(cv, M, sy + 9, "SPORT", 15, RED, weight=1.35, tracking=1.5)
    draw_text(cv, M + 76, sy + 10.5,
              "POCHETTINO STARTS AT MANCHESTER UNITED · ALCARAZ BEATS MEDVEDEV 6-2 6-4 · "
              "ENGLAND WIN ODI SERIES 2-1", 13, INK, weight=1.05)
    draw_text(cv, M + 76, sy + 29,
              "CHELSEA TOP GROUP, 1-0 OVER PSG · SOUTH AFRICA BEAT BANGLADESH BY NINE WICKETS · "
              "BARTY FOR HALL OF FAME", 13, INK, weight=1.05)

    # ---- footer ------------------------------------------------------------------
    draw_text(cv, W / 2, 1004,
              "SOURCES: REUTERS · ASSOCIATED PRESS · JUST SECURITY · SAVE THE CHILDREN · 38 NORTH · FIFA",
              10.5, GREY, align="center")

    return cv.downsample()

def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    rgb = render()
    write_png(os.path.join(out_dir, "entry.png"), W, H, rgb)

if __name__ == "__main__":
    main()
