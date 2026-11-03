"""Batch proof that the visitor tb schematic simulates correctly.

Strict-expands design/analog/xschem/wave_top_tb_<mode>.sch (see
scripts/expand_tb.py), runs it in ngspice, and — for modes with a flat-deck
oracle (sine/saw) — requires BIT-IDENTICAL vout/vfilt traces vs
results/tb_replay_<mode>.txt. Tri has no flat oracle; it must simply run.

Usage: python3 scripts/run_expanded.py [--mode sine|saw|tri]
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORACLES = ("sine", "saw")

ap = argparse.ArgumentParser()
ap.add_argument("--mode", default="sine", choices=["sine", "saw", "tri"])
a = ap.parse_args()

deck = ROOT / "results" / f"tb_expand_{a.mode}.spice"
subprocess.run([sys.executable, str(ROOT / "scripts" / "expand_tb.py"),
                str(ROOT / "design" / "analog" / "xschem" /
                    f"wave_top_tb_{a.mode}.sch"), str(deck)], check=True)
txt = deck.with_suffix(".txt")
log = deck.with_suffix(".log")
deck.write_text(deck.read_text()
                + ".control\nrun\n"
                + f"wrdata {txt} v(vout) v(vfilt)\n.endc\n.end\n")
subprocess.run(["ngspice", "-b", "-o", str(log), str(deck)], check=True)
rows = [ln for ln in txt.read_text().splitlines()
        if ln.strip() and not ln.startswith("Time")]
print(f"{a.mode}: {len(rows)} data rows -> {txt.name}")
if a.mode in ORACLES:
    ref = (ROOT / "results" / f"tb_replay_{a.mode}.txt").read_text().splitlines()
    got = txt.read_text().splitlines()
    assert len(got) == len(ref), f"row count {len(got)} vs {len(ref)}"
    bad = [(i, g, r) for i, (g, r) in enumerate(zip(got, ref)) if g != r]
    assert not bad, f"{len(bad)} differing rows, first: {bad[:3]}"
    print(f"{a.mode}: BIT-IDENTICAL vs tb_replay_{a.mode}.txt ({len(ref)} rows)")
