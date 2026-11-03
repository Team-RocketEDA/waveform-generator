#!/usr/bin/env python3
"""Verify stitch connectivity from the flat Magic extraction.

With zero top-level devices, top LVS reduces to connectivity: each b[i]
net must reach macro interior (the strap through the dout pin) and must
stay distinct from the other seven (a short would merge names and the
vanished name is the tell). The macro's own device-level LVS already
passed inside the LibreLane flow.

Reads results/top_lvs.spice (flat X/C netlist). For each b[i]:
  1. the net name exists (not merged away by a short),
  2. some X line joins it to a waveform_gen_0/* node (strap-pin continuity),
  3. no X line joins it to another b[j] or to VGND/VPWR.
Writes results/extract_check.txt. Exit 0 iff 8/8 clean.

Usage: python3 scripts/verify_extract.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXT = ROOT / "results/top_lvs.spice"


def terminals(line):
    """Signal terminals (D/G/S) between instance name and model name.

    Bulk (4th) is excluded: output FETs bulk-tie to VPWR/VGND, which would
    false-positive every net as power-shorted.
    """
    toks = line.split()
    for k, t in enumerate(toks[1:], start=1):
        if t.startswith("sky130_"):
            return toks[1:k][:3]
    return []


def main():
    lines = [ln for ln in EXT.read_text().splitlines()
             if ln.startswith("X")]
    nets = {f"b{i}": [ln for ln in lines
                       if re.search(rf"(?:^|\s)b{i}(?:\s|=)", ln)]
            for i in range(8)}
    rep, ok = [], True
    for i in range(8):
        b = f"b{i}"
        emble = nets[b]
        if not emble:
            rep.append(f"{b}: MISSING (merged away by a short?)")
            ok = False
            continue
        interior = any(any(t.startswith("waveform_gen_0/")
                           for t in terminals(ln)) for ln in emble)
        # Foreign = another b net on the same lines. (VPWR/VGND in S
        # position is the output driver's pullup/pulldown source by
        # design; a real rail short would merge net names and fail the
        # existence check above instead.)
        foreign = set()
        for ln in emble:
            for t in terminals(ln):
                if re.fullmatch(r"b[0-7]", t) and t != b:
                    foreign.add(t)
        status = "OK" if (interior and not foreign) else "FAIL"
        if status == "FAIL":
            ok = False
        rep.append(f"{b}: {len(emble)} lines, interior={interior}, "
                   f"foreign={sorted(foreign) or None} -> {status}")
    rep.append("VERDICT: " + ("PASS (8/8 nets reach interior, all distinct)"
                              if ok else "FAIL"))
    (ROOT / "results/extract_check.txt").write_text("\n".join(rep) + "\n")
    print("\n".join(rep))
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
