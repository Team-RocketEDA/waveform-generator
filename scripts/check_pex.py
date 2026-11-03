#!/usr/bin/env python3
"""Check full-period PEX sim outputs (results/pex_raw_<mode>.txt from
tb_pex_<mode>.spice, ~262 clocks each) against the RTL golden code files
(results/codes_<mode>.txt, 256 codes/mode from the Icarus TB).

Thresholds b[7:0] at 0.9V, samples near each window end, searches clock
shift 0..4 for the best 256-code alignment, requires 256/256 per mode.

Usage: MPLCONFIGDIR=/tmp <venv>/bin/python scripts/check_pex.py [--modes sine,saw,tri]
Writes results/pex_check.txt + results/pex_wave.png, exits nonzero on FAIL.
"""
import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
TPER = 20e-9
MODES = ["sine", "saw", "tri"]

ap = argparse.ArgumentParser()
ap.add_argument("--modes", default=",".join(MODES))
a = ap.parse_args()
modes = [m for m in a.modes.split(",") if m in MODES]

fig, axes = plt.subplots(len(modes), 1, figsize=(10, 3 * len(modes)),
                         sharex=True)
if len(modes) == 1:
    axes = [axes]
rep, ok = [], True
for ax, mode in zip(axes, modes):
    golden = np.array([int(x) for x in
                       (RES / f"codes_{mode}.txt").read_text().split()],
                      dtype=float)
    assert len(golden) == 256, f"{mode}: {len(golden)} golden codes"
    raw = np.loadtxt(RES / f"pex_raw_{mode}.txt", skiprows=1)
    t = raw[:, 0]
    bits = np.array([raw[:, 2 * i + 1] > 0.9 for i in range(8)]).T  # b7..b0
    codes = (bits * (128 >> np.arange(8))).sum(axis=1)
    # skip reset + stale windows, then cover a full 256 period + margin
    samp = np.array([codes[min(np.searchsorted(t, (k + 0.95) * TPER), len(t) - 1)]
                     for k in range(3, 263)])
    # golden is one 256-code period; shift search wraps modulo the period
    best = max(range(5),
               key=lambda s: sum(samp[k] == golden[(k + s) % 256]
                                 for k in range(256)))
    match = sum(samp[k] == golden[(k + best) % 256] for k in range(256))
    verdict = "PASS" if match == 256 else "FAIL"
    ok &= verdict == "PASS"
    rep.append(f"{mode}: shift {best}, {match}/256 -> {verdict}")
    gext = np.concatenate([golden, golden[:4]])
    ax.step(np.arange(256), samp[:256], where="post", label=f"PEX b[7:0]")
    ax.step(np.arange(256), gext[best:best + 256], where="post",
            linestyle="--", label=f"RTL golden (shift {best})")
    ax.set_ylabel("dout code")
    ax.set_title(f"{mode}: {match}/256 -> {verdict}")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(True, alpha=0.3)
axes[-1].set_xlabel("clock (one full 256-code period)")
fig.suptitle("PEX extracted-GDS vs RTL golden, full period per mode")
fig.tight_layout()
fig.savefig(RES / "pex_wave.png", dpi=100)

verdict = "PASS" if ok else "FAIL"
rep.append(f"VERDICT: {verdict}")
(RES / "pex_check.txt").write_text(
    f"pex full-period: extracted stitch_top, step=1, 262 clocks/mode\n"
    + "\n".join(rep) + "\n")
print(open(RES / "pex_check.txt").read())
sys.exit(0 if ok else 1)
