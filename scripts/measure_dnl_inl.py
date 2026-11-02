#!/usr/bin/env python3
"""DC code sweep: measure the R-2R DAC transfer curve, compute DNL/INL.

For each code 0..255 writes a DC deck (ideal bit sources + wave_top
assembly, .op + print), runs `ngspice -b`, parses v(vdac) from stdout,
then endpoint-fits LSB from codes 0/255 and reports:
  DNL[k] = (V[k+1]-V[k])/LSB - 1,  INL[k] = (V[k]-Videal[k])/LSB.
Writes results/dc_sweep.txt (code voltage) and results/dnl_inl.txt
(verdict + extrema). Exit 0 on DNL/INL <= 1 LSB, else 2.

Usage: python3 scripts/measure_dnl_inl.py [--codes N]  (subset smoke)
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VREF = 1.8
VRE = re.compile(r"v\(vdac\)\s*=\s*(-?[0-9.eE+-]+)")


def sim_code(code):
    deck = [f"* dc code {code}",
            ".include design/analog/wave_top.spice"]
    for b in range(7, -1, -1):
        v = VREF if (code >> b) & 1 else 0.0
        deck.append(f"Vb{b} b{b} 0 DC {v:.3f}")
    deck += ["", ".control", "option noinit", "op", "print v(vdac)",
             ".endc", ".end", ""]
    (ROOT / "results/dc_tmp.spice").write_text("\n".join(deck))
    # NOTE: `print` vectors land in the -o log file, not in stdout.
    subprocess.run(["ngspice", "-b", "-o", "results/dc_tmp.log",
                    "results/dc_tmp.spice"],
                   cwd=ROOT, capture_output=True, text=True)
    log = (ROOT / "results/dc_tmp.log").read_text()
    m = VRE.search(log)
    if not m:
        raise RuntimeError(f"code {code}: no v(vdac) in ngspice log\n" + log[-2000:])
    return float(m.group(1))


def main():
    n = 256
    if "--codes" in sys.argv:
        n = int(sys.argv[sys.argv.index("--codes") + 1])
    volts = []
    for code in range(n):
        volts.append(sim_code(code))
        if code % 32 == 0:
            print(f"  code {code}/{n}", flush=True)
    (ROOT / "results/dc_sweep.txt").write_text(
        "\n".join(f"{c} {v:.9g}" for c, v in enumerate(volts)) + "\n")
    lsb = (volts[-1] - volts[0]) / (n - 1) if n > 1 else float("nan")
    dnl = [(volts[k + 1] - volts[k]) / lsb - 1 for k in range(n - 1)]
    inl = [(volts[k] - (volts[0] + k * lsb)) / lsb for k in range(n)]
    rep = (f"codes={n} lsb_V={lsb:.9g} "
           f"max|DNL|={max(abs(x) for x in dnl):.4f} LSB "
           f"max|INL|={max(abs(x) for x in inl):.4f} LSB\n"
           f"V(0)={volts[0]:.6f} V({n - 1})={volts[-1]:.6f} "
           f"Vref=1.8 ideal_LSB={VREF / 256:.9g}\n")
    ok = max(abs(x) for x in dnl) <= 1.0 and max(abs(x) for x in inl) <= 1.0
    rep += ("VERDICT: PASS (DNL/INL <= 1 LSB)\n" if ok
            else "VERDICT: FAIL (exceeds 1 LSB)\n")
    (ROOT / "results/dnl_inl.txt").write_text(rep)
    print(rep, end="")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
