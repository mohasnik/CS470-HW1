#ifndef __SRAM_TB_H__
#define __SRAM_TB_H__

#include <systemc.h>
#include <iostream>
#include "sram.h"

// Testbench parameters
#define SRAM_LATENCY  2
#define SRAM_WORDS    16
typedef sc_uint<8> sram_data_t;

SC_MODULE(SramTB) {

    sc_signal<sc_logic> clk;
    sc_signal<sc_logic> rst_ni;
    sc_signal<sc_logic> req_i;
    sc_signal<sc_logic> we_i;
    sc_signal<sc_lv<4>> addr_i;   // clog2(16) = 4 bits
    sc_signal<sram_data_t> wdata_i;
    sc_signal<sram_data_t> rdata_o;

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

        // default signal values
        req_i.write(SC_LOGIC_0);
        we_i.write(SC_LOGIC_0);
        addr_i.write(0);
        wdata_i.write(0);

        SC_THREAD(gen_clock);
        SC_THREAD(gen_reset);
        SC_THREAD(stimulus);
    }

    // 10 ns period clock
    void gen_clock() {
        clk.write(SC_LOGIC_0);
        while (true) {
            wait(5, SC_NS);
            clk.write(SC_LOGIC_1);
            wait(5, SC_NS);
            clk.write(SC_LOGIC_0);
        }
    }

    // rst_ni active-low: hold low (reset) for first 30 ns, then deassert high
    void gen_reset() {
        rst_ni.write(SC_LOGIC_0);
        wait(30, SC_NS);
        rst_ni.write(SC_LOGIC_1);
    }

    void do_write(int addr, sram_data_t data) {
        addr_i.write(addr);
        wdata_i.write(data);
        we_i.write(SC_LOGIC_1);
        req_i.write(SC_LOGIC_1);
        wait(clk.posedge_event());   // one cycle to latch the request
        req_i.write(SC_LOGIC_0);
        we_i.write(SC_LOGIC_0);
        // wait for latency cycles to pass so the write completes in DUT
        for (int i = 1; i < SRAM_LATENCY; i++)
            wait(clk.posedge_event());
        std::cout << "[TB] WRITE addr=" << addr << " data=" << (int)data << "\n";
    }

    void do_read(int addr) {
        addr_i.write(addr);
        we_i.write(SC_LOGIC_0);
        req_i.write(SC_LOGIC_1);
        wait(clk.posedge_event());   // one cycle to latch the request
        req_i.write(SC_LOGIC_0);
        // wait for remaining latency cycles
        for (int i = 1; i < SRAM_LATENCY; i++)
            wait(clk.posedge_event());
        // one extra cycle: DUT has the extra wait() at end of its loop
        wait(clk.posedge_event());
        std::cout << "[TB] READ  addr=" << addr << " data=" << rdata_o.read() << "\n";
    }

    void stimulus() {
        // wait until reset is released
        wait(rst_ni.posedge_event());
        wait(clk.posedge_event());

        std::cout << "[TB] --- Write phase ---\n";
        do_write(0,  0xAA);
        do_write(1,  0xBB);
        do_write(2,  0xCC);
        do_write(5,  0x55);
        do_write(15, 0xFF);

        std::cout << "[TB] --- Read phase ---\n";
        do_read(0);
        do_read(1);
        do_read(2);
        do_read(5);
        do_read(15);

        // read an address that was never written — expect default (0)
        std::cout << "[TB] --- Read uninitialized address ---\n";
        do_read(7);

        std::cout << "[TB] Done.\n";
        sc_stop();
    }
};

#endif
