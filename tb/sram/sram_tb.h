#ifndef __SRAM_TB_H__
#define __SRAM_TB_H__

#include <systemc.h>
#include <iostream>
#include <iomanip>
#include <vector>
#include <cstdlib>
#include "sram.h"

// Testbench parameters
#define SRAM_LATENCY  5
#define SRAM_WORDS    128
typedef sc_uint<8> sram_data_t;

enum class OpType { READ, WRITE };

struct Op {
    OpType      type;
    int         addr;
    sram_data_t data;   // only used for WRITE
};

// Generate a random mixed sequence of reads and writes.
// - write_ratio: probability [0.0, 1.0] that an op is a write
// - Addresses are random in [0, SRAM_WORDS-1]
static std::vector<Op> gen_mixed_seq(int size, float write_ratio = 0.5f) {
    std::vector<Op> seq(size);
    for (auto& op : seq) {
        op.type = ((rand() / (float)RAND_MAX) < write_ratio) ? OpType::WRITE : OpType::READ;
        op.addr = rand() % SRAM_WORDS;
        op.data = (sram_data_t)(rand() % 256);
    }
    return seq;
}

SC_MODULE(SramTB) {

    sc_signal<sc_logic>                     clk;
    sc_signal<sc_logic>                     rst_ni;
    sc_signal<sc_logic>                     req_i;
    sc_signal<sc_logic>                     we_i;
    sc_signal<sc_lv<clog2<SRAM_WORDS>()>>  addr_i;
    sc_signal<sram_data_t>                  wdata_i;
    sc_signal<sram_data_t>                  rdata_o;

    Sram<SRAM_LATENCY, SRAM_WORDS, sram_data_t> *dut;

    SC_CTOR(SramTB) {
        dut = new Sram<SRAM_LATENCY, SRAM_WORDS, sram_data_t>("sram_dut");
        dut->clk_i(clk);
        dut->rst_ni(rst_ni);
        dut->req_i(req_i);
        dut->we_i(we_i);
        dut->addr_i(addr_i);
        dut->wdata_i(wdata_i);
        dut->rdata_o(rdata_o);

        req_i.write(SC_LOGIC_0);
        we_i.write(SC_LOGIC_0);
        addr_i.write(0);
        wdata_i.write(0);

        SC_THREAD(gen_clock);
        SC_THREAD(gen_reset);
        SC_THREAD(stimulus);
    }

    void gen_clock() {
        clk.write(SC_LOGIC_0);
        while (true) {
            wait(5, SC_NS);
            clk.write(SC_LOGIC_1);
            wait(5, SC_NS);
            clk.write(SC_LOGIC_0);
        }
    }

    void gen_reset() {
        rst_ni.write(SC_LOGIC_0);
        wait(30, SC_NS);
        rst_ni.write(SC_LOGIC_1);
    }

    void idle_random(int max_gap = 4) {
        int n = rand() % (max_gap + 1);
        for (int i = 0; i < n; i++)
            wait(clk.posedge_event());
        if (n > 0)
            std::cout << "[TB]   (idle " << n << " cycle" << (n > 1 ? "s" : "") << ")\n";
    }

    void do_write(int addr, sram_data_t data) {
        addr_i.write(addr);
        wdata_i.write(data);
        we_i.write(SC_LOGIC_1);
        req_i.write(SC_LOGIC_1);
        wait(clk.posedge_event());
        req_i.write(SC_LOGIC_0);
        we_i.write(SC_LOGIC_0);
        for (int i = 1; i < SRAM_LATENCY; i++)
            wait(clk.posedge_event());
    }

    sram_data_t do_read(int addr) {
        addr_i.write(addr);
        we_i.write(SC_LOGIC_0);
        req_i.write(SC_LOGIC_1);
        wait(clk.posedge_event());
        req_i.write(SC_LOGIC_0);
        for (int i = 1; i < SRAM_LATENCY; i++)
            wait(clk.posedge_event());
        // one extra cycle: DUT has an additional wait() at end of its eval loop
        wait(clk.posedge_event());
        return rdata_o.read();
    }

    void stimulus() {
        srand(42);  // fixed seed — change to srand(time(0)) for a different run each time

        wait(rst_ni.posedge_event());
        wait(clk.posedge_event());

        // shadow memory: tracks the expected state of the SRAM
        sram_data_t shadow[SRAM_WORDS] = {};   // zero-initialized (matches reset)
        bool        ever_written[SRAM_WORDS] = {};

        const auto seq = gen_mixed_seq(40, 0.5f);

        int pass = 0, fail = 0;
        std::cout << "\n[TB] === Mixed read/write sequence ===\n";

        for (const auto& op : seq) {
            idle_random(3);

            if (op.type == OpType::WRITE) {
                do_write(op.addr, op.data);
                shadow[op.addr]       = op.data;
                ever_written[op.addr] = true;

                std::cout << "[TB] WRITE addr=0x" << std::hex << std::setw(2) << std::setfill('0') << op.addr
                          << "  data=0x" << std::setw(2) << std::setfill('0') << (int)op.data
                          << std::dec << "\n";

            } else {
                sram_data_t expected = shadow[op.addr];
                sram_data_t got      = do_read(op.addr);
                bool ok = (got == expected);

                std::cout << "[TB] READ  addr=0x" << std::hex << std::setw(2) << std::setfill('0') << op.addr
                          << "  expected=0x" << std::setw(2) << std::setfill('0') << (int)expected
                          << "  got=0x"      << std::setw(2) << std::setfill('0') << (int)got
                          << std::dec << "  " << (ok ? "PASS" : "FAIL");

                if (!ever_written[op.addr])
                    std::cout << " (uninitialized)";
                std::cout << "\n";

                ok ? pass++ : fail++;
            }
        }

        std::cout << "\n[TB] === Result: " << pass << " PASS, " << fail << " FAIL ===\n";
        sc_stop();
    }
};

#endif
