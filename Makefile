# Contract-only targets. Implemented recipes run; TODO recipes fail loudly.
RTL_TB = results/tb_wave

.PHONY: rtl tran dnl waveform plot stitch gds arch help
help:
	@echo "rtl      - icarus TB -> results/codes_{sine,saw,tri}.txt"
	@echo "tran     - RTL codes -> ngspice tran, 50 MHz update (all modes)"
	@echo "dnl      - 256-code DC sweep -> DNL/INL verdict"
	@echo "waveform - SPICE-vs-model agreement on saw tran (replaces glitch)"
	@echo "plot     - waveforms.png + dnl_inl.png"
	@echo "stitch   - gen + verify + Magic DRC + plot of dout->b stitch"
	@echo "gds    - TODO (contract: scripts/synth_gds.py)"
	@echo "arch   - TODO (contract: docs/architecture/)"

rtl:
	iverilog -o $(RTL_TB) -g2012 design/digital/waveform_gen.v design/digital/sine_rom.v tests/tb_waveform_gen.v
	vvp $(RTL_TB)

tran:
	python3 scripts/gen_spice_tb.py sine
	python3 scripts/gen_spice_tb.py saw
	python3 scripts/gen_spice_tb.py tri
	ngspice -b -o results/tran_sine.log results/tb_tran_sine.spice
	ngspice -b -o results/tran_saw.log results/tb_tran_saw.spice
	ngspice -b -o results/tran_tri.log results/tb_tran_tri.spice

dnl:
	python3 scripts/measure_dnl_inl.py

waveform:
	MPLCONFIGDIR=/tmp ../rocket-engine/.venv/bin/python scripts/check_waveform.py

plot:
	MPLCONFIGDIR=/tmp ../rocket-engine/.venv/bin/python scripts/plot_waveforms.py sine

stitch:
	python3 scripts/gen_stitch.py
	MPLCONFIGDIR=/tmp ../rocket-engine/.venv/bin/python scripts/verify_stitch.py
	cd results && printf 'source stitch.tcl\nquit -noprompt\n' | magic -dnull -noconsole -rcfile /home/alrida-ismail/.local/share/pdk/sky130A/libs.tech/magic/sky130A.magicrc > stitch.log 2>&1
	grep -a "Total DRC" results/stitch.log
	MPLCONFIGDIR=/tmp ../rocket-engine/.venv/bin/python scripts/plot_gds.py results/stitched.gds stitch_top exports/stitch_shot.png

gds:
	/tmp/llex/squashfs-root/AppRun librelane librelane_config.json --manual-pdk --pdk-root /home/alrida-ismail/.local/share/pdk -p sky130A -s sky130_fd_sc_hd --condensed --run-tag wave --save-views-to exports/views
	cp runs/wave/final/gds/waveform_gen.gds exports/waveform_gen.gds
	cp runs/wave/final/render/waveform_gen.png exports/gds_shot.png

# PEX path: extract stitch_top with parasitics, then simulate the flat
# transistor-level netlist (results/top_pex.spice) for 24 clocks and check
# b[7:0] against the RTL golden sine codes. Extraction itself is interactive
# Magic (see docs/magic_stitch.md "parasitic extraction"); everything after
# top_pex.spice exists is scripted here.
pex: results/top_pex.spice
	sed -e 's/\[/_/g' -e 's/\]//g' results/top_pex.spice > results/top_pex_sim.spice
	for m in sine saw tri; do \
	  python3 scripts/gen_pex_tb.py --mode $$m --nclk 262; \
	  ngspice -b -o results/pex_$$m.log results/tb_pex_$$m.spice; \
	done
	MPLCONFIGDIR=/tmp ../rocket-engine/.venv/bin/python scripts/check_pex.py

results/top_pex.spice:
	@echo "missing $@: extract stitch_top in Magic (ext2spice -o, see docs/magic_stitch.md)"
	@exit 1

# PDK ladder path: xschem schematic -> netlist -> 256-code DC sweep (DNL/INL).
pdkdac:
	xschem -n -o design/analog/xschem/r2r_dac8_pdk.spice -N design/analog/xschem/r2r_dac8_pdk.sch
	python3 scripts/pdk_dac_sweep.py

touchcheck:
	python3 scripts/xschem_touchcheck.py design/analog/xschem/r2r_dac8_pdk.sch

# Analog PCell layout: folded R-2R + RC macro GDS (needs the isolated
# sky130/gdsfactory venv, see requirements-gfsky130.txt).
analoglay:
	MPLCONFIGDIR=/tmp /tmp/gfsky130/bin/python scripts/gen_analog_layout.py

arch:
	@echo "TODO: archify candidate -> docs/architecture/ board"
	@exit 1
