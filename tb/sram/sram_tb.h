#ifndef __SRAM_TB_H__
#define __SRAM_TB_H__

#include <systemc.h>
#include <iostream>
#include <vector>
#include <cstdlib>
#include "sram.h"

// Testbench parameters
#define SRAM_LATENCY  2
#define SRAM_WORDS    16
typedef sc_uint<8> sram_data_t;

struct WriteEntry {
    int          addr;
    sram_data_t  data;
};

SC_MODULE(SramTB) {

    sc_signal<sc_logic>    clk;
    sc_signal<sc_logic>    rst_ni;
    sc_signal<sc_logic>    req_i;
    sc_signal<sc_logic>    we_i;
    sc_signal<sc_lv<4>>    addr_i;   // clog2(16) = 4 bits
    sc_signal<sram_data_t> wdata_i;
    sc_signal<sram_data_t> rdata_o;

    Sram<SRAM_LATENCY, SRAM_WORDS, sram_data_t> *dut;

    // write sequence: (addr, data) pairs — edit freely
    const std::vector<WriteEntry> write_seq = {
        {  0, 0xAA },
        {  3, 0x11 },
        {  7, 0xBE },
        {  1, 0xFF },
        { 15, 0x42 },
        {  5, 0x99 },
        {  2, 0x7F },
    };

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

    // rst_ni active-low: hold low for 30 ns, then release
    void gen_reset() {
        rst_ni.write(SC_LOGIC_0);
        wait(30, SC_NS);
        rst_ni.write(SC_LOGIC_1);
    }

    // idle for N random clock cycles (0 = no wait)
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
        std::cout << "[TB] WRITE addr=0x" << std::hex << addr
                  << " data=0x" << (int)data << std::dec << "\n";
    }

    // returns the value on rdata_o after the correct number of latency cycles
    sram_data_t do_read(int addr) {
        addr_i.write(addr);
        we_i.write(SC_LOGIC_0);
        req_i.write(SC_LOGIC_1);
        wait(clk.posedge_event());
        req_i.write(SC_LOGIC_0);
        for (int i = 1; i < SRAM_LATENCY; i++)
            wait(clk.posedge_event());
        // one extra cycle: DUT has an additional wait() at the end of its eval loop
        wait(clk.posedge_event());
        return rdata_o.read();
    }

    void stimulus() {
        srand(42);  // fixed seed for reproducibility

        wait(rst_ni.posedge_event());
        wait(clk.posedge_event());

        // --- Write phase (with random idle gaps between writes) ---
        std::cout << "\n[TB] === Write phase ===\n";
        for (const auto& e : write_seq) {
            idle_random(4);
            do_write(e.addr, e.data);
        }

        // settle for a few cycles before reading
        for (int i = 0; i < 3; i++)
            wait(clk.posedge_event());

        // --- Read-back phase (verify all written values) ---
        std::cout << "\n[TB] === Read-back & verify phase ===\n";
        int pass = 0, fail = 0;
        for (const auto& e : write_seq) {
            sram_data_t got = do_read(e.addr);
            bool ok = (got == e.data);
            std::cout << "[TB] READ  addr=0x" << std::hex << e.addr
                      << "  expected=0x" << (int)e.data
                      << "  got=0x"      << (int)got << std::dec
                      << "  " << (ok ? "PASS" : "FAIL") << "\n";
            ok ? pass++ : fail++;
        }

        // --- Read unwritten addresses (expect 0 from reset) ---
        std::cout << "\n[TB] === Unwritten address check ===\n";
        // collect addresses NOT in write_seq
        bool written[SRAM_WORDS] = {};
        for (const auto& e : write_seq) written[e.addr] = true;
        for (int i = 0; i < SRAM_WORDS; i++) {
            if (written[i]) continue;
            sram_data_t got = do_read(i);
            bool ok = (got == sram_data_t(0));
            std::cout << "[TB] READ  addr=0x" << std::hex << i
                      << "  expected=0x00  got=0x" << (int)got << std::dec
                      << "  " << (ok ? "PASS" : "FAIL") << "\n";
            ok ? pass++ : fail++;
        }

        std::cout << "\n[TB] === Result: " << pass << " PASS, " << fail << " FAIL ===\n";
        sc_stop();
    }
};

#endif
