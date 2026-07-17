"""
ascii_scan_generator_v3.py

Converts a photo into an animated "terminal scan" ASCII-art SVG, built for
embedding in a GitHub profile README (github.com/<username>/<username>).

v3 changes from v2:
  - Proper CLI (argparse) instead of positional-only sys.argv — you can now
    tweak columns, font size, colors, title text, and timing without
    touching the code.
  - Auto-generates the terminal title ("user@github:~$ ./scan --target=...")
    from your GitHub username + the input filename, or you can override it.
  - Clear error handling: missing file / bad image now prints a readable
    message instead of a raw traceback.
  - Output size (COLS) is validated so you can't accidentally pass 0 or a
    negative value and get a divide-by-zero.
  - Same visual style as v2: white/silver ASCII glyphs with a soft glow,
    macOS-style terminal chrome, blinking cursor, CRT scanline overlay, and
    a cyan accent reserved for the chrome/border/scan-beam only.

Usage:
    python3 ascii_scan_generator_v3.py path/to/photo.jpg assets/ascii-scan.svg

    # common overrides
    python3 ascii_scan_generator_v3.py photo.jpg out.svg --user kartiktiwari --cols 110

Requires: Pillow (pip install pillow)
"""

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:
    sys.exit("Missing dependency. Install it with:  pip install pillow")

# ---- Fixed layout constants -------------------------------------------
CHAR_W_RATIO = 0.58   # monospace glyph width/height ratio
CHROME_H = 28          # terminal title-bar height in px
PADDING = 14           # inner padding around the ascii art
DEFAULT_CHARSET = " .:-=+*#%@"   # sparse -> dense
# ------------------------------------------------------------------------


def lerp(a, b, t):
    return a + (b - a) * t


def pixel_to_char_and_color(v, charset, solid_color=None):
    """v: brightness 0-255. Returns (char, css_color).
    Darker source pixels (subject/hair/clothing) map to denser characters
    so the person reads clearly against the dark background.

    If solid_color is given, every glyph uses that one color (e.g. pure
    white) — only the character density varies, not the color. Otherwise
    falls back to the old gray-to-white gradient (sparse=dim, dense=bright).
    """
    inv = 255 - v
    idx = int((inv / 255) * (len(charset) - 1))
    ch = charset[idx]

    if solid_color:
        return ch, solid_color

    t = inv / 255
    g = int(lerp(90, 255, t))
    return ch, f"rgb({g},{g},{g})"


def image_to_ascii_grid(path, cols):
    try:
        im = Image.open(path).convert("L")
    except FileNotFoundError:
        sys.exit(f"Error: couldn't find input image '{path}'")
    except UnidentifiedImageError:
        sys.exit(f"Error: '{path}' doesn't look like a valid image file")

    w, h = im.size
    rows = max(1, round(cols * CHAR_W_RATIO * (h / w)))
    im_small = im.resize((cols, rows))
    pixels = list(im_small.getdata())
    grid = [pixels[r * cols:(r + 1) * cols] for r in range(rows)]
    return grid, cols, rows


def build_svg(grid, cols, rows, args):
    font_size = args.font_size
    char_w = font_size * CHAR_W_RATIO
    line_h = font_size * 1.15

    art_w = cols * char_w
    art_h = rows * line_h

    svg_w = art_w + PADDING * 2
    svg_h = art_h + PADDING * 2 + CHROME_H

    scan_delay_step = (args.scan_duration * 0.7) / max(rows, 1)
    total_cycle = args.scan_duration + args.loop_pause

    style = f"""
    <style>
      .bgrect {{ fill: {args.bg}; }}
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
        font-weight: 600;
        white-space: pre;
        text-shadow: 0 0 3px rgba(255,255,255,0.25);
      }}
      .row {{
        opacity: 0;
        animation: revealRow {total_cycle}s ease-in-out infinite;
      }}
      @keyframes revealRow {{
        0%   {{ opacity: 0; }}
        4%   {{ opacity: 1; text-shadow: 0 0 4px rgba(255,255,255,0.55); }}
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
        fill: {args.accent};
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
        stroke: {args.accent};
        stroke-opacity: 0.4;
        stroke-width: 1.4;
      }}
      .statusText {{
        font-family: 'Courier New', ui-monospace, monospace;
        font-size: 9px;
        fill: {args.accent};
        animation: revealRow {total_cycle}s ease-in-out infinite;
        animation-delay: {args.scan_duration * 0.72:.2f}s;
      }}
    </style>
    """

    defs = f"""
    <defs>
      <linearGradient id="glow" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="{args.accent}" stop-opacity="0"/>
        <stop offset="50%" stop-color="{args.accent}" stop-opacity="0.6"/>
        <stop offset="100%" stop-color="{args.accent}" stop-opacity="0"/>
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
        f'height="{svg_h:.0f}" viewBox="0 0 {svg_w:.0f} {svg_h:.0f}" '
        f'role="img" aria-label="Animated ASCII scan portrait">'
    )
    parts.append(f'<title>{args.title}</title>')
    parts.append(style)
    parts.append(defs)

    # outer window
    parts.append('<rect class="bgrect" width="100%" height="100%" rx="10"/>')

    # title chrome bar
    parts.append(
        f'<path class="chrome" d="M0,10 a10,10 0 0 1 10,-10 h{svg_w-20:.0f} '
        f'a10,10 0 0 1 10,10 v{CHROME_H-10:.0f} h-{svg_w:.0f} z"/>'
    )
    dot_y = CHROME_H / 2
    for i, col in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        parts.append(f'<circle class="dot" cx="{14 + i*16}" cy="{dot_y:.0f}" r="4.5" fill="{col}"/>')
    parts.append(f'<text class="title" x="{svg_w/2:.0f}" y="{dot_y+4:.0f}" text-anchor="middle">{args.title}</text>')

    # ASCII rows (offset below chrome)
    y_off = CHROME_H + PADDING
    x_off = PADDING
    for r, row in enumerate(grid):
        y = y_off + (r + 1) * line_h
        delay = r * scan_delay_step
        row_chars = [pixel_to_char_and_color(v, args.charset, args.text_color) for v in row]

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

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        f.write("\n".join(parts))


def parse_args():
    p = argparse.ArgumentParser(
        description="Convert a photo into an animated ASCII-scan SVG for a GitHub profile README."
    )
    p.add_argument("input", help="Path to the source photo (png/jpg)")
    p.add_argument("output", nargs="?", default="ascii-scan.svg",
                    help="Output SVG path (default: ascii-scan.svg)")
    p.add_argument("--user", default="kartik",
                    help="Username shown in the fake terminal prompt (default: kartik)")
    p.add_argument("--cols", type=int, default=100,
                    help="Number of ASCII columns / detail level (default: 100)")
    p.add_argument("--font-size", type=int, default=7, help="Glyph font size in px (default: 7)")
    p.add_argument("--accent", default="#36BCF7", help="Accent color for chrome/border/scan-beam")
    p.add_argument("--bg", default="#0D1117", help="Background color")
    p.add_argument("--charset", default=DEFAULT_CHARSET,
                    help="Characters from sparse to dense (default: ' .:-=+*#%%@')")
    p.add_argument("--text-color", default="#FFFFFF", dest="text_color",
                    help="Solid color for every glyph (default: pure white, #FFFFFF)")
    p.add_argument("--gradient", action="store_const", const=None, dest="text_color",
                    help="Use the old dim-gray-to-white fade instead of solid white")
    p.add_argument("--title", default=None,
                    help="Override the full terminal title text")
    p.add_argument("--scan-duration", type=float, default=4.2, dest="scan_duration",
                    help="Seconds for one scan pass (default: 4.2)")
    p.add_argument("--loop-pause", type=float, default=1.2, dest="loop_pause",
                    help="Pause in seconds before the animation loops (default: 1.2)")
    args = p.parse_args()

    if args.cols < 10:
        sys.exit("Error: --cols must be at least 10")
    if len(args.charset) < 2:
        sys.exit("Error: --charset needs at least 2 characters")

    if args.title is None:
        fname = Path(args.input).name
        args.title = f"{args.user}@github:~$ ./scan --target={fname}"

    return args


def main():
    args = parse_args()
    grid, cols, rows = image_to_ascii_grid(args.input, args.cols)
    build_svg(grid, cols, rows, args)
    print(f"Wrote {args.output}  ({cols}x{rows} chars)")


if __name__ == "__main__":
    main()
