# PEX sim: does the extracted GDS actually waveform-generate?

Yes — for the digital path. `make pex` simulates the flat transistor netlist
Magic extracts from `stitch_top` (3,224 FETs + 88 node caps, C-only: this
extract style emits no wire resistors) for 24 clocks at 50 MHz in sine mode,
thresholds the `b[7:0]` strap nets at 0.9 V, and compares against the RTL
golden sine codes.

![PEX dout vs RTL golden](../exports/pex_wave.png)

Result (`results/pex_check.txt`): **20/20 consecutive codes match — PASS.**

```
sampled: 80 83 86 89 8c 90 93 96 99 9c 9f a2 a5 a8 ab ae b1 b3 b6 b9
golden : 80 83 86 89 8c 90 93 96 99 9c 9f a2 a5 a8 ab ae b1 b3 b6 b9
```

## What this proves (and does not)

- Proves: the LibreLane macro + the 8 hand straps deliver correct codes at
  the `b[7:0]` pads, parasitics included. Connectivity (LVS-extract 8/8) and
  function (this sim) agree.
- Does not prove analog function: past `b[7:0]` there is no DAC or filter
  geometry yet — those pads float. The R-2R + RC proof stays in ideal SPICE
  (`results/waveform_check.txt`, DNL/INL 0.0001 LSB) until the analog macro
  is laid out and stitched for real.

## Reproduce

`scripts/gen_pex_tb.py` writes the deck (sine, step=1, 24 clocks);
`scripts/check_pex.py` checks + plots. The 452 KB extract
(`results/top_pex.spice`) is regenerable scratch (git-ignored) — see
`docs/magic_stitch.md` "Parasitic extraction". Two ngspice-42 gotchas are
handled in the scripts: `tran` must live inside `.control`, and bracket nets
(`step[0]`) simulate in a `sed`-renamed copy (`step_0`) because `v()` probes
reject brackets.
