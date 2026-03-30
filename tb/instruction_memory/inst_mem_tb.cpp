#include "inst_mem_tb.h"

// PROJECT_SOURCE_DIR is injected by CMake at compile time.
// Fallback lets the file compile outside CMake too.
#ifndef PROJECT_SOURCE_DIR
#define PROJECT_SOURCE_DIR "."
#endif

int sc_main(int argc, char* argv[]) {

    // JSON path: first CLI arg, or default to given_tests/01 inside project root
    std::string json_path = (argc > 1)
        ? argv[1]
        : std::string(PROJECT_SOURCE_DIR) + "/given_tests/01/input.json";

    InstMemTB tb("tb");

    sc_trace_file *tf = sc_create_vcd_trace_file("inst_mem_tb");
    sc_trace(tf, tb.clk,      "clk");
    sc_trace(tf, tb.rst,      "rst");
    sc_trace(tf, tb.r_req_i,  "r_req_i");
    sc_trace(tf, tb.r_addr_i, "r_addr_i");
    sc_trace(tf, tb.r_ack_i,  "r_ack_i");
    for (int i = 0; i < 4; i++)
        tb.tr[i].trace(tf, "r_data_o_" + std::to_string(i));

    tb.dut->loadFromJson(json_path);

    sc_start(500, SC_NS);

    sc_close_vcd_trace_file(tf);
    return 0;
}