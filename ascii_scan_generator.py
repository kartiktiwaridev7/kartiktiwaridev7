"""
ascii_scan_generator_v2.py

Converts a photo into an animated "terminal scan" ASCII-art SVG.
v2 changes from v1:
  - ASCII characters render in white/silver (not blue) with a soft glow
  - Adds a macOS-style terminal window chrome (traffic-light dots + title bar)
  - Adds a blinking terminal cursor after the "scan" finishes
  - Adds a subtle CRT scanline texture overlay for a more "hacker terminal" feel
  - Cyan accent color is kept only for the moving scan-beam + border/chrome,
    so it reads as an accent, not the subject

Usage:
    python3 ascii_scan_generator_v2.py input.png output.svg

Requires: Pillow (pip install pillow)
"""

import sys
from PIL import Image

# ---- Tunable settings -------------------------------------------------
COLS = 100                    # number of ASCII columns
FONT_SIZE = 7                 # px
CHAR_W_RATIO = 0.58           # monospace glyph width/height ratio
BG_COLOR = "#0D1117"          # matches GitHub dark theme used in README
CHARSET = " .:-=+*#%@"        # sparse -> dense
ACCENT = "#36BCF7"            # cyan accent (chrome / scanline / border only)
TITLE_TEXT = "kartik@github:~$ ./scan --target=kartik_tiwari.jpg"
SCAN_DURATION = 4.2           # seconds for one scan pass
LOOP_PAUSE = 1.2              # pause before looping
CHROME_H = 28                 # terminal title-bar height in px
PADDING = 14                  # inner padding around the ascii art
# ------------------------------------------------------------------------


def lerp(a, b, t):
    return a + (b - a) * t


def pixel_to_char_and_color(v):
    """v: brightness 0-255. Returns (char, hex_color).
    Inverted: darker source pixels (subject/hair/clothing) map to denser
    characters so the person reads clearly against the dark background.
    Color ramps from dim gray (sparse) to bright white (dense) for depth.
    """
    inv = 255 - v
    idx = int((inv / 255) * (len(CHARSET) - 1))
    ch = CHARSET[idx]
    t = inv / 255
    # dim gray -> pure white
    g = int(lerp(90, 255, t))
    color = f"rgb({g},{g},{g})"
    return ch, color


def image_to_ascii_grid(path, cols=COLS):
    im = Image.open(path).convert("L")
    w, h = im.size
    rows = max(1, round(cols * CHAR_W_RATIO * (h / w)))
    im_small = im.resize((cols, rows))
    pixels = list(im_small.getdata())
    grid = [pixels[r * cols:(r + 1) * cols] for r in range(rows)]
    return grid, cols, rows


def build_svg(grid, cols, rows, out_path):
    font_size = FONT_SIZE
    char_w = font_size * CHAR_W_RATIO
    line_h = font_size * 1.15

    art_w = cols * char_w
    art_h = rows * line_h

    svg_w = art_w + PADDING * 2
    svg_h = art_h + PADDING * 2 + CHROME_H

    scan_delay_step = (SCAN_DURATION * 0.7) / max(rows, 1)
    total_cycle = SCAN_DURATION + LOOP_PAUSE

    style = f"""
    <style>
      .bgrect {{ fill: {BG_COLOR}; }}
      .chrome {{ fill: #161b22; }}
      .dot {{ }}
      .title {{
        font-family: 'Courier New', ui-monospace, monospace;
        font-size: 11px;
        fill: #8b949e;
      }}
      text.ascii {{
        font-family: 'Courier New', ui-monospace, monospace;
        font-size: {font_size}px;
        white-space: pre;
      }}
      .row {{
        opacity: 0;
        animation: revealRow {total_cycle}s ease-in-out infinite;
      }}
      @keyframes revealRow {{
        0%   {{ opacity: 0; }}
        4%   {{ opacity: 1; text-shadow: 0 0 2px rgba(255,255,255,0.35); }}
        70%  {{ opacity: 1; }}
        88%  {{ opacity: 0.2; }}
        100% {{ opacity: 0; }}
      }}
      .scanline {{
        animation: moveScan {total_cycle}s linear infinite;
      }}
      @keyframes moveScan {{
        0%   {{ transform: translateY(-10px); opacity: 0; }}
        3%   {{ opacity: 1; }}
        68%  {{ transform: translateY({art_h - 4:.1f}px); opacity: 1; }}
        76%  {{ opacity: 0; }}
        100% {{ opacity: 0; transform: translateY(-10px); }}
      }}
      .cursor {{
        fill: {ACCENT};
        animation: blink 1s steps(1) infinite;
      }}
      @keyframes blink {{
        0%, 49%   {{ opacity: 1; }}
        50%, 100% {{ opacity: 0; }}
      }}
      .crt {{
        fill: url(#crtLines);
        opacity: 0.5;
        mix-blend-mode: overlay;
      }}
      .frame {{
        fill: none;
        stroke: {ACCENT};
        stroke-opacity: 0.4;
        stroke-width: 1.4;
      }}
      .statusText {{
        font-family: 'Courier New', ui-monospace, monospace;
        font-size: 9px;
        fill: {ACCENT};
        animation: revealRow {total_cycle}s ease-in-out infinite;
        animation-delay: {SCAN_DURATION * 0.72:.2f}s;
      }}
    </style>
    """

    defs = f"""
    <defs>
      <linearGradient id="glow" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="{ACCENT}" stop-opacity="0"/>
        <stop offset="50%" stop-color="{ACCENT}" stop-opacity="0.6"/>
        <stop offset="100%" stop-color="{ACCENT}" stop-opacity="0"/>
      </linearGradient>
      <pattern id="crtLines" width="4" height="4" patternUnits="userSpaceOnUse">
        <rect width="4" height="2" fill="black" fill-opacity="0"/>
        <rect y="2" width="4" height="1" fill="black" fill-opacity="0.35"/>
      </pattern>
    </defs>
    """

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w:.0f}" '
        f'height="{svg_h:.0f}" viewBox="0 0 {svg_w:.0f} {svg_h:.0f}">'
    )
    parts.append(style)
    parts.append(defs)

    # outer window
    parts.append(f'<rect class="bgrect" width="100%" height="100%" rx="10"/>')

    # title chrome bar
    parts.append(f'<path class="chrome" d="M0,10 a10,10 0 0 1 10,-10 h{svg_w-20:.0f} a10,10 0 0 1 10,10 v{CHROME_H-10:.0f} h-{svg_w:.0f} z"/>')
    dot_y = CHROME_H / 2
    for i, col in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        parts.append(f'<circle class="dot" cx="{14 + i*16}" cy="{dot_y:.0f}" r="4.5" fill="{col}"/>')
    parts.append(f'<text class="title" x="{svg_w/2:.0f}" y="{dot_y+4:.0f}" text-anchor="middle">{TITLE_TEXT}</text>')

    # ASCII rows (offset below chrome)
    y_off = CHROME_H + PADDING
    x_off = PADDING
    for r, row in enumerate(grid):
        y = y_off + (r + 1) * line_h
        delay = r * scan_delay_step
        row_chars = [pixel_to_char_and_color(v) for v in row]

        tspans_list = []
        cur_color = None
        cur_text = ""
        for ch, color in row_chars:
            if color != cur_color:
                if cur_text:
                    tspans_list.append((cur_color, cur_text))
                cur_color = color
                cur_text = ch
            else:
                cur_text += ch
        if cur_text:
            tspans_list.append((cur_color, cur_text))

        tspan_str = "".join(
            f'<tspan fill="{color}">{text.replace(" ", "&#160;")}</tspan>'
            for color, text in tspans_list
        )
        parts.append(
            f'<text class="ascii row" x="{x_off}" y="{y:.1f}" '
            f'style="animation-delay:{delay:.3f}s">{tspan_str}</text>'
        )

    # scanning beam (glow line sweeping top -> bottom), clipped to art area
    parts.append(f'<g class="scanline" transform="translate(0,{y_off})">')
    parts.append(f'<rect x="{x_off}" y="0" width="{art_w:.0f}" height="2" fill="#ffffff"/>')
    parts.append(f'<rect x="{x_off}" y="-7" width="{art_w:.0f}" height="9" fill="url(#glow)"/>')
    parts.append('</g>')

    # status line + blinking cursor at bottom of art area
    status_y = y_off + art_h + 2
    parts.append(
        f'<text class="statusText" x="{x_off}" y="{status_y:.0f}">'
        f'scan complete: 100%</text>'
    )
    parts.append(
        f'<rect class="cursor" x="{x_off + 118}" y="{status_y-8:.0f}" width="6" height="10"/>'
    )

    # CRT scanline texture over the whole art area
    parts.append(f'<rect class="crt" x="{x_off}" y="{y_off}" width="{art_w:.0f}" height="{art_h:.0f}"/>')

    # outer frame
    parts.append(f'<rect class="frame" x="1" y="1" width="{svg_w-2:.0f}" height="{svg_h-2:.0f}" rx="10"/>')
    parts.append("</svg>")

    with open(out_path, "w") as f:
        f.write("\n".join(parts))


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "pfp_final.png"
    dst = sys.argv[2] if len(sys.argv) > 2 else "ascii-scan.svg"
    grid, cols, rows = image_to_ascii_grid(src)
    build_svg(grid, cols, rows, dst)
    print(f"Wrote {dst}  ({cols}x{rows} chars)")
