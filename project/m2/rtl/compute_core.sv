// =============================================================================
// compute_core.sv
//
// ESN reservoir state-update compute core (single-neuron, Option α).
//
// Project   : Hardware Accelerator for Reservoir State Update in ESNs
// Course    : ECE 510 — Hardware for AI/ML, Spring 2026, Portland State Univ.
// Author    : Venkata Sriram Kamarajugadda
// Milestone : M2
//
// -----------------------------------------------------------------------------
// PURPOSE
// -----------------------------------------------------------------------------
// Computes ONE neuron's reservoir state update of an Echo State Network:
//
//     acc = Σ_{k=0}^{N-1} w[k] * x_prev[k]   (dot product)
//     pre = acc + win_u                       (input projection)
//     act = tanh(pre)                         (PWL approx)
//     x_new = (1 - a) * x_prev_self + a * act (leak blend)
//
// All datapath elements are Q15 except internal accumulator and adder
// stages, which are Q30 in 32-bit signed format. This module instantiates:
//
//     q15_mac    — serial MAC (one weight × one state per cycle)
//     q15_tanh   — combinational 7-segment PWL tanh
//     q15_blend  — combinational leak-rate blend
//
// The reservoir-level loop (computing N neurons per timestep) is HANDLED
// EXTERNALLY by repeated invocation of this core. The core processes one
// neuron per "start..done" transaction.
//
// -----------------------------------------------------------------------------
// FSM
// -----------------------------------------------------------------------------
//
//   S_IDLE     →  wait for `start` pulse
//   S_LOAD     →  register leak_rate, win_u, x_prev_self; clear MAC accumulator
//   S_ACCUM    →  consume (w, x) stream; advance MAC each valid cycle
//   S_ADDU     →  add win_u to the MAC accumulator (one cycle)
//   S_NL       →  feed accumulator through tanh and blend (combinational); register x_new
//   S_DONE     →  assert x_new_valid + done for one cycle; return to S_IDLE
//
// -----------------------------------------------------------------------------
// CLOCK / RESET
// -----------------------------------------------------------------------------
// Single clock domain: clk.
// Reset: synchronous, active-high.
//
// -----------------------------------------------------------------------------
// PORTS
// -----------------------------------------------------------------------------
//   Name           Dir   Width        Purpose
//   ----           ---   -----        -------
//   clk            in    1            System clock
//   rst            in    1            Synchronous active-high reset
//   start          in    1            Pulse high for 1 cycle to begin update
//   N_minus_1      in    16           Dot-product length minus 1 (e.g. 999)
//   leak_rate      in    16  signed   Q15 leak rate a, in [0, +1.0)
//   win_u          in    32  signed   Q30 pre-computed Win*u(t) for this neuron
//   x_prev_self    in    16  signed   Q15 previous state x_prev[i] for this neuron
//   w_data         in    16  signed   Q15 weight w[k]
//   w_valid        in    1            Weight valid this cycle
//   x_data         in    16  signed   Q15 previous state x_prev[k]
//   x_valid        in    1            x_prev valid this cycle
//   busy           out   1            High while computing (S_LOAD..S_NL)
//   x_new          out   16  signed   Q15 updated state for this neuron
//   x_new_valid    out   1            Pulse high when x_new is valid
//   done           out   1            Pulse high when computation complete
// =============================================================================

module compute_core #(
    parameter int DATA_W = 16,
    parameter int ACC_W  = 32
) (
    input  logic                       clk,
    input  logic                       rst,

    // Control
    input  logic                       start,
    input  logic [15:0]                N_minus_1,
    input  logic signed [DATA_W-1:0]   leak_rate,
    input  logic signed [ACC_W-1:0]    win_u,
    input  logic signed [DATA_W-1:0]   x_prev_self,

    // Streamed dot-product operands
    input  logic signed [DATA_W-1:0]   w_data,
    input  logic                       w_valid,
    input  logic signed [DATA_W-1:0]   x_data,
    input  logic                       x_valid,

    // Status / output
    output logic                       busy,
    output logic                       accepting_data,  // high in S_ACCUM
    output logic signed [DATA_W-1:0]   x_new,
    output logic                       x_new_valid,
    output logic                       done
);

    // -------------------------------------------------------------------------
    // FSM state encoding
    // -------------------------------------------------------------------------
    typedef enum logic [2:0] {
        S_IDLE  = 3'd0,
        S_LOAD  = 3'd1,
        S_ACCUM = 3'd2,
        S_ADDU  = 3'd3,
        S_NL    = 3'd4,
        S_DONE  = 3'd5
    } state_t;

    state_t state, next_state;

    // -------------------------------------------------------------------------
    // Registered control / data
    // -------------------------------------------------------------------------
    logic signed [DATA_W-1:0] leak_rate_reg;
    logic signed [ACC_W-1:0]  win_u_reg;
    logic signed [DATA_W-1:0] x_prev_self_reg;
    logic [15:0]              k_counter;
    logic [15:0]              N_minus_1_reg;

    // -------------------------------------------------------------------------
    // q15_mac instance
    // -------------------------------------------------------------------------
    logic                     mac_clr;
    logic                     mac_en;
    logic signed [ACC_W-1:0]  mac_acc;

    // En only when both operands valid AND we're in S_ACCUM
    assign mac_en  = (state == S_ACCUM) && w_valid && x_valid;
    // Clear pulse fires in S_LOAD to zero the accumulator
    assign mac_clr = (state == S_LOAD);

    q15_mac u_mac (
        .clk    (clk),
        .rst    (rst),
        .clr    (mac_clr),
        .en     (mac_en),
        .w      (w_data),
        .x      (x_data),
        .acc    (mac_acc)
    );

    // -------------------------------------------------------------------------
    // After dot product, add win_u to mac_acc.
    // We do this by writing the sum into a holding register in S_ADDU.
    // -------------------------------------------------------------------------
    logic signed [ACC_W-1:0]  pre_act;   // mac_acc + win_u

    always_ff @(posedge clk) begin
        if (rst)
            pre_act <= '0;
        else if (state == S_ADDU)
            pre_act <= mac_acc + win_u_reg;
    end

    // -------------------------------------------------------------------------
    // q15_tanh — combinational
    // -------------------------------------------------------------------------
    logic signed [DATA_W-1:0] tanh_out;

    q15_tanh u_tanh (
        .acc       (pre_act),
        .tanh_out  (tanh_out)
    );

    // -------------------------------------------------------------------------
    // q15_blend — combinational
    // -------------------------------------------------------------------------
    logic signed [DATA_W-1:0] blend_out;

    q15_blend u_blend (
        .x_prev     (x_prev_self_reg),
        .tanh_out   (tanh_out),
        .leak_rate  (leak_rate_reg),
        .x_new      (blend_out)
    );

    // -------------------------------------------------------------------------
    // Output register: capture blend_out in S_NL, present in S_DONE
    // -------------------------------------------------------------------------
    logic signed [DATA_W-1:0] x_new_reg;
    logic                     x_new_valid_reg;
    logic                     done_reg;

    always_ff @(posedge clk) begin
        if (rst) begin
            x_new_reg       <= '0;
            x_new_valid_reg <= 1'b0;
            done_reg        <= 1'b0;
        end else begin
            // Default: deassert valid/done; only pulse for 1 cycle
            x_new_valid_reg <= 1'b0;
            done_reg        <= 1'b0;

            if (state == S_NL) begin
                x_new_reg <= blend_out;
            end
            if (state == S_DONE) begin
                x_new_valid_reg <= 1'b1;
                done_reg        <= 1'b1;
            end
        end
    end

    assign x_new       = x_new_reg;
    assign x_new_valid = x_new_valid_reg;
    assign done        = done_reg;
    assign busy        = (state != S_IDLE) && (state != S_DONE);
    assign accepting_data = (state == S_ACCUM);

    // -------------------------------------------------------------------------
    // FSM — sequential state register
    // -------------------------------------------------------------------------
    always_ff @(posedge clk) begin
        if (rst)
            state <= S_IDLE;
        else
            state <= next_state;
    end

    // -------------------------------------------------------------------------
    // FSM — next-state logic
    // -------------------------------------------------------------------------
    always_comb begin
        next_state = state;
        unique case (state)
            S_IDLE: begin
                if (start)
                    next_state = S_LOAD;
            end
            S_LOAD: begin
                next_state = S_ACCUM;
            end
            S_ACCUM: begin
                // Stay in S_ACCUM until k_counter has been advanced past
                // N_minus_1_reg.  The counter increments only on valid
                // (w_valid && x_valid) cycles, so this naturally stalls
                // if the stream isn't ready.
                if (mac_en && (k_counter == N_minus_1_reg))
                    next_state = S_ADDU;
            end
            S_ADDU: begin
                next_state = S_NL;
            end
            S_NL: begin
                next_state = S_DONE;
            end
            S_DONE: begin
                next_state = S_IDLE;
            end
            default: next_state = S_IDLE;
        endcase
    end

    // -------------------------------------------------------------------------
    // Registered datapath captures
    // -------------------------------------------------------------------------
    always_ff @(posedge clk) begin
        if (rst) begin
            leak_rate_reg   <= '0;
            win_u_reg       <= '0;
            x_prev_self_reg <= '0;
            N_minus_1_reg   <= '0;
            k_counter       <= '0;
        end else begin
            unique case (state)
                S_IDLE: begin
                    if (start) begin
                        // Capture configuration when start pulses
                        leak_rate_reg   <= leak_rate;
                        win_u_reg       <= win_u;
                        x_prev_self_reg <= x_prev_self;
                        N_minus_1_reg   <= N_minus_1;
                        k_counter       <= '0;
                    end
                end
                S_ACCUM: begin
                    if (mac_en) begin
                        k_counter <= k_counter + 16'd1;
                    end
                end
                default: ;  // hold
            endcase
        end
    end

endmodule
