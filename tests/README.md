# tests/ — testbench entities (harnesses, never fabricated).

| Bench | Type | DUT (legal sibling) | Contract |
|---|---|---|---|
| `tb_waveform_gen.v` | hdl | `waveform_gen` | drives sine/saw/tri, writes `results/codes_*.txt`, dumps `results/wave.vcd` |
| tran decks (generated) | spice | `wave_top` | `scripts/gen_spice_tb.py` output → `results/tb_tran_*.spice`; analyses live here, not in `design/` |
| dc decks (generated) | spice | `r2r_dac8` | `scripts/measure_dnl_inl.py` output → per-code `.op` + `print`, verdict in `results/dnl_inl.txt` |
| waveform check | spice-tran | `wave_top` | `scripts/check_waveform.py`: SPICE vs analytic reference (tau chase), verdict in `results/waveform_check.txt` |

Rule: handwritten sources are saved here and never overwritten by generators;
generated decks land in `results/` (exhaust).
