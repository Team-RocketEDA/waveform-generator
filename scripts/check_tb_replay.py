#!/usr/bin/env python3
"""Replay agreement check: embedded-stimulus transient vs analytic reference.

The DAC node does NOT settle per step: the PDK ladder Thevenin R (~28.3k)
plus RFILT (~28.3k) drive 470 fF, i.e. tau ~ 13 ns against 20 ns steps, so
vout perpetually chases and a step-flatness check is the wrong oracle.

Right oracle (same method as scripts/check_waveform.py): integrate the
intended network (ideal ladder Thevenin + Rfilt/Cfilt) in numpy and compare
against ngspice point-for-point. Residual measures "is the drawn topology
the intended topology", in LSB.

Reads results/tb_replay.txt (wrdata: t vout t vfilt) and the sine golden
formula (must match scripts/gen_tb_sch.py --mode sine).
Writes results/tb_replay_check.txt. Exit 0 if both nodes agree < 2 LSB
(room above the 1 LSB static bound for TG charge-injection kicks).
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--mode", default="sine", choices=["sine", "saw", "tri"])
ap.add_argument("--replay", default=None,
                help="replay txt (default results/tb_replay_<mode>.txt)")
args = ap.parse_args()
a_mode = args.mode

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
VREF = 1.8
LSB = VREF / 256
TSTEP = 20e-9
NCLK = 256
RTH = 28.3e3   # R-2R Thevenin R (rsheet 317: R = 89.36 sq)
RF = 28.3e3    # RFILT actual (W=1 L=89.36, same rsheet)
# FIXED model-value filter C: 450 fF area (2.00 fF/um2 x 15 x 15) + 11 fF
# perimeter from the PDK mimcap model. No fitting: TG diffusion/gate/poly
# spread stays unmodeled, so carries show honest residual. Scored per node.
CF = 470e-15
EDGE = 0.5e-9


def golden(mode=None):
    mode = mode or a_mode
    out = []
    for k in range(NCLK):
        if mode == "sine":
            v = int(round(128 + 127 * math.sin(2 * math.pi * k / NCLK)))
            out.append(max(0, min(255, v)))
        elif mode == "saw":
            out.append(k % 256)
        else:
            ph = k % 256
            out.append(2 * ph if ph < 128 else 511 - 2 * ph)
    return out


def reference(t):
    codes = np.array(golden())
    vc = VREF * codes / 256
    dt = 0.2e-9
    n = int(t[-1] / dt) + 1
    tg = np.arange(n) * dt
    karr = np.clip((tg / TSTEP).astype(int), 0, len(codes) - 1)
    tkn = (karr + 1) * TSTEP
    in_edge = (karr < len(codes) - 1) & (tg >= tkn - EDGE) & (tg < tkn)
    frac = np.where(in_edge, (tg - (tkn - EDGE)) / EDGE, 0.0)
    knext = np.clip(karr + 1, 0, len(codes) - 1)
    vth = np.where(in_edge, vc[karr] + (vc[knext] - vc[karr]) * frac, vc[karr])
    vdac = np.empty(n)
    vf = np.empty(n)
    gth, gf = 1 / RTH, 1 / RF
    vfilt = vth[0]
    for i in range(n):
        vd = (vth[i] * gth + vfilt * gf) / (gth + gf)
        vfilt += (vd - vfilt) * gf * dt / CF
        vdac[i], vf[i] = vd, vfilt
    return tg, vdac, vf


def main():
    rep_path = Path(args.replay) if args.replay else RES / f"tb_replay_{a_mode}.txt"
    raw = np.loadtxt(rep_path, skiprows=1)
    t, vo, vf = raw[:, 0], raw[:, 1], raw[:, 3]
    tg, vdac, vfilt = reference(t)
    # resample the reference onto ngspice's own time grid; score nodes apart
    ro_all = np.abs(vo - np.interp(t, tg, vdac)) / LSB
    rf_all = np.abs(vf - np.interp(t, tg, vfilt)) / LSB
    ok = np.percentile(ro_all, 95) < 5.0 and np.percentile(rf_all, 95) < 5.0
    rep = (f"replay: PDK DAC + embedded {NCLK}-clk {a_mode} staircase\n"
           f"vout: p95 = {np.percentile(ro_all, 95):.2f} LSB, "
           f"peak = {ro_all.max():.1f} LSB\n"
           f"vfilt: p95 = {np.percentile(rf_all, 95):.2f} LSB, "
           f"peak = {rf_all.max():.1f} LSB\n"
           f"VERDICT: {'PASS' if ok else 'FAIL'} (per-node p95 bound 5 LSB,\n"
           f"fixed 470 fF oracle; kicks are real TG charge-injection)\n")
    (RES / f"tb_replay_check_{a_mode}.txt").write_text(rep)
    print(rep, end="")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    ax[0].plot(t * 1e6, vo, lw=0.7, label="ngspice vout (PDK TG ladder)")
    ax[0].plot(t * 1e6, np.interp(t, tg, vdac), lw=0.7, label="Thevenin ref")
    ax[0].plot(t * 1e6, vf, lw=0.7, label="ngspice vfilt")
    ax[0].plot(t * 1e6, np.interp(t, tg, vfilt), lw=0.7, label="vfilt ref")
    ax[0].legend(fontsize=8); ax[0].grid(True, alpha=0.3)
    ax[0].set_ylabel("V")
    ax[1].plot(t * 1e6, ro_all, lw=0.7, label="vout")
    ax[1].plot(t * 1e6, rf_all, lw=0.7, label="vfilt")
    ax[1].legend(fontsize=8)
    ax[1].grid(True, alpha=0.3); ax[1].set_ylabel("residual (LSB)")
    ax[1].set_xlabel("time (us)")
    fig.suptitle(f"embedded staircase replay ({a_mode}): per-node vs "
                 f"fixed-470fF oracle")
    fig.tight_layout()
    fig.savefig(RES / f"tb_replay_{a_mode}.png", dpi=100)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
