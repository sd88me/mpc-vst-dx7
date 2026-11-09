#!/usr/bin/env python3
"""Write skins/TUI.json + skins/Q-Links.json (the MPC's native skin files) from Python, and copy the art they use.

Spike version (PLAN-2.0.md Phase 1b / §6): one test tab with the live envelope (Envelope, envelopeType "Pitch") on OP1's EG,
the same eight EG params as generic sliders, a film-strip algorithm picture, a horizontal film-strip fader, and a momentary
NEXT BANK membrane button with the bank name next to it.

    python3 tools/make_dx7_skin.py --assets   # art -> art/
    python3 tools/make_tui.py                 # -> skins/
"""
import os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "art")
OUT = os.path.join(ROOT, "skins")
LOCK = [l.strip() for l in open(os.path.join(ROOT, "params.lock")) if l.strip()]


def P(key):
    return "Parameter %d" % LOCK.index(key)


# ---- a JSON writer that keeps key order and allows the overlay widgets' duplicate "version" key ------------------
class Obj:
    """An ordered JSON object that may repeat a key: Obj(("version", 2), ("version", 1), ...)."""
    def __init__(self, *pairs):
        self.pairs = list(pairs)


def dump(v, ind=0):
    sp = "  " * ind
    if hasattr(v, "pairs"):   # Obj from either copy of this module (it is also imported by skin_pages)
        pairs = v.pairs
    elif isinstance(v, dict):
        pairs = list(v.items())
    else:
        pairs = None
    if pairs is not None:
        if not pairs:
            return "{}"
        inner = (",\n").join("%s  %s: %s" % (sp, dump(k), dump(x, ind + 1)) for k, x in pairs)
        return "{\n%s\n%s}" % (inner, sp)
    if isinstance(v, list):
        if not v:
            return "[]"
        return "[\n%s\n%s]" % (",\n".join(sp + "  " + dump(x, ind + 1) for x in v), sp)
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return repr(v)
    if isinstance(v, int):
        return str(v)
    s = str(v).replace("\\", "\\\\").replace('"', '\\"')
    return '"%s"' % s


# ---- building blocks -----------------------------------------------------------------------------------------------
def bounds(b, focus="No", visible="Always", invalid="Show"):
    return {"version": 1, "acceptsHWFocus": focus, "showWhenDataModelInvalid": invalid, "whenVisible": visible,
            "boundsType": "Absolute", "bounds": b}


def entry(name, typ, data, b, remap=None, focus="No", visible="Always"):
    return {"version": 2,
            "componentData": {"version": 1, "name": name, "type": typ, "data": data},
            "handle remapping": {"version": 1, "map": [{"key": "Data", "value": remap}] if remap else []},
            "bounds": bounds(b, focus, visible)}


def bg(colour="0", image=""):
    return {"version": 1, "focussed": {"version": 1, "colour": colour, "image": image},
            "unfocussed": {"version": 1, "colour": colour, "image": image}}


def component(children, actions=None, ignore=False, background=None):
    return {"version": 2, "actions": actions or [], "backgroundData": background or bg(),
            "ignoreMousePresses": ignore, "disableCoarseDataWheel": False, "componentsData": children}


def act(on, handler, extra=""):
    return {"version": 1, "onAction": on, "handler": handler, "handleName": "Data", "additionalData": extra}


FOCUS = {"version": 1, "backgroundColour": "19ffffff", "outlineColour": "ffe81f40", "backgroundInset": 4.0, "outlineThickness": 1.0}


def text_style(h=22.0, colour="ffbea880", style="SemiBold", just="left verticallyCentred", case="Upper Case", font="Roboto"):
    return {"version": 1, "font": {"version": 1, "name": font, "style": style, "height": h}, "colour": colour,
            "justification": just, "case": case}


def label(kind, b, remap=None, text=None, **ts):
    d = {"version": 1, "textStyle": text_style(**ts), "type": kind, "handleName": "Data" if remap else "Invalid"}
    if text is not None:
        d["text"] = text
    return entry("label", "Label", d, b, remap)


def definitions():
    """Reusable components: generic slider slot, the two overlays."""
    slider_slot = component([
        entry("focus", "Focus", FOCUS, "0 0 278 107", visible="WhenFocussed"),
        entry("slider", "Slider", {"version": 1, "handleName": "Data"}, "15 15 248 77"),
    ], actions=[act("Mouse Down", "Q-Link"), act("Double Click", "Show Overlay", "knob overlay"),
                act("Enter Pressed", "Show Overlay", "knob overlay")])
    knob_overlay = component([entry("overlay", "KnobOverlay", Obj(
        ("version", 2), ("version", 1),
        ("actions", [{"version": 1, "onAction": "Focus Lost", "handler": "Focus Lost", "handleName": "Focus Lost", "additionalData": ""}]),
        ("overlayType", "Knob With Header"), ("scaleType", "Linear"), ("polarityType", "Unipolar"),
        ("showMinusSign", True), ("handleName", "Data")), "0 0 1280 800", focus="Yes")], ignore=True)
    return [{"key": "sliderSlot", "value": slider_slot}, {"key": "knob overlay", "value": knob_overlay}]


def envelope_for(prefix, fill="00000000", header=False, name="ENVELOPE"):
    """The live DX7 EG: envelopeType "Pitch" = 5 levels + 4 times. Rates are speeds, the widget wants times: Invert/.
    Stage letters hidden (transparent handle text). fill: the widget's fill colour (on the Force it drew a box, not under
    the curve; kept configurable for the comparison in PLAN-2.0.md)."""
    k = lambda s: P(prefix + s)
    return Obj(
        ("version", 1), ("envelopeType", "Pitch"), ("envelopeStyle", "WithHeader" if header else "WithoutHeader"), ("envelopeName", name),
        ("backgroundColour", "00000000"), ("scaleColour", "ff4a423c"), ("lineColour", "ffded2b8"), ("fillColour", fill),
        ("highlightColour", "2a58ecd6"), ("lineWidth", 3), ("handleWidth", 26), ("handleHeight", 26), ("handleShape", "Circle"),
        ("handleLineWidth", 2), ("handleLineColour", "ff58ecd6"), ("handleFillColour", "ff141210"), ("handleTextColour", "00000000"),
        ("handleLineWidthOnPressed", 3), ("handleLineColourOnPressed", "ff58ecd6"), ("handleFillColourOnPressed", "ff141210"),
        ("handleTextColourOnPressed", "00000000"), ("handleArrowLineColourOnPressed", "ff58ecd6"),
        ("handleArrowFillColourOnPressed", "ff58ecd6"),
        ("pitchEnvelopeLevel1Handle", k("l4")),
        ("pitchEnvelopeDelayHandle", "Invert/" + k("r1")),
        ("pitchEnvelopeLevel2Handle", k("l1")),
        ("pitchEnvelopeAttackHandle", "Invert/" + k("r2")),
        ("pitchEnvelopeLevel3Handle", k("l2")),
        ("pitchEnvelopeDecayHandle", "Invert/" + k("r3")),
        ("pitchEnvelopeSustainHandle", k("l3")),
        ("pitchEnvelopeReleaseHandle", "Invert/" + k("r4")),
        ("pitchEnvelopeLevel5Handle", k("l4")),
        ("forceHideShapeHandles", True), ("forceCurveShape", 0.5), ("curveType", "Quadratic"))


def envelope(op):
    return envelope_for("op%d_eg_" % op, header=True, name="OP%d ENVELOPE" % op)


TEST = set(os.environ.get("DEXED_SKIN_TEST", "").split(","))   # bisect switches: noneg, norepl, noseg, noenv, noimg

SLIDERS = {}   # width -> film strip file, for the hslider<w> components


def need_slider(w, tag, strip):
    SLIDERS[(w, tag)] = strip


FIELDS = set()   # widths of the invisible LCD stepper fields (lcdfield<w>)


def need_field(w):
    FIELDS.add(w)


VFADERS = {}   # height -> film strip file, for the vfader<h> components


def need_vfader(h, strip):
    VFADERS[h] = strip


def slider_defs():
    """One reusable component per slider width: the film strip (Knob dragged sideways), a focus ring, Q-Link on touch,
    the big knob overlay on double tap / Enter."""
    out = []
    for (w, tag), strip in sorted(SLIDERS.items()):
        out.append({"key": "hslider%d%s" % (w, tag), "value": component([
            entry("focus", "Focus", FOCUS, ("0 0 %d 30" % w) if "noneg" in TEST else ("-6 -30 %d 66" % (w + 12)), visible="WhenFocussed"),
            entry("strip", "Knob", {"version": 3, "knobType": "FilmStrip", "filmStrip": strip, "numFrames": 127, "invert": False,
                                    "dragOrientation": "Horizontal", "handleName": "Data"}, "0 0 %d 30" % w),
        ], actions=[act("Mouse Down", "Q-Link"), act("Double Click", "Show Overlay", "knob overlay"),
                    act("Enter Pressed", "Show Overlay", "knob overlay")])})
    for w in sorted(FIELDS):
        # An invisible control over a live text field: focusable (the data wheel steps it, a Q-Link bank can own it) and
        # draggable. Its own value text is transparent; the field's name is a Label underneath.
        ts = {"version": 1, "font": {"version": 1, "name": "Roboto", "style": "Regular", "height": 20.0}, "colour": "00000000",
              "justification": "horizontallyCentred verticallyCentred", "case": "Original"}
        out.append({"key": "lcdfield%d" % w, "value": component([
            entry("focus", "Focus", {"version": 1, "backgroundColour": "221fb5a4", "outlineColour": "ff1fb5a4",
                                     "backgroundInset": 0.0, "outlineThickness": 2.0}, "0 0 %d 56" % w, visible="WhenFocussed"),
            entry("field", "Knob", {"version": 4, "knobType": "ValueSlider", "textStyle": ts, "dragOrientation": "Horizontal",
                                    "handleName": "Data"}, "0 0 %d 56" % w),
        ], actions=[act("Mouse Down", "Q-Link")])})
    for h, strip in sorted(VFADERS.items()):
        out.append({"key": "vfader%d" % h, "value": component([
            entry("focus", "Focus", FOCUS, "0 0 36 %d" % h, visible="WhenFocussed"),
            entry("strip", "Knob", {"version": 3, "knobType": "FilmStrip", "filmStrip": strip, "numFrames": 127, "invert": False,
                                    "dragOrientation": "Vertical", "handleName": "Data"}, "0 0 36 %d" % h),
        ], actions=[act("Mouse Down", "Q-Link"), act("Double Click", "Show Overlay", "knob overlay"),
                    act("Enter Pressed", "Show Overlay", "knob overlay")])})
    return out


def spike_tab():
    kids = [entry("bg", "Image", {"version": 2, "imageType": "Regular", "colour": "0", "image": "bg_spike.png"}, "0 0 1280 628")]
    kids.append(entry("env", "Envelope", envelope(1), "16 8 760 330", focus="Yes"))
    for i, s in enumerate(["r1", "r2", "r3", "r4", "l1", "l2", "l3", "l4"]):
        r, c = divmod(i, 4)
        kids.append(entry("eg " + s, "sliderSlot", {"version": 1, "handleName": "Data"},
                          "%d %d 278 107" % (23 + c * 320, 360 + r * 130), remap=P("op1_eg_" + s), focus="Yes"))
    # algorithm picture: a 32-frame strip following the algorithm param
    kids.append(entry("algo", "Image", {"version": 2, "imageType": "FilmStrip", "colour": "0", "image": "algo_thumb.png",
                                         "numFrames": 32, "handleName": "Data"}, "800 20 456 166", remap=P("algorithm")))
    # horizontal film-strip fader (Knob dragged sideways) on OP1 level, with its value
    kids.append(label("Name", "800 196 300 28", remap=P("op1_level")))
    kids.append(label("Value", "1100 196 156 28", remap=P("op1_level"), just="right verticallyCentred", colour="ffece8de", style="Regular"))
    kids.append(entry("level", "Knob", {"version": 3, "knobType": "FilmStrip", "filmStrip": "slider_h.png", "numFrames": 127,
                                         "invert": False, "dragOrientation": "Horizontal", "handleName": "Data"},
                      "800 226 172 46", remap=P("op1_level"), focus="Yes"))
    # momentary NEXT BANK membrane + live bank name
    kids.append(entry("next bank", "Button", {"version": 2, "onImage": "membrane_on.png", "offImage": "membrane_off.png",
                                               "buttonId": 1, "numButtonsInGroup": 1, "handleName": "Data",
                                               "gestureBehaviour": "Instant"},
                      "800 290 50 42", remap=P("next_syx_bank"), focus="Yes"))
    kids.append(label("Text", "860 290 120 42", text="NEXT BANK"))
    kids.append(label("Value", "990 290 270 42", remap=P("bank_name"), colour="ffece8de", style="Regular", case="Original"))
    return {"version": 1, "tabName": "SPIKE", "fnKeyIndex": 0, "fnKeySubIndex": 0,
            "componentDefinition": component(kids, background=bg("ff1e1a18")),
            "qlinkBoundsData": ["16 352 1248 124", "16 482 1248 124"]}


def qlinks():
    rates = [LOCK.index("op1_eg_" + s) for s in ("r1", "r2", "r3", "r4")]
    levels = [LOCK.index("op1_eg_" + s) for s in ("l1", "l2", "l3", "l4")]
    q = {"Q-Link %d" % n: -1 for n in range(1, 17)}
    for i in range(4):
        q["Q-Link %d" % (13 + i)] = rates[i]    # top row (RowTopDown banks it first)
        q["Q-Link %d" % (9 + i)] = levels[i]
    prog = {"Q-Link %d" % n: -1 for n in range(1, 17)}
    return {"version": 4, "info": {"version": 1, "type": "CompleteDescription"},
            "Screen Mode Q-Links": {"version": 4, "map": [
                {"Tab": 1, "SubTab": 1, "Bank Direction": "RowTopDown", "Q-Links": q}]},
            "Program Mode Q-Links": prog}


def qlinks_for(pages):
    """Screen-mode Q-Links: each page's groups of four, top group on the top knob row (Bank Direction RowTopDown)."""
    maps = []
    for p in pages:
        q = {"Q-Link %d" % n: -1 for n in range(1, 17)}
        for gi, keys in enumerate(p.qlink_rows[:4]):
            first = 13 - 4 * gi
            for i, key in enumerate(keys):
                q["Q-Link %d" % (first + i)] = LOCK.index(key)
        maps.append({"Tab": p.fn + 1, "SubTab": p.sub + 1, "Bank Direction": "RowTopDown", "Q-Links": q})
    prog = {"Q-Link %d" % n: -1 for n in range(1, 17)}
    return {"version": 4, "info": {"version": 1, "type": "CompleteDescription"},
            "Screen Mode Q-Links": {"version": 4, "map": maps}, "Program Mode Q-Links": prog}


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import skin_pages
    # Same tab order as 1.x: VOICE, CARTS, ALGO, OP1..OP6, one operator per tab (the Force pages the keys behind ">").
    pages = [skin_pages.voice_page(0), skin_pages.carts_page(1), skin_pages.algo_page(2)]
    if os.environ.get("DEXED_OPS") == "six":   # six separate OP keys (the old layout)
        pages += [skin_pages.op_page(op, 2 + op) for op in range(1, 7)]
    else:   # default: one OP key with six sub-tabs (the key steps forward through OP1..OP6)
        pages += [skin_pages.op_page(op, 3, sub=op - 1) for op in range(1, 7)]
    for p in pages:
        drop = []
        if "noseg" in TEST: drop.append("Button")
        if "noenv" in TEST or ("env1" in TEST and p is not pages[0]) or ("env2" in TEST and p not in pages[:2]) or ("envop2" in TEST and p is not pages[1]): drop.append("Envelope")
        if "noimg" in TEST: drop.append("Image")
        p.kids = [k for k in p.kids if k["componentData"]["type"] not in drop]
        if "norepl" in TEST: p.choices = {}
    tabs = [p.tab() for p in pages]
    repl, seen = [], set()
    for p in pages:
        for key, labels in p.choices.items():
            if key not in seen:
                seen.add(key)
                repl.append({"key": P(key), "value": labels})
    tui = {"pageData": {"version": 1,
                        "componentDefinitions": {"version": 2, "importFiles": [],
                                                 "localComponentDefinitions": definitions() + skin_pages.tui.slider_defs()},
                        "replacementStrings": repl,
                        "info": {"version": 1, "type": "CompleteDescription"},
                        "tabs": tabs}}
    open(os.path.join(OUT, "TUI.json"), "w").write(dump(tui) + "\n")
    open(os.path.join(OUT, "Q-Links.json"), "w").write(dump(qlinks_for(pages)) + "\n")
    print("wrote", OUT, "-", len(tabs), "tabs,", len(os.listdir(OUT)), "files")


if __name__ == "__main__":
    main()
