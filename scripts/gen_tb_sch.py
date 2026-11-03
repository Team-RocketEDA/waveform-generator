"""Generate a self-contained xschem testbench for the PDK R-2R DAC.

Replays the RTL staircase (sine/saw/tri golden formulas, bit-identical with
design/digital) as 8 edge-compressed PWL sources straight into the DAC
hierarchy — no RTL sim, no digital macro needed. Sim + plot directives ride
along in code.sym blocks, so opening one file and pressing Simulate shows
the analog path working with live ngspice plots.

Outputs (never hand-edit; regenerate):
  design/analog/xschem/r2r_dac8_pdk.sym  (pins in DAC .sch file order)
  design/analog/xschem/stair_stepper_<mode>.sch/.sym (PWL stepper block)
  design/analog/xschem/wave_top_tb_<mode>.sch (XDAC + XSTEP + supplies)

Usage: python3 scripts/gen_tb_sch.py [--mode sine|saw|tri]
Verify: xschem -n (hierarchy must expand) + ngspice -b on the netlist,
        sampled codes must equal the golden formula.
"""
import argparse
import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCH = ROOT / "design" / "analog" / "xschem" / "r2r_dac8_pdk.sch"
TPER = 20e-9
NCLK = 256
VHI = 1.8

ap = argparse.ArgumentParser()
ap.add_argument("--mode", default="sine", choices=["sine", "saw", "tri"])
a = ap.parse_args()


def codes(mode):
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


EDGE = 0.5e-9  # proven step width from gen_spice_tb.py (1 ps collapses tran)


def pwl_tables(seq):
    """Per-bit edge-compressed (t, v) tables: initial point + every flip."""
    tabs = []
    for bit in range(8):
        pts = [(0.0, float((seq[0] >> bit) & 1) * VHI)]
        for k in range(1, len(seq)):
            if ((seq[k] ^ seq[k - 1]) >> bit) & 1:
                t = k * TPER
                pts.append((t - EDGE, float((seq[k - 1] >> bit) & 1) * VHI))
                pts.append((t, float((seq[k] >> bit) & 1) * VHI))
        pts.append((len(seq) * TPER, float((seq[-1] >> bit) & 1) * VHI))
        tabs.append(" ".join(f"{t:.9g} {v:.1f}" for t, v in pts))
    return tabs


def dac_pins():
    pins = []  # (lab,) in schematic file order
    for line in open(SCH):
        m = re.match(r"C \{devices/[io]pin\.sym\} \S+ \S+ 0 0 \{name=\S+ lab=([^}]*)\}",
                     line)
        if m:
            pins.append(m.group(1))
    assert len(pins) == 13, pins
    return pins


def emit_symbol(pins):
    n = len(pins)
    h = max(400, 60 * n)
    L = ["v {xschem version=3.4.0 file_version=1.2}", "G {}",
         "K {type=subcircuit", 'format="@name @pinlist @symname"',
         'template="name=X1"}', "V {}", "S {}", "E {}",
         f"L 4 0 0 0 {h} {{}}", f"L 4 0 {h} 300 {h} {{}}",
         f"L 4 300 {h} 300 0 {{}}", f"L 4 300 0 0 0 {{}}"]
    for i, lab in enumerate(pins):
        y = 30 + i * ((h - 60) // max(1, n - 1))
        L.append(f"B 5 -5 {y - 5} 5 {y + 5} {{name={lab} dir=inout}}")
    L.append("T {@symname} 150 -25 0 0 0.3 0.3 {}")
    L.append("T {@name} 150 15 0 0 0.2 0.2 {}")
    out = SCH.parent / "r2r_dac8_pdk.sym"
    out.write_text("\n".join(L) + "\n")
    print(f"wrote {out} ({n} pins)")


def _sch_head():
    return ["v {xschem version=3.4.0 file_version=1.2}", "G {}",
            "K {}", "V {}", "S {}", "E {}"]


def emit_stepper(seq, tables):
    """stair_stepper_<mode>: 8 PWL bit sources + ground, opin b7..b0.

    The SPICE model of the staircase stepper as one hierarchical block.
    opin file order (b7..b0) matches stair_stepper_<mode>.sym pin order.
    """
    L = _sch_head()

    def C(sym, x, y, attrs):
        L.append(f"C {{{sym}}} {x} {y} 0 0 {{{attrs}}}")

    def N(x1, y1, x2, y2, lab=None):
        L.append(f"N {x1} {y1} {x2} {y2} {{{('lab=' + lab) if lab else ''}}}")

    labs = [f"b{i}" for i in range(7, -1, -1)]
    for i, lab in enumerate(labs):
        Y = 30 + i * 60
        # plain vsource with pwl() value: the E-named vsource_pwl template
        # breaks the ngspice operating point (gmin/source stepping fail);
        # V-named PWL converges (52k-row tran proven in batch).
        C("devices/vsource.sym", 200, Y + 30,
          f"name=V{lab} value=\"pwl({tables[7 - i]})\"")
        N(200, Y, 600, Y, lab)          # p -> opin stub
        C("devices/opin.sym", 600, Y, f"name=p_{lab} lab={lab}")
        N(200, Y + 60, 100, Y + 60)     # m -> ground spine
    N(100, 90, 100, 510)                # ground spine
    C("devices/gnd.sym", 100, 510, "name=g0 lab=0")
    out = SCH.parent / f"stair_stepper_{a.mode}.sch"
    out.write_text("\n".join(L) + "\n")
    # symbol: pins right edge, same ys, same b7..b0 order
    S = ["v {xschem version=3.4.0 file_version=1.2}", "G {}",
         "K {type=subcircuit", 'format="@name @pinlist @symname"',
         'template="name=X1"}', "V {}", "S {}", "E {}",
         "L 4 0 0 0 510 {}", "L 4 0 510 300 510 {}",
         "L 4 300 510 300 0 {}", "L 4 300 0 0 0 {}"]
    for i, lab in enumerate(labs):
        Y = 30 + i * 60
        S.append(f"B 5 295 {Y - 5} 305 {Y + 5} {{name={lab} dir=out}}")
    S.append("T {@symname} 150 -25 0 0 0.3 0.3 {}")
    S.append("T {@name} 150 15 0 0 0.2 0.2 {}")
    sout = SCH.parent / f"stair_stepper_{a.mode}.sym"
    sout.write_text("\n".join(S) + "\n")
    print(f"wrote {out} + {sout}")


def emit_tb(pins, seq, tables):
    L = _sch_head()
    inst_pin_y = {lab: 30 + i * 60 for i, lab in enumerate(pins)}

    def C(sym, x, y, attrs):
        L.append(f"C {{{sym}}} {x} {y} 0 0 {{{attrs}}}")

    def N(x1, y1, x2, y2, lab=None):
        L.append(f"N {x1} {y1} {x2} {y2} {{{('lab=' + lab) if lab else ''}}}")

    # DAC macro + stepper block, pin-to-pin (both use y=30+i*60 rows)
    C("r2r_dac8_pdk.sym", 600, 0, "name=XDAC")
    C(f"stair_stepper_{a.mode}.sym", 100, 0, "name=XSTEP")
    for i in range(8):
        lab = f"b{7 - i}"
        Y = inst_pin_y[lab]
        N(400, Y, 600, Y, lab)
    # supplies (right side, clear of the macro box)
    C("devices/vsource.sym", 1030, 510, "name=EVREF value=1.8")
    N(900, 480, 1030, 480, "vref")
    N(1030, 540, 1030, 900)
    C("devices/vsource.sym", 1000, 570, "name=EVDD value=1.8")
    N(900, 540, 1000, 540, "vpwr")
    N(1000, 600, 1000, 900)
    N(900, 600, 1100, 600, "vgnd")
    N(1100, 600, 1100, 900)
    N(1000, 900, 1100, 900)
    C("devices/gnd.sym", 1050, 900, "name=g1 lab=0")
    # probed outputs
    N(900, 660, 1000, 660, "vfilt")
    N(900, 720, 1000, 720, "vout")
    # sim + plot directives (verbatim netlist_commands blocks)
    C("devices/code.sym", 100, -320, "name=s_lib value=\""
      ".lib /home/alrida-ismail/.local/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice tt\"")
    C("devices/code.sym", 100, -260, "name=s_tran value=\""
      f".tran 100p {NCLK * TPER}\")")
    C("devices/code.sym", 100, -200, "name=s_save value=\""
      ".save v(vout) v(vfilt) v(b7) v(b0)\"")
    # NOTE: analyses stay single-line (xschem-multiline is GUI-verified
    # separately). Simulate in xschem, then Add Wave -> v(vout), v(vfilt):
    # the staircase + filtered sine appear in the waves viewer.
    C("devices/code.sym", 100, -140, "name=s_note value=\""
      "* tb: 256clk staircase replay of the RTL golden (see gen_tb_sch.py)\"")
    out = SCH.parent / f"wave_top_tb_{a.mode}.sch"
    out.write_text("\n".join(L) + "\n")
    print(f"wrote {out} (mode={a.mode})")


def emit_deck(seq, tables):
    """Flat ngspice deck mirroring wave_top_tb.sch (batch proof of stimulus)."""
    # xschem netlists the DAC as a flat top cell (**.subckt commented out);
    # unwrap it into an includable subcircuit for the batch deck. The GUI
    # flow needs none of this: hierarchy expansion handles it on netlist.
    sub = (ROOT / "design" / "analog" / "xschem" / "r2r_dac8_pdk.spice").read_text()
    sub = sub.replace("**.subckt", ".subckt").replace("**.ends", ".ends")
    (ROOT / "results" / "dac_subckt.spice").write_text(sub)
    D = [".lib /home/alrida-ismail/.local/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice tt",
         ".include results/dac_subckt.spice"]
    D.append("XDAC b7 b6 b5 b4 b3 b2 b1 b0 vref vpwr 0 vfilt vout "
               "r2r_dac8_pdk")
    for i in range(8):
        D.append(f"Vb{7 - i} b{7 - i} 0 pwl({tables[7 - i]})")
    D += ["VREF vref 0 DC 1.8", "VDD vpwr 0 DC 1.8",
          f".tran 100p {NCLK * TPER}",
          ".save v(vout) v(vfilt)",
          ".control", "run",
          f"wrdata results/tb_replay_{a.mode}.txt v(vout) v(vfilt)",
          ".endc", ".end"]
    out = ROOT / "results" / f"tb_wave_top_{a.mode}.spice"
    out.write_text("\n".join(D) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    pins = dac_pins()
    emit_symbol(pins)
    seq = codes(a.mode)
    tabs = pwl_tables(seq)
    emit_stepper(seq, tabs)
    emit_tb(pins, seq, tabs)
    emit_deck(seq, tabs)
    # structural self-check: stepper opin order == sym pin order == tb nets
    assert [f"b{i}" for i in range(7, -1, -1)] == \
        [lab for lab in pins if lab.startswith("b")], "pin order drift"
    print("pin-order self-check OK")
