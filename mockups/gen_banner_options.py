#!/usr/bin/env python3
"""Render masthead/banner redesign options as one contact sheet.

The current hero band is tall (kicker + small-caps region + a 66px name +
italic tagline + meta bar) and leaves a lot of dead space. Each option below
is drawn full-width with the real Ink Blue / Amber tokens so the height and
feel can be compared directly. Approx rendered band height is printed on each.
"""
import html
import cairosvg

SERIF = "Times New Roman, Liberation Serif, Georgia, serif"
SANS  = "Liberation Sans, Arial, sans-serif"

BLUE   = "#15264F"
ACCENT = "#E0851A"
BG     = "#EEF1F6"
CARD   = "#FFFFFF"
LINE   = "#DBE0E8"
INK    = "#16213E"
MUTE   = "#69707E"
WHITE  = "#FFFFFF"
W_SOFT = "rgba(255,255,255,.62)"
W_TAG  = "rgba(255,255,255,.55)"
W_BAR  = "rgba(255,255,255,.55)"


def esc(s): return html.escape(s, quote=True)


def T(x, y, s, size, fill, family=SANS, weight="400", anchor="start", spacing=None, italic=False):
    sp = f' letter-spacing="{spacing}"' if spacing is not None else ""
    it = ' font-style="italic"' if italic else ""
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
            f'fill="{fill}" font-weight="{weight}" text-anchor="{anchor}"{sp}{it}>{esc(s)}</text>')


def R(x, y, w, h, fill, rx=0, stroke=None, sw=1):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{s}/>'


def L(x1, y1, x2, y2, stroke, sw=1):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}"/>'


def live(x, y, fill_dot=ACCENT, fill_txt=WHITE):
    return (f'<circle cx="{x}" cy="{y-3}" r="3.5" fill="{fill_dot}"/>'
            + T(x + 9, y, "LIVE", 10.5, fill_txt, SANS, "600", spacing="1"))


W = 1040          # full band width
PAD = 0
GAP = 26
LABELH = 30


def band_current(x, y):
    h = 196
    o = [R(x, y, W, h, BLUE)]
    o.append(R(x, y, W, 5, ACCENT))
    cx = x + W / 2
    o.append(T(cx, y + 40, "REGIONAL INTELLIGENCE DESK · DAILY EDITION", 11, ACCENT, SANS, "700", "middle", "4"))
    o.append(T(cx, y + 74, "MIDDLE EAST", 26, W_SOFT, SERIF, "400", "middle", "10"))
    o.append(T(cx, y + 120, "Intelligence Hub", 52, WHITE, SERIF, "700", "middle"))
    o.append(T(cx, y + 150, "Front pages & sources across the Middle East", 16, W_TAG, SERIF, "400", "middle", italic=True))
    o.append(live(cx - 150, y + 178))
    o.append(T(cx, y + 178, "· Monday, June 22, 2026 ·", 11.5, W_BAR, SANS, "600", "middle"))
    o.append(T(cx + 150, y + 178, "REFRESHED EVERY 30 MIN", 10.5, W_BAR, SANS, "600", "end", "0.5"))
    return "\n".join(o), h, "CURRENT  —  ~196px tall"


def band_A(x, y):
    """Compact centered: drop the kicker + tagline, shrink the name, keep a centred lockup."""
    h = 104
    o = [R(x, y, W, h, BLUE)]
    o.append(R(x, y, W, 4, ACCENT))
    cx = x + W / 2
    o.append(T(cx, y + 46, "MIDDLE EAST", 13, W_SOFT, SERIF, "400", "middle", "8"))
    o.append(T(cx, y + 76, "Intelligence Hub", 34, WHITE, SERIF, "700", "middle"))
    o.append(live(x + 28, y + 26, fill_txt=W_BAR))
    o.append(T(x + W - 28, y + 26, "MON · JUN 22 · LIVE EVERY 30 MIN", 10.5, W_BAR, SANS, "600", "end", "0.5"))
    return "\n".join(o), h, "A · COMPACT CENTERED  —  ~104px  (no kicker/tagline, smaller name, meta on top edge)"


def band_B(x, y):
    """Horizontal wordmark: name left, meta right, one row — most compact."""
    h = 76
    o = [R(x, y, W, h, BLUE)]
    o.append(R(x, y, W, 4, ACCENT))
    # left lockup, two tight lines
    o.append(T(x + 30, y + 33, "MIDDLE EAST", 11, W_SOFT, SERIF, "400", "start", "6"))
    o.append(T(x + 30, y + 58, "Intelligence Hub", 27, WHITE, SERIF, "700", "start"))
    # right meta block
    o.append(live(x + W - 250, y + 34, fill_txt=WHITE))
    o.append(T(x + W - 30, y + 34, "Monday, June 22, 2026", 12, WHITE, SANS, "600", "end"))
    o.append(T(x + W - 30, y + 54, "Refreshed every 30 minutes", 11, W_BAR, SANS, "500", "end"))
    return "\n".join(o), h, "B · HORIZONTAL WORDMARK  —  ~76px  (name left, live + date right, single row)"


def band_C(x, y):
    """One-line lockup: region + name inline, centred, slim meta bar under a divider."""
    h = 92
    o = [R(x, y, W, h, BLUE)]
    o.append(R(x, y, W, 4, ACCENT))
    cx = x + W / 2
    # inline: small caps region then bold name on the same baseline
    o.append(T(cx - 8, y + 50, "MIDDLE EAST ", 15, W_SOFT, SERIF, "400", "end", "6"))
    o.append(T(cx - 2, y + 50, "Intelligence Hub", 30, WHITE, SERIF, "700", "start"))
    o.append(L(x + 30, y + 66, x + W - 30, y + 66, "rgba(255,255,255,.14)"))
    o.append(live(x + 30, y + 82, fill_txt=W_BAR))
    o.append(T(cx, y + 82, "Front pages, headlines & briefings across the Middle East", 11.5, W_BAR, SANS, "500", "middle"))
    o.append(T(x + W - 30, y + 82, "JUN 22 · EVERY 30 MIN", 10.5, W_BAR, SANS, "600", "end", "0.5"))
    return "\n".join(o), h, "C · ONE-LINE LOCKUP  —  ~92px  (region + name inline, thin meta strip)"


def band_D(x, y):
    """Slim utility bar: app-style top bar, very short."""
    h = 58
    o = [R(x, y, W, h, BLUE)]
    o.append(R(x, y, W, 3, ACCENT))
    # left: amber tick + inline wordmark
    o.append(R(x + 30, y + 22, 4, 18, ACCENT))
    o.append(T(x + 44, y + 28, "MIDDLE EAST", 10.5, W_SOFT, SANS, "700", "start", "3"))
    o.append(T(x + 44, y + 45, "Intelligence Hub", 18, WHITE, SERIF, "700", "start"))
    # right meta
    o.append(live(x + W - 235, y + 36, fill_txt=WHITE))
    o.append(T(x + W - 30, y + 36, "Mon, Jun 22 · refreshed every 30 min", 11, W_BAR, SANS, "500", "end"))
    return "\n".join(o), h, "D · SLIM UTILITY BAR  —  ~58px  (app-style top bar, most space saved)"


BUILDERS = [band_current, band_A, band_B, band_C, band_D]

MARGIN = 26
HEADER = 70
# precompute heights
parts = []
y = HEADER + MARGIN
xs = MARGIN
total_h = HEADER + MARGIN
for b in BUILDERS:
    # peek height by calling with dummy then discard? call once
    svg_band, bh, label = b(xs, y + LABELH)
    parts.append((svg_band, bh, label, y))
    y += LABELH + bh + GAP
    total_h = y

WTOT = MARGIN * 2 + W
HTOT = int(total_h + MARGIN)

body = [R(0, 0, WTOT, HTOT, "#FFFFFF"),
        R(0, 0, WTOT, HEADER, BLUE), R(0, 0, WTOT, 4, ACCENT),
        T(MARGIN, 44, "HOMEPAGE BANNER — SIZE OPTIONS", 20, WHITE, SERIF, "700")]
for svg_band, bh, label, yy in parts:
    body.append(T(MARGIN, yy + 20, label, 13, INK, SANS, "700"))
    body.append(svg_band)

svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{WTOT}" height="{HTOT}" '
       f'viewBox="0 0 {WTOT} {HTOT}">{"".join(body)}</svg>')
cairosvg.svg2png(bytestring=svg.encode("utf-8"),
                 write_to="/home/user/mena-newsstand/mockups/banner_options.png",
                 output_width=WTOT, output_height=HTOT, background_color="white")
print(f"wrote banner_options.png ({WTOT}x{HTOT})")
