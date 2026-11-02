# docs/architecture/ — inspectable block boards (archify, gates pass; browser-check skipped: no Chrome on this box).

- [Top: LUT -> R-2R -> LPF](wave-top.html) — the three stages as separate blocks with bus widths.
- [Stage 1: digital LUT](stage1.html) — phase acc, sine ROM, saw/tri fold, mode mux.
- [Stage 2: R-2R DAC](stage2.html) — switches, shunts, series chain, termination.
- [Stage 3: RC filter](stage3.html) — series R, shunt C, vfilt out.

Candidates live in `.archify/` (re-finalize from there). Evidence pins `--repo-root` + commit `f51d2d5`.

## L0: wave_top (LUT -> R-2R -> RC)

| Edge | Bus | Width | Carries |
|---|---|---|---|
| phase acc -> LUT/mux | `phase` | 8 b | sample index (step-programmable rate) |
| mux -> pins | `dout` = b7..b0 | 8 b digital | waveform codes (sine/saw/tri) |
| pins -> DAC | ideal bit Vs | 8 × 0/1.8 V | switch states (Ron=0 this rev) |
| DAC -> filter | `vdac` | analog V | staircase, 0–1.793 V, LSB 7.03 mV |
| filter -> out | `vfilt` | analog V | reconstructed sine/saw/tri, fc ≈ 3.4 MHz |

## Drill-down (one page each, archify `architecture` finalize)

1. `waveform_gen` — phase acc, sine ROM (256×8), tri fold, mode mux; ports
   clk/rst_n/en/mode/step/dout/phase_out.
2. `r2r_dac8` — R/2R ladder, termination, ideal-switch assumption + Ron budget
   for the sky130 transmission-gate revision.
3. `rc_filter` — R/C choice vs fout (~195 kHz @ 50 MHz update) and step
   rate (50 MHz): barely-there smoothing, ~3 deg shift, ~50 ns delay;
   buffer insertion point for the future op-amp IP.
4. `interface` — full port table + DNL/INL contract (≤ 1 LSB) + GDS stitch plan.

Rendering: `archify finalize architecture candidate.json <page>.html --quality
showcase`, one candidate per page; `.md` stays source of truth (albert pattern).
