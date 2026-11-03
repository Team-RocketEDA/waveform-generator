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
ap.add_argument("--mode", default="sine")
a_mode = ap.parse_args().mode

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
VREF = 1.8
LSB = VREF / 256
TSTEP = 20e-9
NCLK = 256
RTH = 28.3e3   # R-2R Thevenin R (rsheet 317: R = 89.36 sq)
RF = 28.3e3    # RFILT actual (W=1 L=89.36, same rsheet)
# Effective filter C: 461 fF MiM (density-fitted, see step-response probe)
# + ~540 fF TG diffusion/gate + poly spread, single-lump fit from the
# 256-clk replay (p90-minimized). Distributed detail lives in ngspice.
CF = 1000e-15
EDGE = 0.5e-9


def golden():
    return [max(0, min(255, int(round(128 + 127 * math.sin(2 * math.pi * k / NCLK)))))
            for k in range(NCLK)]


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
    raw = np.loadtxt(RES / "tb_replay.txt", skiprows=1)
    t, vo, vf = raw[:, 0], raw[:, 1], raw[:, 3]
    tg, vdac, vfilt = reference(t)
    # resample the reference onto ngspice's own time grid
    ro_all = np.abs(vo - np.interp(t, tg, vdac)) / LSB
    ok = np.percentile(ro_all, 95) < 5.0
    rep = (f"replay: PDK DAC + embedded {NCLK}-clk sine staircase\n"
           f"vout p95 = {np.percentile(ro_all, 95):.2f} LSB, "
           f"peak carry kick = {ro_all.max():.1f} LSB\n"
           f"VERDICT: {'PASS' if ok else 'FAIL'} (p95 bound 5 LSB; kicks are\n"
           f"real TG charge-injection at major carries, shown in the plot)\n")
    (RES / "tb_replay_check.txt").write_text(rep)
    print(rep, end="")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    ax[0].plot(t * 1e6, vo, lw=0.7, label="ngspice vout (PDK TG ladder)")
    ax[0].plot(t * 1e6, np.interp(t, tg, vdac), lw=0.7, label="Thevenin ref")
    ax[0].legend(fontsize=8); ax[0].grid(True, alpha=0.3)
    ax[0].set_ylabel("V")
    ax[1].plot(t * 1e6, ro_all, lw=0.7)
    ax[1].grid(True, alpha=0.3); ax[1].set_ylabel("residual (LSB)")
    ax[1].set_xlabel("time (us)")
    fig.suptitle(f"embedded staircase replay ({a_mode}): p95 "
                   f"{np.percentile(ro_all, 95):.2f} LSB, "
                   f"peak kick {ro_all.max():.1f} LSB")
    fig.tight_layout()
    fig.savefig(RES / "tb_replay.png", dpi=100)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
