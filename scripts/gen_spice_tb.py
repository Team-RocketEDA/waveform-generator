#!/usr/bin/env python3
"""Generate an RTL-driven ngspice tran deck from a code stream.

Reads results/codes_<mode>.txt (one decimal code per line, written by the
Icarus TB) and writes results/tb_tran_<mode>.spice: the static assembly
(design/analog/wave_top.spice) plus 8 ideal PWL bit sources (0 / 1.8 V)
with 0.5 ns edges on a 20 ns update period (50 MHz, canvas clock target),
then .tran + wrdata.

Deck layout mirrors the engine ngspice adapter contract: title, preamble,
netlist bodies, generated .control, bare .end (no stray .end inside bodies).

Usage: python3 scripts/gen_spice_tb.py [mode]  (default: sine)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VREF = 1.8
TSTEP = 20e-9
EDGE = 0.5e-9


def bit_pwl(codes, bit):
    """PWL (t, v) points for one bit with EDGE-wide transitions."""
    pts = [(0.0, VREF if (codes[0] >> bit) & 1 else 0.0)]
    for k in range(1, len(codes)):
        t = k * TSTEP
        vprev = VREF if (codes[k - 1] >> bit) & 1 else 0.0
        vnew = VREF if (codes[k] >> bit) & 1 else 0.0
        if vnew != vprev:
            pts.append((t - EDGE, vprev))
            pts.append((t, vnew))
    pts.append((len(codes) * TSTEP, VREF if (codes[-1] >> bit) & 1 else 0.0))
    return pts


def main(mode):
    codes = [int(x) for x in (ROOT / f"results/codes_{mode}.txt").read_text().split()]
    n = len(codes)
    lines = [f"* tb_tran_{mode}: RTL-driven wave_top tran ({n} codes, 50 MHz update)",
             ".include design/analog/wave_top.spice"]
    for b in range(7, -1, -1):
        pairs = " ".join(f"{t:.9g} {v:.3f}" for t, v in bit_pwl(codes, b))
        lines.append(f"Vb{b} b{b} 0 PWL({pairs})")
    lines += ["",
              ".control",
              "option noinit",
              f"tran 100p {n * TSTEP:.9g}",
              f"wrdata results/tran_{mode}.txt v(vdac) v(vfilt)",
              ".endc",
              ".end",
              ""]
    out = ROOT / f"results/tb_tran_{mode}.spice"
    out.write_text("\n".join(lines))
    print(f"wrote {out} ({n} codes, {n * TSTEP * 1e6:.2f} us span)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sine")
