#include "sram_tb.h"

int sc_main(int argc, char* argv[]) {

    SramTB tb("tb");

    sc_trace_file *tf = sc_create_vcd_trace_file("sram_tb");
    sc_trace(tf, tb.clk,     "clk");
    sc_trace(tf, tb.rst_ni,  "rst_ni");
    sc_trace(tf, tb.req_i,   "req_i");
    sc_trace(tf, tb.we_i,    "we_i");
    sc_trace(tf, tb.addr_i,  "addr_i");
    sc_trace(tf, tb.wdata_i, "wdata_i");
    sc_trace(tf, tb.rdata_o, "rdata_o");
    for (int i = 0; i < SRAM_WORDS; i++)
        sc_trace(tf, tb.dut->mem[i], "mem_" + std::to_string(i));

    sc_start(1000, SC_NS);

    sc_close_vcd_trace_file(tf);
    return 0;
}
