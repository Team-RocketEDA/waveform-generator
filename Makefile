# Contract-only targets. Implemented recipes run; TODO recipes fail loudly.
RTL_TB = results/tb_wave

.PHONY: rtl tran dnl waveform plot gds arch help
help:
	@echo "rtl      - icarus TB -> results/codes_{sine,saw,tri}.txt"
	@echo "tran     - RTL codes -> ngspice tran, 50 MHz update (all modes)"
	@echo "dnl      - 256-code DC sweep -> DNL/INL verdict"
	@echo "waveform - SPICE-vs-model agreement on saw tran (replaces glitch)"
	@echo "plot     - waveforms.png + dnl_inl.png"
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

gds:
	/tmp/llex/squashfs-root/AppRun librelane librelane_config.json --manual-pdk --pdk-root /home/alrida-ismail/.local/share/pdk -p sky130A -s sky130_fd_sc_hd --condensed --run-tag wave --save-views-to exports/views
	cp runs/wave/final/gds/waveform_gen.gds exports/waveform_gen.gds
	cp runs/wave/final/render/waveform_gen.png exports/gds_shot.png

arch:
	@echo "TODO: archify candidate -> docs/architecture/ board"
	@exit 1
