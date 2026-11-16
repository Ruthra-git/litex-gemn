// gemm_core.v v0.7 - 4x4x4 int8 GEMM tile engine, area/timing-optimized datapath.
// Same ports and cycle-exact behavior as v0.6 (cycles = 64/LANES + 1, C valid at DONE, accumulate
// semantics, error rules). The operands of each output group are selected one cycle ahead with small
// constant-width muxes into operand registers, and results are written through per-slot register
// enables, instead of variable part-selects on wide vectors.
`default_nettype none

module gemm_core #(
    parameter LANES = 4              // 4, 8 or 16
) (
    input  wire         clk,
    input  wire         rst,         // synchronous, active high (also the soft reset)
    input  wire         start,       // pulse: begin a tile
    input  wire         done_clear,  // pulse: clear done
    input  wire         accumulate,  // sampled when start is accepted
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
    localparam OPW         = 32 * OUT_PER_CYC;

`ifndef SYNTHESIS
    initial begin
        if (LANES != 4 && LANES != 8 && LANES != 16) begin
            $display("gemm_core: LANES must be 4, 8 or 16 (got %0d)", LANES);
            $finish;
        end
    end
`endif

    reg [127:0]   a_reg, b_reg;
    reg [7:0]     cyc;
    reg           acc_mode;
    reg [OPW-1:0] opa, opb;          // operands of the output group computed in this cycle

    // ---- selection helpers: small, constant-width muxes ----
    function automatic [31:0] sel_row(input [127:0] a, input [1:0] row);
        begin
            case (row)
                2'd0:    sel_row = a[31:0];
                2'd1:    sel_row = a[63:32];
                2'd2:    sel_row = a[95:64];
                default: sel_row = a[127:96];
            endcase
        end
    endfunction

    // bytes B[k][col] for k = 0..3, packed {b3, b2, b1, b0}
    function automatic [31:0] sel_col(input [127:0] b, input [1:0] col);
        reg [7:0] b0, b1, b2, b3;
        begin
            case (col)
                2'd0:    begin b0 = b[7:0];   b1 = b[39:32]; b2 = b[71:64]; b3 = b[103:96];  end
                2'd1:    begin b0 = b[15:8];  b1 = b[47:40]; b2 = b[79:72]; b3 = b[111:104]; end
                2'd2:    begin b0 = b[23:16]; b1 = b[55:48]; b2 = b[87:80]; b3 = b[119:112]; end
                default: begin b0 = b[31:24]; b1 = b[63:56]; b2 = b[95:88]; b3 = b[127:120]; end
            endcase
            sel_col = {b3, b2, b1, b0};
        end
    endfunction

    function automatic signed [31:0] dot4p(input [31:0] a, input [31:0] b);
        reg signed [7:0] a0, a1, a2, a3, b0, b1, b2, b3;
        begin
            a0 = a[7:0];  a1 = a[15:8];  a2 = a[23:16];  a3 = a[31:24];
            b0 = b[7:0];  b1 = b[15:8];  b2 = b[23:16];  b3 = b[31:24];
            dot4p = a0 * b0 + a1 * b1 + a2 * b2 + a3 * b3;
        end
    endfunction

    function automatic [31:0] slot_rd(input [511:0] c, input [3:0] i);
        begin
            case (i)
                4'd0:    slot_rd = c[31:0];
                4'd1:    slot_rd = c[63:32];
                4'd2:    slot_rd = c[95:64];
                4'd3:    slot_rd = c[127:96];
                4'd4:    slot_rd = c[159:128];
                4'd5:    slot_rd = c[191:160];
                4'd6:    slot_rd = c[223:192];
                4'd7:    slot_rd = c[255:224];
                4'd8:    slot_rd = c[287:256];
                4'd9:    slot_rd = c[319:288];
                4'd10:   slot_rd = c[351:320];
                4'd11:   slot_rd = c[383:352];
                4'd12:   slot_rd = c[415:384];
                4'd13:   slot_rd = c[447:416];
                4'd14:   slot_rd = c[479:448];
                default: slot_rd = c[511:480];
            endcase
        end
    endfunction

    integer o1, o2, o3, s1;
    reg [3:0]   idx4, cn4, idxn4;
    reg [OPW-1:0]           newv;    // value each lane stores this cycle
    reg [4*OUT_PER_CYC-1:0] slot;    // destination slot of each lane this cycle
    reg [OPW-1:0]           nopa, nopb;   // operands of the next group
    reg [OPW-1:0]           iopa, iopb;   // operands of the first group (taken at accept)

    // result of this cycle's output group
    always @* begin
        newv = {OPW{1'b0}};
        slot = {(4*OUT_PER_CYC){1'b0}};
        for (o1 = 0; o1 < OUT_PER_CYC; o1 = o1 + 1) begin
            idx4 = cyc[3:0] * OUT_PER_CYC + o1;
            slot[4*o1 +: 4] = idx4;
            newv[32*o1 +: 32] = (acc_mode ? slot_rd(c_flat, idx4) : 32'd0)
                                + dot4p(opa[32*o1 +: 32], opb[32*o1 +: 32]);
        end
    end

    // operands for the next group, selected from the latched tile
    always @* begin
        nopa = {OPW{1'b0}};
        nopb = {OPW{1'b0}};
        cn4  = cyc[3:0] + 4'd1;
        for (o2 = 0; o2 < OUT_PER_CYC; o2 = o2 + 1) begin
            idxn4 = cn4 * OUT_PER_CYC + o2;
            nopa[32*o2 +: 32] = sel_row(a_reg, idxn4[3:2]);
            nopb[32*o2 +: 32] = sel_col(b_reg, idxn4[1:0]);
        end
    end

    // operands for group 0 (row 0, columns 0..OUT_PER_CYC-1), taken from the inputs at accept
    always @* begin
        iopa = {OPW{1'b0}};
        iopb = {OPW{1'b0}};
        for (o3 = 0; o3 < OUT_PER_CYC; o3 = o3 + 1) begin
            iopa[32*o3 +: 32] = a_flat[31:0];
            iopb[32*o3 +: 32] = sel_col(b_flat, o3);
        end
    end

    always @(posedge clk) begin
        if (rst) begin
            busy     <= 1'b0;
            done     <= 1'b0;
            error    <= 1'b0;
            cyc      <= 8'd0;
            cycles   <= 16'd0;
            c_flat   <= 512'd0;
            a_reg    <= 128'd0;
            b_reg    <= 128'd0;
            acc_mode <= 1'b0;
            opa      <= {OPW{1'b0}};
            opb      <= {OPW{1'b0}};
        end else begin
            if (done_clear) done <= 1'b0;

            if (start) begin
                if (busy) begin
                    error <= 1'b1;               // start while busy: ignored
                end else begin
                    error    <= 1'b0;
                    done     <= 1'b0;
                    busy     <= 1'b1;
                    a_reg    <= a_flat;          // latch inputs at accept
                    b_reg    <= b_flat;
                    acc_mode <= accumulate;
                    cyc      <= 8'd0;
                    cycles   <= 16'd1;           // the accept cycle
                    opa      <= iopa;
                    opb      <= iopb;
                end
            end

            if (busy) begin
                cycles <= cycles + 16'd1;
                opa    <= nopa;
                opb    <= nopb;
                for (s1 = 0; s1 < 16; s1 = s1 + 1)
                    if (slot[4*(s1 % OUT_PER_CYC) +: 4] == s1)
                        c_flat[s1*32 +: 32] <= newv[32*(s1 % OUT_PER_CYC) +: 32];
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
