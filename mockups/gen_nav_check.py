#!/usr/bin/env python3
"""Render the nav bar at phone width to verify the World Briefing tab is not clipped.

Simulates the flex layout: with the old centred-overflow, the first tab is
clipped on the left; with auto-margin spacers + tighter padding it is flush-left
and fully visible.
"""
import html, cairosvg

SANS = "Liberation Sans, Arial, sans-serif"
ACCENT = "#E0851A"
MUTE = "#69707E"
LINE = "#DBE0E8"
PHONE = 375
TABS = ["WORLD BRIEFING", "HEADLINES", "FRONT PAGES", "PULSE", "ARCHIVE"]


def esc(s): return html.escape(s, quote=True)


def char_w(fs): return fs * 0.62  # rough uppercase semibold advance


def tab_w(label, fs, padx, ls):
    return len(label) * (char_w(fs) + ls) + padx * 2


def render(fname, fs, padx, ls, centered_clip, title):
    h = 90
    parts = [f'<rect x="0" y="0" width="{PHONE}" height="{h}" fill="#fff"/>',
             f'<text x="12" y="20" font-family="{SANS}" font-size="11" fill="#999">{esc(title)}</text>',
             f'<rect x="0" y="30" width="{PHONE}" height="52" fill="#fff"/>',
             f'<line x1="0" y1="82" x2="{PHONE}" y2="82" stroke="{LINE}"/>']
    widths = [tab_w(t, fs, padx, ls) for t in TABS]
    total = sum(widths)
    if centered_clip:
        # centred overflow: content centred, left part clipped off-screen (unreachable)
        x = (PHONE - total) / 2
    else:
        x = 0  # flush-left, scrollable
    # clip region = viewport
    parts.append(f'<defs><clipPath id="vp"><rect x="0" y="30" width="{PHONE}" height="52"/></clipPath></defs>')
    parts.append('<g clip-path="url(#vp)">')
    for i, (t, w) in enumerate(zip(TABS, widths)):
        col = ACCENT if i == 0 else MUTE
        tx = x + w / 2
        # letter-spacing approximation via textLength
        parts.append(f'<text x="{tx:.1f}" y="62" font-family="{SANS}" font-size="{fs}" '
                     f'fill="{col}" font-weight="600" text-anchor="middle" '
                     f'letter-spacing="{ls}">{esc(t)}</text>')
        if i == 0:
            parts.append(f'<rect x="{x:.1f}" y="79" width="{w:.1f}" height="3" fill="{ACCENT}"/>')
        x += w
    parts.append('</g>')
    # right-edge fade hint if overflow
    if total > PHONE:
        parts.append(f'<rect x="{PHONE-26}" y="30" width="26" height="52" '
                     f'fill="url(#fade)"/>')
        parts.insert(0, '<defs><linearGradient id="fade" x1="0" x2="1">'
                     '<stop offset="0" stop-color="#fff" stop-opacity="0"/>'
                     '<stop offset="1" stop-color="#fff" stop-opacity="1"/>'
                     '</linearGradient></defs>')
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{PHONE}" height="{h}" '
           f'viewBox="0 0 {PHONE} {h}">{"".join(parts)}</svg>')
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=fname,
                     output_width=PHONE * 2, output_height=h * 2, background_color="white")
    print(f"wrote {fname}  total_tabs_width={total:.0f}px viewport={PHONE}px")


# stack before/after into one image
import subprocess
render("/tmp/nav_before.png", 12.5, 20, 0.8, True, "BEFORE  (centred — World Briefing clipped on the left)")
render("/tmp/nav_after.png", 11, 12, 0.3, False, "AFTER  (flush-left, tighter — World Briefing fully visible, scrolls right)")
