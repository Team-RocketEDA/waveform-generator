"""Batch proof that the visitor tb schematic simulates correctly.

Strict-expands design/analog/xschem/wave_top_tb_<mode>.sch (see
scripts/expand_tb.py) and runs it in ngspice with the schematic's OWN
.control block (save/run/write/wrdata) — the batch run proves exactly the
recipe the visitor's Simulate button executes. For modes with a flat-deck
oracle (sine/saw) the GUI txt must be BIT-IDENTICAL to
results/tb_replay_<mode>.txt. Tri has no flat oracle; it must simply run.

Sim exhaust (the .raw the embedded graph loads, plus the _gui.txt) is
moved into results/; the bulky .raw is deleted after a green run.

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
text = deck.read_text()
assert ".control" in text and "\nrun\n" in text, \
    "schematic .control block missing from expanded deck"
log = deck.with_suffix(".log")
subprocess.run(["ngspice", "-b", "-o", str(log), str(deck)],
               check=True, cwd=ROOT)
raw = ROOT / f"wave_top_tb_{a.mode}.raw"
guitxt = ROOT / f"wave_top_tb_{a.mode}_gui.txt"
assert guitxt.exists(), f"schematic wrdata did not produce {guitxt.name}"
txt = deck.with_suffix(".txt")
guitxt.rename(txt)
rows = [ln for ln in txt.read_text().splitlines()
        if ln.strip() and not ln.startswith("Time")]
print(f"{a.mode}: {len(rows)} data rows -> {txt.name}")
if raw.exists():
    print(f"{a.mode}: dropping {(raw.stat().st_size + 512) // 1024} KiB "
          f"{raw.name} (GUI artifact, regenerable)")
    raw.unlink()
if a.mode in ORACLES:
    ref = (ROOT / "results" / f"tb_replay_{a.mode}.txt").read_text().splitlines()
    got = txt.read_text().splitlines()
    assert len(got) == len(ref), f"row count {len(got)} vs {len(ref)}"
    bad = [(i, g, r) for i, (g, r) in enumerate(zip(got, ref)) if g != r]
    assert not bad, f"{len(bad)} differing rows, first: {bad[:3]}"
    print(f"{a.mode}: BIT-IDENTICAL vs tb_replay_{a.mode}.txt ({len(ref)} rows)")
