# waveform-generator — 8-bit programmable waveform generator

Signal chain: `waveform_gen` (RTL: phase acc + sine/saw/triangle) →
`r2r_dac8` (SPICE R-2R, ideal switches) → `rc_filter` (first-order RC) →
nice signals. PDK: sky130A. Constraints: [canvas.toml](canvas.toml).

## Repo map (mirrors rocket-engine taxonomy)

| Path | Contract |
|---|---|
| `rocket.yaml` | project manifest: blocks, PDKs, testbench links |
| `canvas.toml` | constraints-first intent (I28 ingredient): 10 MHz, 1.8 V, 8 bit, DNL/INL ≤ 1 LSB |
| `design/digital/` | `hdl_component` — synthesizable RTL only, no analog |
| `design/analog/` | `spice_block`s + `wave_top` assembly netlist, no analyses |
| `tests/` | `testbench` harnesses (HDL TB + TB contract notes) |
| `scripts/` | generators + measurement (bodies where done, contracts where stubbed) |
| `workflows/` | engine task bindings (contract stubs) |
| `ip/manifest.yaml` | reusable-block registry (stub) |
| `results/` | run exhaust: logs, code streams, measurements (gitignored) |
| `exports/` | GDS + screenshots (gitignored binaries, keep PNGs) |
| `docs/architecture/` | block-diagram board contract (archify candidate planned) |

## Status

DONE: RTL + LUT + Icarus TB, analog blocks, RTL-driven tran at 50 MHz
(3 modes, 5.12 us spans), DC sweep DNL/INL PASS (max 0.0001 LSB),
SPICE-vs-model waveform agreement PASS (0.21/0.01 LSB), plots.
Magic `lef read` confirmed for the LibreLane macro drop-in.
STUB (contract only): `scripts/synth_gds.py`, `workflows/*`,
`docs/architecture/` board, final GDS + screenshot.
