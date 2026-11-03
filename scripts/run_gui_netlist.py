"""Batch proof of the GUI netlist: what Simulate really runs.

Netlists design/analog/xschem/wave_top_tb_<mode>.sch with the REAL xschem
netlister (command mode, no X: xschem -x -r --rcfile xschemrc -n -s -q),
runs the resulting deck in ngspice, and — for modes with a flat-deck
oracle (sine/saw) — requires BIT-IDENTICAL vout/vfilt traces vs
results/tb_replay_<mode>.txt. Tri has no flat oracle; it must simply run.

This closes the loop the strict expander (scripts/expand_tb.py) cannot:
it proves the schematic xschem itself sees — directives, hierarchy,
PDK symbols — simulates to the same waves, so the visitor's Simulate
button reproduces the checked-in results.

Also guards the exact regression that killed the GUI sim once: a stray
')' after a code.sym closing quote leaked into the netlist ('.tran ...)')
while the batch expander stayed green. The expanded deck is NOT used here.

Usage: python3 scripts/run_gui_netlist.py [--mode sine|saw|tri]
Requires: xschem on PATH, project xschemrc (PDK symbols).
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORACLES = ("sine", "saw")

ap = argparse.ArgumentParser()
ap.add_argument("--mode", default="sine", choices=["sine", "saw", "tri"])
a = ap.parse_args()

outdir = ROOT / "results" / f"guinet_{a.mode}"
outdir.mkdir(exist_ok=True)
sch = ROOT / "design" / "analog" / "xschem" / f"wave_top_tb_{a.mode}.sch"
env = dict(os.environ)
env.pop("DISPLAY", None)  # -x is command mode; a stale DISPLAY only confuses it
r = subprocess.run(
    ["xschem", "-x", "-r", "--rcfile", str(ROOT / "xschemrc"),
     "-n", "-s", "-q", str(sch), "-o", str(outdir)],
    capture_output=True, text=True, cwd=ROOT, env=env)
deck = outdir / f"wave_top_tb_{a.mode}.spice"
assert deck.exists(), f"xschem netlist failed:\n{r.stdout}\n{r.stderr}"
text = deck.read_text()
assert ".tran 100p 5.12e-06\n" in text, "tran line mangled in GUI netlist"
assert text.count(".control") == 1 and "\nrun\n" in text, \
    "schematic .control block missing from GUI netlist"
log = outdir / "ngspice.log"
subprocess.run(["ngspice", "-b", "-o", str(log), str(deck)],
               check=True, cwd=outdir)
guitxt = outdir / f"wave_top_tb_{a.mode}_gui.txt"
assert guitxt.exists(), f"schematic wrdata did not produce {guitxt.name}"
rows = [ln for ln in guitxt.read_text().splitlines()
        if ln.strip() and not ln.startswith("Time")]
print(f"{a.mode}: GUI netlist -> {len(rows)} data rows ({deck.name})")
for artifact in outdir.glob("*.raw"):
    print(f"{a.mode}: dropping {(artifact.stat().st_size + 512) // 1024} "
          f"KiB {artifact.name} (GUI artifact, regenerable)")
    artifact.unlink()
if a.mode in ORACLES:
    ref = (ROOT / "results" / f"tb_replay_{a.mode}.txt").read_text().splitlines()
    got = guitxt.read_text().splitlines()
    assert len(got) == len(ref), f"row count {len(got)} vs {len(ref)}"
    bad = [(i, g, rr) for i, (g, rr) in enumerate(zip(got, ref)) if g != rr]
    assert not bad, f"{len(bad)} differing rows, first: {bad[:3]}"
    print(f"{a.mode}: BIT-IDENTICAL vs tb_replay_{a.mode}.txt ({len(ref)} rows)")
