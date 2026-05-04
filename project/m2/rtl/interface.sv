// =============================================================================
// interface.sv
//
// AXI4-Lite + AXI4-Stream interface wrapper around compute_core.
//
// Project   : Hardware Accelerator for Reservoir State Update in ESNs
// Course    : ECE 510 — Hardware for AI/ML, Spring 2026, Portland State Univ.
// Author    : Venkata Sriram Kamarajugadda
// Milestone : M2
//
// -----------------------------------------------------------------------------
// PROTOCOL CONFORMANCE
// -----------------------------------------------------------------------------
// Implements:
//   - AXI4-Lite slave port for configuration and status (5 channels:
//     AW, W, B, AR, R) per ARM IHI 0022 §B1.
//   - AXI4-Stream slave port for streamed (weight, x_prev) operand pairs
//     per ARM IHI 0051 §2 (TVALID/TREADY handshake honored).
//
// Reset: synchronous, active-high (rst). All registers reset to 0.
// Single clock domain: clk.
//
// -----------------------------------------------------------------------------
// DESIGN PATTERN — COMBINATIONAL READY, REGISTERED EVERYTHING ELSE
// -----------------------------------------------------------------------------
// AXI4-Lite slaves should NOT register the *ready signals through a normal
// always_ff. If awready is registered, it doesn't change until a clock edge,
// which means a master driving awvalid on cycle N cannot complete the
// handshake until cycle N+1 at the earliest. Worse, if the FSM checks
// "if (awvalid && awready)" inside the same always_ff that updates
// awready, the registered value of awready (still 0 after reset) prevents
// the handshake from ever being detected.
//
// Standard pattern used here:
//   - awready / wready / arready are COMBINATIONAL outputs derived from FSM
//     state and any capture flags.
//   - bvalid / rvalid / rdata are REGISTERED.
//   - Registered captures (awaddr_reg, etc.) and FSM state update on the
//     rising edge.
//
// -----------------------------------------------------------------------------
// AXI4-LITE REGISTER MAP (32-bit aligned, byte-addressable)
// -----------------------------------------------------------------------------
//
//   Address  Name        Access  Description
//   -------  ----------  ------  -----------------------------------------
//   0x00     CTRL        W       bit[0] = start pulse (self-clearing)
//   0x04     STATUS      R       bit[0] = busy, bit[1] = done (sticky)
//   0x08     N_MINUS_1   W       Dot-product length minus 1 (low 16 bits)
//   0x0C     LEAK_RATE   W       Q15 leak rate (low 16 bits)
//   0x10     WIN_U       W       Q30 input projection (full 32 bits)
//   0x14     X_PREV      W       Q15 x_prev_self for this neuron (low 16)
//   0x18     X_NEW       R       Q15 x_new captured from last update
//
// -----------------------------------------------------------------------------
// AXI4-STREAM PACKING
// -----------------------------------------------------------------------------
// Each TDATA beat (32 bits) = { x_data[15:0], w_data[15:0] }
//   tdata[31:16] = x_prev[k]
//   tdata[15:0]  = w[k]
// =============================================================================

module interface_axi #(
    parameter int AXIL_ADDR_W = 8,
    parameter int AXIL_DATA_W = 32,
    parameter int AXIS_DATA_W = 32
) (
    input  logic                          clk,
    input  logic                          rst,

    // AXI4-Lite slave
    input  logic [AXIL_ADDR_W-1:0]        s_axil_awaddr,
    input  logic                          s_axil_awvalid,
    output logic                          s_axil_awready,

    input  logic [AXIL_DATA_W-1:0]        s_axil_wdata,
    input  logic [(AXIL_DATA_W/8)-1:0]    s_axil_wstrb,
    input  logic                          s_axil_wvalid,
    output logic                          s_axil_wready,

    output logic [1:0]                    s_axil_bresp,
    output logic                          s_axil_bvalid,
    input  logic                          s_axil_bready,

    input  logic [AXIL_ADDR_W-1:0]        s_axil_araddr,
    input  logic                          s_axil_arvalid,
    output logic                          s_axil_arready,

    output logic [AXIL_DATA_W-1:0]        s_axil_rdata,
    output logic [1:0]                    s_axil_rresp,
    output logic                          s_axil_rvalid,
    input  logic                          s_axil_rready,

    // AXI4-Stream slave
    input  logic [AXIS_DATA_W-1:0]        s_axis_tdata,
    input  logic                          s_axis_tvalid,
    output logic                          s_axis_tready,
    input  logic                          s_axis_tlast       // ignored
);

    // -------------------------------------------------------------------------
    // Register addresses
    // -------------------------------------------------------------------------
    localparam logic [7:0] ADDR_CTRL      = 8'h00;
    localparam logic [7:0] ADDR_STATUS    = 8'h04;
    localparam logic [7:0] ADDR_N_MINUS_1 = 8'h08;
    localparam logic [7:0] ADDR_LEAK_RATE = 8'h0C;
    localparam logic [7:0] ADDR_WIN_U     = 8'h10;
    localparam logic [7:0] ADDR_X_PREV    = 8'h14;
    localparam logic [7:0] ADDR_X_NEW     = 8'h18;

    localparam logic [1:0] RESP_OKAY = 2'b00;

    // -------------------------------------------------------------------------
    // Configuration registers (written by AXI4-Lite)
    // -------------------------------------------------------------------------
    logic [15:0]        reg_n_minus_1;
    logic signed [15:0] reg_leak_rate;
    logic signed [31:0] reg_win_u;
    logic signed [15:0] reg_x_prev;

    logic               start_pulse;     // single-cycle pulse to compute_core

    // -------------------------------------------------------------------------
    // compute_core instance
    // -------------------------------------------------------------------------
    logic signed [15:0] core_w_data;
    logic               core_w_valid;
    logic signed [15:0] core_x_data;
    logic               core_x_valid;

    logic               core_busy;
    logic               core_accepting_data;
    logic               core_done;
    logic               core_x_new_valid;
    logic signed [15:0] core_x_new;

    compute_core u_core (
        .clk         (clk),
        .rst         (rst),
        .start       (start_pulse),
        .N_minus_1   (reg_n_minus_1),
        .leak_rate   (reg_leak_rate),
        .win_u       (reg_win_u),
        .x_prev_self (reg_x_prev),

        .w_data      (core_w_data),
        .w_valid     (core_w_valid),
        .x_data      (core_x_data),
        .x_valid     (core_x_valid),

        .busy           (core_busy),
        .accepting_data (core_accepting_data),
        .x_new          (core_x_new),
        .x_new_valid    (core_x_new_valid),
        .done           (core_done)
    );

    // -------------------------------------------------------------------------
    // Latch x_new and sticky 'done' status
    // -------------------------------------------------------------------------
    logic signed [15:0] reg_x_new;
    logic               sticky_done;

    always_ff @(posedge clk) begin
        if (rst) begin
            reg_x_new   <= '0;
            sticky_done <= 1'b0;
        end else begin
            if (core_x_new_valid)
                reg_x_new <= core_x_new;
            if (core_done)
                sticky_done <= 1'b1;
            else if (start_pulse)
                sticky_done <= 1'b0;
        end
    end

    // =========================================================================
    // AXI4-LITE WRITE — combinational ready, registered B response
    //
    // The slave can accept AW and W in either order (AXI4-Lite §B1.5).
    // We use two capture flags to remember when each side has been
    // accepted, and complete the write (latching into the register file
    // and asserting B) when both have arrived.
    //
    // ready signals:
    //   awready = 1 when we don't already have an awaddr captured AND we're
    //             not in the middle of a B response.
    //   wready  = 1 when we don't already have wdata captured AND we're
    //             not in the middle of a B response.
    // =========================================================================
    logic [7:0]         awaddr_q;     // captured AW address
    logic               aw_q_valid;   // we have a valid captured AW

    logic [31:0]        wdata_q;      // captured W data
    logic               w_q_valid;    // we have a valid captured W

    logic               b_pending;    // bvalid is high, waiting for bready

    // Combinational ready: accept new AW/W only when slot is empty and no
    // outstanding B response is pending.
    assign s_axil_awready = !aw_q_valid && !b_pending;
    assign s_axil_wready  = !w_q_valid  && !b_pending;

    // Detect when this cycle's transfers occur
    logic aw_xfer;  // address transfer this cycle
    logic w_xfer;   // data transfer this cycle
    assign aw_xfer = s_axil_awvalid && s_axil_awready;
    assign w_xfer  = s_axil_wvalid  && s_axil_wready;

    // Decoded write address (from this cycle's transfer or latched)
    logic [7:0] write_addr;
    logic [31:0] write_data;
    assign write_addr = aw_q_valid ? awaddr_q : s_axil_awaddr;
    assign write_data = w_q_valid  ? wdata_q  : s_axil_wdata;

    // The write completes when both AW and W are available
    // (either both transfer this cycle OR a previously captured one + the other transferring now)
    logic write_complete;
    assign write_complete = (aw_q_valid || aw_xfer) && (w_q_valid || w_xfer)
                            && !b_pending;

    always_ff @(posedge clk) begin
        if (rst) begin
            aw_q_valid    <= 1'b0;
            awaddr_q      <= '0;
            w_q_valid     <= 1'b0;
            wdata_q       <= '0;
            b_pending     <= 1'b0;
            s_axil_bvalid <= 1'b0;
            s_axil_bresp  <= RESP_OKAY;

            reg_n_minus_1 <= '0;
            reg_leak_rate <= '0;
            reg_win_u     <= '0;
            reg_x_prev    <= '0;
            start_pulse   <= 1'b0;
        end else begin
            // Default: pulse signals only fire one cycle
            start_pulse <= 1'b0;

            // Capture AW if accepted but no W yet (or both this cycle and we'll consume in same cycle below)
            if (aw_xfer && !write_complete) begin
                awaddr_q   <= s_axil_awaddr;
                aw_q_valid <= 1'b1;
            end
            if (w_xfer && !write_complete) begin
                wdata_q   <= s_axil_wdata;
                w_q_valid <= 1'b1;
            end

            // Complete the write
            if (write_complete) begin
                // Apply write to register file
                unique case (write_addr)
                    ADDR_CTRL: begin
                        if (write_data[0]) start_pulse <= 1'b1;
                    end
                    ADDR_N_MINUS_1: reg_n_minus_1 <= write_data[15:0];
                    ADDR_LEAK_RATE: reg_leak_rate <= write_data[15:0];
                    ADDR_WIN_U:     reg_win_u     <= write_data[31:0];
                    ADDR_X_PREV:    reg_x_prev    <= write_data[15:0];
                    default: ; // unmapped: silent write
                endcase

                // Clear capture flags, raise B response
                aw_q_valid    <= 1'b0;
                w_q_valid     <= 1'b0;
                b_pending     <= 1'b1;
                s_axil_bvalid <= 1'b1;
                s_axil_bresp  <= RESP_OKAY;
            end

            // Drop B once accepted by master
            if (s_axil_bvalid && s_axil_bready) begin
                s_axil_bvalid <= 1'b0;
                b_pending     <= 1'b0;
            end
        end
    end

    // =========================================================================
    // AXI4-LITE READ — combinational arready, registered R response
    // =========================================================================
    logic       r_pending;

    assign s_axil_arready = !r_pending;

    logic ar_xfer;
    assign ar_xfer = s_axil_arvalid && s_axil_arready;

    always_ff @(posedge clk) begin
        if (rst) begin
            r_pending     <= 1'b0;
            s_axil_rvalid <= 1'b0;
            s_axil_rresp  <= RESP_OKAY;
            s_axil_rdata  <= '0;
        end else begin
            if (ar_xfer) begin
                // Combinational decode of read data
                unique case (s_axil_araddr[7:0])
                    ADDR_STATUS: s_axil_rdata <= {30'h0, sticky_done, core_busy};
                    ADDR_X_NEW:  s_axil_rdata <= {{16{reg_x_new[15]}}, reg_x_new};
                    default:     s_axil_rdata <= 32'h0;
                endcase
                s_axil_rvalid <= 1'b1;
                s_axil_rresp  <= RESP_OKAY;
                r_pending     <= 1'b1;
            end

            if (s_axil_rvalid && s_axil_rready) begin
                s_axil_rvalid <= 1'b0;
                r_pending     <= 1'b0;
            end
        end
    end

    // =========================================================================
    // AXI4-STREAM SLAVE
    // =========================================================================
    assign s_axis_tready = core_accepting_data;
    assign core_w_data   = s_axis_tdata[15:0];
    assign core_x_data   = s_axis_tdata[31:16];
    assign core_w_valid  = s_axis_tvalid && s_axis_tready;
    assign core_x_valid  = s_axis_tvalid && s_axis_tready;

endmodule
