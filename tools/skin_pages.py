#!/usr/bin/env python3
"""The Dexed 2.0 skin pages. Each page's coordinates are defined once, here. A Page draws its static art
(panel, legends, rules, tick scales) into a background PNG and records the live widgets (film-strip sliders,
value labels, membrane buttons, algorithm strip, envelope) for TUI.json at exactly the same positions.

Used by tools/make_tui.py. Layout follows docs/PLAN-2.0.md §5 (stacked OP layout) and the mockups in docs/skin-preview/.
"""
import os, re
from PIL import ImageDraw

import make_dx7_skin as art
from make_dx7_skin import TAN, LILAC, CREAM
import make_tui as tui

SKINS = tui.OUT
_made = set()


def asset(name, make):
    """Write a skin image once (by file name) and return the name."""
    if name not in _made:
        make().save(os.path.join(SKINS, name))
        _made.add(name)
    return name


FUNC = os.environ.get("DEXED_SLIDER") == "func"     # variant B: slider colour by function
TEAL, AMBER, LILAC_, CORAL = (34, 182, 166), (240, 168, 58), (146, 150, 226), (232, 104, 96)
BIPOLAR = ("detune", "octave_transpose", "transpose", "pitch_eg_l")


def slider_style(key):
    bip = any(b in key for b in BIPOLAR)
    if not FUNC:
        return TEAL, bip, "t"
    if key.endswith("level") or "_l1" in key or "_l2" in key or "_l3" in key or "_l4" in key:
        return AMBER, bip, "a"
    if any(s in key for s in ("_r1", "_r2", "_r3", "_r4", "speed", "delay")):
        return TEAL, bip, "t"
    if any(s in key for s in ("coarse", "fine", "detune", "transpose", "octave")):
        return LILAC_, bip, "l"
    return CORAL, bip, "c"


def slider_strip(w, h=30, style=(TEAL, False, "t")):
    fill, bip, tag = style
    return asset("slider_h_%d%s%s.png" % (w, tag, "b" if bip else ""),
                 lambda: art.film_strip([art.fader_frame(w, h, i / 126, True, fill=fill, bipolar=bip) for i in range(127)]))


def membrane_img(w, h, lit, caption=None, colour=None, number=None):
    key = "mem_%dx%d_%s_%s%s%s.png" % (w, h, "on" if lit else "off", "n%d_" % number if number else "",
                                     re.sub(r"[^A-Za-z0-9]", "_", (caption or "blank").replace("+", "p").replace("-", "m").replace("<", "prev").replace(">", "next").replace("&", "and")),
                                     "" if colour is None else "_%02x%02x%02x" % colour)
    kw = {"lit": lit, "caption": caption, "number": number}
    if colour is not None:
        kw["colour"] = colour
    return asset(key, lambda: art.membrane(w, h, **kw))


def vfader_strip(h):
    return asset("fader_v_%d.png" % h,
                 lambda: art.film_strip([art.fader_frame(h, 36, i / 126, False, fill=TEAL) for i in range(127)]))


class Page:
    def __init__(self, name, fn_index, seed=7, sub=0):
        self.name = name
        self.fn = fn_index
        self.sub = sub
        self.bg = art.panel(1280, 628, seed=seed)
        self.d = ImageDraw.Draw(self.bg)
        self.kids = []
        self.groups = []         # Q-Link rectangles, in Q-Link bank order
        self.qlink_rows = []     # parameter keys per group of four (top row first)
        self.choices = {}        # param key -> option names, for replacementStrings

    # ---- static art ----
    def header(self, x0, x1, y, text):
        art.group_header(self.d, x0, x1, y, text)

    def legend(self, x, y, text, size=14, col=TAN, wght=600, anchor="la"):
        art.legend(self.d, x, y, text, size, col, wght, anchor)

    # ---- widgets ----
    def slider(self, key, x, y, w, name):
        """Name (baked) + live value (Label) + horizontal film-strip slider (Knob dragged sideways) + tick scale (baked)."""
        st = slider_style(key)
        self.legend(x, y, name, 13, (160, 142, 110))
        art.scale_ticks(self.d, True, x + 9, y + 50, w - 18)
        self.kids.append(tui.label("Value", "%d %d %d 24" % (x + w - 110, y - 5, 110), remap=tui.P(key),
                                   just="right verticallyCentred", colour="fffff6e4", style="Medium", h=23.0))
        tag = "%s%s" % (st[2], "b" if st[1] else "")
        self.kids.append(tui.entry(key, "hslider%d%s" % (w, tag), {"version": 1, "handleName": "Data"},
                                   "%d %d %d 30" % (x, y + 20, w), remap=tui.P(key), focus="Yes"))
        tui.need_slider(w, tag, slider_strip(w, 30, st))

    def vfader(self, key, x, y, h, name):
        """Vertical DX7 slider: name above (baked), film strip, tick scale (baked), live value below."""
        self.legend(x + 18, y, name, anchor="ma")
        art.scale_ticks(self.d, False, x + 38, y + 22 + 12, h - 24)
        self.kids.append(tui.entry(key, "vfader%d" % h, {"version": 1, "handleName": "Data"},
                                   "%d %d 36 %d" % (x, y + 22, h), remap=tui.P(key), focus="Yes"))
        self.kids.append(tui.label("Value", "%d %d 100 26" % (x - 32, y + h + 28), remap=tui.P(key),
                                   just="horizontallyCentred verticallyCentred", colour="ffece8de", style="Regular", h=20.0))
        tui.need_vfader(h, vfader_strip(h))

    def segments(self, key, x, y, w, h, labels, gap=4):
        """A radio group of membrane switches, one per option; captions are baked into the images."""
        bw = (w - (len(labels) - 1) * gap) // len(labels)
        for i, lb in enumerate(labels):
            on, off = membrane_img(bw, h, True, lb), membrane_img(bw, h, False, lb)
            self.kids.append(tui.entry("%s %d" % (key, i), "Button",
                                       {"version": 2, "onImage": on, "offImage": off, "buttonId": i,
                                        "numButtonsInGroup": len(labels), "handleName": "Data", "gestureBehaviour": "Instant"},
                                       "%d %d %d %d" % (x + i * (bw + gap) - 6, y - 6, bw + 12, h + 12), remap=tui.P(key), focus="Yes"))
        self.choices[key] = labels

    def toggle(self, key, x, y, w, h, on_caption="ON", off_caption="OFF", colour=None):
        on, off = membrane_img(w, h, True, on_caption, colour), membrane_img(w, h, False, off_caption, colour)
        self.kids.append(tui.entry(key, "Button", {"version": 2, "onImage": on, "offImage": off, "buttonId": 1,
                                                   "numButtonsInGroup": 1, "handleName": "Data", "gestureBehaviour": "Instant"},
                                   "%d %d %d %d" % (x - 6, y - 6, w + 12, h + 12), remap=tui.P(key), focus="Yes"))

    def image_strip(self, key, image, frames, b):
        self.kids.append(tui.entry(key + " picture", "Image", {"version": 2, "imageType": "FilmStrip", "colour": "0", "image": image,
                                                               "numFrames": frames, "handleName": "Data"}, b, remap=tui.P(key)))

    def envelope(self, prefix, b, name):
        self.kids.append(tui.entry(name, "Envelope", tui.envelope_for(prefix), b, focus="Yes"))

    def qlink_group(self, rect, keys):
        self.groups.append("%d %d %d %d" % (rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]))
        self.qlink_rows.append(keys)

    def tab(self):
        bgname = "bg_%s.png" % self.name.lower()
        self.bg.save(os.path.join(SKINS, bgname))
        kids = [tui.entry("bg", "Image", {"version": 2, "imageType": "Regular", "colour": "0", "image": bgname}, "0 0 1280 628")] + self.kids
        return {"version": 1, "tabName": self.name, "fnKeyIndex": self.fn, "fnKeySubIndex": self.sub,
                "componentDefinition": tui.component(kids, background=tui.bg("ff1e1a18")),
                "qlinkBoundsData": self.groups}


# ---------------------------------------------------------------------------------------------------------------------
def voice_header(p, random=False):
    """DEXED wordmark (baked), red LED patch number (32-frame strip on `preset`), the LCD with live cart/patch names."""
    wm = art.wordmark("DEXED", 40)
    p.bg.paste(wm, (20, 10), wm)
    p.legend(22, 62, "DIGITAL PROGRAMMABLE ALGORITHM SYNTHESIZER", 10, TAN, 500)
    led = asset("led_preset.png", lambda: art.film_strip([art.led_window(str(i + 1), 84, 56) for i in range(32)]))
    led_x = 252 if random else 278   # VOICE has no RANDOM button: LED, LCD and the oscillator block spread out
    p.image_strip("preset", led, 32, "%d 8 84 56" % led_x)
    # one line, cart | patch side by side, big type, with step arrows (cart ◂ ▸ | patch ◂ ▸) printed on the glass
    LX, split = (346 if random else 384), 280
    arrows = ((17, -1), (263, 1), (split + 17, -1), (510 - 17, 1))
    lcd = art.lcd(510, 56, rows=1, cols=28, divider=split, arrows=arrows)
    p.bg.paste(lcd, (LX, 8), lcd)
    for key, x, w in (("bank_name", LX + 36, 212), ("patch_name", LX + split + 36, 162)):
        p.kids.append(tui.label("Value", "%d 12 %d 48" % (x, w), remap=tui.P(key), just="left verticallyCentred",
                                colour="ff1e241c", style="Medium", case="Upper Case", h=30.0))
    for key, x, w in (("syx_bank_index", LX + 36, 212), ("preset", LX + split + 36, 162)):   # data wheel / Q-Link / drag
        p.kids.append(tui.entry(key + " field", "lcdfield%d" % w, {"version": 1, "handleName": "Data"}, "%d 8 %d 56" % (x, w),
                                remap=tui.P(key), focus="Yes"))
        tui.need_field(w)
    from PIL import Image
    hit_off = asset("lcd_hit_off.png", lambda: Image.new("RGBA", (30, 56), (0, 0, 0, 0)))
    hit_on = asset("lcd_hit_on.png", lambda: Image.new("RGBA", (30, 56), (0, 0, 0, 70)))
    for key, cx in (("prev_syx_bank", 17), ("next_syx_bank", 263), ("preset_prev", split + 17), ("preset_next", 510 - 17)):
        p.kids.append(tui.entry(key, "Button", {"version": 2, "onImage": hit_on, "offImage": hit_off, "buttonId": 1, "numButtonsInGroup": 1,
                                                 "handleName": "Data", "gestureBehaviour": "Instant"},
                                "%d 8 30 56" % (LX + cx - 15), remap=tui.P(key)))
    if random:
        # RANDOM: a random cart and a random patch in it, on every press (function-key orange)
        orange = (227, 163, 107)
        on, off = membrane_img(100, 44, True, "RANDOM", orange), membrane_img(100, 44, False, "RANDOM", orange)
        p.kids.append(tui.entry("rand_prog", "Button", {"version": 2, "onImage": on, "offImage": off, "buttonId": 1, "numButtonsInGroup": 1,
                                                        "handleName": "Data", "gestureBehaviour": "Instant"},
                                "1156 12 112 56", remap=tui.P("rand_prog"), focus="Yes"))
    p.d.line([16, 80, 1262, 80], fill=(14, 12, 11), width=2)
    p.d.line([16, 82, 1262, 82], fill=(62, 55, 50), width=1)


def voice_page(fn):
    """VOICE: header (+ osc key sync, octave), VOICE and LFO rows (Q-Link groups 1, 2), LFO PMS + sync, the LFO wave
    membranes, PITCH EG RATE / LEVEL rows (groups 3, 4) beside the interactive pitch envelope."""
    p = Page("VOICE", fn, seed=9)
    voice_header(p)
    X0, SW = 16, 232

    def col(i, w=SW):
        return X0 + 14 + i * (w + 16)

    # header right: oscillator key sync + octave (screen only)
    p.header(936, 1262, 16, "OSCILLATOR")
    p.legend(936, 28, "KEY SYNC", 13)
    p.toggle("osc_sync", 936, 46, 80, 28)
    p.slider("octave_transpose", 1050, 24, 212, "OCTAVE")
    p.choices["osc_sync"] = ["OFF", "ON"]
    # VOICE (group 1)
    p.header(X0 + 8, 1002, 104, "VOICE")
    for i, (key, n) in enumerate([("output_level", "OUTPUT LEVEL"), ("algorithm", "ALGORITHM"), ("feedback", "FEEDBACK"),
                                  ("transpose", "TRANSPOSE")]):
        p.slider(key, col(i), 116, SW, n)
    p.qlink_group((X0, 88, 1010, 180), ["output_level", "algorithm", "feedback", "transpose"])
    # LFO (group 2)
    p.header(X0 + 8, 1002, 204, "LFO")
    for i, (key, n) in enumerate([("lfo_speed", "SPEED"), ("lfo_delay", "DELAY"), ("lfo_pmd", "PMD"), ("lfo_amd", "AMD")]):
        p.slider(key, col(i), 216, SW, n)
    p.qlink_group((X0, 188, 1010, 280), ["lfo_speed", "lfo_delay", "lfo_pmd", "lfo_amd"])
    # right column (screen only): PMS + LFO key sync
    rx = 1030
    p.header(rx, 1262, 104, "LFO")
    p.slider("lfo_pms", rx, 116, 232, "PITCH MOD SENS")
    p.legend(rx, 216, "KEY SYNC", 14)
    p.toggle("lfo_sync", rx + 136, 210, 96, 30)
    p.choices["lfo_sync"] = ["OFF", "ON"]
    # LFO wave membranes (screen only)
    p.header(X0 + 8, 1262, 304, "LFO WAVE")
    p.segments("lfo_wave", X0 + 14, 316, 1240, 34, ["TRIANGLE", "SAW DOWN", "SAW UP", "SQUARE", "SINE", "SAMPLE & HOLD"])
    # pitch EG (groups 3, 4) + envelope
    EW = 140
    for gi, (title, part, y) in enumerate([("PITCH EG RATE", "r", 370), ("PITCH EG LEVEL", "l", 480)]):
        p.header(X0 + 8, 632, y + 18, title)
        keys = []
        for i in range(4):
            key = "pitch_eg_%s%d" % (part, i + 1)
            p.slider(key, col(i, EW), y + 30, EW, "%s %d" % ("RATE" if part == "r" else "LEVEL", i + 1))
            keys.append(key)
        p.qlink_group((X0, y + 2, 640, y + 94), keys)
    p.header(660, 1262, 388, "PITCH ENVELOPE")
    art.window(p.bg, 666, 404, 1262, 618, grid=(8, 2))   # the middle line is "no pitch shift" (level 50)
    p.envelope("pitch_eg_", "666 404 596 214", "pitch envelope")
    return p


def algo_page(fn):
    """ALGO: the voice structure. The algorithm diagram (32-frame strip); a VOICE column with ALGORITHM, FEEDBACK,
    OUTPUT LEVEL (Q-Link group 1) and OSC KEY SYNC; and an operator mixer: six strips with ON and OUTPUT LEVEL
    (op 1-4 levels = group 2, op 5-6 = group 3). Balancing carrier/modulator levels against the algorithm is the
    most common FM edit, so it gets its own page."""
    p = Page("ALGO", fn, seed=5)
    p.header(358, 800, 18, "ALGORITHM")
    art.window(p.bg, 358, 36, 800, 302, grid=(1, 1))
    big = asset("algo_med.png", lambda: art.film_strip([art.algo_image(a + 1, 380, 212) for a in range(32)]))
    p.image_strip("algorithm", big, 32, "389 63 380 212")
    # GENERATE (Q-Link group 4): a musically-ruled random voice. STYLE picks the rules, AMOUNT 100 = a new voice from scratch
    # (new algorithm), lower = vary the current voice by that much. Carrier ratios (the key note) are never touched.
    gx, gw = 836, 420
    p.header(gx, gx + gw, 18, "GENERATE")
    orange = (227, 163, 107)
    bw = (gw - 10) // 2
    for n, (key, cap, x) in enumerate((("generate", "GENERATE", gx), ("mutate", "MUTATE", gx + bw + 10))):
        on, off = membrane_img(bw, 48, True, cap, orange), membrane_img(bw, 48, False, cap, orange)
        p.kids.append(tui.entry(key, "Button", {"version": 2, "onImage": on, "offImage": off, "buttonId": 1, "numButtonsInGroup": 1,
                                                 "handleName": "Data", "gestureBehaviour": "Instant"},
                                "%d 32 %d 60" % (x - 6, bw + 12), remap=tui.P(key), focus="Yes"))
    # STYLE: a picker (radio group on gen_style), two rows of four; ALL = a random style each press, CHAOS = no rules at all
    names = ["PLUCK", "BELL", "PAD", "BASS", "EP", "LEAD", "ALL", "CHAOS"]
    p.legend(gx, 100, "STYLE", 13, (160, 142, 110))
    sw = (gw - 3 * 6) // 4
    for i, nm in enumerate(names):
        r, c = divmod(i, 4)
        x, y = gx + c * (sw + 6), 124 + r * 54
        on, off = membrane_img(sw, 44, True, nm), membrane_img(sw, 44, False, nm)
        p.kids.append(tui.entry("gen_style %d" % i, "Button", {"version": 2, "onImage": on, "offImage": off, "buttonId": i,
                                                                "numButtonsInGroup": 8, "handleName": "Data", "gestureBehaviour": "Instant"},
                                "%d %d %d %d" % (x - 3, y - 3, sw + 6, 50), remap=tui.P("gen_style"), focus="Yes"))
    p.choices["gen_style"] = names
    p.slider("gen_amount", gx, 238, gw, "MUTATE AMOUNT")
    # VOICE column (group 1)
    vx, vw = 24, 310
    p.header(vx, 334, 18, "VOICE")
    for i, (key, n) in enumerate([("algorithm", "ALGORITHM"), ("feedback", "FEEDBACK"), ("output_level", "OUTPUT LEVEL")]):
        p.slider(key, vx, 32 + i * 72, vw, n)
    p.legend(vx, 262, "OSC KEY SYNC")
    p.toggle("osc_sync", vx + vw - 96, 254, 96, 30)
    p.choices["osc_sync"] = ["OFF", "ON"]
    p.qlink_group((vx - 10, 4, 344, 300), ["algorithm", "feedback", "output_level", "osc_sync"])
    # operator mixer
    p.header(24, 1262, 330, "OPERATORS")
    keys = []
    for i in range(6):
        op = i + 1
        x = 24 + i * 208
        p.d.text((x + 4, 344), str(op), font=art.font(34, 700), fill=CREAM, anchor="lt")
        on = membrane_img(104, 36, True, "ON")
        off = membrane_img(104, 36, False, "OFF")
        key = "op%d_on" % op
        p.kids.append(tui.entry(key, "Button", {"version": 2, "onImage": on, "offImage": off, "buttonId": 1, "numButtonsInGroup": 1,
                                                 "handleName": "Data", "gestureBehaviour": "Instant"},
                                "%d %d 116 48" % (x + 60, 340), remap=tui.P(key), focus="Yes"))
        p.choices[key] = ["OFF", "ON"]
        p.vfader("op%d_level" % op, x + 82, 394, 160, "LEVEL")
        keys.append("op%d_level" % op)
    p.qlink_group((16, 386, 846, 624), keys[:4])
    p.qlink_group((850, 386, 1272, 624), keys[4:])
    p.qlink_group((816, 100, 1272, 310), ["gen_style", "gen_amount"])
    return p


def tile_frame(w, h, lit):
    """A cart tile: printed frame with a transparent middle, so the live name Label placed under it shows through
    (a Label on top of a Button swallows its taps)."""
    from PIL import Image
    def make():
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, w - 1, h - 1], outline=(31, 182, 166, 255) if lit else (78, 70, 64, 255), width=2)
        d.line([2, h - 2, w - 3, h - 2], fill=(10, 9, 8, 200))
        return img
    return asset("tile_%dx%d_%s.png" % (w, h, "on" if lit else "off"), make)


def carts_page(fn):
    """CARTS: the header (DEXED, LED, LCD); the cart list (22 tiles, momentary bank_slot_N, live names, paged);
    the DX7 1-32 memory-select grid as one 32-button radio group on `preset` (the lit switch is the current patch),
    each with its live patch name printed under it."""
    p = Page("CARTS", fn, seed=11)
    voice_header(p, random=True)
    # favourites, in the header right of the LCD: +FAV in the panel's STORE red, -FAV in lilac, live status
    p.header(870, 1140, 16, "FAVOURITES")
    for i, (key, cap, col) in enumerate([("fav_save", "+FAV", art.STORE_RED), ("fav_delete", "-FAV", art.LILAC)]):
        on, off = membrane_img(110, 30, True, cap, col), membrane_img(110, 30, False, cap, col)
        p.kids.append(tui.entry(key, "Button", {"version": 2, "onImage": on, "offImage": off, "buttonId": 1, "numButtonsInGroup": 1,
                                                 "handleName": "Data", "gestureBehaviour": "Instant"},
                                "%d 22 122 42" % (870 + i * 124 - 6), remap=tui.P(key), focus="Yes"))
    p.kids.append(tui.label("Value", "870 56 270 22", remap=tui.P("fav_text"), just="left verticallyCentred",
                            colour="ffbea880", style="Regular", case="Original", h=14.0))
    p.qlink_group((246, 2, 862, 76), ["syx_bank_index", "preset"])   # Q-Link 1: cart, Q-Link 2: patch (VOICE's 16 are full)
    # cart list: 2 columns x 11
    p.header(24, 330, 104, "CARTRIDGE")
    def hl_strip():
        from PIL import Image
        frames = []
        for k in range(23):
            f = Image.new("RGBA", (304, 432), (0, 0, 0, 0))
            if k < 22:
                c, r = divmod(k, 11)
                ImageDraw.Draw(f).rectangle([c * 156, r * 40, c * 156 + 147, r * 40 + 31], fill=(18, 78, 70, 255))
            frames.append(f)
        return art.film_strip(frames)
    p.image_strip("bank_cur_slot", asset("cart_current.png", hl_strip), 23, "24 116 304 432")   # under the tiles
    for i in range(22):
        c, r = divmod(i, 11)
        x, y = 24 + c * 156, 116 + r * 40
        key = "bank_slot_%d" % (i + 1)
        p.d.rectangle([x, y, x + 147, y + 31], fill=(14, 12, 11))
        p.kids.append(tui.label("Value", "%d %d 132 32" % (x + 10, y), remap=tui.P(key), colour="ffbea880", style="Medium",
                                case="Original", h=17.0))
        p.kids.append(tui.entry(key, "Button", {"version": 2, "onImage": tile_frame(148, 32, True), "offImage": tile_frame(148, 32, False),
                                                 "buttonId": 1, "numButtonsInGroup": 1, "handleName": "Data", "gestureBehaviour": "Instant"},
                                "%d %d 148 32" % (x, y), remap=tui.P(key), focus="Yes"))
    p.kids.append(tui.label("Value", "24 566 110 40", remap=tui.P("bank_page_text"), colour="ffbea880", style="Medium", case="Original", h=17.0))
    for i, (key, cap) in enumerate([("bank_page_prev", "<"), ("bank_page_next", ">")]):
        on, off = membrane_img(80, 34, True, cap, art.LILAC), membrane_img(80, 34, False, cap, art.LILAC)
        p.kids.append(tui.entry(key, "Button", {"version": 2, "onImage": on, "offImage": off, "buttonId": 1, "numButtonsInGroup": 1,
                                                 "handleName": "Data", "gestureBehaviour": "Instant"},
                                "%d 563 92 46" % (150 + i * 92 - 6), remap=tui.P(key), focus="Yes"))
    # memory select 1-32: one radio group on `preset`
    p.header(352, 1262, 104, "MEMORY SELECT")
    for i in range(32):
        r, c = divmod(i, 8)
        x, y = 352 + c * 114, 118 + r * 124
        on, off = membrane_img(104, 62, True, number=i + 1), membrane_img(104, 62, False, number=i + 1)
        p.kids.append(tui.entry("patch %d" % (i + 1), "Button", {"version": 2, "onImage": on, "offImage": off, "buttonId": i,
                                                                 "numButtonsInGroup": 32, "handleName": "Data", "gestureBehaviour": "Instant"},
                                "%d %d 116 74" % (x - 6, y - 6), remap=tui.P("preset"), focus="Yes"))
        p.kids.append(tui.label("Value", "%d %d 114 24" % (x - 5, y + 65), remap=tui.P("patch_slot_%d" % (i + 1)),
                                just="horizontallyCentred verticallyCentred", colour="ffe9d6ae", style="Medium", case="Upper Case", h=18.0))
    p.choices["preset"] = [str(i + 1) for i in range(32)]
    return p


def op_page(op, fn, sub=0):
    """OP tab, stacked layout: OSCILLATOR / SENSITIVITY / KEYBOARD LEVEL SCALING rows of 4, EG RATE and EG LEVEL rows,
    the interactive envelope; right column: operator number, its ON switch, the algorithm with this op lit."""
    p = Page("OP%d" % op, fn, sub=sub)
    k = lambda s: "op%d_%s" % (op, s)
    X0, X1, SW = 16, 1010, 232

    def col(i, w=SW):
        return X0 + 14 + i * (w + 16)

    # OSCILLATOR (Q-Link group 1)
    p.header(X0 + 8, X1 - 8, 18, "OSCILLATOR")
    for i, (s, n) in enumerate([("level", "OUTPUT LEVEL"), ("coarse", "FREQ COARSE"), ("fine", "FREQ FINE"), ("detune", "DETUNE")]):
        p.slider(k(s), col(i), 30, SW, n)
    p.qlink_group((X0, 2, X1, 94), [k("level"), k("coarse"), k("fine"), k("detune")])
    # SENSITIVITY + OSC MODE (group 2)
    p.header(X0 + 8, X1 - 8, 118, "SENSITIVITY")
    for i, (s, n) in enumerate([("vel_sens", "KEY VELOCITY"), ("amp_mod", "AMP MOD"), ("rate_scale", "RATE SCALING")]):
        p.slider(k(s), col(i), 130, SW, n)
    p.legend(col(3), 130, "OSC MODE")
    p.segments(k("osc_mode"), col(3), 154, SW, 30, ["RATIO", "FIXED"])
    p.qlink_group((X0, 102, X1, 194), [k("vel_sens"), k("amp_mod"), k("rate_scale"), k("osc_mode")])
    # KEYBOARD LEVEL SCALING (screen only)
    p.header(X0 + 8, X1 - 8, 218, "KEYBOARD LEVEL SCALING")
    for i, (s, n) in enumerate([("key_bp", "BREAK POINT"), ("key_ld", "L DEPTH"), ("key_rd", "R DEPTH")]):
        p.slider(k(s), col(i), 230, SW, n)
    x = col(3)
    curves = ["-LIN", "-EXP", "+EXP", "+LIN"]
    p.legend(x, 230, "L CURVE", 13)
    p.segments(k("key_lc"), x + 64, 226, SW - 64, 24, curves, gap=3)
    p.legend(x, 264, "R CURVE", 13)
    p.segments(k("key_rc"), x + 64, 260, SW - 64, 24, curves, gap=3)
    # EG RATE / EG LEVEL (groups 3, 4)
    EW = 140
    for gi, (title, part, y) in enumerate([("EG RATE", "r", 330), ("EG LEVEL", "l", 470)]):
        p.header(X0 + 8, 632, y + 18, title)
        keys = []
        for i in range(4):
            key = k("eg_%s%d" % (part, i + 1))
            p.slider(key, col(i, EW), y + 30, EW, "%s %d" % ("RATE" if part == "r" else "LEVEL", i + 1))
            keys.append(key)
        p.qlink_group((X0, y + 2, 640, y + 94), keys)
    # the interactive envelope (stage letters and fill hidden, see make_tui.envelope_for)
    p.header(660, 1262, 318, "ENVELOPE")
    art.window(p.bg, 666, 334, 1262, 618)
    p.envelope("op%d_eg_" % op, "666 334 596 284", "op%d envelope" % op)   # transparent: the window art shows through
    # right column: operator number, ON, algorithm
    rx = 1034
    p.legend(rx, 26, "OPERATOR", 16, LILAC, 600, anchor="ls")
    p.d.text((rx, 30), str(op), font=art.font(110, 700), fill=CREAM, anchor="lt")
    p.toggle(k("on"), rx + 76, 50, 150, 64)
    p.legend(rx + 76, 134, "OPERATOR ON-OFF", 12)
    p.header(rx, 1262, 200, "ALGORITHM")
    strip = asset("algo_op%d.png" % op, lambda: art.film_strip([art.algo_image(a + 1, 228, 100, hl_op=op) for a in range(32)]))
    p.image_strip("algorithm", strip, 32, "%d 210 228 100" % rx)
    p.choices[k("on")] = ["OFF", "ON"]
    return p
