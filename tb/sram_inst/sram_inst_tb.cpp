#include "sram_inst_tb.h"

int sc_main(int argc, char* argv[]) {

    SramInstTB tb("tb");

    sc_trace_file *tf = sc_create_vcd_trace_file("sram_inst_tb");
    sc_trace(tf, tb.clk,    "clk");
    sc_trace(tf, tb.rst_ni, "rst_ni");
    sc_trace(tf, tb.req_i,  "req_i");
    sc_trace(tf, tb.we_i,   "we_i");
    sc_trace(tf, tb.addr_i, "addr_i");
    // Instruction fields traced via InstructionTracer (direct sc_trace on Instruction is a no-op stub)
    tb.wdata_tracer.trace(tf, "wdata");
    tb.rdata_tracer.trace(tf, "rdata");

    sc_start(5000, SC_NS);

    sc_close_vcd_trace_file(tf);
    return 0;
}