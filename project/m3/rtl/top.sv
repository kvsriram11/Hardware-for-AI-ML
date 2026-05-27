// =============================================================================
// top.sv
//
// M3 integrated top module for the ESN reservoir state-update accelerator.
//
// Project   : Hardware Accelerator for Reservoir State Update in ESNs
// Course    : ECE 510 — Hardware for AI/ML, Spring 2026, Portland State Univ.
// Author    : Venkata Sriram Kamarajugadda
// Milestone : M3
//
// -----------------------------------------------------------------------------
// PURPOSE
// -----------------------------------------------------------------------------
// This is the integrated top-level module the M3 grader scrapes for. It
// instantiates the M2 AXI interface wrapper (interface_axi), which in turn
// instantiates the M2 compute_core (the 5-state FSM driving q15_mac,
// q15_tanh, and q15_blend).
//
// There is NO glue logic between the interface and the compute core. The
// interface wrapper exposes only AXI ports to the outside world; all
// compute-core signals are private. This satisfies the M3 rule that the
// testbench must drive the design exclusively through the host-side
// interface and cannot touch compute-core ports directly.
//
// Module hierarchy:
//
//   top (this file)
//   └── interface_axi
//       └── compute_core
//           ├── q15_mac
//           ├── q15_tanh
//           └── q15_blend
//
// -----------------------------------------------------------------------------
// PARAMETERS
// -----------------------------------------------------------------------------
//   AXIL_ADDR_W : AXI4-Lite address width (default 8 → 256-byte reg space)
//   AXIL_DATA_W : AXI4-Lite data width    (default 32, byte-strobed)
//   AXIS_DATA_W : AXI4-Stream data width  (default 32 — packs {x[15:0], w[15:0]})
//
// -----------------------------------------------------------------------------
// PORT LIST  (all external host-visible signals — AXI only)
// -----------------------------------------------------------------------------
//   Name                    Dir  Width            Role
//   ----------------------- ---  ---------------  -----------------------------
//   clk                     in   1                System clock (single domain)
//   rst                     in   1                Synchronous active-high reset
//
//   AXI4-Lite slave (config + status register file):
//   s_axil_awaddr           in   AXIL_ADDR_W      Write-address payload
//   s_axil_awvalid          in   1                Write-address valid
//   s_axil_awready          out  1                Write-address ready (comb)
//   s_axil_wdata            in   AXIL_DATA_W      Write-data payload
//   s_axil_wstrb            in   AXIL_DATA_W/8    Write byte-enable strobes
//   s_axil_wvalid           in   1                Write-data valid
//   s_axil_wready           out  1                Write-data ready (comb)
//   s_axil_bresp            out  2                Write response (RESP_OKAY)
//   s_axil_bvalid           out  1                Write response valid (reg)
//   s_axil_bready           in   1                Write response ready
//   s_axil_araddr           in   AXIL_ADDR_W      Read-address payload
//   s_axil_arvalid          in   1                Read-address valid
//   s_axil_arready          out  1                Read-address ready (comb)
//   s_axil_rdata            out  AXIL_DATA_W      Read-data payload (reg)
//   s_axil_rresp            out  2                Read response (RESP_OKAY)
//   s_axil_rvalid           out  1                Read-data valid (reg)
//   s_axil_rready           in   1                Read-data ready
//
//   AXI4-Stream slave (operand stream — packed (w_k, x_prev_k) beats):
//   s_axis_tdata            in   AXIS_DATA_W      {x_prev[15:0], w[15:0]}
//   s_axis_tvalid           in   1                Beat valid
//   s_axis_tready           out  1                Beat ready (back-pressured by FSM)
//   s_axis_tlast            in   1                Ignored (length comes from N-1)
//
// -----------------------------------------------------------------------------
// GLUE LOGIC
// -----------------------------------------------------------------------------
// None. The interface wrapper and compute core share a single clock domain
// and a single synchronous active-high reset. The wrapper exposes only AXI
// ports; the compute core is fully encapsulated within the wrapper. No
// FIFOs, no clock-domain crossings, no width converters are required.
//
// -----------------------------------------------------------------------------
// SYNTHESIS NOTES
// -----------------------------------------------------------------------------
// This module is the OpenLane 2 synthesis target (DESIGN_NAME=top). All
// other RTL files in project/m2/rtl/ are pulled in via VERILOG_FILES in
// project/m3/synth/config.json. The PDK is sky130A.
// =============================================================================

`default_nettype none

module top #(
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
    input  logic                          s_axis_tlast
);

    // -------------------------------------------------------------------------
    // Sole instance: M2 AXI interface wrapper (instantiates compute_core inside)
    // -------------------------------------------------------------------------
    interface_axi #(
        .AXIL_ADDR_W (AXIL_ADDR_W),
        .AXIL_DATA_W (AXIL_DATA_W),
        .AXIS_DATA_W (AXIS_DATA_W)
    ) u_iface (
        .clk            (clk),
        .rst            (rst),

        .s_axil_awaddr  (s_axil_awaddr),
        .s_axil_awvalid (s_axil_awvalid),
        .s_axil_awready (s_axil_awready),

        .s_axil_wdata   (s_axil_wdata),
        .s_axil_wstrb   (s_axil_wstrb),
        .s_axil_wvalid  (s_axil_wvalid),
        .s_axil_wready  (s_axil_wready),

        .s_axil_bresp   (s_axil_bresp),
        .s_axil_bvalid  (s_axil_bvalid),
        .s_axil_bready  (s_axil_bready),

        .s_axil_araddr  (s_axil_araddr),
        .s_axil_arvalid (s_axil_arvalid),
        .s_axil_arready (s_axil_arready),

        .s_axil_rdata   (s_axil_rdata),
        .s_axil_rresp   (s_axil_rresp),
        .s_axil_rvalid  (s_axil_rvalid),
        .s_axil_rready  (s_axil_rready),

        .s_axis_tdata   (s_axis_tdata),
        .s_axis_tvalid  (s_axis_tvalid),
        .s_axis_tready  (s_axis_tready),
        .s_axis_tlast   (s_axis_tlast)
    );

    // -------------------------------------------------------------------------
    // SIMULATION-ONLY: VCD waveform dump.
    // The `COCOTB_SIM` macro is defined automatically by cocotb when running
    // a cocotb-driven simulation; synthesis tools (Yosys/OpenLane) never see
    // this block. Pattern taken from the official cocotb Icarus support docs.
    // -------------------------------------------------------------------------
    `ifdef COCOTB_SIM
        initial begin
            $dumpfile("dump.vcd");
            $dumpvars(0, top);
            #1;
        end
    `endif

endmodule

`default_nettype wire