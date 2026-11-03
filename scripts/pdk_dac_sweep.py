#!/usr/bin/env python3
"""DC sweep the PDK-mapped DAC (xschem netlist) over all 256 codes and
measure DNL/INL with endpoint fit (same math as scripts/measure_dnl_inl.py).

One ngspice run: 256 unrolled (alter bit sources, op, print vout) steps.
Bit sources drive the TG muxes exactly like the RTL dout pins will.

Usage: python3 scripts/pdk_dac_sweep.py
Writes results/pdk_dc.txt (raw) + results/pdk_dnl_inl.txt (verdict).
Exits nonzero if |DNL| or |INL| exceeds 1 LSB.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
SCH = ROOT / "design" / "analog" / "xschem" / "r2r_dac8_pdk.sch"
NET = ROOT / "design" / "analog" / "xschem" / "r2r_dac8_pdk.spice"
PDKRC = "/home/alrida-ismail/.local/share/pdk/sky130A/libs.tech/xschem/xschemrc"
LIB = "/home/alrida-ismail/.local/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice"

subprocess.run(
    ["xschem", "--rcfile", PDKRC, "-n", "-s", "-o", str(NET.parent) + "/",
     "-N", NET.name, str(SCH)],
    check=True, capture_output=True, timeout=120)
body = NET.read_text()
assert body.count("IS MISSING") == 0, "unresolved symbols in netlist"
assert len(re.findall(r"^X", body, re.M)) == 66, "instance count changed"

ctl = ["* pdk DAC DC sweep: 256 codes, TG muxes, endpoint-fit DNL/INL",
       f".lib {LIB} tt", ".temp 27",
       # xschem emits a FLAT netlist (no .subckt): its top nets are driven
       ".include design/analog/xschem/r2r_dac8_pdk.spice"]
for b in range(8):
    ctl.append(f"Vb{b} b{b} 0 DC 0")
ctl += ["Vvref vref 0 DC 1.8", "Vvpwr vpwr 0 DC 1.8",
        # vgnd is a FLOATING net name, not SPICE ground: it needs its own
        # 0V source (in the chip this is the ground pad).
        "Vvgnd vgnd 0 DC 0", ".control"]
for code in range(256):
    for b in range(8):
        ctl.append(f"alter @Vb{b}[dc] = {1.8 if (code >> b) & 1 else 0.0}")
    ctl.append("op")
    ctl.append(f"echo CODE {code} $&vout")
ctl += ["quit", ".endc", ".end"]
deck = RES / "pdk_dc.spice"
deck.write_text("\n".join(ctl) + "\n")

r = subprocess.run(["ngspice", "-b", "-o", str(RES / "pdk_dc.log"), str(deck)],
                   capture_output=True, text=True, timeout=600)
log = (RES / "pdk_dc.log").read_text()
got = [(int(m.group(1)), float(m.group(2))) for m in
       re.finditer(r"^CODE\s+(\d+)\s+(\S+)", log, re.M)]
got.sort()
assert [k for k, _ in got] == list(range(256)), \
    f"got {len(got)}/256 op points (see pdk_dc.log)"
vals = [v for _, v in got]
(RES / "pdk_dc.txt").write_text("\n".join(f"{v:.6f}" for v in vals) + "\n")

v0, v1 = vals[0], vals[-1]
lsb = (v1 - v0) / 255
dnl = [(vals[k + 1] - vals[k]) / lsb - 1 for k in range(255)]
inl, acc = [], 0.0
for d in dnl:
    acc += d
    inl.append(acc)
md, mi = max(abs(x) for x in dnl), max(abs(x) for x in inl)
verdict = "PASS" if (md <= 1.0 and mi <= 1.0) else "FAIL"
(RES / "pdk_dnl_inl.txt").write_text(
    f"pdk r2r: W=4 compensated-R TG-mux, tt, 256-code DC sweep\n"
    f"vout(0)={v0:.6f} V vout(255)={v1:.6f} V LSB={lsb * 1e3:.4f} mV\n"
    f"max|DNL|={md:.4f} LSB max|INL|={mi:.4f} LSB -> {verdict}\n")
print(open(RES / "pdk_dnl_inl.txt").read())
sys.exit(0 if verdict == "PASS" else 1)
