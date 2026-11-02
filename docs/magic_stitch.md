# Magic stitch runbook (verified live, Magic 8.3.685 + sky130A)

Import a LibreLane macro, drop it in a top cell, wire it, DRC it.

## Import (order matters)

```
tech load ~/.local/share/pdk/sky130A/libs.tech/magic/sky130A.tech
gds readonly true
gds read <macro>.gds      # geometry FIRST ...
lef read <macro>.lef      # ... then LEF annotates ports (0 dup warnings;
                          # reversed order gives 437 "already existed")
```

Prefer the rcfile, which does the tech load plus `drc euclidean on`:
`magic -dnull -noconsole -rcfile <pdk>/libs.tech/magic/sky130A.magicrc`.

## Cells: use `load`, not `cellname create`

`cellname create` does not reliably switch cells — paint silently lands in
the imported macro and the later `save` dies on its read-only timestamp.
`load <cell>` creates-or-switches deterministically every time:

```
load stitch_top
box 0 0 <w> <h>
getcell waveform_gen     # origin-anchored (probe-verified identity
                         # transform): LEF coords land 1:1
```

## Units: typed boxes are 100/um

`box 14727 ...` displays as 147.27 um. Imported GDS geometry lives at
200/um internally. Generated Tcl must emit LEF_um * 100 (LEF decimals land
on exact integers). Painting at *200 puts wires at 2x — floating in space
with a vacuous DRC 0. The plot caught it; see `exports/stitch_shot.png`.

## DRC + GDS out

```
select top cell
drc euclidean on
drc style drc(full)
drc check
drc catchup
drc count total        # prints "Total DRC errors found: N"
gds write <abs path>   # absolute: cwd differs between recipe and run
```

Never run bare `drc listall` — it segfaults 8.3.685. (`drc listall why`
is safe but silent in batch.)

## Automated stitch (this repo)

`scripts/gen_stitch.py` parses the LEF, asserts overlap-with-own-pin and
clearance in Python, and writes `results/stitch.tcl`.
`scripts/verify_stitch.py` re-checks every strap against ALL macro metal
with klayout regions (shorts + 140 nm spacing) — this catches what Magic
DRC cannot (same-layer overlap reads as connection).
`scripts/plot_gds.py` renders any GDS headlessly. `make stitch` runs all four.

## Parasitic extraction (PEX model for sim)

Flat transistor-level netlist out of the stitched top, for the `make pex`
sim path:

```
load stitch_top
extract all
ext2spice extresist on     # requested; this style still emits C-only
ext2spice -o <abs path>/top_pex.spice   # bare filename is silently ignored
```

What comes out (3224 X + 88 C, no `.subckt` wrapper, C-only parasitics):
top-level nets are `VGND VPWR clk en mode[0] mode[1] phase_out[0..7] rst_n
step[0..7] b[0..7]` — strap nets keep the analog-side `b[i]` name (the
`dout[i]` macro labels merge away). `scripts/gen_pex_tb.py` drives those
nets directly (24 clocks, sine step=1); `scripts/check_pex.py` thresholds
`b[7:0]` at 0.9 V against the RTL golden codes. One ngspice-42 gotcha:
`v(b[7])` probe syntax fails (brackets = vector indexing), so the testbench
aliases each strap through a 0 V source (`Vb7 b7alias b[7] DC 0`).
