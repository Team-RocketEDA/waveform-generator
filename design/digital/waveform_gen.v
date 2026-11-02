// waveform_gen.v — 8-bit programmable waveform generator (synthesizable RTL).
//
// Hierarchy: wave_top (assembly) -> waveform_gen (hdl_component) -> sine ROM.
// Analog (R-2R DAC + RC) lives in design/analog/ and is NOT part of this file.
//
// Modes:
//   2'b00 : sine     (256-entry LUT, unsigned offset-binary, mid=128)
//   2'b01 : sawtooth (phase accumulator output directly)
//   2'b10 : triangle (full-scale fold of phase: 0,2,...,254,255,253,...,1)
//   2'b11 : hold     (dout holds last value, phase still advances when en=1)
//
// Frequency = (step / 256) * f_clk. step=1 gives one full period per 256 clks.
// Reset is async active-low. Enable gates phase advance and dout update.
//
// Sky130 note: pure synchronous logic + ROM. No PDK cells inferred here;
// synthesis maps to sky130_fd_sc_hd via yosys/librelane later.
`default_nettype none

module waveform_gen #(
    parameter integer WIDTH = 8,
    parameter integer LUT_SIZE = 256
) (
    input  wire             clk,
    input  wire             rst_n,
    input  wire             en,
    input  wire [1:0]       mode,
    input  wire [WIDTH-1:0] step,
    output reg  [WIDTH-1:0] dout,
    output wire [WIDTH-1:0] phase_out
);

    reg [WIDTH-1:0] phase;

    // 256x8 sine ROM (generated case table, scripts/gen_lut.py).
    // Pure logic, no SRAM macro; sim and synthesis elaborate the same gates.
    wire [WIDTH-1:0] sine_val;
    sine_rom u_sine_rom (.addr(phase), .dout(sine_val));
    wire [WIDTH-1:0] saw_val  = phase;
    // Full-scale triangle without multiplier:
    // rising  : phase 0..127   -> 0,2,...,254
    // falling : phase 128..255 -> 255,253,...,1
    wire [WIDTH-1:0] tri_val =
        (phase[WIDTH-1] == 1'b0) ? {phase[WIDTH-2:0], 1'b0}
                                 : {~phase[WIDTH-2:0], 1'b1};

    assign phase_out = phase;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            phase <= {WIDTH{1'b0}};
            dout  <= {WIDTH{1'b0}};
        end else if (en) begin
            phase <= phase + step;
            case (mode)
                2'b00:   dout <= sine_val;
                2'b01:   dout <= saw_val;
                2'b10:   dout <= tri_val;
                default: dout <= dout; // 2'b11 hold
            endcase
        end
    end

endmodule
`default_nettype wire
