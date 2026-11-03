"""Render a placement-faithful map of an xschem .sch (instances + wires).

Headless stand-in for a GUI screenshot: parses C/N records and draws every
instance at its true schematic coordinate, colored by device kind. Open the
same .sch in xschem to inspect/zoom the real thing (see ./xschemrc).

Usage: python3 scripts/plot_schematic.py <in.sch> <out.png>
"""
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

KIND = [
    ("nfet_01v8", "tab:blue", "N"),
    ("pfet_01v8", "tab:red", "P"),
    ("res_high_po", "tab:orange", "R"),
    ("cap_mim_m3_1", "tab:green", "C"),
    ("lab_pin", "tab:purple", "L"),
    ("ipin", "black", "in"),
    ("opin", "black", "out"),
]

sch, out = sys.argv[1], sys.argv[2]
inst, wires = [], []
pending = None  # wire record continued on the next line: `N x1 y1 x2 y2 {` + `lab=..}`
for raw in open(sch):
    line = raw.rstrip("\n")
    if pending is not None:
        lab = line.strip().rstrip("}")
        wires.append((*pending, lab))
        pending = None
        continue
    m = re.match(r"C \{([^}]*)\} (\S+) (\S+) \d \d \{(.*)\}", line)
    if m:
        sym, x, y, attrs = m.group(1), float(m.group(2)), float(m.group(3)), m.group(4)
        nm = re.search(r"name=(\S+)", attrs)
        inst.append((sym, x, y, nm.group(1) if nm else "?"))
        continue
    m = re.match(r"N (\S+) (\S+) (\S+) (\S+) \{$", line)
    if m:
        pending = tuple(float(m.group(i)) for i in range(1, 5))
        continue
    m = re.match(r"N (\S+) (\S+) (\S+) (\S+) \{(.*)\}", line)
    if m:
        wires.append(tuple(float(m.group(i)) for i in range(1, 5)) + (m.group(5),))

fig, ax = plt.subplots(figsize=(14, 8))
for x1, y1, x2, y2, lab in wires:
    ax.plot([x1, x2], [-y1, -y2], color="0.45", lw=0.6)
for sym, x, y, nm in inst:
    for key, color, tag in KIND:
        if key in sym:
            break
    else:
        color, tag = "gray", "?"
    w = 60 if "lab_pin" not in sym and "pin" not in sym else 30
    ax.add_patch(Rectangle((x - w / 2, -y - 15), w, 30, fc=color, alpha=0.75,
                           ec="black", lw=0.4))
    if "pin" not in sym:
        ax.text(x, -y, f"{tag}:{nm}", ha="center", va="center", fontsize=3.5,
                color="white", weight="bold")
    else:
        labm = re.search(r"lab=(\S+)", nm)
        ax.text(x, -y - 22, labm.group(1) if labm else nm, ha="center",
                va="top", fontsize=4, color="black")
xs = [x for _, x, _, _ in inst] + [v for w in wires for v in (w[0], w[2])]
ys = [-y for _, _, y, _ in inst] + [-w[1] for w in wires] + [-w[3] for w in wires]
ax.set_xlim(min(xs) - 80, max(xs) + 80)
ax.set_ylim(min(ys) - 80, max(ys) + 80)
ax.set_aspect("equal")
ax.set_title(f"{sch} — {len(inst)} instances, {len(wires)} wires "
             "(rendered headless from .sch database; open in xschem to inspect)")
ax.set_xlabel("schematic x")
ax.set_ylabel("schematic y")
fig.savefig(out, dpi=130, bbox_inches="tight")
print(f"wrote {out}")
