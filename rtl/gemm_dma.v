// gemm_dma.v v0.5 - descriptor-driven DMA master for gemm_core.
// One descriptor = one 4x4 output tile: K_TILES steps of (fetch A tile, fetch B tile, compute,
// accumulate), then one write-back of the 16 C words. Byte addresses; classic Wishbone master.
`default_nettype none

module gemm_dma #(
    parameter TIMEOUT = 1024
) (
    input  wire         clk,
    input  wire         rst,

    input  wire         start,
    input  wire         clr,
    input  wire         acc_first,
    input  wire [31:0]  a_addr,
    input  wire [31:0]  a_stride,
    input  wire [31:0]  b_addr,
    input  wire [31:0]  b_stride,
    input  wire [31:0]  c_addr,
    input  wire [31:0]  c_stride,
    input  wire [15:0]  k_tiles,

    output reg          busy,
    output reg          done,
    output reg          error,
    output reg  [2:0]   err_code,
    output reg  [31:0]  cycles,

    output reg          core_clr,
    output reg          core_start,
    output reg          core_acc,
    input  wire         core_done,
    input  wire [511:0] c_flat,

    output reg          ld_a,
    output reg          ld_b,
    output reg  [1:0]   ld_idx,
    output reg  [31:0]  ld_data,

    output reg          m_cyc,
    output reg          m_stb,
    output reg          m_we,
    output reg  [31:0]  m_adr,
    output reg  [31:0]  m_dat_w,
    output reg  [3:0]   m_sel,
    input  wire [31:0]  m_dat_r,
    input  wire         m_ack,
    input  wire         m_err
);
    localparam [3:0] S_IDLE = 4'd0, S_CHECK = 4'd1, S_A_REQ = 4'd2, S_A_WAIT = 4'd3,
                     S_B_REQ = 4'd4, S_B_WAIT = 4'd5, S_CLR = 4'd6, S_START = 4'd7,
                     S_WAIT_CORE = 4'd8, S_C_REQ = 4'd9, S_C_WAIT = 4'd10, S_FINISH = 4'd11;
    localparam [2:0] E_ALIGN = 3'd1, E_BUS = 3'd2, E_TIMEOUT = 3'd3, E_PARAM = 3'd4;

    reg [3:0]  st;
    reg [31:0] a_ptr, b_ptr, c_ptr, a_str, b_str, c_str;
    reg [15:0] kcnt;
    reg        first, accf;
    reg [31:0] cur_adr, row_base;
    reg [4:0]  idx;
    reg [15:0] to_cnt;

    always @(posedge clk) begin
        if (rst) begin
            st <= S_IDLE;   busy <= 1'b0;  done <= 1'b0;  error <= 1'b0;
            err_code <= 3'd0;  cycles <= 32'd0;
            core_clr <= 1'b0;  core_start <= 1'b0;  core_acc <= 1'b0;
            ld_a <= 1'b0;  ld_b <= 1'b0;  ld_idx <= 2'd0;  ld_data <= 32'd0;
            m_cyc <= 1'b0;  m_stb <= 1'b0;  m_we <= 1'b0;
            m_adr <= 32'd0;  m_dat_w <= 32'd0;  m_sel <= 4'd0;
            a_ptr <= 32'd0;  b_ptr <= 32'd0;  c_ptr <= 32'd0;
            a_str <= 32'd0;  b_str <= 32'd0;  c_str <= 32'd0;
            kcnt <= 16'd0;  first <= 1'b0;  accf <= 1'b0;
            cur_adr <= 32'd0;  row_base <= 32'd0;  idx <= 5'd0;  to_cnt <= 16'd0;
        end else begin
            core_clr   <= 1'b0;
            core_start <= 1'b0;
            ld_a       <= 1'b0;
            ld_b       <= 1'b0;
            if (clr && !busy) begin
                done <= 1'b0;  error <= 1'b0;  err_code <= 3'd0;
            end
            if (busy) cycles <= cycles + 32'd1;

            case (st)
            S_IDLE: begin
                if (start) begin
                    busy <= 1'b1;  done <= 1'b0;  error <= 1'b0;  err_code <= 3'd0;
                    cycles <= 32'd0;
                    a_ptr <= a_addr;  b_ptr <= b_addr;  c_ptr <= c_addr;
                    a_str <= a_stride;  b_str <= b_stride;  c_str <= c_stride;
                    kcnt <= k_tiles;  first <= 1'b1;  accf <= acc_first;
                    st <= S_CHECK;
                end
            end

            S_CHECK: begin
                if (a_ptr[1:0] != 2'b00 || b_ptr[1:0] != 2'b00 || c_ptr[1:0] != 2'b00 ||
                    a_str[1:0] != 2'b00 || b_str[1:0] != 2'b00 || c_str[1:0] != 2'b00) begin
                    busy <= 1'b0;  error <= 1'b1;  err_code <= E_ALIGN;  st <= S_IDLE;
                end else if (kcnt == 16'd0) begin
                    busy <= 1'b0;  error <= 1'b1;  err_code <= E_PARAM;  st <= S_IDLE;
                end else begin
                    cur_adr <= a_ptr;  idx <= 5'd0;  st <= S_A_REQ;
                end
            end

            // ---- fetch the 4 words of the A tile ----
            S_A_REQ: begin
                m_cyc <= 1'b1;  m_stb <= 1'b1;  m_we <= 1'b0;
                m_adr <= cur_adr;  m_sel <= 4'hF;  to_cnt <= 16'd0;
                st <= S_A_WAIT;
            end
            S_A_WAIT: begin
                if (m_ack) begin
                    m_cyc <= 1'b0;  m_stb <= 1'b0;
                    ld_a <= 1'b1;  ld_idx <= idx[1:0];  ld_data <= m_dat_r;
                    if (idx == 5'd3) begin
                        idx <= 5'd0;  cur_adr <= b_ptr;  st <= S_B_REQ;
                    end else begin
                        idx <= idx + 5'd1;  cur_adr <= cur_adr + a_str;  st <= S_A_REQ;
                    end
                end else if (m_err) begin
                    m_cyc <= 1'b0;  m_stb <= 1'b0;
                    busy <= 1'b0;  error <= 1'b1;  err_code <= E_BUS;  st <= S_IDLE;
                end else if (to_cnt >= TIMEOUT) begin
                    m_cyc <= 1'b0;  m_stb <= 1'b0;
                    busy <= 1'b0;  error <= 1'b1;  err_code <= E_TIMEOUT;  st <= S_IDLE;
                end else begin
                    to_cnt <= to_cnt + 16'd1;
                end
            end

            // ---- fetch the 4 words of the B tile ----
            S_B_REQ: begin
                m_cyc <= 1'b1;  m_stb <= 1'b1;  m_we <= 1'b0;
                m_adr <= cur_adr;  m_sel <= 4'hF;  to_cnt <= 16'd0;
                st <= S_B_WAIT;
            end
            S_B_WAIT: begin
                if (m_ack) begin
                    m_cyc <= 1'b0;  m_stb <= 1'b0;
                    ld_b <= 1'b1;  ld_idx <= idx[1:0];  ld_data <= m_dat_r;
                    if (idx == 5'd3) begin
                        idx <= 5'd0;  st <= S_CLR;
                    end else begin
                        idx <= idx + 5'd1;  cur_adr <= cur_adr + b_str;  st <= S_B_REQ;
                    end
                end else if (m_err) begin
                    m_cyc <= 1'b0;  m_stb <= 1'b0;
                    busy <= 1'b0;  error <= 1'b1;  err_code <= E_BUS;  st <= S_IDLE;
                end else if (to_cnt >= TIMEOUT) begin
                    m_cyc <= 1'b0;  m_stb <= 1'b0;
                    busy <= 1'b0;  error <= 1'b1;  err_code <= E_TIMEOUT;  st <= S_IDLE;
                end else begin
                    to_cnt <= to_cnt + 16'd1;
                end
            end

            // ---- run the core for this K step ----
            S_CLR: begin
                core_clr <= 1'b1;
                st <= S_START;
            end
            S_START: begin
                core_start <= 1'b1;
                core_acc   <= first ? accf : 1'b1;
                to_cnt     <= 16'd0;
                st <= S_WAIT_CORE;
            end
            S_WAIT_CORE: begin
                if (core_done) begin
                    first <= 1'b0;
                    if (kcnt == 16'd1) begin
                        cur_adr <= c_ptr;  row_base <= c_ptr;  idx <= 5'd0;  st <= S_C_REQ;
                    end else begin
                        kcnt  <= kcnt - 16'd1;
                        a_ptr <= a_ptr + 32'd4;
                        b_ptr <= b_ptr + {b_str[29:0], 2'b00};
                        cur_adr <= a_ptr + 32'd4;
                        idx <= 5'd0;
                        st <= S_A_REQ;
                    end
                end else if (to_cnt >= TIMEOUT) begin
                    busy <= 1'b0;  error <= 1'b1;  err_code <= E_TIMEOUT;  st <= S_IDLE;
                end else begin
                    to_cnt <= to_cnt + 16'd1;
                end
            end

            // ---- write back the 16 C words ----
            S_C_REQ: begin
                m_cyc <= 1'b1;  m_stb <= 1'b1;  m_we <= 1'b1;
                m_adr <= cur_adr;  m_sel <= 4'hF;
                m_dat_w <= c_flat[{idx[3:0], 5'd0} +: 32];
                to_cnt <= 16'd0;
                st <= S_C_WAIT;
            end
            S_C_WAIT: begin
                if (m_ack) begin
                    m_cyc <= 1'b0;  m_stb <= 1'b0;  m_we <= 1'b0;
                    if (idx == 5'd15) begin
                        st <= S_FINISH;
                    end else begin
                        idx <= idx + 5'd1;
                        if (idx[1:0] == 2'd3) begin
                            row_base <= row_base + c_str;
                            cur_adr  <= row_base + c_str;
                        end else begin
                            cur_adr <= cur_adr + 32'd4;
                        end
                        st <= S_C_REQ;
                    end
                end else if (m_err) begin
                    m_cyc <= 1'b0;  m_stb <= 1'b0;  m_we <= 1'b0;
                    busy <= 1'b0;  error <= 1'b1;  err_code <= E_BUS;  st <= S_IDLE;
                end else if (to_cnt >= TIMEOUT) begin
                    m_cyc <= 1'b0;  m_stb <= 1'b0;  m_we <= 1'b0;
                    busy <= 1'b0;  error <= 1'b1;  err_code <= E_TIMEOUT;  st <= S_IDLE;
                end else begin
                    to_cnt <= to_cnt + 16'd1;
                end
            end

            S_FINISH: begin
                busy <= 1'b0;  done <= 1'b1;  st <= S_IDLE;
            end

            default: st <= S_IDLE;
            endcase
        end
    end
endmodule
`default_nettype wire
