// gemm_wb.v v0.3 - Wishbone B4 classic slave around gemm_core.
// 256-byte window, 32-bit data, word address wb_adr[5:0]. See docs/SPEC.md for the map.
`default_nettype none

module gemm_wb #(
    parameter LANES = 4
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        wb_cyc,
    input  wire        wb_stb,
    input  wire        wb_we,
    input  wire [5:0]  wb_adr,
    input  wire [31:0] wb_dat_w,
    input  wire [3:0]  wb_sel,
    output reg  [31:0] wb_dat_r,
    output reg         wb_ack,
    output wire        irq
);
    localparam [7:0]  LANES8   = LANES;
    localparam [31:0] ID_VAL   = 32'h47454D4D;               // "GEMM"
    localparam [31:0] INFO_VAL = {16'h0003, 8'd4, LANES8};   // version, tile dim, LANES

    reg [127:0] a_buf, b_buf;
    reg         acc_en, irq_en;
    reg         start_p, clear_p, srst_p;

    wire [511:0] c_flat;
    wire         busy, done, error;
    wire [15:0]  cycles;

    gemm_core #(.LANES(LANES)) u_core (
        .clk        (clk),
        .rst        (rst | srst_p),
        .start      (start_p),
        .done_clear (clear_p),
        .accumulate (acc_en),
        .a_flat     (a_buf),
        .b_flat     (b_buf),
        .c_flat     (c_flat),
        .busy       (busy),
        .done       (done),
        .error      (error),
        .cycles     (cycles)
    );

    assign irq = done & irq_en;

    // ---- address decode (word address) ----
    wire [5:0] w      = wb_adr;
    wire is_ab        = (w[5:3] == 3'b000);   // words 0..7: A (0..3), B (4..7)
    wire is_b         = w[2];
    wire [1:0] ab_idx = w[1:0];
    wire is_c         = (w[5:4] == 2'b01);    // words 16..31
    wire is_reg       = (w[5:3] == 3'b100);   // words 32..39
    wire access       = wb_cyc & wb_stb & ~wb_ack;

    function [31:0] merge(input [31:0] old, input [31:0] nw, input [3:0] sel);
        reg [31:0] r;
        begin
            r[31:24] = sel[3] ? nw[31:24] : old[31:24];
            r[23:16] = sel[2] ? nw[23:16] : old[23:16];
            r[15:8]  = sel[1] ? nw[15:8]  : old[15:8];
            r[7:0]   = sel[0] ? nw[7:0]   : old[7:0];
            merge = r;
        end
    endfunction

    // ---- read mux ----
    reg [31:0] rdata;
    always @* begin
        rdata = 32'd0;
        if (is_reg) begin
            case (w[2:0])
                3'd0:    rdata = {29'd0, irq_en, acc_en, 1'b0};
                3'd1:    rdata = {29'd0, error, done, busy};
                3'd2:    rdata = {16'd0, cycles};
                3'd3:    rdata = ID_VAL;
                3'd4:    rdata = INFO_VAL;
                default: rdata = 32'd0;
            endcase
        end else if (is_c) begin
            rdata = c_flat[{w[3:0], 5'd0} +: 32];
        end else if (is_ab) begin
            rdata = is_b ? b_buf[{ab_idx, 5'd0} +: 32]
                         : a_buf[{ab_idx, 5'd0} +: 32];
        end
    end

    // ---- bus logic: one transfer = 2 cycles (access, then ack) ----
    always @(posedge clk) begin
        if (rst) begin
            a_buf    <= 128'd0;
            b_buf    <= 128'd0;
            acc_en   <= 1'b0;
            irq_en   <= 1'b0;
            start_p  <= 1'b0;
            clear_p  <= 1'b0;
            srst_p   <= 1'b0;
            wb_ack   <= 1'b0;
            wb_dat_r <= 32'd0;
        end else begin
            wb_ack  <= 1'b0;
            start_p <= 1'b0;
            clear_p <= 1'b0;
            srst_p  <= 1'b0;
            if (access) begin
                wb_ack <= 1'b1;
                if (wb_we) begin
                    if (is_ab) begin
                        if (is_b)
                            b_buf[{ab_idx, 5'd0} +: 32] <=
                                merge(b_buf[{ab_idx, 5'd0} +: 32], wb_dat_w, wb_sel);
                        else
                            a_buf[{ab_idx, 5'd0} +: 32] <=
                                merge(a_buf[{ab_idx, 5'd0} +: 32], wb_dat_w, wb_sel);
                    end else if (is_reg && w[2:0] == 3'd0 && wb_sel[0]) begin
                        start_p <= wb_dat_w[0];
                        acc_en  <= wb_dat_w[1];
                        irq_en  <= wb_dat_w[2];
                        srst_p  <= wb_dat_w[3];
                        clear_p <= wb_dat_w[4];
                    end
                    // writes to C, STATUS, CYCLES, ID, INFO and unmapped words are ignored
                end else begin
                    wb_dat_r <= rdata;
                end
            end
        end
    end
endmodule
`default_nettype wire
