#!/usr/bin/env python3
"""Synthesize waveform_gen to GDS (CONTRACT STUB — no body yet).

Contract:
  Reads: design/digital/waveform_gen.v, canvas.toml [tools.librelane].
  Writes: exports/waveform_gen.gds, exports/gds_shot.png, results/synth.log.
  Engine binding: tasks synthesize.hdl -> implement.asic (see workflows/asic.yaml).
  Verdict: GDS opens in KLayout + screenshot committed; exit 0 only then.

Body arrives after sim signoff. Until then this exits 2 (UNIMPLEMENTED).
"""
import sys

if __name__ == "__main__":
    print("UNIMPLEMENTED: digital synth body not written (contract only).")
    sys.exit(2)
