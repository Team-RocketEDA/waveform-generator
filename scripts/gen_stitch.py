#!/usr/bin/env python3
"""Generate a Magic stitch test: digital macro + analog landing pads.

Reads pin geometry from the LibreLane LEF, computes met3 straps (plus
m2->m3 / m3->m4 vias for the top-edge pins) and writes results/stitch.tcl.
Units: Magic TYPED box coords are 100/um for this tech (verified: typed
14727 displays as 147.27 um; imported GDS geometry is 200/um, so every
emitted number is LEF_um * 100, NOT * 200).

Strategy that removes placement doubt: the macro instance is
origin-anchored (probe-verified identity transform), and the analog side
is paint + labels directly in the top cell — no second instance whose
anchoring could silently shift pins.

Python-side asserts guarantee overlap-with-own-pin and clearance-to-others
before Magic ever runs; Magic re-checks with full DRC.

Usage: python3 scripts/gen_stitch.py
Expects: runs/wave2/final/{gds,lef}/waveform_gen.{gds,lef}
Writes:  results/stitch.tcl
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEF = ROOT / "runs/wave2/final/lef/waveform_gen.lef"
GDS = ROOT / "runs/wave2/final/gds/waveform_gen.gds"
MACRO = "waveform_gen"
S = 100  # typed Magic units per micron (NOT the 200/um of .mag internals)
TOP_PINS = [f"dout[{i}]" for i in range(8)]
STUB_PINS = [f"b{i}" for i in range(8)]
MIN_CLEAR = 30  # 0.3 um, conservative vs 0.14 um met rules
STUB_X = 10000  # landing pads start at x = 100 um (typed units)
STUB_W = 230    # pad width: strap lands with 0.3 um east margin


def um2t(x):
    return int(round(x * S))


def parse_lef_pins(text):
    """name -> list of (layer, x0, y0, x1, y1 in um)."""
    pins = {}
    for m in re.finditer(r"^  PIN (\S+)\s*\n(.*?)^  END \1",
                         text, re.M | re.S):
        rects = re.findall(r"LAYER (\S+)\s*;\s*\n\s*RECT ([\d.]+) ([\d.]+)"
                           r" ([\d.]+) ([\d.]+)", m.group(2))
        pins[m.group(1)] = [(lay, float(x0), float(y0), float(x1), float(y1))
                             for lay, x0, y0, x1, y1 in rects]
    return pins


def rects_overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def rect_gap(a, b):
    dx = max(b[0] - a[2], a[0] - b[2], 0)
    dy = max(b[1] - a[3], a[1] - b[3], 0)
    return max(dx, dy)


def rect_inside(q, cover, margin=0):
    return (cover[0] + margin <= q[0] and cover[1] + margin <= q[1]
            and q[2] <= cover[2] - margin and q[3] <= cover[3] - margin)


def build_nets():
    """Parse LEF, compute + assert stitch geometry.
    Returns (nets, pin_db, pin_lay, others, mw, mh, dout) in typed units."""
    pins = parse_lef_pins(LEF.read_text())
    dout = {}
    for p in TOP_PINS:
        assert p in pins, f"LEF pin missing: {p}"
        assert len(pins[p]) == 1, f"{p} has {len(pins[p])} ports, need 1"
        dout[p] = pins[p][0]
    others = [(n, r) for n, rs in pins.items() if n not in TOP_PINS for r in rs]

    m = re.search(r"SIZE ([\d.]+) BY ([\d.]+)", LEF.read_text())
    mw, mh = um2t(float(m.group(1))), um2t(float(m.group(2)))

    pin_y = {p: (dout[p][2] + dout[p][4]) / 2 for p in TOP_PINS}
    # North channel slots for the top-edge pins (staggered, no crossings).
    chan = {"dout[4]": 88.0, "dout[5]": 86.5}
    slot = {p: (chan[p] if p in chan else pin_y[p]) for p in TOP_PINS}

    nets = {}
    for i, p in enumerate(TOP_PINS):
        lay, x0, y0, x1, y1 = dout[p]
        cx = (x0 + x1) / 2
        sy = slot[p]
        r, v = [], []
        if lay == "met3":
            r.append(("m3", (um2t(x0), um2t(sy) - 30,
                             STUB_X + STUB_W, um2t(sy) + 30)))
        else:
            assert lay == "met2", f"{p} on unexpected layer {lay}"
            vx, vy = um2t(cx), um2t(y0) + 25
            pad = (um2t(cx) - 25, um2t(y0) - 20,
                   um2t(cx) + 25, um2t(y1) + 20)
            r.append(("m2", pad))
            v.append(("m3c", (vx - 15, vy - 15, vx + 15, vy + 15)))
            nx0, nx1 = um2t(cx) - 30, um2t(cx) + 30
            if p == "dout[5]":
                r.append(("m3", (nx0, um2t(y0) - 10, nx1, um2t(86.8))))
                v.append(("m3c", (um2t(cx) - 15, um2t(86.5) - 15,
                                 um2t(cx) + 15, um2t(86.5) + 15)))
                # East jog on m2 (proven-empty sky; clearance check verifies).
                # (v3 never lands from Magic paint, so no met4 jog.)
                r.append(("m2", (nx0, um2t(86.5) - 30,
                                 STUB_X + STUB_W, um2t(86.5) + 30)))
                v.append(("m3c", (STUB_X + 170, um2t(86.5) - 15,
                                 STUB_X + 200, um2t(86.5) + 15)))
                r.append(("m3", (STUB_X, um2t(sy) - 30,
                                 STUB_X + STUB_W, um2t(sy) + 30)))
            else:
                nortop = um2t(sy) + 30
                r.append(("m3", (nx0, um2t(y0) - 10, nx1, nortop)))
                r.append(("m3", (nx0, um2t(sy) - 30,
                                 STUB_X + STUB_W, um2t(sy) + 30)))
        stub = (STUB_X, um2t(sy) - 30, STUB_X + STUB_W, um2t(sy) + 30)
        nets[STUB_PINS[i]] = (r, v, stub)

    # ---- asserts ----
    pin_db = {p: tuple(um2t(v) for v in dout[p][1:]) for p in TOP_PINS}
    pin_lay = {p: dout[p][0] for p in TOP_PINS}
    for i, p in enumerate(TOP_PINS):
        s = STUB_PINS[i]
        r, v, stub = nets[s]
        if pin_lay[p] == "met3":
            assert any(rects_overlap(q, pin_db[p])
                       for lay, q in r if lay == "m3"), \
                f"{s}: strap misses own pin"
        else:
            # met2 pin: pad must cover it.
            pad = [q for lay, q in r if lay == "m2"][0]
            assert rect_inside(pin_db[p], pad, 0), f"{s}: pad misses pin"
        for lay, q in r:
            metal = {"m2": "met2", "m3": "met3", "m4": "met4"}[lay]
            for on, ors in others:
                if ors[0] != metal:
                    continue
                g = rect_gap(q, tuple(um2t(z) for z in ors[1:]))
                assert g >= MIN_CLEAR, f"{s}: {lay} only {g}t from {on}"
        for j, p2 in enumerate(TOP_PINS):
            if j == i:
                continue
            for lay, q in r:
                for lay2, q2 in nets[STUB_PINS[j]][0]:
                    if lay != lay2:
                        continue
                    g = rect_gap(q, q2)
                    assert g >= MIN_CLEAR, \
                        f"{s} vs {STUB_PINS[j]}: {lay} gap {g}t"
        covers = {"m3c": ("m2", "m3")}
        pin_ml = {"met2": "m2", "met3": "m3", "met4": "m4"}[pin_lay[p]]
        for clay, q in v:
            for side in covers[clay]:
                cands = [c for lay, c in r if lay == side]
                if pin_ml == side:
                    cands.append(pin_db[p])
                assert any(rect_inside(q, c, 5) for c in cands), \
                    f"{s}: {clay} via lacks {side} enclosure"

    return nets, pin_db, pin_lay, others, mw, mh, dout


MLAYER = {"met1": "m1", "met2": "m2", "met3": "m3",
          "met4": "m4", "met5": "m5"}


def main():
    nets, _, _, others, mw, mh, dout = build_nets()
    # ---- emit Tcl (top cell holds macro instance + all stitch paint) ----
    t = ["# stitch.tcl — generated by scripts/gen_stitch.py. Do not hand-edit.",
         "# Typed box units are 100/um for this tech; macro instance is",
         "# origin-anchored (probe-verified identity transform).",
         "gds readonly true",
         f"gds read {GDS}",
         f"lef read {LEF}",
         "load stitch_top",
         "cellname",
         f"box 0 0 {mw} {mh}",
         f"getcell {MACRO}"]
    # Land every UNWIRED macro pin in top metal + label it: this is what
    # gives the extracted top a complete port list (needed for LVS/PEX).
    # Landings copy pin rects exactly, so they touch nothing foreign.
    # dout pins are skipped: already strapped to the b labels (a second
    # label would short two ports in LVS).
    for n, r in others:
        lay, x0, y0, x1, y1 = r
        if lay not in MLAYER:
            continue
        t.append(f"box {um2t(x0)} {um2t(y0)} {um2t(x1)} {um2t(y1)}")
        t.append(f"paint {MLAYER[lay]}")
        t.append(f"label {n}".replace("[", "\\[").replace("]", "\\]"))
    for i, s in enumerate(STUB_PINS):
        _, _, stub = nets[s]
        t.append(f"box {stub[0]} {stub[1]} {stub[2]} {stub[3]}")
        t.append("paint m3")
        t.append(f"label {s}")
    for s in STUB_PINS:
        r, v, _ = nets[s]
        for lay, q in r:
            t.append(f"box {q[0]} {q[1]} {q[2]} {q[3]}")
            t.append(f"paint {lay}")
        for clay, q in v:
            t.append(f"box {q[0]} {q[1]} {q[2]} {q[3]}")
            t.append(f"paint {clay}")
    t += ["select top cell",
          "save stitch_top",
          "drc euclidean on",
          "drc style drc(full)",
          "drc check",
          "drc catchup",
          "drc count total",
          f"gds write {ROOT}/results/stitched.gds"]
    out = ROOT / "results/stitch.tcl"
    out.write_text("\n".join(t) + "\n")
    print(f"wrote {out} ({len(t)} commands, 8 nets)")


if __name__ == "__main__":
    sys.exit(main())
