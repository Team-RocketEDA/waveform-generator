# extract_top.tcl — committed recipe: extract stitch_top, emit LVS + PEX views.
# Run AFTER make stitch (needs results/stitch_top.mag + macro GDS present):
#   cd results && magic -dnull -noconsole -rcfile <sky130A.magicrc> \
#     < ../scripts/extract_top.tcl > extract.log 2>&1   (see Makefile: extract)
# Outputs: results/top_lvs.spice (blackbox macro, for netgen LVS),
#          results/top_pex.spice (transistor-level + parasitics, for ngspice).
# NOTE: keep this session single-shot; re-reads re-timestamp the GDS cell.
gds readonly true
gds read ../runs/wave2/final/gds/waveform_gen.gds
lef read ../runs/wave2/final/lef/waveform_gen.lef
load stitch_top
extract all
ext2spice lvs
ext2spice -o top_lvs.spice
ext2spice extresist on
ext2spice -o top_pex.spice
quit -noprompt
