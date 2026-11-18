// gemm_dma_props.vh
// Formal properties for gemm_dma.v v0.6
//
// Properties:
//   F1  - legal FSM state
//   F2  - busy matches FSM
//   F3  - busy excludes done/error
//   F4  - done and error never coexist
//   F5  - error flag matches err_code
//   F6  - Wishbone bus-state consistency
//   F7  - descriptor validation
//   F8  - core control pulses originate from correct states
//   F9  - A/B loads only occur following acknowledged reads
//
// Optional:
//   F10 - bounded termination
//   F11 - exact transfer count
//   Covers - reachability of interesting scenarios

`ifndef F_KMAX
`define F_KMAX 2
`endif

reg f_past_valid = 1'b0;

always @(posedge clk)
    f_past_valid <= 1'b1;


// ------------------------------------------------------------
// Initial reset assumption
// ------------------------------------------------------------

always @* begin
    if (!f_past_valid)
        assume(rst);
end


// ------------------------------------------------------------
// Environment assumptions
// ------------------------------------------------------------

// Slave cannot ACK and ERR simultaneously.
always @* begin
    assume(!(m_ack && m_err));
end

// Slave cannot respond without an active request.
always @* begin
    if (!m_stb) begin
        assume(!m_ack);
        assume(!m_err);
    end
end

// Restrict descriptor size for tractable formal exploration.
always @* begin
    assume(k_tiles <= `F_KMAX);
end

// Control-focused verification.
// DMA control does not branch on these data values.
always @* begin
    assume(m_dat_r == 32'd0);
    assume(c_flat  == 512'd0);
end


// ------------------------------------------------------------
// F1 - Legal FSM state
// ------------------------------------------------------------

always @* if (f_past_valid) begin
    assert(
        st == S_IDLE      ||
        st == S_CHECK     ||
        st == S_A_REQ     ||
        st == S_A_WAIT    ||
        st == S_B_REQ     ||
        st == S_B_WAIT    ||
        st == S_CLR       ||
        st == S_START     ||
        st == S_WAIT_CORE ||
        st == S_C_REQ     ||
        st == S_C_WAIT    ||
        st == S_FINISH
    );
end


// ------------------------------------------------------------
// F2 - busy reflects FSM activity
// ------------------------------------------------------------

always @* if (f_past_valid) begin
    assert(busy == (st != S_IDLE));
end


// ------------------------------------------------------------
// F3 - busy excludes done and error
// ------------------------------------------------------------

always @* if (f_past_valid) begin
    if (busy) begin
        assert(!done);
        assert(!error);
    end
end


// ------------------------------------------------------------
// F4 - done and error are mutually exclusive
// ------------------------------------------------------------

always @* if (f_past_valid) begin
    assert(!(done && error));
end


// ------------------------------------------------------------
// F5 - error flag agrees with error code
// ------------------------------------------------------------

always @* if (f_past_valid) begin
    assert(error == (err_code != 3'd0));
end


// ------------------------------------------------------------
// F6 - Wishbone bus-state consistency
// ------------------------------------------------------------

// CYC and STB remain consistent in this implementation.
always @* if (f_past_valid) begin
    assert(m_cyc == m_stb);

    assert(
        m_stb ==
        (
            st == S_A_WAIT ||
            st == S_B_WAIT ||
            st == S_C_WAIT
        )
    );

    // Write-enable is active only during C write transactions.
    assert(m_we == (st == S_C_WAIT));
end


// ------------------------------------------------------------
// F7 - Descriptor validation
// ------------------------------------------------------------

wire f_misaligned =
    (a_ptr[1:0] != 2'b00) ||
    (b_ptr[1:0] != 2'b00) ||
    (c_ptr[1:0] != 2'b00) ||
    (a_str[1:0] != 2'b00) ||
    (b_str[1:0] != 2'b00) ||
    (c_str[1:0] != 2'b00);

always @(posedge clk)
    if (f_past_valid && !$past(rst)) begin

        if ($past(st) == S_CHECK) begin

            // Misaligned descriptor.
            if ($past(f_misaligned)) begin
                assert(
                    error &&
                    err_code == E_ALIGN &&
                    !busy &&
                    st == S_IDLE
                );
            end

            // Invalid K parameter.
            else if ($past(kcnt) == 16'd0) begin
                assert(
                    error &&
                    err_code == E_PARAM &&
                    !busy &&
                    st == S_IDLE
                );
            end

            // Valid descriptor.
            else begin
                assert(
                    busy &&
                    !error &&
                    st == S_A_REQ
                );
            end
        end
    end


// ------------------------------------------------------------
// F8 - Core control pulses
// ------------------------------------------------------------

always @(posedge clk)
    if (f_past_valid && !$past(rst)) begin

        if (core_start)
            assert($past(st) == S_START);

        if (core_clr)
            assert($past(st) == S_CLR);
    end


// ------------------------------------------------------------
// F9 - A/B tile buffer loads
// ------------------------------------------------------------

always @(posedge clk)
    if (f_past_valid && !$past(rst)) begin

        if (ld_a)
            assert(
                $past(st) == S_A_WAIT &&
                $past(m_ack)
            );

        if (ld_b)
            assert(
                $past(st) == S_B_WAIT &&
                $past(m_ack)
            );
    end


// ============================================================
// Optional progress and transfer-count properties
// ============================================================

`ifdef F_PROGRESS

// ------------------------------------------------------------
// F10 - Bounded termination
//
// Generalized for TIMEOUT rather than assuming TIMEOUT=2.
//
// The bound is intentionally conservative:
//   bus transfers: 8*K + 16
//   core waits:    K
//   each wait:     TIMEOUT+1 cycles
//   additional FSM overhead
// ------------------------------------------------------------

localparam [31:0] F_KMAX = `F_KMAX;

localparam [31:0] F_BOUND =
    ((8*F_KMAX + 16 + F_KMAX) * (TIMEOUT + 1))
    + (20*F_KMAX)
    + 20;

reg [31:0] f_cnt = 32'd0;
reg [15:0] f_k   = 16'd0;

always @(posedge clk) begin

    if (rst || !busy)
        f_cnt <= 32'd0;
    else
        f_cnt <= f_cnt + 32'd1;

    if (st == S_IDLE && start)
        f_k <= k_tiles;
end

always @* if (f_past_valid) begin
    assert(f_cnt <= F_BOUND);
end


// ------------------------------------------------------------
// F11 - Exact transfer count
//
// Each K tile:
//   A reads = 4
//   B reads = 4
//
// Final output:
//   C writes = 16
//
// Expected:
//   xfers = 8*K + 16
// ------------------------------------------------------------

always @* if (f_past_valid) begin

    if (st == S_FINISH) begin
        assert(
            xfers ==
            (({16'd0, f_k} << 3) + 32'd16)
        );
    end

end


// ------------------------------------------------------------
// Reachability covers
// ------------------------------------------------------------

always @(posedge clk)
    if (f_past_valid) begin

        cover(st == S_FINISH && f_k == 16'd2);

        cover(done && !error);

        cover(error && err_code == E_ALIGN);
        cover(error && err_code == E_BUS);
        cover(error && err_code == E_TIMEOUT);
        cover(error && err_code == E_PARAM);

        cover(
            $past(st) == S_A_WAIT &&
            st == S_B_WAIT
        );

        cover(
            $past(st) == S_B_WAIT &&
            st == S_CLR
        );

        cover(
            $past(st) == S_WAIT_CORE &&
            st == S_A_REQ
        );

        cover(
            $past(st) == S_WAIT_CORE &&
            st == S_C_REQ
        );
    end

`endif
