#ifndef __INST_MEM_TB__
#define __INST_MEM_TB__

#include <systemc.h>
#include <iostream>
#include "instruction_memory.h"

#define MEM_SIZE 256


SC_MODULE(InstMemTB) {

    sc_signal<sc_logic>     clk;
    sc_signal<sc_logic>     rst;
    sc_signal<sc_logic>     r_req_i;
    sc_signal<sc_uint<32>>  r_addr_i;
    sc_signal<sc_logic>     r_ack_i;
    sc_signal<Instruction>  r_data_o[4];

    InstructionTracer tr[4];  // VCD shadow tracers, one per r_data_o slot

    InstructionMemory<MEM_SIZE> *dut;

    SC_CTOR(InstMemTB) {
        dut = new InstructionMemory<MEM_SIZE>("inst_mem");
        dut->clk(clk);
        dut->rst(rst);
        dut->r_req_i(r_req_i);
        dut->r_addr_i(r_addr_i);
        dut->r_ack_o(r_ack_i);
        for (int i = 0; i < 4; i++)
            dut->r_data_o[i](r_data_o[i]);

        r_req_i.write(SC_LOGIC_0);
        r_addr_i.write(0);

        SC_THREAD(gen_clock);
        SC_THREAD(gen_reset);
        SC_THREAD(stimulus);

        SC_METHOD(update_shadow);
        for (int i = 0; i < 4; i++)
            sensitive << r_data_o[i];
    }

    void update_shadow() {
        for (int i = 0; i < 4; i++)
            tr[i].update(r_data_o[i].read());
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

    // reset high for first 30 ns, then deassert
    void gen_reset() {
        rst.write(SC_LOGIC_1);
        wait(30, SC_NS);
        rst.write(SC_LOGIC_0);
    }

    // read all loaded instructions 4 at a time using req/ack handshake
    void stimulus() {
        wait(rst.negedge_event());
        wait(clk.posedge_event());

        int total = dut->loadedCount;
        int groups = (total + 3) / 4;

        for (int g = 0; g < groups; g++) {
            int base_addr = g * 4;

            r_addr_i.write(base_addr);
            r_req_i.write(SC_LOGIC_1);

            wait(r_ack_i.posedge_event());

            std::cout << "[TB] Read group " << g
                      << " (addr " << base_addr << "-" << base_addr + 3 << "):\n";
            for (int i = 0; i < 4; i++) {
                int pc = base_addr + i;
                if (pc < total)
                    std::cout << "  PC=" << pc << "  " << r_data_o[i].read() << "\n";
            }

            r_req_i.write(SC_LOGIC_0);
            wait(clk.posedge_event());
        }

        std::cout << "[TB] Done reading " << total << " instructions.\n";
        sc_stop();
    }
};

#endif