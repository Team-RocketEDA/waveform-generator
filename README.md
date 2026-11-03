# waveform-generator — 8-bit programmable waveform generator

## 1. Summary

`waveform_gen` (synthesizable RTL: phase accumulator + 256-entry sine LUT +
saw/triangle modes) → `r2r_dac8` (8-bit R-2R ladder, CMOS transmission-gate
switches + polysilicon resistors) → `rc_filter` (first-order RC, ~3.4 MHz) →
nice signals. PDK sky130A, 50 MHz update, DNL/INL ≤ 1 LSB. This repo holds the
RTL, the PDK-mapped analog schematic, the PCell analog layout, the stitched
top GDS, and every script that reproduces them.

## 2. Managed through rocket-engine, built with Muse Spark

This project was created and run as a rocket-engine project: the engine
orchestrates open-source silicon tools — Icarus, yosys/LibreLane, ngspice,
xschem, Magic, Netgen, gdsfactory — behind one contract surface. The repo is
the project database: `rocket.yaml` declares the blocks and their I/O,
`canvas.toml` declares the design intent up front (50 MHz, 1.8 V, 8 bit,
DNL/INL ≤ 1 LSB), and every stage gates on verification (RTL golden codes,
DC sweeps, DRC, extraction reachability, extracted-GDS simulation) before the
next begins, with full artifact provenance in `exports/`.

Muse Spark worked inside that structure as the collaborating agent: the human
sets intent and inspects at every gate (schematic in xschem, GDS renders,
waveform plots), the agent executes the stages and brings back measured
evidence. Where an engine binding exists, the flow runs through it; where the
work is project-specific, handrolled generators plug in as tasks under the
same contracts — same results, fully reproducible, no hand-drawn polygons and
no hand-written netlists anywhere. That is the point of rocket: a human and
an AI agent co-developing real ASIC work in one repo, with the engine holding
the process together.

## 3. Schematic — generated headless, inspected in xschem

![R-2R + filter schematic map](exports/schematic_map.png)

`design/analog/xschem/r2r_dac8_pdk.sch` (103 instances, 398 wires) is emitted
by `scripts/gen_analog_pdk.py`: 8 bit-slices (series-R rung + 2R shunt + W=20
TG pair + local inverter for the complementary select), vout trunk, RFILT +
15×15 MiM cap, physical rails. The figure above is rendered headless from the
`.sch` database by `scripts/plot_schematic.py` (blue NMOS, red PMOS, orange
poly-R, green cap). Open the same file in xschem to zoom the real thing —
`make touchcheck` (0 dangling nets) and `make pdkdac` (netlist + 256-code
sweep) run with no exports thanks to the project-local `./xschemrc`.

## 4. Layout

<table>
<tr>
<td width="68%" valign="top">

<img src="exports/stitch_shot.png" width="100%" alt="stitched top GDS" />

<table>
<tr>
<td width="50%" valign="top"><img src="exports/analog_macro_shot.png" width="100%" alt="analog macro GDS" /></td>
<td width="50%" valign="top"><img src="exports/gds_shot.png" width="100%" alt="digital macro GDS" /></td>
</tr>
</table>

</td>
<td width="32%" valign="top">

**Top — `stitch_top` (102×88 um).** LibreLane digital macro + 8 metal straps
to the analog `b[7:0]` pins. Magic DRC 0; extraction reaches all 8 pads.

**Bottom-left — `r2r_dac8_macro` (537×238 um).** The analog half, drawn with
sky130 PCells by `scripts/gen_analog_layout.py`: 15 folded poly-resistor
columns (46 legs, exact R/2R), segmented node trunk, 8 drain drops awaiting
the TG band, RFILT + MiM block at left. Magic DRC 0.

**Bottom-right — `waveform_gen` (74×85 um).** Digital macro out of LibreLane
(sky130A, DRC 0 / LVS 0): phase accumulator, mode mux, sine ROM.

</td>
</tr>
</table>

## 5. Metrics

| Metric | Value | How proven |
|---|---|---|
| Clock / supply / resolution | 50 MHz / 1.8 V / 8 bit | `canvas.toml` + Icarus TB, 256 codes/mode |
| Ideal-ladder DNL / INL | 0.0001 / 0.0001 LSB | ngspice DC sweep, `results/dnl_inl.txt` |
| PDK-ladder DNL / INL (tt) | 0.22 / 0.19 LSB | 256-code sweep on foundry models, PASS ≤ 1 LSB |
| LSB / full-scale | 7.03 mV / 0 → 1.793 V | measured, both ladders |
| Filter corner | ~3.4 MHz vs 195 kHz fundamental | light by design: smooths, barely phase-shifts |
| Digital macro | 74.2 × 85.0 um, DRC 0, LVS 0 | LibreLane sky130A |
| Analog macro | 537 × 238 um, DRC 0 (LVS pending) | Magic `drc(full)` on PCell GDS |
| Extracted-GDS function | 256/256 sine, saw, tri | ngspice on Magic-extracted `stitch_top` |
| Stitch connectivity | 8/8 pads extracted | `scripts/verify_extract.py` |

## 6. Waveform plots

Analog path (ideal SPICE: DAC staircase + filtered output):

![DAC staircase and filtered output](exports/waveforms.png)

Digital path through extracted silicon (PEX b[7:0] vs RTL golden, full period
per mode — sine, saw, triangle, all 256/256):

![PEX full-period vs RTL golden](exports/pex_wave.png)

## 7. Run, verify, prerequisites

Prerequisites: Icarus Verilog, ngspice-42, yosys, Magic 8.3 + Netgen (all
with sky130A at `~/.local/share/pdk/sky130A`), LibreLane AppRun, Python with
`matplotlib`/`numpy`, and the isolated PCell venv
(`requirements-gfsky130.txt`: `sky130==1.0.0` + `gdsfactory~=9.40.1`).

| Command | Proves |
|---|---|
| `iverilog … && vvp results/tb_wave` | RTL: 256 codes/mode vs golden |
| `make tran && make dnl` | ideal analog: staircase + DNL/INL ≤ 1 LSB |
| `make pdkdac` | PDK schematic → netlist → 256-code sweep (DNL 0.22/INL 0.19) |
| `make touchcheck` | schematic has no dangling nets |
| `make analoglay` (+ Magic `drc(full)`) | analog macro GDS, DRC 0 |
| `make pex` | extracted-GDS function, 256/256 × 3 modes |

Repo map: `rocket.yaml` manifest · `canvas.toml` intent · `design/digital/`
RTL · `design/analog/` SPICE + xschem + GDS · `tests/` benches ·
`scripts/` generators · `docs/` writeups (`pex_sim.md`, `magic_stitch.md`,
`architecture/`) · `exports/` GDS + screenshots.

## Conclusion

The chain is proven in three independent layers — RTL simulation, foundry-
model analog simulation, and transistor-level simulation of extracted GDS —
with the layout generated, not drawn, at every step. What remains is the TG
switch band in the analog macro, LVS against the xschem source, and the
re-stitch: at that point `stitch_top` becomes real mixed-signal silicon and
this README's top figure gets re-rendered with it.
