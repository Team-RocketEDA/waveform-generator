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
