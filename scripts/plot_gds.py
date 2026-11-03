#!/usr/bin/env python3
"""Render a GDS top cell to PNG with klayout.db + matplotlib (no GUI needed).

Usage: venv_python scripts/plot_gds.py <gds> [top] [out.png]
Defaults: top = GDS top cell, out = results/<stem>.png.
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from klayout import db

ROOT = Path(__file__).resolve().parents[1]


def main():
    gds = Path(sys.argv[1])
    ly = db.Layout()
    ly.read(str(gds))
    top = sys.argv[2] if len(sys.argv) > 2 else None
    cell = ly.top_cell() if top is None else ly.cell(top)
    # Descend hierarchy: top-cell-only drawing renders macro children as
    # empty outlines (46k shapes hide one level down in stitch_top).
    # In-memory only; the GDS on disk is untouched.
    cell.flatten(-1, True)
    out = Path(sys.argv[3]) if len(sys.argv) > 3 else \
        ROOT / f"results/{gds.stem}.png"

    dbu = ly.dbu
    seen = set()
    for li in ly.layer_indexes():
        info = ly.get_info(li)
        for _ in cell.each_shape(li):
            seen.add((info.layer, info.datatype))
            break
    layers = sorted(seen)
    cmap = plt.get_cmap("tab20")
    fig, ax = plt.subplots(figsize=(10, 10))
    for k, (ln, dt) in enumerate(layers):
        li = ly.layer(ln, dt)
        color = cmap(k % 20)
        first = True
        for sh in cell.each_shape(li):
            pts = None
            if sh.is_box():
                b = sh.box
                pts = [(b.left, b.bottom), (b.right, b.bottom),
                       (b.right, b.top), (b.left, b.top)]
            elif sh.is_polygon() or sh.is_path():
                pts = [(p.x, p.y) for p in sh.polygon.each_point_hull()]
            if pts:
                poly = [(x * dbu, y * dbu) for x, y in pts]
                ax.add_patch(Polygon(poly, closed=True, facecolor=color,
                                     edgecolor="none", alpha=0.55,
                                     label=f"{ln}/{dt}" if first else None))
                first = False
    # Instances (macro children) as outlines.
    for inst in cell.each_inst():
        b = inst.bbox()
        x0, y0 = b.left * dbu, b.bottom * dbu
        x1, y1 = b.right * dbu, b.top * dbu
        ax.plot([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0],
                color="black", lw=1.2)
        ax.text(x0, y1, inst.cell.name, fontsize=7)
    bb = cell.bbox()
    ax.set(xlim=(bb.left * dbu, bb.right * dbu),
           ylim=(bb.bottom * dbu, bb.top * dbu), aspect="equal",
           xlabel="um", ylabel="um",
           title=f"{cell.name}  ({(bb.right-bb.left)*dbu:.1f} x "
                 f"{(bb.top-bb.bottom)*dbu:.1f} um, {len(layers)} layers)")
    ax.legend(fontsize=6, ncol=2, loc="upper right")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
