#!/usr/bin/env python3
"""xschem short-circuit checker: parse N-record wires from a .sch and flag
every endpoint-touch or collinear overlap between wires carrying DIFFERENT
wire labs (design intent). Pure X-crossings (midpoint/midpoint, no endpoint
involved) are safe in xschem and not flagged.

This catches the classic generator bug: a supply tap routed at a row that
coincides with another stage's jog/drop endpoints (e.g. RTERM vgnd tap at
y=1355 through stage 0's b_n jog endpoints -> whole-net merge).

Caveat: wire labs are INTENT here (the SPICE netlister ignores bare wire
labs for naming; pins/lab_pins name nets). A flagged touch is guilty only
if the two fragments also merge in the netlist - but any flag deserves a
look, since same-lab overlaps are always harmless.

Usage: python3 scripts/xschem_touchcheck.py <file.sch>
Exits nonzero with the flag list when any cross-label touch exists.
"""
import re
import sys
from pathlib import Path


def parse(sch):
    segs = []
    lines = Path(sch).read_text().split("\n")
    i = 0
    while i < len(lines):
        m = re.match(r"^N (\S+) (\S+) (\S+) (\S+) \{$", lines[i])
        if m:
            lab = ""
            if i + 1 < len(lines):
                lm = re.match(r"^lab=(.+)\}$", lines[i + 1])
                if lm:
                    lab = lm.group(1)
            segs.append(tuple(map(float, m.groups())) + (lab,))
            i += 2
            continue
        # single-line form `N x1 y1 x2 y2 {lab=X}` (what gen_tb_sch.py emits)
        m = re.match(r"^N (\S+) (\S+) (\S+) (\S+) \{(.*)\}$", lines[i])
        if m:
            lab = m.group(5)
            if lab.startswith("lab="):
                lab = lab[4:]
            segs.append(tuple(map(float, m.groups()[:4])) + (lab,))
            i += 1
        else:
            i += 1
    return segs


def touches(a, b):
    (x1, y1, x2, y2, _), (x3, y3, x4, y4, _) = a, b
    for (px, py) in [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]:
        on_a = min(x1, x2) - 1e-9 <= px <= max(x1, x2) + 1e-9 and \
            min(y1, y2) - 1e-9 <= py <= max(y1, y2) + 1e-9
        on_b = min(x3, x4) - 1e-9 <= px <= max(x3, x4) + 1e-9 and \
            min(y3, y4) - 1e-9 <= py <= max(y3, y4) + 1e-9
        if on_a and on_b and (px, py) in [(x1, y1), (x2, y2),
                                          (x3, y3), (x4, y4)]:
            return True  # endpoint-involved: T or pileup (X excluded)
    for horiz in (True, False):
        c1, c2 = (y1, y3) if horiz else (x1, x3)
        v1, v2 = (x1, x3) if horiz else (y1, y3)
        w1, w2 = (x2, x4) if horiz else (y2, y4)
        if c1 == c2:
            lo = max(min(v1, w1), min(v2, w2))
            hi = min(max(v1, w1), max(v2, w2))
            if hi > lo:
                return True
    return False


def main():
    segs = parse(sys.argv[1])
    flags = []
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            if segs[i][4] != segs[j][4] and touches(segs[i], segs[j]):
                flags.append((segs[i], segs[j]))
    # unlabeled stubs (lab '') touching a labeled net are joins, not shorts
    flags = [f for f in flags if f[0][4] and f[1][4]]
    for a, b in flags:
        print(f"SHORT? {a[4]} x {b[4]}: {a[:4]} / {b[:4]}")
    print(f"{len(segs)} wires, {len(flags)} cross-label touches -> "
          f"{'FAIL' if flags else 'PASS'}")
    sys.exit(1 if flags else 0)


if __name__ == "__main__":
    main()
