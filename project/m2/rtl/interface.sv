//==========================================================================
// interface.sv — AXI4-Lite slave for control/status + AXI4-Stream sink/source
//
// Register map (AXI4-Lite, byte-addressed, 32-bit data):
//   0x00 CTRL   [0]=start, [1]=soft_rst, [2]=mode_run
//   0x04 STATUS [0]=busy, [1]=done, [2]=err
//   0x08 LEAK_A signed Q1.(DATA_W-1) leak coefficient
//   0x0C WIN_T  signed ACC_W-truncated Win term (low 32 bits)
//   0x10 XPREV  signed DATA_W x_prev[i] (sign-extended to 32)
//   0x14 XNEXT  signed DATA_W x_next captured from compute_core (read-only)
//
// AXI4-Stream:
//   s_axis (W_ROW || X_CHUNK packed) carries one chunk per beat:
//     tdata[MAC_WIDTH*DATA_W-1            : 0]                = x_chunk
//     tdata[2*MAC_WIDTH*DATA_W-1 : MAC_WIDTH*DATA_W]          = w_row chunk
//     tlast = 1 on the final chunk of the row.
//
// Single clock, active-low sync reset. AXI handshakes: TVALID/TREADY,
// AW/W/B/AR/R per AXI4-Lite spec section A2.
//==========================================================================
`timescale 1ns/1ps
`default_nettype none
module interface_axi #(
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

    // AXI4-Lite slave
    input  wire [AXIL_AW-1:0]         s_axil_awaddr,
    input  wire                       s_axil_awvalid,
    output reg                        s_axil_awready,
    input  wire [AXIL_DW-1:0]         s_axil_wdata,
    input  wire [AXIL_DW/8-1:0]       s_axil_wstrb,
    input  wire                       s_axil_wvalid,
    output reg                        s_axil_wready,
    output reg  [1:0]                 s_axil_bresp,
    output reg                        s_axil_bvalid,
    input  wire                       s_axil_bready,
    input  wire [AXIL_AW-1:0]         s_axil_araddr,
    input  wire                       s_axil_arvalid,
    output reg                        s_axil_arready,
    output reg  [AXIL_DW-1:0]         s_axil_rdata,
    output reg  [1:0]                 s_axil_rresp,
    output reg                        s_axil_rvalid,
    input  wire                       s_axil_rready,

    // AXI4-Stream sink (W rows + x chunks)
    input  wire [AXIS_DW-1:0]         s_axis_tdata,
    input  wire                       s_axis_tvalid,
    output wire                       s_axis_tready,
    input  wire                       s_axis_tlast
);

`ifdef __ICARUS__
    initial begin
        $dumpfile("waves.vcd");
        $dumpvars(0, interface_axi);
    end
`endif

    // ---- Control/status registers ----
    reg start_pulse, busy_q, done_q;
    reg signed [DATA_W-1:0] leak_a_q;
    reg signed [ACC_W-1:0]  win_term_q;
    reg signed [DATA_W-1:0] x_prev_q;
    reg signed [DATA_W-1:0] x_next_q;

    // ---- AXI4-Lite write FSM ----
    typedef enum logic [1:0] {AW_IDLE, AW_DATA, AW_RESP} aw_state_t;
    aw_state_t aw_state;
    reg [AXIL_AW-1:0] aw_addr;
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            aw_state <= AW_IDLE; s_axil_awready <= 1'b0; s_axil_wready <= 1'b0;
            s_axil_bvalid <= 1'b0; s_axil_bresp <= 2'b00;
            leak_a_q <= '0; win_term_q <= '0; x_prev_q <= '0;
            start_pulse <= 1'b0;
        end else begin
            start_pulse <= 1'b0;
            case (aw_state)
                AW_IDLE: begin
                    s_axil_awready <= 1'b1;
                    if (s_axil_awvalid && s_axil_awready) begin
                        aw_addr <= s_axil_awaddr;
                        s_axil_awready <= 1'b0;
                        s_axil_wready <= 1'b1;
                        aw_state <= AW_DATA;
                    end
                end
                AW_DATA: if (s_axil_wvalid && s_axil_wready) begin
                    case (aw_addr[7:0])
                        8'h00: if (s_axil_wdata[0]) start_pulse <= 1'b1;
                        8'h08: leak_a_q   <= s_axil_wdata[DATA_W-1:0];
                        8'h0C: win_term_q <= {{(ACC_W-AXIL_DW){s_axil_wdata[AXIL_DW-1]}}, s_axil_wdata};
                        8'h10: x_prev_q   <= s_axil_wdata[DATA_W-1:0];
                        default: ;
                    endcase
                    s_axil_wready <= 1'b0;
                    s_axil_bvalid <= 1'b1;
                    s_axil_bresp  <= 2'b00;
                    aw_state <= AW_RESP;
                end
                AW_RESP: if (s_axil_bvalid && s_axil_bready) begin
                    s_axil_bvalid <= 1'b0;
                    aw_state <= AW_IDLE;
                end
                default: aw_state <= AW_IDLE;
            endcase
        end
    end

    // ---- AXI4-Lite read FSM ----
    typedef enum logic [0:0] {AR_IDLE, AR_RESP} ar_state_t;
    ar_state_t ar_state;
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            ar_state <= AR_IDLE; s_axil_arready <= 1'b0;
            s_axil_rvalid <= 1'b0; s_axil_rresp <= 2'b00; s_axil_rdata <= '0;
        end else case (ar_state)
            AR_IDLE: begin
                s_axil_arready <= 1'b1;
                if (s_axil_arvalid && s_axil_arready) begin
                    s_axil_arready <= 1'b0;
                    s_axil_rvalid  <= 1'b1;
                    s_axil_rresp   <= 2'b00;
                    case (s_axil_araddr[7:0])
                        8'h04: s_axil_rdata <= {29'd0, 1'b0, done_q, busy_q};
                        8'h08: s_axil_rdata <= {{(AXIL_DW-DATA_W){leak_a_q[DATA_W-1]}}, leak_a_q};
                        8'h10: s_axil_rdata <= {{(AXIL_DW-DATA_W){x_prev_q[DATA_W-1]}}, x_prev_q};
                        8'h14: s_axil_rdata <= {{(AXIL_DW-DATA_W){x_next_q[DATA_W-1]}}, x_next_q};
                        default: s_axil_rdata <= 32'hDEAD_BEEF;
                    endcase
                    ar_state <= AR_RESP;
                end
            end
            AR_RESP: if (s_axil_rvalid && s_axil_rready) begin
                s_axil_rvalid <= 1'b0;
                ar_state <= AR_IDLE;
            end
        endcase
    end

    // ---- compute_core integration ----
    wire cc_done;
    wire signed [DATA_W-1:0] cc_xnext;
    assign s_axis_tready = (busy_q);
    wire signed [MAC_WIDTH*DATA_W-1:0] w_chunk = s_axis_tdata[2*MAC_WIDTH*DATA_W-1 -: MAC_WIDTH*DATA_W];
    wire signed [MAC_WIDTH*DATA_W-1:0] x_chunk = s_axis_tdata[MAC_WIDTH*DATA_W-1 : 0];
    wire chunk_v = s_axis_tvalid && s_axis_tready;

    compute_core #(
        .DATA_W(DATA_W), .MAC_WIDTH(MAC_WIDTH), .ACC_W(ACC_W), .FRAC_W(FRAC_W)
    ) u_cc (
        .clk(clk), .rst_n(rst_n),
        .start(start_pulse),
        .leak_a(leak_a_q),
        .x_prev_i(x_prev_q),
        .win_term_i(win_term_q),
        .w_row(w_chunk),
        .x_chunk(x_chunk),
        .chunk_valid(chunk_v),
        .last_chunk(s_axis_tlast),
        .x_next_o(cc_xnext),
        .done(cc_done)
    );
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            busy_q <= 1'b0; done_q <= 1'b0; x_next_q <= '0;
        end else begin
            if (start_pulse) begin busy_q <= 1'b1; done_q <= 1'b0; end
            if (cc_done)     begin busy_q <= 1'b0; done_q <= 1'b1; x_next_q <= cc_xnext; end
        end
    end
endmodule
`default_nettype wire
