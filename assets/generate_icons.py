"""Generate Salieri AI icon assets.

Run once (or whenever the design changes) with the repo's Python 3.10
interpreter, which has Pillow installed:

    python assets/generate_icons.py

Outputs (all under assets/):
  icon.png    - 256x256 master, used by electron-builder for the app icon
  icon.ico    - Windows multi-size .ico for electron-builder / NSIS
  tray.png    - 32x32 tray icon (loaded by the Electron main process)
  tray-16.png - 16x16 tray variant for dense trays

Design: a rounded-square "memory core" in the app's accent purple with a
glowing orb and a ring, evoking the Amadeus system aesthetic. Purely
programmatic so no binary art has to be checked in or licensed.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).parent

ACCENT = (124, 92, 252)      # --accent from global.css (#7c5cfc)
ACCENT_DEEP = (74, 60, 252)  # gradient companion
GLOW = (180, 160, 255)
BG = (20, 18, 34)


def _rounded_rect_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def _lerp(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def render_icon(size: int) -> Image.Image:
    """Render the icon at `size` (supersampled 4x for clean curves)."""
    S = size * 4
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # Rounded-square base with a vertical accent gradient.
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    bd = ImageDraw.Draw(base)
    radius = int(S * 0.22)
    bd.rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=BG + (255,))

    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / max(S - 1, 1)
        gd.line([(0, y), (S, y)], fill=_lerp(ACCENT_DEEP, ACCENT, t) + (38,))
    base = Image.alpha_composite(base, Image.composite(
        grad, Image.new("RGBA", (S, S), (0, 0, 0, 0)),
        _rounded_rect_mask(S, radius)))

    # Clip everything drawn so far to the rounded square.
    base.putalpha(_rounded_rect_mask(S, radius))

    # Glow layer: soft radial bloom behind the core.
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gdw = ImageDraw.Draw(glow)
    cx = cy = S // 2
    for r, alpha in [(int(S * 0.34), 60), (int(S * 0.28), 90)]:
        gdw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=GLOW + (alpha,))
    glow = glow.filter(ImageFilter.GaussianBlur(S * 0.06))

    img = Image.alpha_composite(img, base)
    img = Image.alpha_composite(img, glow)

    # Memory core: bright orb + accent ring.
    d = ImageDraw.Draw(img)
    core_r = int(S * 0.16)
    d.ellipse([cx - core_r, cy - core_r, cx + core_r, cy + core_r],
              fill=(235, 230, 255, 255))
    # Inner highlight (top-left) to give the orb depth.
    hi_r = int(core_r * 0.45)
    d.ellipse([cx - core_r // 2 - hi_r, cy - core_r // 2 - hi_r,
               cx - core_r // 2 + hi_r, cy - core_r // 2 + hi_r],
              fill=(255, 255, 255, 220))
    ring_w = max(2, int(S * 0.035))
    ring_r = int(S * 0.30)
    d.ellipse([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
              outline=ACCENT + (255,), width=ring_w)
    # Ring arc accent (top-right), brighter, like an orbital highlight.
    d.arc([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
          start=-70, end=20, fill=(255, 255, 255, 235), width=ring_w)

    return img.resize((size, size), Image.LANCZOS)


def main():
    master = render_icon(256)
    master.save(OUT / "icon.png")

    # Multi-size .ico for the Windows installer/executable.
    master.save(
        OUT / "icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

    render_icon(32).save(OUT / "tray.png")
    render_icon(16).save(OUT / "tray-16.png")

    for name in ("icon.png", "icon.ico", "tray.png", "tray-16.png"):
        p = OUT / name
        print(f"wrote {p} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
