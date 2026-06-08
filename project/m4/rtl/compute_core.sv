//==========================================================================
// compute_core.sv — ESN state-update compute core for one neuron stream.
//
// Purpose:
//   Compute x_next[i] = leak_blend(x_prev[i], tanh(MAC(W_row_i, x_prev) + Win_term))
//   for one neuron i. The host streams weight rows + x vector + Win term
//   through AXI; this module fires the MAC array, tanh, and leak blend.
//
// For M2 verification: a small N (default 16) is used so the testbench
// can run one full neuron update in ~10 cycles. N is a parameter so the
// same RTL scales to N=1000 for M3/M4.
//
// FSM: IDLE -> MAC -> FLUSH -> ACTIVATE -> BLEND -> DONE -> IDLE
//
// Ports:
//   clk        : in   single-clock
//   rst_n      : in   active-low sync reset
//   start      : in   pulse to begin one neuron update
//   leak_a     : in   Q-format leak coefficient
//   x_prev_i   : in   prior state for neuron i
//   win_term_i : in   pre-computed Win @ [1,u] scalar for neuron i
//   w_row      : in   MAC_WIDTH lane bus, current chunk of W row
//   x_chunk    : in   MAC_WIDTH lane bus, current chunk of x_prev vector
//   chunk_valid: in   1 when w_row/x_chunk are valid this cycle
//   last_chunk : in   1 on the final chunk of the row
//   x_next_o   : out  computed next state for neuron i (DATA_W signed)
//   done       : out  1-cycle pulse when x_next_o is valid
//==========================================================================
`timescale 1ns/1ps
`default_nettype none
module compute_core #(
    parameter int DATA_W    = 16,
    parameter int MAC_WIDTH = 16,
    parameter int ACC_W     = 40,
    parameter int FRAC_W    = 15
) (
    input  wire                                 clk,
    input  wire                                 rst_n,
    input  wire                                 start,
    input  wire signed [DATA_W-1:0]             leak_a,
    input  wire signed [DATA_W-1:0]             x_prev_i,
    input  wire signed [ACC_W-1:0]              win_term_i,
    input  wire signed [MAC_WIDTH*DATA_W-1:0]   w_row,
    input  wire signed [MAC_WIDTH*DATA_W-1:0]   x_chunk,
    input  wire                                 chunk_valid,
    input  wire                                 last_chunk,
    output reg  signed [DATA_W-1:0]             x_next_o,
    output reg                                  done
);

    // (M4: no per-lane $dumpvars — 64 instances would each dump their full
    //  subtree. top.sv enumerates only the control signals the waveform needs.)

    // FSM
    typedef enum logic [2:0] {S_IDLE, S_MAC, S_FLUSH, S_ACTIVATE, S_BLEND, S_DONE} state_t;
    state_t state, next_state;
    reg last_chunk_q;
    reg [2:0] flush_cnt;
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            state <= S_IDLE;
            last_chunk_q <= 1'b0;
            flush_cnt <= 0;
        end else begin
            state <= next_state;
            if (chunk_valid && last_chunk) last_chunk_q <= 1'b1;
            else if (state == S_IDLE)      last_chunk_q <= 1'b0;
            if (state == S_FLUSH) flush_cnt <= flush_cnt + 1;
            else                  flush_cnt <= 0;
        end
    end
    always_comb begin
        next_state = state;
        case (state)
            S_IDLE:     if (start) next_state = S_MAC;
            S_MAC:      if (last_chunk_q) next_state = S_FLUSH;
            S_FLUSH:    if (flush_cnt == 3'd3) next_state = S_ACTIVATE; // drain MAC pipeline
            S_ACTIVATE: next_state = S_BLEND;
            S_BLEND:    next_state = S_DONE;
            S_DONE:     next_state = S_IDLE;
            default:    next_state = S_IDLE;
        endcase
    end

    // MAC array
    wire mac_en  = (state == S_MAC) || (state == S_FLUSH);
    wire mul_en  = (state == S_MAC) && chunk_valid;
    wire mac_clr = (state == S_IDLE) && start;
    wire signed [ACC_W-1:0] mac_sum;
    mac_array #(
        .DATA_W(DATA_W), .MAC_WIDTH(MAC_WIDTH), .ACC_W(ACC_W)
    ) u_mac (
        .clk(clk), .rst_n(rst_n),
        .en(mac_en), .mul_en(mul_en),
        .w_in(w_row), .x_in(x_chunk),
        .acc_clr(mac_clr), .sum_out(mac_sum)
    );

    // Pre-activation = MAC sum + Win term (latched at S_ACTIVATE entry)
    reg signed [ACC_W-1:0] pre_act;
    always_ff @(posedge clk) begin
        if (!rst_n)               pre_act <= '0;
        else if (state == S_FLUSH && flush_cnt == 3'd3) pre_act <= (mac_sum >>> FRAC_W) + win_term_i;
    end

    // tanh
    wire act_en = (state == S_ACTIVATE);
    wire signed [DATA_W-1:0] tanh_out;
    tanh_pwl #(
        .DATA_W(DATA_W), .ACC_W(ACC_W), .FRAC_W(FRAC_W)
    ) u_tanh (
        .clk(clk), .rst_n(rst_n),
        .en(act_en), .pre_in(pre_act), .act_out(tanh_out)
    );

    // leak blend
    wire blend_en = (state == S_BLEND);
    wire signed [DATA_W-1:0] blend_out;
    leak_blend #(.DATA_W(DATA_W)) u_blend (
        .clk(clk), .rst_n(rst_n),
        .en(blend_en),
        .a(leak_a),
        .x_prev(x_prev_i),
        .z(tanh_out),
        .x_next(blend_out)
    );

    // output capture
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            x_next_o <= '0;
            done     <= 1'b0;
        end else if (state == S_DONE) begin
            x_next_o <= blend_out;
            done     <= 1'b1;
        end else begin
            done <= 1'b0;
        end
    end
endmodule
`default_nettype wire
