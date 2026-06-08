//==========================================================================
// top.sv — M3 integrated top for the ESN state-update accelerator.
//
// Integration level:
//   This is the synthesizable chip-top. It wraps the M2 verification IP:
//
//       top  ->  interface_axi  ->  compute_core  ->  {mac_array, tanh_pwl,
//                                                       leak_blend}
//
//   The host drives EVERYTHING through two AXI interfaces — there are no
//   back-door control pins. AXI4-Lite carries the per-neuron scalars
//   (LEAK_A, WIN_T, XPREV) plus CTRL.start and STATUS polling; AXI4-Stream
//   carries the streamed (w_row, x_chunk) beats. One full N-neuron reservoir
//   state-update is N sequential single-neuron updates issued by the host.
//
// N is NOT a hardware parameter. compute_core is a fixed MAC_WIDTH-lane
// streaming MAC: an N-element row is delivered as ceil(N/MAC_WIDTH) AXIS
// beats and accumulated in the ACC_W accumulator. Gate area is therefore
// independent of reservoir size N — the same silicon runs N=64 (cosim) and
// N=1000 (production). See synth/synthesis_notes.md.
//
// Single clock (clk), active-low synchronous reset (rst_n).
//
// Register map (AXI4-Lite, byte-addressed, 32-bit data) — inherited from
// interface.sv:
//   0x00 CTRL   [0]=start
//   0x04 STATUS [0]=busy, [1]=done
//   0x08 LEAK_A signed Q1.(DATA_W-1) leak coefficient
//   0x0C WIN_T  signed ACC_W Win term (low 32 bits)
//   0x10 XPREV  signed DATA_W x_prev[i]
//   0x14 XNEXT  signed DATA_W x_next[i] (read-only)
//==========================================================================
`timescale 1ns/1ps
`default_nettype none
module top #(
    parameter int DATA_W    = 16,
    parameter int MAC_WIDTH = 16,
    parameter int ACC_W     = 40,
    parameter int FRAC_W    = 15,
    parameter int AXIL_AW   = 8,
    parameter int AXIL_DW   = 32,
    parameter int AXIS_DW   = 2*MAC_WIDTH*DATA_W
) (
    input  wire                       clk,
    input  wire                       rst_n,

    // ---- AXI4-Lite slave (control / status / scalars) ----
    input  wire [AXIL_AW-1:0]         s_axil_awaddr,
    input  wire                       s_axil_awvalid,
    output wire                       s_axil_awready,
    input  wire [AXIL_DW-1:0]         s_axil_wdata,
    input  wire [AXIL_DW/8-1:0]       s_axil_wstrb,
    input  wire                       s_axil_wvalid,
    output wire                       s_axil_wready,
    output wire [1:0]                 s_axil_bresp,
    output wire                       s_axil_bvalid,
    input  wire                       s_axil_bready,
    input  wire [AXIL_AW-1:0]         s_axil_araddr,
    input  wire                       s_axil_arvalid,
    output wire                       s_axil_arready,
    output wire [AXIL_DW-1:0]         s_axil_rdata,
    output wire [1:0]                 s_axil_rresp,
    output wire                       s_axil_rvalid,
    input  wire                       s_axil_rready,

    // ---- AXI4-Stream sink (W rows + x chunks) ----
    input  wire [AXIS_DW-1:0]         s_axis_tdata,
    input  wire                       s_axis_tvalid,
    output wire                       s_axis_tready,
    input  wire                       s_axis_tlast
);

    // The integration is a single instance — interface_axi already contains
    // the compute_core datapath. top exists as the named synthesis target and
    // the stable chip-boundary pinout for M3/M4.
    interface_axi #(
        .DATA_W   (DATA_W),
        .MAC_WIDTH(MAC_WIDTH),
        .ACC_W    (ACC_W),
        .FRAC_W   (FRAC_W),
        .AXIL_AW  (AXIL_AW),
        .AXIL_DW  (AXIL_DW),
        .AXIS_DW  (AXIS_DW)
    ) u_if (
        .clk           (clk),
        .rst_n         (rst_n),
        .s_axil_awaddr (s_axil_awaddr),
        .s_axil_awvalid(s_axil_awvalid),
        .s_axil_awready(s_axil_awready),
        .s_axil_wdata  (s_axil_wdata),
        .s_axil_wstrb  (s_axil_wstrb),
        .s_axil_wvalid (s_axil_wvalid),
        .s_axil_wready (s_axil_wready),
        .s_axil_bresp  (s_axil_bresp),
        .s_axil_bvalid (s_axil_bvalid),
        .s_axil_bready (s_axil_bready),
        .s_axil_araddr (s_axil_araddr),
        .s_axil_arvalid(s_axil_arvalid),
        .s_axil_arready(s_axil_arready),
        .s_axil_rdata  (s_axil_rdata),
        .s_axil_rresp  (s_axil_rresp),
        .s_axil_rvalid (s_axil_rvalid),
        .s_axil_rready (s_axil_rready),
        .s_axis_tdata  (s_axis_tdata),
        .s_axis_tvalid (s_axis_tvalid),
        .s_axis_tready (s_axis_tready),
        .s_axis_tlast  (s_axis_tlast)
    );

endmodule
`default_nettype wire
