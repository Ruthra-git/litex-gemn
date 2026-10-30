// gemm_core.v - 4x4x4 int8 GEMM tile engine.
// C[4x4] = A[4x4] * B[4x4], int8 x int8 -> int32 (cannot overflow: |sum| <= 65536).
// LANES MACs per cycle: LANES/4 output elements complete per cycle.
`default_nettype none

module gemm_core #(
    parameter LANES = 4              // 4, 8 or 16
) (
    input  wire         clk,
    input  wire         rst,         // synchronous, active high (also the soft reset)
    input  wire         start,       // pulse: begin a tile
    input  wire         done_clear,  // pulse: clear done
    input  wire [127:0] a_flat,      // 16 x int8, row-major, element 0 in bits [7:0]
    input  wire [127:0] b_flat,      // 16 x int8, row-major (K x N)
    output reg  [511:0] c_flat,      // 16 x int32, row-major, element 0 in bits [31:0]
    output reg          busy,
    output reg          done,
    output reg          error,
    output reg  [15:0]  cycles       // accept cycle + compute cycles
);
    localparam OUT_PER_CYC = LANES / 4;
    localparam NCYC        = 16 / OUT_PER_CYC;

    initial begin
        if (LANES != 4 && LANES != 8 && LANES != 16) begin
            $display("gemm_core: LANES must be 4, 8 or 16 (got %0d)", LANES);
            $finish;
        end
    end

    reg [127:0] a_reg, b_reg;
    reg [7:0]   cyc;
    integer     o;

    // dot product of row `row` of A with column `col` of B (K = 4)
    function automatic signed [31:0] dot4(input [127:0] a, input [127:0] b,
                                          input integer row, input integer col);
        integer k;
        reg signed [7:0]  ae, be;
        reg signed [31:0] acc;
        begin
            acc = 0;
            for (k = 0; k < 4; k = k + 1) begin
                ae  = a[(row*4 + k)*8 +: 8];
                be  = b[(k*4 + col)*8 +: 8];
                acc = acc + ae * be;
            end
            dot4 = acc;
        end
    endfunction

    always @(posedge clk) begin
        if (rst) begin
            busy   <= 1'b0;
            done   <= 1'b0;
            error  <= 1'b0;
            cyc    <= 8'd0;
            cycles <= 16'd0;
            c_flat <= 512'd0;
            a_reg  <= 128'd0;
            b_reg  <= 128'd0;
        end else begin
            if (done_clear) done <= 1'b0;

            if (start) begin
                if (busy) begin
                    error <= 1'b1;               // start while busy: ignored
                end else begin
                    error  <= 1'b0;
                    done   <= 1'b0;
                    busy   <= 1'b1;
                    a_reg  <= a_flat;            // latch inputs at accept
                    b_reg  <= b_flat;
                    cyc    <= 8'd0;
                    cycles <= 16'd1;             // the accept cycle
                end
            end

            if (busy) begin
                cycles <= cycles + 16'd1;
                for (o = 0; o < OUT_PER_CYC; o = o + 1) begin
                    c_flat[(cyc*OUT_PER_CYC + o)*32 +: 32] <=
                        dot4(a_reg, b_reg, (cyc*OUT_PER_CYC + o) / 4,
                                           (cyc*OUT_PER_CYC + o) % 4);
                end
                if (cyc == NCYC - 1) begin
                    busy <= 1'b0;
                    done <= 1'b1;
                end
                cyc <= cyc + 8'd1;
            end
        end
    end
endmodule
`default_nettype wire
