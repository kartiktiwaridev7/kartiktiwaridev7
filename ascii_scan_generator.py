"""
ascii_scan_generator.py

Converts a photo into an animated "scanning" ASCII-art SVG,
styled to match a dark terminal GitHub README theme.

Usage:
    python3 ascii_scan_generator.py input.png output.svg

Requires: Pillow (pip install pillow)
"""

import sys
from PIL import Image

# ---- Tunable settings -------------------------------------------------
COLS = 110                    # number of ASCII columns
FONT_SIZE = 7                 # px
CHAR_W_RATIO = 0.58           # monospace glyph width/height ratio
BG_COLOR = "#0D1117"          # matches GitHub dark theme used in README
CHARSET = " .:-=+*#%@"        # sparse -> dense, dark -> bright
COLOR_LOW = (54, 188, 247)    # #36BCF7 cyan  (dim pixels)
COLOR_HIGH = (108, 92, 231)   # #6C5CE7 purple (bright pixels) -- blended
SCAN_DURATION = 4.2           # seconds for one scan pass
LOOP_PAUSE = 1.0              # pause before looping
# ------------------------------------------------------------------------


def lerp(a, b, t):
    return a + (b - a) * t


def pixel_to_char_and_color(v):
    """v: brightness 0-255. Returns (char, hex_color).
    Inverted: darker source pixels (subject/hair/clothing) map to denser
    characters so the person reads clearly; bright background stays sparse.
    """
    inv = 255 - v
    idx = int((inv / 255) * (len(CHARSET) - 1))
    ch = CHARSET[idx]
    t = inv / 255
    r = int(lerp(COLOR_LOW[0], COLOR_HIGH[0], t))
    g = int(lerp(COLOR_LOW[1], COLOR_HIGH[1], t))
    b = int(lerp(COLOR_LOW[2], COLOR_HIGH[2], t))
    return ch, f"rgb({r},{g},{b})"


def image_to_ascii_grid(path, cols=COLS):
    im = Image.open(path).convert("L")
    w, h = im.size
    # keep the SVG's overall aspect ratio matched to the source image,
    # accounting for monospace glyphs being narrower than they are tall
    rows = max(1, round(cols * CHAR_W_RATIO * (h / w)))
    im_small = im.resize((cols, rows))
    pixels = list(im_small.getdata())
    grid = [pixels[r * cols:(r + 1) * cols] for r in range(rows)]
    return grid, cols, rows


def build_svg(grid, cols, rows, out_path):
    font_size = FONT_SIZE
    char_w = font_size * CHAR_W_RATIO
    line_h = font_size * 1.15

    svg_w = cols * char_w
    svg_h = rows * line_h

    scan_delay_step = (SCAN_DURATION * 0.7) / max(rows, 1)

    style = f"""
    <style>
      .bgrect {{ fill: {BG_COLOR}; }}
      text {{
        font-family: 'Courier New', ui-monospace, monospace;
        font-size: {font_size}px;
        white-space: pre;
      }}
      .row {{
        opacity: 0;
        animation: revealRow {SCAN_DURATION + LOOP_PAUSE}s ease-in-out infinite;
      }}
      @keyframes revealRow {{
        0%   {{ opacity: 0; }}
        4%   {{ opacity: 1; }}
        75%  {{ opacity: 1; }}
        92%  {{ opacity: 0.15; }}
        100% {{ opacity: 0; }}
      }}
      .scanline {{
        animation: moveScan {SCAN_DURATION + LOOP_PAUSE}s linear infinite;
      }}
      @keyframes moveScan {{
        0%   {{ transform: translateY(-10px); opacity: 0; }}
        3%   {{ opacity: 1; }}
        70%  {{ transform: translateY({svg_h - 10:.1f}px); opacity: 1; }}
        78%  {{ opacity: 0; }}
        100% {{ opacity: 0; transform: translateY(-10px); }}
      }}
      .frame {{
        fill: none;
        stroke: #36BCF7;
        stroke-opacity: 0.35;
        stroke-width: 1.5;
      }}
    </style>
    """

    parts = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w:.0f}" '
        f'height="{svg_h:.0f}" viewBox="0 0 {svg_w:.0f} {svg_h:.0f}">'
    )
    parts.append(style)
    parts.append(f'<rect class="bgrect" width="100%" height="100%" rx="10"/>')

    # ASCII rows
    for r, row in enumerate(grid):
        y = (r + 1) * line_h
        delay = r * scan_delay_step
        chars = []
        colors_same = True
        first_color = None
        row_chars = []
        for v in row:
            ch, color = pixel_to_char_and_color(v)
            row_chars.append((ch, color))

        # group consecutive same-color runs into tspans to keep file small-ish
        tspans = []
        cur_color = None
        cur_text = ""
        for ch, color in row_chars:
            if color != cur_color:
                if cur_text:
                    tspans.append((cur_color, cur_text))
                cur_color = color
                cur_text = ch
            else:
                cur_text += ch
        if cur_text:
            tspans.append((cur_color, cur_text))

        tspan_str = "".join(
            f'<tspan fill="{color}">{text.replace(" ", "&#160;")}</tspan>'
            for color, text in tspans
        )
        parts.append(
            f'<text class="row" x="0" y="{y:.1f}" '
            f'style="animation-delay:{delay:.3f}s">{tspan_str}</text>'
        )

    # scanning bar (glow line sweeping top -> bottom)
    parts.append(
        f'<g class="scanline">'
        f'<rect x="0" y="0" width="{svg_w:.0f}" height="2.5" fill="#36BCF7"/>'
        f'<rect x="0" y="-6" width="{svg_w:.0f}" height="8" fill="url(#glow)"/>'
        f'</g>'
    )
    parts.insert(2, (
        '<defs><linearGradient id="glow" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#36BCF7" stop-opacity="0"/>'
        '<stop offset="50%" stop-color="#36BCF7" stop-opacity="0.55"/>'
        '<stop offset="100%" stop-color="#36BCF7" stop-opacity="0"/>'
        '</linearGradient></defs>'
    ))

    parts.append(f'<rect class="frame" x="1" y="1" width="{svg_w-2:.0f}" height="{svg_h-2:.0f}" rx="10"/>')
    parts.append("</svg>")

    with open(out_path, "w") as f:
        f.write("\n".join(parts))


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "profile_final.png"
    dst = sys.argv[2] if len(sys.argv) > 2 else "ascii-scan.svg"
    grid, cols, rows = image_to_ascii_grid(src)
    build_svg(grid, cols, rows, dst)
    print(f"Wrote {dst}  ({cols}x{rows} chars)")
