#!/usr/bin/env python3
"""Render the Dexed (DX7) 2.0 skin art: panel backgrounds, membrane switches, slider film strips,
LED digits, LCD bezel, the striped DX7/DEXED wordmark, algorithm art, plus preview mockups.

Pillow only. Everything is drawn from code (no proprietary art, no logo files) so the look is
reproducible and can be re-tuned here. See docs/PLAN-2.0.md, Phase 2.

    python3 tools/make_dx7_skin.py            # assets -> skins/, previews -> skins/preview/
"""
import math, os, random, re, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "art")
PREV = os.path.join(ROOT, "docs", "skin-preview")
FONT = os.path.join(HERE, "fonts", "RobotoCondensed.ttf")
SS = 3  # supersampling factor for small parts

# ---- palette, from the reference photos (ref/*.webp) ----------------------------------------
PANEL_TOP = (44, 38, 35)      # chocolate brown, lit
PANEL_BOT = (24, 21, 20)
TAN = (190, 168, 128)         # lower legend print
LILAC = (146, 150, 205)       # group-header print
CREAM = (222, 210, 184)       # algorithm chart print
TEAL = (34, 182, 166)         # "DX green" membrane switch
TEAL_LIT = (88, 236, 214)
RED_LED = (255, 40, 58)
LCD_BG = (178, 192, 170)
LCD_INK = (30, 36, 28)
STORE_RED = (226, 112, 122)
QLINK = (232, 31, 64)         # MPC's own focus colour (for the mockup)


def font(px, wght=500):
    f = ImageFont.truetype(FONT, int(px))
    try:
        f.set_variation_by_axes([wght])
    except Exception:
        pass
    return f


def ensure(*dirs):
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(len(a)))


# ---- panel -------------------------------------------------------------------------------------
def panel(w, h, seed=7):
    """Brown panel: vertical gradient, top-left key light, fine grain, edge vignette."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    rnd = random.Random(seed)
    kx, ky = -0.15 * w, -0.35 * h            # key light off the top-left corner
    kr = math.hypot(w, h) * 0.9
    for y in range(h):
        base = lerp(PANEL_TOP, PANEL_BOT, y / max(1, h - 1))
        for x in range(w):
            d = math.hypot(x - kx, y - ky) / kr
            light = max(0.0, 1.0 - d) ** 2 * 26          # warm highlight
            vx = min(x, w - 1 - x) / (0.12 * w)
            vy = min(y, h - 1 - y) / (0.18 * h)
            vig = 1.0 - 0.18 * (1 - min(1.0, vx)) ** 2 - 0.14 * (1 - min(1.0, vy)) ** 2
            g = rnd.randint(-3, 3)
            px[x, y] = (int(min(255, (base[0] + light * 1.05) * vig + g)),
                        int(min(255, (base[1] + light * 0.95) * vig + g)),
                        int(min(255, (base[2] + light * 0.85) * vig + g)))
    # a faint horizontal sheen band, like the moulding catching the light
    sheen = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sheen).rectangle([0, int(h * 0.02), w, int(h * 0.05)], fill=18)
    sheen = sheen.filter(ImageFilter.GaussianBlur(6))
    img = Image.composite(Image.new("RGB", (w, h), (120, 110, 100)), img, sheen)
    return img


def window(img, x0, y0, x1, y1, grid=(8, 4)):
    """A recessed display window in the panel: dark glass inset with a moulded bezel lit from the top left
    (shadow on the top/left inner edge, highlight on the bottom/right), a faint grid and a soft glass sheen."""
    d = ImageDraw.Draw(img)
    d.rectangle([x0 - 6, y0 - 6, x1 + 6, y1 + 6], fill=(30, 26, 24))                  # bezel
    d.line([x0 - 6, y1 + 6, x1 + 6, y1 + 6], fill=(78, 70, 64), width=2)              # lit lower lip
    d.line([x1 + 6, y0 - 6, x1 + 6, y1 + 6], fill=(66, 59, 54), width=2)
    d.line([x0 - 6, y0 - 6, x1 + 6, y0 - 6], fill=(12, 10, 9), width=2)               # shadowed upper edge
    d.line([x0 - 6, y0 - 6, x0 - 6, y1 + 6], fill=(14, 12, 11), width=2)
    for y in range(y0, y1 + 1):                                                      # glass: slightly lighter at the top
        t = (y - y0) / max(1, y1 - y0)
        d.line([x0, y, x1, y], fill=lerp((26, 23, 21), (15, 13, 12), t))
    gx, gy = grid
    for i in range(1, gx):
        xx = x0 + i * (x1 - x0) / gx
        d.line([xx, y0 + 2, xx, y1 - 2], fill=(36, 32, 29))
    for i in range(1, gy):
        yy = y0 + i * (y1 - y0) / gy
        d.line([x0 + 2, yy, x1 - 2, yy], fill=(36, 32, 29))
    sh = Image.new("L", img.size, 0)                                                 # inner shadow under the top edge
    ImageDraw.Draw(sh).rectangle([x0, y0, x1, y0 + 8], fill=110)
    sh = sh.filter(ImageFilter.GaussianBlur(5))
    clip = Image.new("L", img.size, 0)
    ImageDraw.Draw(clip).rectangle([x0, y0, x1, y1], fill=255)
    img.paste((0, 0, 0), (0, 0), ImageChops.multiply(sh, clip))
    gl = Image.new("L", img.size, 0)                                                 # glass sheen
    ImageDraw.Draw(gl).polygon([(x0 + 40, y0), (x0 + 140, y0), (x0 + 60, y1), (x0 - 40 if x0 > 40 else x0, y1)], fill=5)
    img.paste((255, 255, 255), (0, 0), ImageChops.multiply(gl, clip))


def legend(d, x, y, text, size=15, col=TAN, wght=500, anchor="la"):
    d.text((x, y), text, font=font(size, wght), fill=col, anchor=anchor)


def group_header(d, x0, x1, y, text, col=LILAC):
    """Lilac group title with the thin rule that runs under the whole group (panel print style)."""
    f = font(15, 600)
    d.text((x0, y), text, font=f, fill=col, anchor="ls")
    d.line([x0, y + 4, x1, y + 4], fill=col, width=1)


# ---- membrane switch ---------------------------------------------------------------------------
def membrane(w, h, lit=False, colour=TEAL, number=None, letter=None, caption=None):
    """A DX7 membrane switch: flat coloured pad, top-edge highlight, soft shadow; lit = brighter + halo."""
    pad = 6
    W, H = (w + pad * 2) * SS, (h + pad * 2) * SS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rectangle([pad * SS + SS, pad * SS + 2 * SS, (pad + w) * SS + SS, (pad + h) * SS + 2 * SS], fill=170)
    sh = sh.filter(ImageFilter.GaussianBlur(2.2 * SS))
    img.paste((0, 0, 0, 255), (0, 0), sh)
    base = TEAL_LIT if (lit and colour == TEAL) else colour
    if not lit and colour == TEAL:
        base = (22, 120, 112)
    if lit:
        glow = Image.new("L", (W, H), 0)
        ImageDraw.Draw(glow).rectangle([pad * SS, pad * SS, (pad + w) * SS, (pad + h) * SS], fill=140)
        glow = glow.filter(ImageFilter.GaussianBlur(4 * SS))
        img.paste(base + (255,), (0, 0), glow)
    face = Image.new("RGBA", (w * SS, h * SS))
    fd = ImageDraw.Draw(face)
    for yy in range(h * SS):
        t = yy / (h * SS)
        c = lerp(tuple(min(255, v + 16) for v in base), tuple(int(v * 0.86) for v in base), t)
        fd.line([0, yy, w * SS, yy], fill=c + (255,))
    fd.line([0, 0, w * SS, 0], fill=tuple(min(255, v + 60) for v in base) + (255,), width=SS)
    fd.rectangle([0, 0, w * SS - 1, h * SS - 1], outline=tuple(int(v * 0.6) for v in base) + (255,), width=SS)
    if lit:   # bright lit edge, like light bleeding through the membrane
        fd.rectangle([SS, SS, w * SS - SS, 3 * SS], fill=(220, 255, 248, 255))
    ink = (34, 46, 44, 255) if colour == TEAL else (50, 40, 40, 255)
    if colour == TEAL and not lit:
        ink = (14, 40, 38, 255)
    if number is not None:
        fd.text((5 * SS, h * SS - 4 * SS), str(number), font=font(min(22, h * 0.62) * SS, 700), fill=ink, anchor="ls")
    if letter:
        fd.text((w * SS - 4 * SS, 3 * SS), letter, font=font(9 * SS, 500), fill=ink, anchor="ra")
    if caption:
        fd.text((w * SS // 2, h * SS // 2), caption, font=font(min(15, h * 0.5) * SS, 700), fill=ink, anchor="mm")
    img.alpha_composite(face, (pad * SS, pad * SS))
    return img.resize((w + pad * 2, h + pad * 2), Image.LANCZOS)


# ---- sliders (DX7 VOLUME / DATA ENTRY style cap) ------------------------------------------------
def slider_cap(w, h, horizontal=False, accent=None):
    """Black ribbed cap with a white index line, lit from the top-left, with a cast shadow."""
    pad = 8
    W, H = (w + pad * 2) * SS, (h + pad * 2) * SS
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rounded_rectangle([(pad + 2) * SS, (pad + 4) * SS, (pad + w + 2) * SS, (pad + h + 4) * SS], 3 * SS, fill=200)
    img.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(3 * SS)))
    cap = Image.new("RGBA", (w * SS, h * SS))
    cd = ImageDraw.Draw(cap)
    n = h * SS if not horizontal else w * SS
    for i in range(n):
        t = i / n
        c = lerp((120, 118, 114), (26, 26, 26), t) if accent else lerp((70, 68, 66), (12, 12, 12), t)
        if horizontal:
            cd.line([i, 0, i, h * SS], fill=c + (255,))
        else:
            cd.line([0, i, w * SS, i], fill=c + (255,))
    # ribs across the grip
    step = 4 * SS
    if horizontal:
        for x in range(step, w * SS - step, step):
            cd.line([x, 3 * SS, x, h * SS - 3 * SS], fill=(0, 0, 0, 160), width=SS)
            cd.line([x + SS, 3 * SS, x + SS, h * SS - 3 * SS], fill=(110, 108, 104, 90), width=SS)
        cd.line([w * SS // 2, 0, w * SS // 2, h * SS], fill=((255, 255, 255, 255) if accent else (240, 240, 236, 255)), width=3 * SS if accent else 2 * SS)
    else:
        for y in range(step, h * SS - step, step):
            cd.line([3 * SS, y, w * SS - 3 * SS, y], fill=(0, 0, 0, 160), width=SS)
            cd.line([3 * SS, y + SS, w * SS - 3 * SS, y + SS], fill=(110, 108, 104, 90), width=SS)
        cd.line([0, h * SS // 2, w * SS, h * SS // 2], fill=(240, 240, 236, 255), width=2 * SS)
    cd.rounded_rectangle([0, 0, w * SS - 1, h * SS - 1], 3 * SS, outline=(0, 0, 0, 255), width=SS)
    cd.line([2 * SS, SS, w * SS - 3 * SS, SS], fill=(150, 146, 140, 255), width=SS)   # top bevel
    mask = Image.new("L", cap.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w * SS - 1, h * SS - 1], 3 * SS, fill=255)
    img.paste(cap, (pad * SS, pad * SS), mask)
    return img.resize((w + pad * 2, h + pad * 2), Image.LANCZOS), pad


def slot(d, x0, y0, x1, y1):
    """Recessed slider slot: dark well with a light lower lip."""
    d.rectangle([x0, y0, x1, y1], fill=(6, 6, 6))
    d.line([x0, y1 + 1, x1, y1 + 1], fill=(70, 62, 56))
    d.line([x1 + 1, y0, x1 + 1, y1], fill=(60, 54, 48))


def fader_frame(length, thick, value, horizontal, ticks=True, fill=None, bipolar=False):
    """One frame of a fader film strip, transparent background (the panel shows through).
    fill: RGB of the lit part of the slot (from the left edge, or from the centre when bipolar), or None for a plain slot."""
    if horizontal:
        W, H = length, thick
    else:
        W, H = thick, length
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    capL, capS = (16, 22) if horizontal else (20, 26)
    if horizontal:
        cy = H // 2
        x0, x1 = capL // 2 + 2, W - capL // 2 - 2
        d.rounded_rectangle([x0 - 1, cy - 5, x1 + 1, cy + 4], 3, fill=(4, 4, 4), outline=(70, 62, 56))
        cap, pad = slider_cap(capL, capS, horizontal=True, accent=fill)
        cx = x0 + value * (x1 - x0)
        if fill is not None:
            c0 = (x0 + x1) / 2 if bipolar else x0
            a_, b_ = sorted((c0, cx))
            if b_ - a_ >= 1:
                glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ImageDraw.Draw(glow).rectangle([a_, cy - 5, b_, cy + 5], fill=fill + (110,))
                img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(3)))
                d.rectangle([a_, cy - 3, b_, cy + 2], fill=fill + (255,))
                d.line([a_, cy - 3, b_, cy - 3], fill=tuple(min(255, c + 70) for c in fill) + (255,))
            if bipolar:
                d.line([(x0 + x1) // 2, cy - 7, (x0 + x1) // 2, cy + 6], fill=(230, 220, 200, 255))
        img.paste(cap, (int(cx) - capL // 2 - pad, (H - capS) // 2 - pad), cap)
    else:
        cx = W // 2
        slot(d, cx - 2, capL // 2 + 2, cx + 2, H - capL // 2 - 2)
        cap, pad = slider_cap(W - 10, capL, accent=fill)
        y = int((1 - value) * (H - capL - 4)) + 2
        if fill is not None:   # lit from the bottom of the slot up to the cap
            top, bot = y + capL // 2, H - capL // 2 - 2
            if bot - top >= 1:
                glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ImageDraw.Draw(glow).rectangle([cx - 5, top, cx + 5, bot], fill=fill + (110,))
                img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(3)))
                d.rectangle([cx - 2, top, cx + 2, bot], fill=fill + (255,))
                d.line([cx - 2, top, cx - 2, bot], fill=tuple(min(255, c + 70) for c in fill) + (255,))
        img.paste(cap, (5 - pad, y - pad), cap)
    return img


def film_strip(frames):
    w, h = frames[0].size
    strip = Image.new("RGBA", (w, h * len(frames)), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        strip.paste(f, (0, i * h))
    return strip


def scale_ticks(d, horizontal, x0, y0, length, n=11, col=TAN):
    col = tuple(int(c * 0.62) for c in col)   # quiet: the fill carries the reading
    for i in range(n):
        t = i / (n - 1)
        L = 6 if i % 5 == 0 else 3
        if horizontal:
            x = x0 + t * length
            d.line([x, y0, x, y0 + L], fill=col)
        else:
            y = y0 + (1 - t) * length
            d.line([x0, y, x0 + L, y], fill=col)


# ---- LED 7-segment ------------------------------------------------------------------------------
SEG = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc",
       "7": "abc", "8": "abcdefg", "9": "abcdfg", " ": ""}


def seven_seg(d, x, y, s, ch, on, off):
    """Draw one italic 7-segment digit of height s at (x, y)."""
    w, t, k = s * 0.5, s * 0.11, 0.12   # width, thickness, italic shear
    def P(px, py):
        return (x + px + (s - py) * k, y + py)
    segs = {"a": [(t, 0), (w - t, 0)], "g": [(t, s / 2), (w - t, s / 2)], "d": [(t, s), (w - t, s)],
            "f": [(0, t), (0, s / 2 - t)], "b": [(w, t), (w, s / 2 - t)],
            "e": [(0, s / 2 + t), (0, s - t)], "c": [(w, s / 2 + t), (w, s - t)]}
    lit = SEG.get(ch, "")
    for name, (p0, p1) in segs.items():
        d.line([P(*p0), P(*p1)], fill=on if name in lit else off, width=int(t))


def led_window(value_text, w=96, h=64):
    img = Image.new("RGBA", (w * SS, h * SS), (12, 6, 8, 255))
    d = ImageDraw.Draw(img)
    s = h * SS * 0.62
    x0 = w * SS * 0.16
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    txt = value_text.rjust(2)
    for i, ch in enumerate(txt):
        xx = x0 + i * s * 0.72
        seven_seg(d, xx, h * SS * 0.18, s, "8", (36, 10, 13, 255), (28, 9, 12, 255))   # ghost segments
        seven_seg(gd, xx, h * SS * 0.18, s, ch, RED_LED + (255,), (0, 0, 0, 0))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(3 * SS)))
    img.alpha_composite(glow)
    d.rectangle([0, 0, w * SS - 1, h * SS - 1], outline=(0, 0, 0, 255), width=2 * SS)
    # smoked-glass glare
    gl = Image.new("L", img.size, 0)
    ImageDraw.Draw(gl).polygon([(0, 0), (w * SS * 0.55, 0), (w * SS * 0.25, h * SS), (0, h * SS)], fill=18)
    img.paste((255, 255, 255, 255), (0, 0), gl)
    return img.resize((w, h), Image.LANCZOS)


# ---- LCD ----------------------------------------------------------------------------------------
def lcd(w=440, h=64, lines=None, per_cell=False, rows=2, cols=16, divider=None, arrows=()):
    """16x2 STN LCD in its black bezel. The cell grid is art; live text goes on top as a Label
    (Roboto) on the device. `lines` is only for previews."""
    img = Image.new("RGBA", (w, h), (8, 8, 8, 255))
    d = ImageDraw.Draw(img)
    gx0, gy0, gx1, gy1 = 12, 9, w - 12, h - 9
    d.rectangle([gx0, gy0, gx1, gy1], fill=LCD_BG)
    cw = (gx1 - gx0 - 8) / cols
    chh = (gy1 - gy0 - 6) / rows
    for r in range(rows):
        for c in range(cols):
            x = gx0 + 4 + c * cw
            y = gy0 + 3 + r * chh
            d.rectangle([x + 1, y + 1, x + cw - 2, y + chh - 2], fill=(170, 184, 162))
    if lines and not per_cell:
        f = font(chh * 0.95, 500)
        for r, t in enumerate(lines[:2]):
            d.text((gx0 + 8, gy0 + 3 + r * chh + chh / 2), t.upper(), font=f, fill=LCD_INK, anchor="lm")
    elif lines:
        f = font(chh * 0.92, 500)
        for r, t in enumerate(lines[:2]):
            for c, ch in enumerate(t.upper()[:16]):
                x = gx0 + 4 + c * cw + cw / 2
                y = gy0 + 3 + r * chh + chh / 2
                d.text((x, y), ch, font=f, fill=LCD_INK, anchor="mm")
    for cx, direction in arrows:   # printed step arrows (the touch zones sit on top of them)
        cy, hw, hh = h // 2, 6, 10
        pts = [(cx + hw, cy - hh), (cx + hw, cy + hh), (cx - hw, cy)] if direction < 0 else \
              [(cx - hw, cy - hh), (cx - hw, cy + hh), (cx + hw, cy)]
        d.polygon(pts, fill=(74, 88, 68))
    if divider is not None:   # a printed rule between two side-by-side fields
        d.line([divider, gy0 + 4, divider, gy1 - 4], fill=(120, 132, 114), width=2)
    # inner shadow + glass glare
    sh = Image.new("L", (w, h), 0)
    ImageDraw.Draw(sh).rectangle([gx0, gy0, gx1, gy0 + 5], fill=90)
    img.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(3)))
    gl = Image.new("L", (w, h), 0)
    ImageDraw.Draw(gl).polygon([(gx0 + 40, gy0), (gx0 + 90, gy0), (gx0 + 60, gy1), (gx0 + 10, gy1)], fill=26)
    img.paste((255, 255, 255, 255), (0, 0), gl)
    return img


# ---- striped wordmark ---------------------------------------------------------------------------
def glyph_polys(ch, x, h, sw):
    """Geometric block letters in the DX7 badge spirit (our own drawing). Returns (polys, advance)."""
    w = h * 0.86
    if ch == "D":
        r = h * 0.32
        outer = [(x, 0), (x + w - r, 0)] + [(x + w - r + r * math.sin(a), r - r * math.cos(a)) for a in [i * math.pi / 2 / 8 for i in range(9)]] \
            + [(x + w, h - r)] + [(x + w - r + r * math.cos(a), h - r + r * math.sin(a)) for a in [i * math.pi / 2 / 8 for i in range(9)]] + [(x, h)]
        return [("fill", outer), ("hole", [(x + sw, sw), (x + w - r, sw), (x + w - sw, r), (x + w - sw, h - r), (x + w - r, h - sw), (x + sw, h - sw)])], w
    if ch == "E":
        w = h * 0.74
        return [("fill", [(x, 0), (x + w, 0), (x + w, sw), (x + sw, sw), (x + sw, h / 2 - sw / 2), (x + w * 0.85, h / 2 - sw / 2),
                          (x + w * 0.85, h / 2 + sw / 2), (x + sw, h / 2 + sw / 2), (x + sw, h - sw), (x + w, h - sw), (x + w, h), (x, h)])], w
    if ch == "X":
        w = h * 0.92
        a = sw * 0.75
        return [("fill", [(x, 0), (x + a * 1.4, 0), (x + w, h), (x + w - a * 1.4, h)]),
                ("fill", [(x + w - a * 1.4, 0), (x + w, 0), (x + a * 1.4, h), (x, h)])], w
    if ch == "7":
        w = h * 0.72
        return [("fill", [(x, 0), (x + w, 0), (x + w, sw), (x + sw * 1.6, h), (x + sw * 0.1, h), (x + w - sw * 1.2, sw), (x, sw)])], w
    return [], h * 0.5


def wordmark(text, h, stripe=2, gap=2, thick=5, col=(214, 214, 210), italic=0.22, outline=True, tracking=0.12):
    """Outlined, horizontally striped, italic extended lettering (the DX7 nameplate treatment)."""
    S = SS
    H = h * S
    sw = H * 0.26
    x = 0
    polys = []
    for ch in text:
        ps, adv = glyph_polys(ch, x, H, sw)
        polys += ps
        x += adv + H * tracking
    W = int(x + H * italic + 4 * S)
    mask = Image.new("L", (W, H + 2 * S), 0)
    md = ImageDraw.Draw(mask)
    shear = lambda p: (p[0] + (H - p[1]) * italic + 2 * S, p[1] + S)
    for kind, p in polys:
        md.polygon([shear(q) for q in p], fill=255 if kind == "fill" else 0)
    stripes = Image.new("L", mask.size, 0)
    sd = ImageDraw.Draw(stripes)
    # DX7 nameplate: fine lines at the top and bottom, a band of thick bars through the middle
    y, Hm = 0, mask.size[1]
    while y < Hm:
        mid = 0.36 <= y / Hm <= 0.66
        on, off = (thick * S, gap * S) if mid else (stripe * S, (gap + 1) * S)
        sd.rectangle([0, y, mask.size[0], y + on - 1], fill=255)
        y += on + off
    fillm = ImageChops.multiply(mask, stripes)
    edge = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(3)), mask.filter(ImageFilter.MinFilter(3))) if outline else Image.new("L", mask.size, 0)
    m = ImageChops.lighter(fillm, edge)
    img = Image.new("RGBA", mask.size, col + (0,))
    img.putalpha(m)
    return img.resize((max(1, W // S), (H + 2 * S) // S), Image.LANCZOS)


# ---- algorithm art (from our own images/algo_NN.svg, restyled as panel print) -------------------
def algo_image(n, w, h, line=CREAM, box_fill=(40, 34, 30), num_col=CREAM, hl_op=None, hl_col=TEAL):
    src = open(os.path.join(ROOT, "images", "algo_%02d.svg" % n)).read()
    m = re.search(r'translate\(([-\d.]+) ([-\d.]+)\) scale\(([-\d.]+)\)', src)
    tx, ty, sc = map(float, m.groups())
    k = min(w / 900, h / 470) * SS
    ox = (w * SS - 900 * k) / 2
    oy = (h * SS - 470 * k) / 2
    T = lambda X, Y: (ox + (tx + X * sc) * k, oy + (ty + Y * sc) * k)
    img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    lw = max(1, int(1.1 * sc * k * 0.9))
    for x1, y1, x2, y2 in re.findall(r'<line x1="([-\d.]+)" y1="([-\d.]+)" x2="([-\d.]+)" y2="([-\d.]+)"', src):
        d.line([T(float(x1), float(y1)), T(float(x2), float(y2))], fill=line, width=lw)
    rects = re.findall(r'<rect x="([-\d.]+)" y="([-\d.]+)" width="([-\d.]+)" height="([-\d.]+)"', src)
    texts = re.findall(r'<text x="([-\d.]+)" y="([-\d.]+)"[^>]*>(\d)</text>', src)
    for (x, y, rw, rh), (_, _, num) in zip(rects, texts):
        x, y, rw, rh = map(float, (x, y, rw, rh))
        p0, p1 = T(x, y), T(x + rw, y + rh)
        hl = hl_op is not None and int(num) == hl_op
        d.rectangle([p0, p1], fill=hl_col if hl else box_fill, outline=hl_col if hl else line, width=lw)
        d.text(((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2), num, font=font((p1[1] - p0[1]) * 0.78, 700),
               fill=(20, 24, 22) if hl else num_col, anchor="mm")
    return img.resize((w, h), Image.LANCZOS)


# ---- page composition (mockups; the device composes the same parts from TUI.json) ---------------
CONTENT_Y = 110   # tab content starts 110 px down the 1280x800 screen


def header(bg, d, bank="ROM1A", patch="BRASS   1", num="1", right=None):
    """Header strip (tab y 0..76), on VOICE and CARTS only: DEXED wordmark, LED, LCD.
    `right(bg, d)` fills the space right of the LCD (favourites on CARTS)."""
    wm = wordmark("DEXED", 40)
    bg.paste(wm, (20, 10), wm)
    legend(d, 22, 70, "DIGITAL PROGRAMMABLE ALGORITHM SYNTHESIZER", 10, TAN, 500)
    led = led_window(num, 84, 56)
    bg.paste(led, (330, 8), led)
    l = lcd(420, 56, [bank, patch])
    bg.paste(l, (426, 8), l)
    if right:
        right(bg, d)
    d.line([16, 80, 1262, 80], fill=(14, 12, 11), width=2)
    d.line([16, 82, 1262, 82], fill=(62, 55, 50), width=1)


def op_strip(bg, d, op, algo, on=True):
    """OP tabs: operator title, its own ON switch, and the current algorithm with this op lit."""
    legend(d, 24, 40, "OPERATOR", 15, LILAC, 600, anchor="ls")
    d.text((24, 46), str(op), font=font(40, 700), fill=CREAM, anchor="lt") if False else None
    big = font(46, 700)
    d.text((112, 44), str(op), font=big, fill=CREAM, anchor="ls")
    m = membrane(76, 40, lit=on, caption="ON" if on else "OFF")
    bg.paste(m, (160 - 6, 10 - 6), m)
    th = algo_image(algo, 200, 70, hl_op=op)
    bg.paste(th, (790, 4), th)
    legend(d, 1006, 74, "ALGORITHM %d" % algo, 11, LILAC, 600, anchor="rs")
    d.line([16, 80, 1010, 80], fill=(14, 12, 11), width=2)
    d.line([16, 82, 1010, 82], fill=(62, 55, 50), width=1)


def mini_slider(bg, d, x, y, w, name, value, vtext):
    """A labelled mini horizontal slider (art = film strip; name baked; value = live Label)."""
    legend(d, x, y, name, 14, TAN, 600)
    d.text((x + w, y), vtext, font=font(18, 500), fill=(236, 232, 222), anchor="ra")
    scale_ticks(d, True, x + 9, y + 50, w - 18)
    f = fader_frame(w, 30, value, True)
    bg.paste(f, (x, y + 20), f)


def v_fader(bg, d, x, y, h, name, value, vtext):
    legend(d, x + 18, y, name, 14, TAN, 600, anchor="ma")
    f = fader_frame(h, 36, value, False)
    bg.paste(f, (x, y + 22), f)
    scale_ticks(d, False, x + 38, y + 22 + 12, h - 24)
    d.text((x + 18, y + h + 30), vtext, font=font(18, 500), fill=(236, 232, 222), anchor="ma")


def seg_buttons(bg, x, y, w, h, labels, active):
    bw = (w - (len(labels) - 1) * 4) // len(labels)
    for i, lb in enumerate(labels):
        m = membrane(bw, h, lit=(i == active), caption=lb)
        bg.paste(m, (x + i * (bw + 4) - 6, y - 6), m)


def eg_curve(bg, d, x0, y0, x1, y1, rates, levels, title="EG", centre=False):
    """Preview of the live Envelope widget (envelopeType "Pitch", see PLAN §6): L4 -> R1 -> L1 -> R2 -> L2 -> R3 -> L3 (sustain)
    -> R4 -> L4. Stage width follows 1 - rate (the skin binds rates through Invert/), plus a fixed sustain segment."""
    group_header(d, x0, x1, y0 + 14, title)
    gy0, gy1 = y0 + 26, y1
    d.rectangle([x0, gy0, x1, gy1], fill=(16, 14, 13))
    for i in range(1, 4):
        yy = gy0 + i * (gy1 - gy0) / 4
        d.line([x0, yy, x1, yy], fill=(48, 42, 38))
    fillbase = (gy0 + gy1) / 2 if centre else gy1
    if centre:   # pitch EG: level 50 = no pitch shift
        yc = (gy0 + gy1) / 2
        for xx in range(int(x0), int(x1), 10):
            d.line([xx, yc, xx + 5, yc], fill=LILAC)
        d.text((x0 + 4, yc - 4), "0", font=font(12, 600), fill=LILAC, anchor="ls")
    wts = [0.08 + (1 - r / 99) for r in rates]
    sus = 0.5
    tot = sum(wts) + sus
    W = x1 - x0 - 12
    Y = lambda L: gy1 - 6 - (L / 99) * (gy1 - gy0 - 12)
    pts = [(x0 + 6, Y(levels[3]))]
    x = x0 + 6
    for i, L in enumerate([levels[0], levels[1], levels[2]]):
        x += W * wts[i] / tot
        pts.append((x, Y(L)))
    x += W * sus / tot
    pts.append((x, Y(levels[2])))
    pts.append((x0 + 6 + W, Y(levels[3])))
    fill = Image.new("RGBA", bg.size, (0, 0, 0, 0))
    ImageDraw.Draw(fill).polygon(pts + [(pts[-1][0], fillbase), (pts[0][0], fillbase)], fill=TEAL + (60,))
    bg.paste(Image.alpha_composite(bg.convert("RGBA"), fill).convert("RGB"))
    d.line(pts, fill=CREAM, width=3)
    for i, p in enumerate(pts[:-1]):
        if i == 4:
            continue
        d.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6], fill=(20, 18, 16), outline=TEAL_LIT, width=2)
    for i, lb in enumerate(["L4", "L1", "L2", "L3", "", "L4"]):
        if lb:
            d.text((min(pts[i][0] + 8, x1 - 4), pts[i][1] - 10), lb, font=font(12, 600), fill=TAN, anchor="rs" if pts[i][0] + 24 > x1 else "ls")


def mock_op_tab(op=1, qlink_group=0, algo=5, stacked=False):
    """OP tab, no header: three full-width slider rows, the EG faders below, and a right-hand column
    (beyond the Q-Link area) with the operator number, its ON switch and the algorithm thumbnail."""
    W, H = 1280, 628
    bg = panel(W, H)
    d = ImageDraw.Draw(bg)
    groups = []
    X0, X1 = 16, 1010
    sw = 232                      # mini slider width, 4 across
    def row(y, title, items, qlink=True, x1=None, w=None):
        x1 = x1 or X1
        w = w or sw
        group_header(d, X0 + 8, x1 - 8, y + 18, title)
        for i, it in enumerate(items):
            x = X0 + 14 + i * (w + 16)
            if it[0] == "seg":
                _, name, labels, act = it
                legend(d, x, y + 30, name, 14, TAN, 600)
                seg_buttons(bg, x, y + 54, sw, 30, labels, act)
            elif it[0] == "curves":
                legend(d, x, y + 30, "L CURVE", 13, TAN, 600)
                seg_buttons(bg, x + 64, y + 26, sw - 64, 24, ["-LIN", "-EXP", "+EXP", "+LIN"], 0)
                legend(d, x, y + 64, "R CURVE", 13, TAN, 600)
                seg_buttons(bg, x + 64, y + 60, sw - 64, 24, ["-LIN", "-EXP", "+EXP", "+LIN"], 3)
            else:
                mini_slider(bg, d, x, y + 30, w, *it)
        if qlink:
            groups.append((X0, y + 2, x1, y + 94))
    row(0, "OSCILLATOR", [("OUTPUT LEVEL", 0.99, "99"), ("FREQ COARSE", 1 / 31, "1"), ("FREQ FINE", 0.0, "0"), ("DETUNE", 0.5, "+0")])
    row(100, "SENSITIVITY", [("KEY VELOCITY", 2 / 7, "2"), ("AMP MOD", 0.0, "0"), ("RATE SCALING", 3 / 7, "3"),
                             ("seg", "OSC MODE", ["RATIO", "FIXED"], 0)])
    row(200, "KEYBOARD LEVEL SCALING", [("BREAK POINT", 39 / 99, "A-1"), ("L DEPTH", 0.0, "0"), ("R DEPTH", 0.2, "20"), ("curves",)],
        qlink=False)
    if stacked:
        # variant: EG RATE and EG LEVEL as two stacked rows of mini sliders (Q-Link groups 3, 4); big envelope beside them
        ew = 140
        row(330, "EG RATE", [("RATE 1", 95 / 99, "95"), ("RATE 2", 29 / 99, "29"), ("RATE 3", 20 / 99, "20"), ("RATE 4", 50 / 99, "50")],
            x1=640, w=ew)
        row(470, "EG LEVEL", [("LEVEL 1", 1.0, "99"), ("LEVEL 2", 95 / 99, "95"), ("LEVEL 3", 0.0, "0"), ("LEVEL 4", 0.0, "0")],
            x1=640, w=ew)
        legend(d, X0 + 8, 604, "Drag the envelope's points to edit it.", 13, TAN, 400)
    else:
        # EG: RATE 1-4 and LEVEL 1-4 (Q-Link groups 3 and 4), faders filling the rest of the height
        for gi, (lab, vals) in enumerate([("EG RATE", [(0.96, "95"), (0.3, "29"), (0.2, "20"), (0.5, "50")]),
                                          ("EG LEVEL", [(1.0, "99"), (0.96, "95"), (0.0, "0"), (0.0, "0")])]):
            gx0 = X0 + gi * 448
            gx1 = gx0 + 436
            gy0 = 302
            group_header(d, gx0 + 8, gx1 - 8, gy0 + 16, lab)
            for i, (v, t) in enumerate(vals):
                v_fader(bg, d, gx0 + 40 + i * 104, gy0 + 26, 236, str(i + 1), v, t)
            groups.append((gx0, gy0, gx1, 624))
    # right column: operator identity, its ON switch, the algorithm with this op lit
    rx = 1034
    legend(d, rx, 26, "OPERATOR", 16, LILAC, 600, anchor="ls")
    d.text((rx, 30), str(op), font=font(110, 700), fill=CREAM, anchor="lt")
    m = membrane(150, 64, lit=True, caption="ON")
    bg.paste(m, (rx + 76 - 6, 50 - 6), m)
    legend(d, rx + 76, 134, "OPERATOR ON-OFF", 12, TAN, 600)
    group_header(d, rx, 1262, 200, "ALGORITHM %d" % algo)
    th = algo_image(algo, 228, 112, hl_op=op)
    bg.paste(th, (rx, 210), th)
    if stacked:
        eg_curve(bg, d, 660, 302, 1268, 622, [95, 29, 20, 50], [99, 95, 0, 0], "ENVELOPE")
    else:
        eg_curve(bg, d, 912, 302, 1268, 622, [95, 29, 20, 50], [99, 95, 0, 0], "ENVELOPE")
    # Q-Link rectangle drawn by the MPC (mockup only): highlight the active group
    x0, y0, x1, y1 = groups[qlink_group]
    d.rectangle([x0, y0, x1, y1], outline=QLINK, width=2)
    return bg, groups


CARTS = ["ROM1A", "ROM1B", "ROM2A", "ROM2B", "ROM3A", "ROM3B", "ROM4A", "ROM4B", "ANALOG 1", "BASS 2", "BELLS",
         "BRASS 07", "CHOIR", "CLAVS", "E.PIANO 3", "FX MIX", "GUITAR", "KEYS 11", "LEADS", "ORGAN 4", "PADS", "STRINGS"]
PATCHES = ["BRASS   1", "BRASS   2", "BRASS   3", "STRINGS 1", "STRINGS 2", "STRINGS 3", "ORCHESTRA", "PIANO   1",
           "PIANO   2", "PIANO   3", "E.PIANO 1", "GUITAR  1", "GUITAR  2", "SYN-LEAD 1", "BASS    1", "BASS    2",
           "E.ORGAN 1", "PIPES   1", "HARPSICH 1", "CLAV    1", "VIBE    1", "MARIMBA", "KOTO", "FLUTE   1",
           "ORCH-CHIME", "TUB BELLS", "STEEL DRUM", "TIMPANI", "REFS WHISL", "VOICE   1", "TRAIN", "TAKE OFF"]


def fav_buttons(bg, d):
    """+FAV / -FAV stacked in the header, right of the LCD."""
    group_header(d, 880, 1238, 16, "FAVOURITES")
    for i, (cap, col) in enumerate([("+FAV", STORE_RED), ("-FAV", LILAC)]):
        m = membrane(110, 26, colour=col, caption=cap)
        bg.paste(m, (1040 + i * 0 - 6, 22 + i * 0 - 6) if False else (880 + i * 124 - 6, 28 - 6), m)
    legend(d, 880, 62, "saved favourites list in the MPC PRESET menu", 11, TAN, 400)


def mock_voice_tab(qlink_group=0):
    """VOICE: header, then VOICE and LFO slider rows (Q-Link groups 1, 2), an LFO extras row (screen only),
    and the pitch EG as two stacked slider rows (groups 3, 4) beside a large interactive pitch envelope."""
    W, H = 1280, 628
    bg = panel(W, H, seed=9)
    d = ImageDraw.Draw(bg)
    header(bg, d, bank="ROM1A", patch="E.PIANO 1", num="11")
    groups = []
    X0 = 16
    def row(y, title, items, x1, w, qlink=True):
        group_header(d, X0 + 8, x1 - 8, y + 18, title)
        for i, it in enumerate(items):
            x = X0 + 14 + i * (w + 16)
            if it[0] == "seg":
                _, name, labels, act, sw = it
                legend(d, x, y + 30, name, 14, TAN, 600)
                seg_buttons(bg, x, y + 54, sw, 30, labels, act)
            elif it[0] == "btn":
                _, name, cap, on = it
                legend(d, x, y + 30, name, 14, TAN, 600)
                m = membrane(96, 30, lit=on, caption=cap)
                bg.paste(m, (x - 6, y + 54 - 6), m)
            else:
                mini_slider(bg, d, x, y + 30, w, *it)
        if qlink:
            groups.append((X0, y + 2, x1, y + 94))
    row(86, "VOICE", [("OUTPUT LEVEL", 0.8, "80"), ("ALGORITHM", 4 / 31, "5"), ("FEEDBACK", 6 / 7, "6"), ("TRANSPOSE", 0.5, "C3")], 1010, 232)
    row(186, "LFO", [("SPEED", 34 / 99, "34"), ("DELAY", 33 / 99, "33"), ("PMD", 0.0, "0"), ("AMD", 0.0, "0")], 1010, 232)
    # header right, screen only: OSC KEY SYNC + OCTAVE
    group_header(d, 870, 1262, 16, "OSCILLATOR")
    legend(d, 870, 28, "KEY SYNC", 13, TAN, 600)
    m = membrane(80, 28, lit=True, caption="ON"); bg.paste(m, (870 - 6, 46 - 6), m)
    mini_slider(bg, d, 980, 24, 282, "OCTAVE", 0.5, "0")
    # right column beside the LFO rows, screen only: PMS + LFO SYNC
    rx = 1030
    group_header(d, rx, 1262, 104, "LFO")
    mini_slider(bg, d, rx, 116, 232, "PITCH MOD SENS", 3 / 7, "3")
    legend(d, rx, 216, "KEY SYNC", 14, TAN, 600)
    m = membrane(96, 30, lit=False, caption="OFF"); bg.paste(m, (rx + 136 - 6, 210 - 6), m)
    # LFO wave: a slim row of 6 membranes (screen only; the Q-Link groups are full)
    group_header(d, X0 + 8, 1262, 304, "LFO WAVE")
    seg_buttons(bg, X0 + 14, 316, 1240, 34, ["TRIANGLE", "SAW DOWN", "SAW UP", "SQUARE", "SINE", "SAMPLE & HOLD"], 4)
    # pitch EG: stacked rows (groups 3, 4) + interactive pitch envelope (centre line = no shift)
    row(370, "PITCH EG RATE", [("RATE 1", 94 / 99, "94"), ("RATE 2", 67 / 99, "67"), ("RATE 3", 95 / 99, "95"), ("RATE 4", 60 / 99, "60")], 640, 140)
    row(480, "PITCH EG LEVEL", [("LEVEL 1", 0.58, "58"), ("LEVEL 2", 0.5, "50"), ("LEVEL 3", 0.5, "50"), ("LEVEL 4", 0.45, "45")], 640, 140)
    eg_curve(bg, d, 660, 364, 1268, 622, [94, 67, 95, 60], [58, 50, 50, 45], "PITCH ENVELOPE", centre=True)
    x0, y0, x1, y1 = groups[qlink_group]
    d.rectangle([x0, y0, x1, y1], outline=QLINK, width=2)
    return bg


def mock_carts_tab(sel_cart=0, sel_patch=0):
    W, H = 1280, 628
    bg = panel(W, H, seed=11)
    d = ImageDraw.Draw(bg)
    header(bg, d, bank=CARTS[sel_cart], patch=PATCHES[sel_patch], num=str(sel_patch + 1), right=fav_buttons)
    # left: cart list, 2 columns x 11
    group_header(d, 24, 330, 108, "CARTRIDGE")
    for i, n in enumerate(CARTS):
        c, r = divmod(i, 11)
        x, y = 24 + c * 156, 120 + r * 40
        on = i == sel_cart
        d.rectangle([x, y, x + 148, y + 32], fill=(14, 12, 11) if not on else (30, 26, 22), outline=(70, 62, 56) if not on else TEAL)
        if on:
            d.rectangle([x + 1, y + 1, x + 5, y + 31], fill=TEAL_LIT)
        d.text((x + 14, y + 16), n, font=font(17, 500), fill=(236, 232, 222) if on else TAN, anchor="lm")
    legend(d, 24, 578, "1 / 205", 14, TAN, 600)
    for i, cap in enumerate(["<", ">", "RESCAN"]):
        m = membrane(62 if i < 2 else 108, 30, colour=(227, 163, 107) if i == 2 else LILAC, caption=cap)
        bg.paste(m, (84 + i * 72 - 6, 568 - 6), m)
    # right: the DX7's 1..32 membrane-switch grid, 4 rows x 8, bigger now the header holds favourites
    group_header(d, 352, 1262, 108, "MEMORY SELECT")
    for i, n in enumerate(PATCHES):
        r, c = divmod(i, 8)
        x, y = 352 + c * 114, 122 + r * 124
        m = membrane(104, 62, lit=(i == sel_patch), number=i + 1)
        bg.paste(m, (x - 6, y - 6), m)
        d.text((x + 52, y + 74), n.replace("   ", " ").replace("  ", " ").strip(), font=font(15, 500), fill=TAN, anchor="ma")
    return bg


def mock_algo_tab(algo=5, off=(3,)):
    W, H = 1280, 628
    bg = panel(W, H, seed=5)
    d = ImageDraw.Draw(bg)
    group_header(d, 24, 1010, 34, "ALGORITHM %d" % algo)
    big = algo_image(algo, 700, 430, hl_op=None)
    bg.paste(big, (24 + (740 - 700) // 2 - 60, 70), big)
    # ALGORITHM / FEEDBACK as vertical faders (Q-Link group with the 6 ops? see plan)
    for i, (n, v, t) in enumerate([("ALGORITHM", (algo - 1) / 31, str(algo)), ("FEEDBACK", 6 / 7, "6")]):
        v_fader(bg, d, 800 + i * 110, 50, 380, n, v, t)
    group_header(d, 24, 1010, 540, "OPERATOR ON-OFF")
    for i in range(6):
        on = (i + 1) not in off
        m = membrane(150, 52, lit=on, number=i + 1, caption=None)
        bg.paste(m, (24 + i * 166 - 6, 556 - 6), m)
        d.text((24 + i * 166 + 140, 556 + 26), "ON" if on else "OFF", font=font(15, 700), fill=(14, 40, 38), anchor="rm")
    return bg


def mpc_chrome(tab, active):
    """Grey stand-in for the MPC's own top bar and tab keys, so previews show the real proportions."""
    scr = Image.new("RGB", (1280, 800), (30, 30, 32))
    d = ImageDraw.Draw(scr)
    d.rectangle([0, 0, 1280, 109], fill=(22, 22, 24))
    d.text((24, 55), "Track 1  ·  Dexed (DX7)", font=font(26, 500), fill=(200, 200, 200), anchor="lm")
    scr.paste(tab, (0, CONTENT_Y))
    names = ["VOICE", "CARTS", "ALGO", "OP1", "OP2", "OP3", "OP4", "OP5", "OP6"]
    kw = 1280 / len(names)
    for i, n in enumerate(names):
        x = i * kw
        d.rectangle([x + 2, 740, x + kw - 2, 798], fill=(60, 60, 64) if n == active else (40, 40, 44))
        d.text((x + kw / 2, 769), n, font=font(22, 600), fill=(240, 240, 240) if n == active else (160, 160, 160), anchor="mm")
    return scr


def asset_sheet():
    sheet = panel(1280, 520, seed=3)
    d = ImageDraw.Draw(sheet)
    x = 20
    wm2 = wordmark("DEXED", 80); sheet.paste(wm2, (20, 24), wm2)
    led = led_window("32", 120, 80); sheet.paste(led, (760, 20), led)
    l = lcd(340, 64, ["INTERNAL VOICE", "INT 5 SYNC.SPLIT"], per_cell=True); sheet.paste(l, (900, 28), l)
    for i in range(8):
        m = membrane(64, 34, lit=(i == 2), number=i + 1, letter="ABCDEFGH"[i]); sheet.paste(m, (20 + i * 76, 150), m)
    for i, c in enumerate([STORE_RED, LILAC, (227, 163, 107)]):
        m = membrane(64, 34, colour=c); sheet.paste(m, (640 + i * 76, 150), m)
    for i, v in enumerate([0, 0.33, 0.66, 1.0]):
        f = fader_frame(230, 36, v, False); sheet.paste(f, (40 + i * 60, 230), f)
        f = fader_frame(220, 30, v, True); sheet.paste(f, (300, 240 + i * 56), f)
    for i, n in enumerate([1, 5, 16, 32]):
        a = algo_image(n, 160, 84, hl_op=1); sheet.paste(a, (560 + (i % 2) * 180, 230 + (i // 2) * 100), a)
    big = algo_image(5, 320, 200, hl_op=3); sheet.paste(big, (930, 230), big)
    return sheet


def write_assets():
    """Production assets for TUI.json (exact native sizes)."""
    ensure(OUT)
    film_strip([fader_frame(230, 36, i / 126, False) for i in range(127)]).save(os.path.join(OUT, "fader_v.png"))
    film_strip([fader_frame(156, 30, i / 126, True) for i in range(127)]).save(os.path.join(OUT, "slider_h.png"))
    film_strip([led_window(str(i + 1), 84, 56) for i in range(32)]).save(os.path.join(OUT, "led_preset.png"))
    film_strip([algo_image(i + 1, 170, 62) for i in range(32)]).save(os.path.join(OUT, "algo_thumb.png"))
    film_strip([algo_image(i + 1, 640, 400) for i in range(32)]).save(os.path.join(OUT, "algo_big.png"))
    lcd(420, 56).save(os.path.join(OUT, "lcd.png"))
    for lit in (False, True):
        membrane(38, 30, lit=lit).save(os.path.join(OUT, "membrane_%s.png" % ("on" if lit else "off")))
    wordmark("DEXED", 40).save(os.path.join(OUT, "wordmark_dexed.png"))


if __name__ == "__main__":
    ensure(OUT, PREV)
    asset_sheet().save(os.path.join(PREV, "assets.png"))
    for g in range(4):
        tab, _ = mock_op_tab(op=1, qlink_group=g)
        mpc_chrome(tab, "OP1").save(os.path.join(PREV, "op1_qlink%d.png" % (g + 1)))
    for g in (0, 2):
        tab, _ = mock_op_tab(op=1, qlink_group=g, stacked=True)
        mpc_chrome(tab, "OP1").save(os.path.join(PREV, "op1_stacked_qlink%d.png" % (g + 1)))
    for g in (0, 1):
        mpc_chrome(mock_voice_tab(qlink_group=g), "VOICE").save(os.path.join(PREV, "voice_qlink%d.png" % (g + 1)))
    mpc_chrome(mock_algo_tab(), "ALGO").save(os.path.join(PREV, "algo.png"))
    mpc_chrome(mock_carts_tab(sel_cart=0, sel_patch=4), "CARTS").save(os.path.join(PREV, "carts.png"))
    if "--assets" in sys.argv:
        write_assets()
    print("wrote", PREV)
