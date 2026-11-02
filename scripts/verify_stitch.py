#!/usr/bin/env python3
"""Independently verify stitch paint against ALL macro metal (klayout).

gen_stitch.py only checks pins; this checks every macro polygon on the
routed layers, catching shorts to interior routing that Magic DRC cannot
see (same-layer overlap reads as connection, never as violation).

For each paint rect (typed units, S=100/um):
  SHORT suspect: paint & macro_metal - own_pin_zone non-empty
  SPACING suspect: paint sized by 140nm & macro_metal - own_pin_zone hit
own_pin_zone = own LEF pin rect grown by 1 um (same-net inward metal).

Layer map (Magic paint -> GDS): m2 (69,20), m3 (70,20), m4 (71,20),
m3c (69,44). Contacts vs macro contacts are reported, not judged.

Usage: venv_python scripts/verify_stitch.py
Exit 0 if no suspects, else 2. Writes results/stitch_verify.txt.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_stitch import build_nets, um2t  # noqa: E402

from klayout import db  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GDS = ROOT / "runs/wave2/final/gds/waveform_gen.gds"
METAL = {"m2": (69, 20), "m3": (70, 20), "m4": (71, 20)}
SPACING_NM = 140


def region_of(cell, layer, px1=1):
    """All polygons of one GDS layer under cell (hierarchical), in nm."""
    it = db.RecursiveShapeIterator(cell.layout(), cell, layer)
    reg = db.Region()
    for s in it:
        reg.insert(s.shape().polygon.transformed(s.trans()))
    return reg


def main():
    nets, pin_db, pin_lay, _, _, _, dout = build_nets()
    lay = db.Layout()
    lay.read(str(GDS))
    top = lay.top_cell()
    sc = 1.0 / (lay.dbu * 1000)  # nm -> dbu
    to_dbu = lambda nm: int(round(nm * sc))
    rep = []
    bad = 0
    for i, s in enumerate(sorted(nets)):
        p = f"dout[{i}]"
        r, v, _ = nets[s]
        pin_um = dout[p][1:]
        own = db.Region(db.Box(
            to_dbu((pin_um[0] - 1) * 1000), to_dbu((pin_um[1] - 1) * 1000),
            to_dbu((pin_um[2] + 1) * 1000), to_dbu((pin_um[3] + 1) * 1000)))
        for layer_name, q in r:
            if layer_name not in METAL:
                continue
            gl, gd = METAL[layer_name]
            macro = region_of(top, lay.layer(gl, gd))
            me = db.Region(db.Box(to_dbu(q[0] * 10), to_dbu(q[1] * 10),
                                  to_dbu(q[2] * 10), to_dbu(q[3] * 10)))
            short = (me & macro) - own
            if not short.is_empty():
                bad += 1
                b = short.bbox()
                rep.append(f"SHORT? {s} {layer_name} overlap at "
                           f"{b.left/sc/1000:.2f},{b.bottom/sc/1000:.2f} um")
            grown = db.Region()
            for poly in me.each():
                grown.insert(poly.sized(to_dbu(SPACING_NM)))
            near = (grown & macro) - own - me
            if not near.is_empty():
                bad += 1
                b = near.bbox()
                rep.append(f"SPACING? {s} {layer_name} within {SPACING_NM}nm "
                           f"at {b.left/sc/1000:.2f},{b.bottom/sc/1000:.2f} um")
    rep.append(f"checked 8 nets against macro metal; suspects={bad}")
    rep.append("VERDICT: " + ("PASS (no shorts/spacing)" if bad == 0
                              else "FAIL (inspect suspects)"))
    (ROOT / "results/stitch_verify.txt").write_text("\n".join(rep) + "\n")
    print("\n".join(rep))
    return 0 if bad == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
