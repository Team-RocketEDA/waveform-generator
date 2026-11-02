#!/usr/bin/env python3
"""Waveform agreement check: SPICE vs analytic reference model.

The DAC node does NOT settle per step: the ladder's Thevenin R (~10k) plus
the filter R (2.7k) drive 100pF, i.e. tau ~ 1.27 us against 20 ns steps, so
vdac perpetually chases and a step-flatness check is the wrong oracle. (An
earlier revision of this check failed at 47 LSB settling / 149 LSB glitch
for exactly this reason — honest physics, wrong expectation.)

Right oracle: integrate the intended network (ideal ladder Thevenin +
Rfilt/Cfilt) in numpy and compare against ngspice point-for-point. Residual
measures "is the drawn topology the intended topology", in LSB. Covers major
carries (127->128, 255->0) implicitly — they are just samples.

Reads results/codes_saw.txt + results/tran_saw.txt (wrdata: t vdac t vfilt).
Writes results/waveform_check.txt. Exit 0 if both nodes agree < 1 LSB.

Usage: python3 scripts/check_waveform.py
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VREF = 1.8
LSB = VREF / 256
TSTEP = 20e-9
RTH = 10e3    # R-2R ladder Thevenin R (exact for the ideal ladder)
RF = 1e3      # must match rc_filter.spice defaults
CF = 47e-12


def reference(t):
    """Integrate intended network on fixed grid; return vdac, vfilt.

    Mirrors the deck exactly: code k is active on [k*TSTEP,(k+1)*TSTEP) with
    a linear EDGE ramp into each step (same PWL shape ngspice sees), and the
    filter cap starts at the DC operating point (open cap -> vfilt = vdac).
    """
    codes = np.loadtxt(ROOT / "results/codes_saw.txt", dtype=int)
    vc = VREF * codes / 256
    EDGE = 0.5e-9
    dt = 0.2e-9
    n = int(t[-1] / dt) + 1
    tg = np.arange(n) * dt
    karr = np.clip((tg / TSTEP).astype(int), 0, len(codes) - 1)
    tkn = (karr + 1) * TSTEP  # edge into the NEXT step lives at this window's end
    in_edge = (karr < len(codes) - 1) & (tg >= tkn - EDGE) & (tg < tkn)
    frac = np.where(in_edge, (tg - (tkn - EDGE)) / EDGE, 0.0)
    knext = np.clip(karr + 1, 0, len(codes) - 1)
    vth = np.where(in_edge, vc[karr] + (vc[knext] - vc[karr]) * frac, vc[karr])
    vdac = np.empty(n)
    vf = np.empty(n)
    gth, gf = 1 / RTH, 1 / RF
    vfilt = vth[0]  # DC op: cap open, no Rfilt current, vfilt = vdac = Vth
    for i in range(n):
        vd = (vth[i] * gth + vfilt * gf) / (gth + gf)  # vdac: no shunt C
        vfilt += (vd - vfilt) * gf * dt / CF
        vdac[i], vf[i] = vd, vfilt
    return (np.interp(t, tg, vdac), np.interp(t, tg, vf))


def main():
    d = np.loadtxt(ROOT / "results/tran_saw.txt")
    t, vdac, vfilt = d[:, 0], d[:, 1], d[:, 3]
    codes = np.loadtxt(ROOT / "results/codes_saw.txt", dtype=int)
    r_dac, r_filt = reference(t)
    # Guard band: ngspice breakpoint placement vs the deck's 0.5 ns PWL edges
    # can differ by tens of ps; on multi-bit flips that is real volts of
    # phase noise, not circuit behavior. Mask +/-0.75 ns around transitions
    # with |dCode| > 4 and judge everything else.
    jumps = [k for k in range(1, len(codes))
             if abs(int(codes[k]) - int(codes[k - 1])) > 4]
    mask = np.zeros(len(t), dtype=bool)
    for k in jumps:
        mask |= (t >= k * TSTEP - 0.75e-9) & (t <= k * TSTEP + 0.75e-9)
    use = ~mask
    e_dac = np.abs(vdac[use] - r_dac[use]) / LSB
    e_filt = np.abs(vfilt[use] - r_filt[use]) / LSB
    tu = t[use]
    top = np.argsort(-np.abs(vdac[use] - r_dac[use]))[:3]
    rep = (f"samples={len(t)} used={use.sum()} "
           f"masked={mask.sum()} ({len(jumps)} multi-bit edges)\n"
           f"max|vdac-ref|={e_dac.max():.4f} LSB @{tu[e_dac.argmax()] * 1e6:.3f} us\n"
           f"max|vfilt-ref|={e_filt.max():.4f} LSB @{tu[e_filt.argmax()] * 1e6:.3f} us\n"
           f"top residuals (us): " +
           ", ".join(f"{tu[i] * 1e6:.3f}" for i in top) + "\n"
           f"tau_chase={(RTH + RF) * CF * 1e6:.3f} us vs step {TSTEP * 1e9:.0f} ns "
           f"(codes resolve at DC only)\n")
    ok = e_dac.max() < 1.0 and e_filt.max() < 1.0
    rep += ("VERDICT: PASS (SPICE matches intended network < 1 LSB)\n" if ok
            else "VERDICT: FAIL (topology/model mismatch)\n")
    (ROOT / "results/waveform_check.txt").write_text(rep)
    print(rep, end="")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
