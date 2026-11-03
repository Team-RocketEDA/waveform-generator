#!/usr/bin/env python3
"""Generate an ngspice testbench that simulates the flat PEX-extracted
stitched top (results/top_pex.spice: 3224 FETs + 88 extracted node caps,
no .subckt wrapper) for 24 clocks and dumps b[7:0].

Top-level nets in the extract: VGND VPWR clk en mode[0] mode[1]
phase_out[0..7] rst_n step[0..7] b[0..7] (b[i] = dout[i] strap nets).

Usage: python3 scripts/gen_pex_tb.py [--mode sine|saw|tri] [--nclk N]
Writes results/tb_pex_<mode>.spice.
"""
import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
TPER = 20e-9
MODES = {"sine": (0, 0), "saw": (0, 1), "tri": (1, 0)}

ap = argparse.ArgumentParser()
ap.add_argument("--mode", default="sine", choices=MODES)
ap.add_argument("--nclk", type=int, default=24)
a = ap.parse_args()
MODE, NCLK = a.mode, a.nclk
M1, M0 = MODES[MODE]

# mode codes: 00=sine, 01=saw, 10=tri
body = (ROOT / "design/digital/sine_rom.v").read_text()
lut = sorted((int(a), int(b, 16))
             for a, b in re.findall(r"8'd(\d+):\s*dout\s*=\s*8'h([0-9A-Fa-f]{2})", body))
codes = [v for _, v in lut]
assert len(codes) == 256, f"sine LUT has {len(codes)} entries"

lines = []
A = lines.append
A(f"* PEX testbench: flat extracted stitch_top, {MODE} mode, step=1, {NCLK} clocks")
A(".lib /home/alrida-ismail/.local/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice tt")
A(".temp 27")
# ngspice-42 mishandles PDK-style bracket nets (b[7]) in v() probes, so the
# generator works on a sed-renamed copy (b[7]->b7 etc.). Regenerable scratch.
A(".include results/top_pex_sim.spice")
A("Vdd VPWR 0 DC 1.8")
A("Vss VGND 0 DC 0")
A("Ven en 0 DC 1.8")
A(f"Vm1 mode_1 0 DC {1.8 * M1}")
A(f"Vm0 mode_0 0 DC {1.8 * M0}")
for i in range(8):
    A(f"Vs{i} step_{i} 0 DC {1.8 if i == 0 else 0.0}")
T = TPER
A(f"Vclk clk 0 PULSE(0 1.8 0 0.5n 0.5n {T/2-0.5e-9:.3e} {T:.3e})")
A(f"Vrst rst_n 0 PWL(0 0 {2*T:.3e} 0 {2*T+1e-9:.3e} 1.8)")
vecs = " ".join(f"v(b{i})" for i in range(7, -1, -1))
# NOTE: tran lives inside .control (like scripts/gen_spice_tb.py): in batch
# mode a .control block replaces the dot-card flow, so a dot-card .tran alone
# never executes and wrdata finds no vectors.
A(f".control\nset wr_vecnames\ntran 0.2n {NCLK*T:.3e}\nwrdata {RES}/pex_raw_{MODE}.txt {vecs}\nquit\n.endc")
A(".end")

(RES / f"tb_pex_{MODE}.spice").write_text("\n".join(lines) + "\n")
print(f"wrote {RES/f'tb_pex_{MODE}.spice'}: {MODE} mode, step=1, {NCLK} clocks x {TPER*1e9:.0f}ns")
golden = [int(x) for x in (RES / f"codes_{MODE}.txt").read_text().split()]
print("expected b sequence (clocks 3..):",
      " ".join(f"{c:02x}" for c in golden[:22]))
