#include "inst_mem_tb.h"
#include <sstream>

#ifndef PROJECT_SOURCE_DIR
#define PROJECT_SOURCE_DIR "."
#endif

int sc_main(int argc, char* argv[]) {

    std::string json_path = (argc > 1)
        ? argv[1]
        : std::string(PROJECT_SOURCE_DIR) + "/given_tests/01/input.json";

    InstMemTB tb("tb");
    tb.json_path = json_path;   // stimulus thread calls loadFromJson after reset

    sc_trace_file *tf = sc_create_vcd_trace_file("inst_mem_tb");

    // ── Top-level control signals ─────────────────────────────────────────────
    sc_trace(tf, tb.clk,    "clk");
    sc_trace(tf, tb.rst_ni, "rst_ni");
    sc_trace(tf, tb.req_i,  "req_i");
    sc_trace(tf, tb.r_ack_o,"r_ack_o");
    sc_trace(tf, tb.pc,     "pc");

    // ── Output ports — each Instruction grouped as r_data_o_N.field ──────────
    for (int i = 0; i < TB_NUM_PORTS; i++)
        tb.port_tr[i].trace(tf, "r_data_o_" + std::to_string(i));

    // ── SRAM bank cells — grouped as bank_N.mem_MM.field ─────────────────────
    // Dot-separated prefix creates a hierarchy group in GTKWave's signal tree.
    for (int b = 0; b < TB_NUM_PORTS; b++) {
        for (int w = 0; w < TB_BANK_WORDS; w++) {
            // zero-pad word index so GTKWave sorts them numerically (mem_00, mem_01, ...)
            std::ostringstream name;
            name << "bank_" << b << ".mem_"
                 << std::setfill('0') << std::setw(2) << w;
            tb.bank_tr[b][w].trace(tf, name.str());
        }
    }

    sc_start(5000, SC_NS);

    sc_close_vcd_trace_file(tf);
    return 0;
}