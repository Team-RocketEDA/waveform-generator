// tb_waveform_gen.v — RTL testbench (testbench entity, not synthesized).
// Drives waveform_gen through sine/saw/triangle, writes decimal code
// streams for the SPICE TB to consume: results/codes_sine.txt etc.
// Also dumps results/wave.vcd for GTKWave.
`timescale 1ns/1ps

module tb_waveform_gen;

    reg clk = 0;
    reg rst_n = 0;
    reg en = 0;
    reg [1:0] mode = 2'b00;
    reg [7:0] step = 8'd1;
    wire [7:0] dout;
    wire [7:0] phase_out;

    waveform_gen dut (
        .clk(clk), .rst_n(rst_n), .en(en),
        .mode(mode), .step(step),
        .dout(dout), .phase_out(phase_out)
    );

    always #5 clk = ~clk; // 100 MHz sim clock (period 10 ns)

    integer f;
    integer i;

    task run_mode(input [1:0] m, input [8*64-1:0] fname);
        begin
            mode = m;
            // resync phase for a clean 0..255 period per mode
            rst_n = 0; #20; rst_n = 1; #10;
            en = 1;
            f = $fopen(fname, "w");
            // 260 cycles: 4 pipeline-fill + 256 period codes
            // dout lags phase by 1 clk (registered); sample after each posedge.
            for (i = 0; i < 260; i = i + 1) begin
                @(posedge clk); #1;
                if (i >= 4) $fwrite(f, "%0d\n", dout);
            end
            $fclose(f);
            en = 0;
            $display("wrote %s (mode %b)", fname, m);
        end
    endtask

    initial begin
        $dumpfile("results/wave.vcd");
        $dumpvars(0, tb_waveform_gen);
        #15 rst_n = 1;
        run_mode(2'b00, "results/codes_sine.txt");
        run_mode(2'b01, "results/codes_saw.txt");
        run_mode(2'b10, "results/codes_tri.txt");
        $display("TB DONE");
        $finish;
    end

endmodule
