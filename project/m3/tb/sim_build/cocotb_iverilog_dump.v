module cocotb_iverilog_dump();
initial begin
    $dumpfile("sim_build/top.fst");
    $dumpvars(0, top);
end
endmodule
