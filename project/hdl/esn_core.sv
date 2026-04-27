// esn_core.sv
// Echo State Network Reservoir State Update — Compute Core
// Project: Hardware Accelerator for ESN (ECE 510, Spring 2026)
// Author : Venkata Sriram Kamarajugadda
//
// Kernel (one neuron per cycle, pipelined):
//   x(t) = (1-a)*x(t-1) + a*tanh(W_res*x(t-1) + W_in*u(t))
//
// This top-level stub implements:
//   - Parameterized data width (default INT16 / Q15)
//   - Reservoir size parameter N
//   - AXI4-Stream slave for input u(t) and reservoir weights
//   - Synchronous active-high reset
//   - Reset-able state register for one neuron (x_reg)
//   - Placeholder pipeline stages: mac_out, tanh_out, blend_out
//
// Precision plan:
//   DATA_W=16  → INT16/Q15  (primary research variant, M2 target)
//   DATA_W=32  → FP32       (M2 functional baseline)
//   DATA_W=8   → INT8       (stretch goal)
//
// Interface: AXI4-Stream data path, AXI4-Lite control (wrappers in separate modules)
// For this stub the AXI wrappers are replaced by simple valid/ready handshake ports.

module esn_core #(
    parameter int DATA_W  = 16,   // bit-width per element (16=INT16/Q15, 8=INT8, 32=FP32 placeholder)
    parameter int ACC_W   = 32,   // accumulator width (always 32-bit to prevent overflow)
    parameter int N       = 1000  // reservoir size (neurons)
) (
    // Clock / reset
    input  logic                clk,
    input  logic                rst,          // synchronous, active-high

    // Scalar input projection result: Win * u(t), pre-computed by host (ACC_W-bit fixed-point)
    input  logic signed [ACC_W-1:0] win_u,   // W_in * u(t) for the current neuron
    input  logic                    win_u_valid,

    // Previous state x(t-1) fed back from SRAM (DATA_W-bit)
    input  logic signed [DATA_W-1:0] x_prev,

    // Recurrent weight w_ij from sparse W_res (DATA_W-bit)
    input  logic signed [DATA_W-1:0] w_res,
    input  logic                     w_valid, // w_res and x_prev are valid this cycle

    // Leak rate (Q15 fixed-point: 0x7FFF ≈ 1.0)
    input  logic [DATA_W-1:0]        leak_rate, // a in [0,1)

    // Output: updated state x(t) for current neuron (DATA_W-bit)
    output logic signed [DATA_W-1:0] x_new,
    output logic                     x_new_valid,

    // Debug / status
    output logic [31:0]              cycle_count
);

    // -------------------------------------------------------------------------
    // Stage 0 — MAC: accumulate W_res * x(t-1) over all non-zero entries,
    //           then add Win*u(t).  Stub: single-cycle accumulation register.
    // -------------------------------------------------------------------------
    logic signed [ACC_W-1:0] mac_accum;

    always_ff @(posedge clk) begin
        if (rst) begin
            mac_accum <= '0;
        end else if (w_valid) begin
            // Wres_ij * x_prev accumulated; sign-extend DATA_W product to ACC_W
            mac_accum <= mac_accum + ACC_W'(signed'(w_res) * signed'(x_prev));
        end else if (win_u_valid) begin
            // Final step: add Win*u(t) to finish pre-activation
            mac_accum <= mac_accum + win_u;
        end
    end

    // -------------------------------------------------------------------------
    // Stage 1 — Piecewise-linear tanh approximation (stub: pass-through clip)
    //           Full PWL implementation in esn_tanh.sv (separate module, M2)
    // -------------------------------------------------------------------------
    logic signed [DATA_W-1:0] tanh_out;
    logic                     tanh_valid;

    always_ff @(posedge clk) begin
        if (rst) begin
            tanh_out   <= '0;
            tanh_valid <= 1'b0;
        end else begin
            // Stub: saturate accumulator to DATA_W range as placeholder for tanh
            if (mac_accum > ACC_W'(signed'({1'b0, {(DATA_W-1){1'b1}}})))
                tanh_out <= {1'b0, {(DATA_W-1){1'b1}}};          // +max
            else if (mac_accum < ACC_W'(signed'({1'b1, {(DATA_W-1){1'b0}}})))
                tanh_out <= {1'b1, {(DATA_W-1){1'b0}}};          // -max
            else
                tanh_out <= mac_accum[DATA_W-1:0];
            tanh_valid <= win_u_valid;  // one cycle after win_u consumed
        end
    end

    // -------------------------------------------------------------------------
    // Stage 2 — Leak-rate blend: x_new = (1-a)*x_prev + a*tanh_out
    //           Q15 multiply: result = (leak * tanh + (0x7FFF - leak) * x_prev) >> 15
    //           Stub: full blend deferred to esn_blend.sv (M2)
    // -------------------------------------------------------------------------
    logic signed [DATA_W-1:0] x_reg;   // the reset-able state register

    always_ff @(posedge clk) begin
        if (rst) begin
            x_reg      <= '0;
            x_new_valid <= 1'b0;
        end else if (tanh_valid) begin
            // Stub blend: straight assignment (leak_rate mixing in M2 module)
            x_reg      <= tanh_out;
            x_new_valid <= 1'b1;
        end else begin
            x_new_valid <= 1'b0;
        end
    end

    assign x_new = x_reg;

    // -------------------------------------------------------------------------
    // Cycle counter (diagnostic)
    // -------------------------------------------------------------------------
    always_ff @(posedge clk) begin
        if (rst)
            cycle_count <= '0;
        else
            cycle_count <= cycle_count + 1;
    end

endmodule
