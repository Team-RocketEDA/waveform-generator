#!/usr/bin/env python3
"""Check PEX sim output (results/pex_raw.txt from tb_pex.spice, b[7:0]) against the
RTL golden sine codes: threshold dout pins at 0.9V, find best clock shift in
0..2, require 20/20 consecutive matches.

Usage: MPLCONFIGDIR=/tmp <venv>/bin/python scripts/check_pex.py
Writes results/pex_check.txt + results/pex_wave.png, exits nonzero on FAIL.
"""
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
NCLK, TPER = 24, 20e-9

body = (ROOT / "design/digital/sine_rom.v").read_text()
lut = sorted((int(a), int(b, 16))
             for a, b in re.findall(r"8'd(\d+):\s*dout\s*=\s*8'h([0-9A-Fa-f]{2})", body))
golden = np.array([v for _, v in lut], dtype=float)

# wr_vecnames writes a "time v(..) ..." header line above the data
raw = np.loadtxt(RES / "pex_raw.txt", skiprows=1)
# wrdata with 8 vectors writes 16 cols (t,v per vector); times identical
t = raw[:, 0]
# wrdata emits time,v per vector -> cols 0,2,4..; vectors dumped b7..b0
bits = np.array([raw[:, 2 * i + 1] > 0.9 for i in range(8)]).T  # b7..b0
codes = (bits * (128 >> np.arange(8))).sum(axis=1)

# sample near end of each clock window: skip reset (releases 41ns) + the first
# stale window, since the first active edge lands at ~60ns
samp = np.array([codes[min(np.searchsorted(t, (k + 0.95) * TPER), len(t) - 1)]
                     for k in range(3, NCLK + 1)])

best = max(range(3), key=lambda s: sum(samp[k] == golden[k + s] for k in range(20)))
match = sum(samp[k] == golden[k + best] for k in range(20))
verdict = "PASS" if match == 20 else "FAIL"

fig, ax = plt.subplots(figsize=(10, 3.5))
ax.step(np.arange(20), samp[:20], where="post", label="PEX b[7:0]")
ax.step(np.arange(20), golden[best:best + 20], where="post",
        linestyle="--", label=f"RTL golden (shift {best})")
ax.set_xlabel("clock"); ax.set_ylabel("dout code")
ax.set_title(f"PEX vs RTL sine codes: {match}/20 match -> {verdict}")
ax.legend(); ax.grid(True, alpha=0.3)
fig.tight_layout(); fig.savefig(RES / "pex_wave.png", dpi=100)

(RES / "pex_check.txt").write_text(
    f"pex: extracted stitch_top (3224 FETs, 88 node caps), sine step=1\n"
    f"best shift: {best} clocks, matches: {match}/20 -> {verdict}\n"
    f"sampled: {' '.join(f'{int(c):02x}' for c in samp[:20])}\n"
    f"golden : {' '.join(f'{int(c):02x}' for c in golden[best:best+20])}\n")
print(open(RES / "pex_check.txt").read())
sys.exit(0 if verdict == "PASS" else 1)
