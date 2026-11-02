# Provenance — waveform_gen digital macro (LibreLane Classic, run wave2)

- Source rev: RTL `design/digital/waveform_gen.v` + `sine_rom.v` at commit `3d0c048`+
- PDK: sky130A (`~/.local/share/pdk/sky130A`), SCL `sky130_fd_sc_hd`, manual root
- Config: `librelane_config.json` (SYNTH_CORNER + DEFAULT_CORNER `nom_tt_025C_1v80`)
- Flow: LibreLane 3.0.17 (`~/tools/librelane-3.0.17` AppImage, extracted), clock 20 ns
- Result: die 6306 µm², core 3942 µm² (74.2 × 85.0 µm), 40 GDS layers
- Signoff: route DRC 0, Magic DRC 0, LVS errors 0, setup WS +12.8 ns / hold +0.49 ns (tt)
- Known non-blocking: 49 max-slew violations at ss_100C corners (demo accepts tt signoff)
- Artifacts: `exports/waveform_gen.gds` (1 MB, gitignored binary),
  `exports/gds_shot.png` (LibreLane render), full views under `exports/views/`
