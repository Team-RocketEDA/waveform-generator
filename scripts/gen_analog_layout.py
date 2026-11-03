"""Generate the R-2R + RC analog macro GDS with sky130 PCells (gdsfactory).

Single source of truth for analog layout, mirroring scripts/gen_analog_pdk.py
(schematic) and canvas.toml (8-bit, 50 MHz update, <1 LSB DNL/INL).

Floorplan (um, origin at field center):
  - 15 folded resistor columns: 8x shunt (4 legs of 2R/4) + 7x series
    (2 legs of R/2), all W=4 poly PCells, terminals strapped on metal1.
  - Series nodes form segmented top trunk; vout pad at far left.
  - Shunt bottoms drop to drain stub pins D7..D0 (TG band lands next bite).
  - RC filter at right: RFILT PCell + 15x15 MiM cap, fout pin.
  - Pins: vout (top-left), D7..D0 + vref/vgnd/fout (bottom).

Run with the isolated PCell venv (see requirements-gfsky130.txt):
    /tmp/gfsky130/bin/python scripts/gen_analog_layout.py
Output: design/analog/gds/r2r_dac8_macro.gds
"""
import gdsfactory as gf
import sky130
from sky130 import LAYER

# --- values mirror gen_analog_pdk.py (rsheet 317.39: R~28.3k, 2R~56.7k) ---
W = 4.0
R_LEN = 357.43
R2_LEN = 716.98
R_LEG = R_LEN / 2          # 178.715, 2 legs per series column
R2_LEG = R2_LEN / 4        # 179.245, 4 legs per shunt column
RFILT_W, RFILT_L = 1.0, 89.36
CAP_W, CAP_L = 15.0, 15.0
LEG_PITCH = 10.0
COL_GAP = 6.0
M1 = LAYER.met1drawing

top = None  # set in build()


def m1(x0, y0, x1, y1):
    top.add_polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer=M1)


def label(x, y, text):
    # text purposes choke Magic GDS input; pads carry the pin function
    pass


def pin_pad(x, y, text, s=6.0):
    m1(x - s / 2, y - s / 2, x + s / 2, y + s / 2)
    label(x, y, text)


def rect(layer, x0, y0, x1, y1):
    top.add_polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], layer=layer)


# Cut size / pitch / enclosure per level, from the sky130 tech LEF
# (M1M2_PR / M2M3_PR / M3M4_PR GENERATE rules).
VIA_RULE = {
    "L1": {"cut": 0.15, "pitch": 0.32, "enc": 0.085},
    "L2": {"cut": 0.20, "pitch": 0.40, "enc": 0.085},
    "L3": {"cut": 0.20, "pitch": 0.40, "enc": 0.090},
}


def via_stack(x, y, bot_layer, top_layer, cut_layer, rule, cuts=2):
    """2x2 cut array + landing pads between two adjacent metal layers."""
    cs = VIA_RULE[rule]["cut"]
    pitch = VIA_RULE[rule]["pitch"]
    enc = VIA_RULE[rule]["enc"]
    span = cuts * cs + (cuts - 1) * (pitch - cs)
    x0, y0 = x - span / 2, y - span / 2
    for i in range(cuts):
        for j in range(cuts):
            rect(cut_layer, x0 + i * pitch, y0 + j * pitch,
                 x0 + i * pitch + cs, y0 + j * pitch + cs)
    rect(bot_layer, x0 - enc, y0 - enc, x0 + span + enc, y0 + span + enc)
    rect(top_layer, x0 - enc, y0 - enc, x0 + span + enc, y0 + span + enc)


def up_stack(x, y, target):
    """met1 up to target metal ('m2'/'m3'/'m4') through stacked vias."""
    mets = [LAYER.met1drawing, LAYER.met2drawing,
            LAYER.met3drawing, LAYER.met4drawing]
    cuts = [LAYER.viadrawing, LAYER.via2drawing, LAYER.via3drawing]
    n = {"m2": 1, "m3": 2, "m4": 3}[target]
    for k in range(n):
        via_stack(x, y, mets[k], mets[k + 1], cuts[k], f"L{k + 1}")


def res_leg(x, y, length):
    r = top << sky130.pcells.sky130_fd_pr__res_generic_po(
        res_width=W, res_length=length)
    r.move((x, y))
    return r


def build_field():
    """Place 15 folded columns; return (node_segs, drops)."""
    # order: S7 R S6 R S5 R S4 R S3 R S2 R S1 R S0  (S=shunt 2R, R=series)
    cols = []
    for b in range(7, -1, -1):
        cols.append(("S", b))
        if b > 0:
            cols.append(("R", b))
    x = 10.0
    tops = {}    # node -> list of leg-top x positions
    drops = {}   # bit -> (x_center, strap_y)
    node_names = ["vout", "n6", "n5", "n4", "n3", "n2", "n1", "n0"]
    node_of_col = {}
    ni = 0
    for kind, b in cols:
        if kind == "S":
            node_of_col[(kind, b)] = node_names[ni]
            ni += 1
        else:
            node_of_col[(kind, b)] = (node_names[ni - 1], node_names[ni])
    for kind, b in cols:
        nlegs = 4 if kind == "S" else 2
        length = R2_LEG if kind == "S" else R_LEG
        legxs = [x + i * LEG_PITCH for i in range(nlegs)]
        legs = [res_leg(lx, 0.0, length) for lx in legxs]
        if kind == "S":
            node = node_of_col[(kind, b)]
            tops.setdefault(node, []).extend(
                legs[i].ports["PLUS"].center[0] for i in range(nlegs))
            # bottom strap + drop to drain stub pin
            by = legs[0].ports["MINUS"].center[1]
            m1(legxs[0] - 3, by - 2.5, legxs[-1] + 3, by + 2.5)
            cx = (legxs[0] + legxs[-1]) / 2
            m1(cx - 1.5, -118.0, cx + 1.5, by)
            pin_pad(cx, -121.0, f"D{b}")
            drops[b] = (cx, by)
        else:
            na, nb = node_of_col[(kind, b)]
            tops.setdefault(na, []).append(legs[0].ports["PLUS"].center[0])
            tops.setdefault(nb, []).append(legs[1].ports["PLUS"].center[0])
            # bottom strap (series link between the two legs)
            by = legs[0].ports["MINUS"].center[1]
            m1(legxs[0] - 3, by - 2.5, legxs[-1] + 3, by + 2.5)
        x = legxs[-1] + COL_GAP + 5.0
    return tops, drops, x


def build_trunk(tops, x_end):
    y = 89.5
    order = ["vout", "n6", "n5", "n4", "n3", "n2", "n1", "n0"]
    for a in order:
        # one segment per node over its OWN tops only: the series-R column
        # straddles two nodes, so spanning both would short the rung
        lo = min(tops[a]) - 3
        hi = max(tops[a]) + 3
        m1(lo, y, hi, y + 5.5)
    # vout pad at far left, n0 probe pad at far right
    m1(min(tops["vout"]) - 14, y, min(tops["vout"]) - 8, y + 5.5)
    label(min(tops["vout"]) - 11, y + 2.75, "vout")
    m1(max(tops["n0"]) + 8, y, max(tops["n0"]) + 14, y + 5.5)
    label(max(tops["n0"]) + 11, y + 2.75, "n0")


def build_filter(x0, vout_x0):
    # filter sits LEFT of the field, fed straight off the vout pad:
    # no long trunk run, no node shorts
    y_trunk = 89.5
    xf = vout_x0 - 30.0
    rf = top << sky130.pcells.sky130_fd_pr__res_generic_po(
        res_width=RFILT_W, res_length=RFILT_L)
    rf.move((xf, 0.0))
    px, py = rf.ports["PLUS"].center
    m1(xf - 1.5, py - 2.5, xf + 1.5, y_trunk + 5.5)   # up to vout trunk level
    m1(vout_x0 - 3, y_trunk, xf + 1.5, y_trunk + 5.5)  # into vout pad
    mx, my = rf.ports["MINUS"].center
    cap = top << sky130.pcells.sky130_fd_pr__cap_mim_m3_1(
        cap_width=CAP_W, cap_length=CAP_L)
    cap.move((xf, -75.0))
    # R bottom (met1) up to TOP plate (met4) via stack at right of cap
    m1(mx - 1.5, -75.0, mx + 1.5, my)
    m1(mx - 1.5, -77.0, xf + 12.0, -73.0)
    up_stack(xf + 12.0, -75.0, "m4")
    rect(LAYER.met4drawing, xf + 1.0, -76.5, xf + 12.5, -73.5)  # into plate
    m1(xf + 10.5, -89.0, xf + 13.5, -74.0)  # stack met1 down to fout pad
    pin_pad(xf + 12.0, -92.0, "fout")
    # BOTTOM plate (met3) down to vgnd pin via stack at left of cap
    rect(LAYER.met3drawing, xf - 12.5, -76.5, xf - 1.0, -73.5)  # into plate
    up_stack(xf - 12.0, -75.0, "m3")
    m1(xf - 13.5, -110.0, xf - 10.5, -75.0)
    pin_pad(xf - 12.0, -113.0, "vgnd")
    pin_pad(20.0, -140.0, "vref")
    return x0


def build():
    global top
    sky130.PDK.activate()
    top = gf.Component("r2r_dac8_macro")
    tops, drops, x_end = build_field()
    build_trunk(tops, x_end)
    x_max = build_filter(x_end, min(tops["vout"]) - 14)
    print(f"macro bbox um: {top.bbox()}")
    print(f"nodes: {sorted(tops)}, drops: {sorted(drops)}")
    return top


if __name__ == "__main__":
    import os
    c = build()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "design", "analog", "gds", "r2r_dac8_macro.gds")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    c.write_gds(out)
    print("wrote", out)
