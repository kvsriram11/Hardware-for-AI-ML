//==========================================================================
// interface.sv — AXI4-Lite host wrapper for the M4 K=64 accelerator top.
//
// Provides the host control/status/readout path around top.sv. The M4 N=1000
// cosim drives `top` directly with a backdoor weight preload (the weight load
// is one-time and explicitly unmeasured per the M4 brief), so this wrapper is
// the integration artifact rather than the measured datapath; it mirrors the
// M2/M3-verified AXI4-Lite handshaking.
//
// Register map (AXI4-Lite, byte-addressed, 32-bit):
//   0x00 CTRL    [0]=start (one pulse per N-update)
//   0x04 STATUS  [0]=busy, [1]=done
//   0x08 LEAK_A  signed Q1.(DATA_W-1) leak coefficient
//   0x10 RDADDR  neuron index to read back
//   0x14 XNEXT   x_next[RDADDR] (read-only, sign-extended)
//==========================================================================
`timescale 1ns/1ps
`default_nettype none
module interface_axi #(
    parameter int DATA_W  = 16,
    parameter int N       = 1000,
    parameter int AXIL_AW = 8,
    parameter int AXIL_DW = 32
) (
    input  wire                   clk,
    input  wire                   rst_n,
    input  wire [AXIL_AW-1:0]     s_axil_awaddr,
    input  wire                   s_axil_awvalid,
    output reg                    s_axil_awready,
    input  wire [AXIL_DW-1:0]     s_axil_wdata,
    input  wire [AXIL_DW/8-1:0]   s_axil_wstrb,
    input  wire                   s_axil_wvalid,
    output reg                    s_axil_wready,
    output reg  [1:0]             s_axil_bresp,
    output reg                    s_axil_bvalid,
    input  wire                   s_axil_bready,
    input  wire [AXIL_AW-1:0]     s_axil_araddr,
    input  wire                   s_axil_arvalid,
    output reg                    s_axil_arready,
    output reg  [AXIL_DW-1:0]     s_axil_rdata,
    output reg  [1:0]             s_axil_rresp,
    output reg                    s_axil_rvalid,
    input  wire                   s_axil_rready
);
    reg  start_pulse;
    reg  signed [DATA_W-1:0] leak_a_q;
    reg  [$clog2(N+1)-1:0]   rd_addr_q;
    wire busy, done;
    wire signed [DATA_W-1:0] rd_data;

    top #(.DATA_W(DATA_W), .N(N)) u_top (
        .clk(clk), .rst_n(rst_n), .start(start_pulse), .leak_a(leak_a_q),
        .busy(busy), .done(done), .cycles(),
        .rd_addr(rd_addr_q), .rd_data(rd_data)
    );

    // ---- AXI4-Lite write ----
    typedef enum logic [1:0] {AW_IDLE, AW_DATA, AW_RESP} aw_t;
    aw_t aw_state; reg [AXIL_AW-1:0] aw_addr;
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            aw_state <= AW_IDLE; s_axil_awready <= 0; s_axil_wready <= 0;
            s_axil_bvalid <= 0; s_axil_bresp <= 0;
            leak_a_q <= 0; rd_addr_q <= 0; start_pulse <= 0;
        end else begin
            start_pulse <= 1'b0;
            case (aw_state)
                AW_IDLE: begin
                    s_axil_awready <= 1'b1;
                    if (s_axil_awvalid && s_axil_awready) begin
                        aw_addr <= s_axil_awaddr; s_axil_awready <= 0;
                        s_axil_wready <= 1'b1; aw_state <= AW_DATA;
                    end
                end
                AW_DATA: if (s_axil_wvalid && s_axil_wready) begin
                    case (aw_addr[7:0])
                        8'h00: if (s_axil_wdata[0]) start_pulse <= 1'b1;
                        8'h08: leak_a_q  <= s_axil_wdata[DATA_W-1:0];
                        8'h10: rd_addr_q <= s_axil_wdata[$clog2(N+1)-1:0];
                        default: ;
                    endcase
                    s_axil_wready <= 0; s_axil_bvalid <= 1'b1; s_axil_bresp <= 0;
                    aw_state <= AW_RESP;
                end
                AW_RESP: if (s_axil_bvalid && s_axil_bready) begin
                    s_axil_bvalid <= 0; aw_state <= AW_IDLE;
                end
                default: aw_state <= AW_IDLE;
            endcase
        end
    end

    // ---- AXI4-Lite read ----
    typedef enum logic [0:0] {AR_IDLE, AR_RESP} ar_t;
    ar_t ar_state;
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            ar_state <= AR_IDLE; s_axil_arready <= 0;
            s_axil_rvalid <= 0; s_axil_rresp <= 0; s_axil_rdata <= 0;
        end else case (ar_state)
            AR_IDLE: begin
                s_axil_arready <= 1'b1;
                if (s_axil_arvalid && s_axil_arready) begin
                    s_axil_arready <= 0; s_axil_rvalid <= 1'b1; s_axil_rresp <= 0;
                    case (s_axil_araddr[7:0])
                        8'h04: s_axil_rdata <= {30'd0, done, busy};
                        8'h14: s_axil_rdata <= {{(AXIL_DW-DATA_W){rd_data[DATA_W-1]}}, rd_data};
                        default: s_axil_rdata <= 32'hDEAD_BEEF;
                    endcase
                    ar_state <= AR_RESP;
                end
            end
            AR_RESP: if (s_axil_rvalid && s_axil_rready) begin
                s_axil_rvalid <= 0; ar_state <= AR_IDLE;
            end
        endcase
    end
endmodule
`default_nettype wire
