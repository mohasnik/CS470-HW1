#include "counter_tb.h"

int sc_main(int argc, char* argv[]) {

    CounterTB tb("tb");

    sc_trace_file *tf = sc_create_vcd_trace_file("counter_tb");

    sc_trace(tf, tb.clk,     "clk");
    sc_trace(tf, tb.rst_ni,  "rst_ni");
    sc_trace(tf, tb.cen_ni,  "cen_ni");
    sc_trace(tf, tb.count_o,       "count_o");
    sc_trace(tf, tb.cout_o,        "cout_o");
    sc_trace(tf, tb.dut->count_r,  "count_r");

    sc_start(5000, SC_NS);

    sc_close_vcd_trace_file(tf);
    return 0;
}
