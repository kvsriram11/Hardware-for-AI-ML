//==========================================================================
// top.sv — M4 K=64 parallel-lane ESN state-update accelerator.
//
// Architecture (the M4 improvement over M3's one-neuron-at-a-time design):
//   K = 64 physical compute lanes run in lockstep. Each lane is an M2
//   compute_core (a MAC_WIDTH=16-wide streaming MAC + tanh + leak blend).
//   A full N=1000 reservoir update is processed in BATCHES = ceil(N/K) = 16
//   batches: batch b updates neurons [b*K .. b*K+K-1] across the 64 lanes
//   simultaneously. The host issues ONE start per full update — there are no
//   per-neuron AXI handshakes (that is what recovers the >=10x speedup).
//
//   Per batch each lane streams NB = ceil(N/MAC_WIDTH) = 63 beats of its own
//   weight row against the SHARED, broadcast x[t-1] chunk vector, then drains
//   the MAC pipeline (compute_core FSM) and emits x_next for its neuron.
//
// Memories (lane-local weight SRAM + resident x): for simulation these are
// initialized via $readmemh under `ifdef __ICARUS__` (one-time preload, NOT
// part of the measured per-step latency, per the M4 brief). In a real flow
// the weight store is a compiled SRAM macro; only the compute fabric (the 64
// lanes) is standard-cell-synthesized — see synth/m4/synthesis_notes.md.
//
// Parameterized by DATA_W for the Q15 / INT8 / Q4 sweep. Single clock,
// active-low synchronous reset.
//==========================================================================
`timescale 1ns/1ps
`default_nettype none
module top #(
    parameter int DATA_W    = 16,
    parameter int MAC_WIDTH = 16,
    parameter int ACC_W     = 40,
    parameter int FRAC_W    = DATA_W - 1,
    parameter int K         = 64,    // parallel lanes
    parameter int N         = 1000   // reservoir size
) (
    input  wire                       clk,
    input  wire                       rst_n,
    input  wire                       start,        // one pulse per N-update
    input  wire signed [DATA_W-1:0]   leak_a,
    output reg                        busy,
    output reg                        done,
    output reg  [31:0]                cycles,       // measured COMPUTE latency
    // x_next readout (host reads on demand after done)
    input  wire [$clog2(N+1)-1:0]     rd_addr,
    output wire signed [DATA_W-1:0]   rd_data
);
    localparam int NB      = (N + MAC_WIDTH - 1) / MAC_WIDTH;  // beats/neuron = 63
    localparam int BATCHES = (N + K - 1) / K;                  // = 16
    localparam int NPAD    = K * BATCHES;                      // = 1024
    localparam int CW      = MAC_WIDTH * DATA_W;               // packed chunk width

    // ---- memories ----
    // lane weight rows: index = (lane*BATCHES + batch)*NB + chunk
    reg [CW-1:0]            w_mem    [0:K*BATCHES*NB-1];
    reg [CW-1:0]            x_chunk_mem [0:NB-1];     // broadcast x[t-1] chunks
    reg signed [DATA_W-1:0] x_scalar [0:NPAD-1];      // per-neuron x_prev[i]
    reg signed [ACC_W-1:0]  win_mem  [0:NPAD-1];      // per-neuron Win term
    reg signed [DATA_W-1:0] xnext_mem[0:NPAD-1];      // results

    assign rd_data = xnext_mem[rd_addr];

`ifdef __ICARUS__
    initial begin
        $readmemh("w_mem.hex",    w_mem);
        $readmemh("x_chunk.hex",  x_chunk_mem);
        $readmemh("x_scalar.hex", x_scalar);
        $readmemh("win.hex",      win_mem);
    end
`endif

    // ---- sequencer FSM ----
    typedef enum logic [2:0] {C_IDLE, C_START, C_STREAM, C_WAIT, C_DONE} cstate_t;
    cstate_t cstate;
    reg [$clog2(BATCHES)-1:0] batch_cnt;
    reg [$clog2(NB)-1:0]      chunk_cnt;

    wire lane_done;
    // Control outputs are COMBINATIONAL functions of the (registered) state +
    // chunk_cnt, so the broadcast chunk index, w_row/x_chunk reads, and
    // chunk_valid all reference the SAME chunk_cnt in the same cycle. Driving
    // them as registers would skew chunk_valid one cycle off chunk_cnt.
    wire cc_start = (cstate == C_START);
    wire cc_cv    = (cstate == C_STREAM);
    wire cc_last  = (cstate == C_STREAM) && (chunk_cnt == NB-1);
    // capture this batch's K results on the lane-done cycle (current batch_cnt)
    wire cap_now  = (cstate == C_WAIT) && lane_done;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            cstate <= C_IDLE; busy <= 1'b0; done <= 1'b0;
            batch_cnt <= '0; chunk_cnt <= '0; cycles <= 32'd0;
        end else begin
            if (busy) cycles <= cycles + 1'b1;
            case (cstate)
                C_IDLE: begin
                    done <= 1'b0;
                    if (start) begin
                        busy <= 1'b1; cycles <= 32'd0;
                        batch_cnt <= '0; cstate <= C_START;
                    end
                end
                C_START: begin            // one start pulse into all lanes
                    chunk_cnt <= '0;
                    cstate <= C_STREAM;
                end
                C_STREAM: begin           // stream NB beats of the broadcast x
                    if (chunk_cnt == NB-1) cstate <= C_WAIT;
                    else                   chunk_cnt <= chunk_cnt + 1'b1;
                end
                C_WAIT: begin             // drain MAC pipeline, await lane done
                    if (lane_done) begin
                        if (batch_cnt == BATCHES-1) begin
                            cstate <= C_DONE;
                        end else begin
                            batch_cnt <= batch_cnt + 1'b1;
                            cstate <= C_START;
                        end
                    end
                end
                C_DONE: begin
                    busy <= 1'b0; done <= 1'b1;
                    cstate <= C_IDLE;
                end
                default: cstate <= C_IDLE;
            endcase
        end
    end

    // ---- K parallel lanes ----
    wire signed [DATA_W-1:0] lane_xnext [0:K-1];
    wire                     lane_done_v [0:K-1];

    genvar L;
    generate
        for (L = 0; L < K; L = L + 1) begin : lanes
            wire [CW-1:0] w_row_l = w_mem[(L*BATCHES + batch_cnt)*NB + chunk_cnt];
            compute_core #(
                .DATA_W(DATA_W), .MAC_WIDTH(MAC_WIDTH),
                .ACC_W(ACC_W), .FRAC_W(FRAC_W)
            ) u_cc (
                .clk(clk), .rst_n(rst_n),
                .start(cc_start),
                .leak_a(leak_a),
                .x_prev_i(x_scalar[batch_cnt*K + L]),
                .win_term_i(win_mem[batch_cnt*K + L]),
                .w_row(w_row_l),
                .x_chunk(x_chunk_mem[chunk_cnt]),
                .chunk_valid(cc_cv),
                .last_chunk(cc_last),
                .x_next_o(lane_xnext[L]),
                .done(lane_done_v[L])
            );
            always_ff @(posedge clk)
                if (cap_now) xnext_mem[batch_cnt*K + L] <= lane_xnext[L];
        end
    endgenerate

    assign lane_done = lane_done_v[0];   // lanes are lockstep-identical

    // ---- debug mirrors for the annotated waveform (top-level, small VCD) ----
`ifdef __ICARUS__
    wire [2:0]              dbg_lane0_state = lanes[0].u_cc.state;
    wire signed [DATA_W-1:0] dbg_lane0_xnext = lane_xnext[0];
    initial begin
        $dumpfile("waves.vcd");
        // enumerate only the control signals (NOT the multi-MB memory arrays)
        $dumpvars(0, clk, rst_n, start, busy, done, cycles,
                     cstate, batch_cnt, chunk_cnt,
                     cc_start, cc_cv, cc_last,
                     dbg_lane0_state, dbg_lane0_xnext);
    end
`endif
endmodule
`default_nettype wire
