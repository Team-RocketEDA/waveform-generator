#!/usr/bin/env python3
"""Generate the device-mapped analog schematic (xschem .sch) from one
topology description. The SAME file netlists (xschem -n) for PDK sim and
drives the Magic layout script, so drawing, sim, and layout cannot drift.

Topology (matches design/analog/r2r_dac8.spice node-for-node, ideal bit
sources replaced by CMOS TG muxes to vref/vgnd + inverters):
  series chain: vout-n6-...-n0 (7x R=100k poly, w=4u l=357.43u)
  shunt:       node[i] -> sw[i] (8x 2R=200k poly, w=4u l=716.98u)
  (10x impedance vs the first cut: TG Ron 0.2-1k single-sided leaves
  45mV MSB error at 10k; at 100k + W=20 TGs the drop is ~2mV.)
  (lengths compensate the ~590R end-contact term so the RATIO is exactly
  2.000; literal 2x length would give 1.894. TG Ron ~70R via W=10 FETs;
  inverters stay W=1. Res display formula in xschem is stale; the model
  rsheet=1112.4 decides.)
  mux per bit: sw[i] <- vref via TG1 (nFET gate b[i], pFET gate b_n[i])
               sw[i] <- vgnd via TG2 (nFET gate b_n[i], pFET gate b[i])
               TG1/TG2 sit SIDE BY SIDE in one row (stacked rows interleave
               across the 170-unit stage pitch and short).
  termination: n0 -> vgnd (2R)
  filter:      vout -> vfilt (R=100k poly) + vfilt -> vgnd (C=470f mim)
  fc = 1/(2*pi*100k*470f) ~ 3.4 MHz (same cutoff, DC-exact: C blocks DC)

xschem rules learned the hard way (verified by experiment, keep them):
  - wires are N records; L records are unconnected graphics.
  - bare wire labs do NOT name nets; pin/lab_pin `lab` attributes do.
  - every instance pin needs a wire ENDPOINT touching it (a stublone wire
    still connects, but two collinear different-lab wires short).
  - wire-wire joins need endpoint touches (T/pileup); X-crossings stay
    separate and are safe to use for crossing.
  - power must be PHYSICAL rails: global wire labs do not join fragments.
    vref rail x=620, vgnd rails x=-260 (left) + x=640 (right),
    vpwr rail x=-300 (left).

Usage: python3 scripts/gen_analog_pdk.py
Writes design/analog/xschem/r2r_dac8_pdk.sch
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "design" / "analog" / "xschem"
OUT.mkdir(parents=True, exist_ok=True)

W = []  # (x1,y1,x2,y2,lab or None)
C = []  # (sym,x,y,rot,attrs)


def wire(x1, y1, x2, y2, lab=None):
    W.append((x1, y1, x2, y2, lab))


def comp(sym, x, y, rot, attrs):
    C.append((sym, x, y, rot, attrs))


def pin(sym, x, y, lab):
    comp(sym, x, y, 0, f"name=p_{lab} lab={lab}")


def labpin(x, y, lab):
    comp("devices/lab_pin.sym", x, y, 0, f"name=lp_{lab} lab={lab}")


NODES = ["vout", "n6", "n5", "n4", "n3", "n2", "n1", "n0"]
YN = {n: k * 220 for k, n in enumerate(NODES)}  # vout=0 ... n0=1540
YGND = 1710
RES = "sky130_fd_pr/res_high_po.sym"
NFET = "sky130_fd_pr/nfet_01v8.sym"
PFET = "sky130_fd_pr/pfet_01v8.sym"

# --- series R: stub / R / stub per segment (rot 0: P up, M down) ---
segs = list(zip(NODES[:-1], NODES[1:],
                ["R76", "R65", "R54", "R43", "R32", "R21", "R10"]))
segs.append(("n0", "vgnd", "RTERM"))
for a, b, nm in segs:
    ya = YN[a]
    yb = YN[b] if b in YN else YGND
    L = 716.98 if nm == "RTERM" else 357.43
    mid = (ya + yb) // 2
    comp(RES, 0, mid, 0, f"name={nm} W=4 L={L} model=res_high_po mult=1")
    if nm == "RTERM":
        wire(0, ya, 0, ya + 55, a)       # top stub ends at P pin
        # M tap goes RIGHT (backbone route overlaps P stub at 220 pitch).
        wire(0, mid + 30, 0, 1610, "vgnd")
        wire(0, 1610, 640, 1610, "vgnd")
    else:
        wire(0, ya, 0, mid - 30, a)      # top stub ends at P pin
        wire(0, mid + 30, 0, yb, b)      # bottom stub starts at M pin
    # body horizontal THROUGH the B pin (-20, mid) joins left vgnd rail
    wire(-260, mid, 100, mid, "vgnd")

for idx, node in enumerate(NODES):
    bit = 7 - idx
    y = YN[node]
    sw, bn, b = f"sw{bit}", f"b_n{bit}", f"b{bit}"
    ytg = y + 155
    # shunt 2R (rot 1: M/P land at (70,y)/(130,y), B at (100,y-20))
    comp(RES, 100, y, 1, f"name=R2B{bit} W=4 L=716.98 model=res_high_po mult=1")
    wire(0, y, 70, y, node)
    wire(130, y, 200, y, sw)
    # B vertical meets body rail at mid=y+110 (PITCH-COUPLED: 220 pitch).
    wire(100, y - 60, 100, y + 110, "vgnd")
    # sw drop + rail across both TGs
    wire(200, y, 200, ytg - 45, sw)
    wire(200, ytg - 45, 560, ytg - 45, sw)
    # TG1 (to vref): nFET x=200 / pFET x=300. TG2 (to vgnd): x=400 / x=500.
    comp(NFET, 200, ytg, 0, f"name=MT1N{bit} W=20 L=0.15 nf=1 mult=1")
    comp(PFET, 300, ytg, 0, f"name=MT1P{bit} W=20 L=0.15 nf=1 mult=1")
    comp(NFET, 400, ytg, 0, f"name=MT2N{bit} W=20 L=0.15 nf=1 mult=1")
    comp(PFET, 500, ytg, 0, f"name=MT2P{bit} W=20 L=0.15 nf=1 mult=1")
    for fx in (220, 320, 420, 520):
        wire(fx, ytg - 45, fx, ytg - 30, sw)      # drains end at rail pins
    # TG1 sources to vref rail: shortened stubs + tap row @y+200
    for fx in (220, 320):
        wire(fx, ytg + 30, fx, ytg + 45, "vref")
    wire(220, ytg + 45, 620, ytg + 45, "vref")
    # TG2 sources to vgnd rail: shortened stubs + tap row @y+210
    for fx in (420, 520):
        wire(fx, ytg + 30, fx, ytg + 55, "vgnd")
    wire(420, ytg + 55, 640, ytg + 55, "vgnd")
    # nFET bulks to vgnd rail: shortened stubs + tap row @y+160
    for fx in (220, 420):
        wire(fx, ytg, fx, ytg + 5, "vgnd")
    wire(220, ytg + 5, 640, ytg + 5, "vgnd")
    # TG1 pFET bulk to vref via its S stub extension
    wire(320, ytg, 320, ytg + 30, "vref")
    # TG2 pFET bulk to vref rail (right side feed @y+150)
    wire(520, ytg - 5, 520, ytg + 12, "vref")
    wire(520, ytg - 5, 620, ytg - 5, "vref")
    # b feed: ipin -> left column -> cross@145 -> jog@145 -> gate drops
    wire(-360, ytg, -200, ytg, b)                 # ipin in
    wire(-200, y + 135, -200, y + 225, b)         # left column up to cross
    wire(-200, y + 145, 180, y + 145, b)          # cross to right system
    wire(180, y + 145, 480, y + 145, b)           # b jog
    wire(180, y + 145, 180, ytg, b)               # drop into TG1N-G
    wire(480, y + 145, 480, ytg, b)               # drop into TG2P-G
    wire(-200, y + 135, -180, y + 135, b)         # inv pfet gate stub
    wire(-200, y + 225, -180, y + 225, b)         # inv nfet gate stub
    # bn feed: trunk@100 -> left drop -> drain rail -> row@175 -> stubs
    wire(-120, y + 100, 140, y + 100, bn)         # trunk
    wire(-120, y + 100, -120, y + 165, bn)        # left drop
    wire(-120, y + 165, -140, y + 165, bn)        # jog into drain rail
    wire(-140, y + 165, -140, y + 195, bn)        # drain rail (both D pins)
    wire(140, y + 100, 140, y + 175, bn)          # trunk drops to row
    wire(140, y + 175, 380, y + 175, bn)          # bn row
    wire(280, y + 175, 280, ytg, bn)              # stub into TG1P-G
    wire(380, y + 175, 380, ytg, bn)              # stub into TG2N-G
    # inverter b -> b_n (left)
    yinv = y + 135
    comp(PFET, -160, yinv, 0, f"name=MINVP{bit} W=1 L=0.15 nf=1 mult=1")
    comp(NFET, -160, yinv + 90, 0, f"name=MINVN{bit} W=1 L=0.15 nf=1 mult=1")
    wire(-140, y + 72, -140, y + 105, "vpwr")     # pfet S (pin at top)
    wire(-140, y + 72, -300, y + 72, "vpwr")      # vpwr tap row
    wire(-140, y + 105, -140, y + 135, "vpwr")    # pfet bulk extension
    wire(-140, y + 255, -140, y + 270, "vgnd")    # nfet S (pin at top)
    wire(-260, y + 270, -140, y + 270, "vgnd")    # vgnd tap row
    wire(-140, y + 225, -140, y + 255, "vgnd")    # nfet bulk extension
    labpin(35, y, node)
    labpin(165, y, sw)
    labpin(-140, y + 180, bn)

# --- power rails ---
wire(620, -60, 620, 1900, "vref")                # vref rail
wire(440, -60, 620, -60, "vref")                 # rail to ipin stub
wire(640, -60, 640, 1900, "vgnd")                # vgnd right rail
wire(-260, 80, -260, 1900, "vgnd")               # vgnd left rail
wire(-260, 90, 440, 90, "vgnd")                  # left rail to ipin stub
wire(-300, 72, -300, 1900, "vpwr")               # vpwr rail
wire(-300, 72, 440, 72, "vpwr")                  # vpwr rail to ipin stub
# filter cap + RTERM bottom join right/left rails
wire(640, 130, 720, 130, "vgnd")
# vgnd backbone: left rail x=-260 meets right rail x=640 (@1750 clears
# stage-0 bottom stubs ending ~1765? no: ends 1410; 1750 is clear air).
wire(-260, 1750, 640, 1750, "vgnd")

# --- RC filter (right side) ---
# vout rail rides at y=-80 (y=0 would short stage 7's shunt row).
wire(0, -80, 560, -80, "vout")
wire(0, -80, 0, 0, "vout")
comp(RES, 640, 0, 1, "name=RFILT W=1 L=89.36 model=res_high_po mult=1")
wire(560, 0, 610, 0, "vout")
wire(670, 0, 720, 0, "vfilt")
comp("sky130_fd_pr/cap_mim_m3_1.sym", 720, 70, 0,
     "name=CFLT model=cap_mim_m3_1 W=15 L=15 MF=1")
wire(720, 0, 720, 40, "vfilt")                # to c0 pin
wire(720, 100, 720, 130, "vgnd")              # from c1 pin

# --- pins ---
for idx, node in enumerate(NODES):
    bit = 7 - idx
    pin("devices/ipin.sym", -360, YN[node] + 155, f"b{bit}")
    wire(-360, YN[node] + 155, -320, YN[node] + 155, f"b{bit}")
pin("devices/ipin.sym", 440, -120, "vref")
wire(440, -120, 440, -60, "vref")
pin("devices/ipin.sym", 400, -180, "vpwr")
wire(400, -180, 400, 72, "vpwr")        # single column into top rail
pin("devices/ipin.sym", 360, -240, "vgnd")
wire(360, -240, 360, 90, "vgnd")        # single column into top rail
pin("devices/opin.sym", 820, 0, "vfilt")
wire(720, 0, 820, 0, "vfilt")
pin("devices/opin.sym", 820, -80, "vout")
wire(560, -80, 820, -80, "vout")
wire(560, -80, 560, 0, "vout")

lines = ["v {xschem version=3.4.7RC file_version=1.2}", "G {}", "K {}",
         "V {}", "S {}", "E {}"]
for x1, y1, x2, y2, lab in W:
    lines.append(f"N {x1} {y1} {x2} {y2} {{")
    lines.append(f"lab={lab}}}" if lab else "}")
for sym, x, y, rot, attrs in C:
    lines.append(f"C {{{sym}}} {x} {y} {rot} 0 {{{attrs}}}")
lines.append("T {R-2R DAC + RC, PDK-mapped (xschem source for sim+layout)} "
             "-360 -300 0 0 0.3 0.3 {}")
(OUT / "r2r_dac8_pdk.sch").write_text("\n".join(lines) + "\n")
print(f"wrote {OUT/'r2r_dac8_pdk.sch'}: {len(C)} instances, {len(W)} wires")
