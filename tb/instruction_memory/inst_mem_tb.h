#ifndef __INST_MEM_TB__
#define __INST_MEM_TB__

#include <systemc.h>
#include <iostream>
#include <iomanip>
#include <sstream>
#include <string>
#include "instruction_memory.h"

#define TB_MEM_SIZE  256
#define TB_NUM_PORTS 4
#define TB_BANK_WORDS (TB_MEM_SIZE / TB_NUM_PORTS)   // = 64

using DUT = InstructionMemory<TB_MEM_SIZE, TB_NUM_PORTS>;

SC_MODULE(InstMemTB) {

    // ── DUT-facing signals ────────────────────────────────────────────────────
    sc_signal<sc_logic>    clk;
    sc_signal<sc_logic>    rst_ni;
    sc_signal<sc_logic>    req_i;
    sc_signal<DUT::addr_t> addr_i;
    sc_signal<sc_logic>    r_ack_o;
    sc_signal<Instruction> r_data_o[TB_NUM_PORTS];

    // ── TB observation signals ────────────────────────────────────────────────
    sc_signal<int>  pc;           // base address currently being requested (1 cycle ahead)
    sc_signal<int>  output_pc;    // base address whose data is currently on r_data_o (VCD-aligned)

    // ── VCD tracers ───────────────────────────────────────────────────────────
    InstructionTracer port_tr[TB_NUM_PORTS];
    InstructionTracer bank_tr[TB_NUM_PORTS][TB_BANK_WORDS];

    // ── Golden reference (PC-indexed, independent of bank layout) ────────────
    // reference[i] = instruction at PC i, loaded directly from bank memory
    // in round-robin order after loadFromJson().
    // Comparing r_data_o[p] against reference[base+p] catches bugs in
    // both SRAM reads AND the round-robin distribution itself.
    Instruction reference[TB_MEM_SIZE];

    DUT         *dut;
    std::string  json_path;

    SC_CTOR(InstMemTB) {
        dut = new DUT("inst_mem");
        dut->clk    (clk);
        dut->rst_ni (rst_ni);
        dut->req_i  (req_i);
        dut->addr_i (addr_i);
        dut->r_ack_o(r_ack_o);
        for (int i = 0; i < TB_NUM_PORTS; i++)
            dut->r_data_o[i](r_data_o[i]);

        req_i.write(SC_LOGIC_0);
        addr_i.write(DUT::addr_t(0));
        pc.write(-1);
        output_pc.write(-1);

        SC_THREAD(gen_clock);
        SC_THREAD(gen_reset);
        SC_THREAD(stimulus);

        SC_METHOD(update_port_tracers);
        for (int i = 0; i < TB_NUM_PORTS; i++)
            sensitive << r_data_o[i];

        // poll bank cells every posedge (mem[] is a plain array, not sc_signal)
        SC_METHOD(update_bank_tracers);
        sensitive << clk.posedge_event();
    }

    // ── Clock: 10 ns period ───────────────────────────────────────────────────
    void gen_clock() {
        clk.write(SC_LOGIC_0);
        while (true) {
            wait(5, SC_NS);
            clk.write(SC_LOGIC_1);
            wait(5, SC_NS);
            clk.write(SC_LOGIC_0);
        }
    }

    // ── Reset: active-low, hold 3 cycles ─────────────────────────────────────
    void gen_reset() {
        rst_ni.write(SC_LOGIC_0);
        for (int i = 0; i < 3; i++)
            wait(clk.posedge_event());
        rst_ni.write(SC_LOGIC_1);
    }

    // ── Reference loader ──────────────────────────────────────────────────────
    // Reconstructs a flat PC-ordered array from the bank memory.
    // Instruction i was written to banks[i % NUM_PORTS]->mem[i / NUM_PORTS],
    // so we reverse that mapping here.
    void loadReference() {
        for (int i = 0; i < dut->loadedCount; i++)
            reference[i] = dut->banks[i % TB_NUM_PORTS]->mem[i / TB_NUM_PORTS];
    }

    void update_port_tracers() {
        for (int i = 0; i < TB_NUM_PORTS; i++)
            port_tr[i].update(r_data_o[i].read());
    }

    void update_bank_tracers() {
        for (int b = 0; b < TB_NUM_PORTS; b++)
            for (int w = 0; w < TB_BANK_WORDS; w++)
                bank_tr[b][w].update(dut->banks[b]->mem[w]);
    }

    // ── Stimulus ──────────────────────────────────────────────────────────────
    // Pipelined timing (BANK_LATENCY=1):
    //   posedge N    : issue req for group 0 (delta)
    //   posedge N+1  : SRAM latches group 0 → issue req for group 1 (delta)
    //   posedge N+2  : SRAM latches group 1 → issue req for group 2 (delta)
    //                  read group 0 data (bank_rdata from delta N+1)
    //   posedge N+3  : read group 1 data, issue group 3 ...
    // req_i stays high continuously — no idle cycle between groups.
    void stimulus() {
        wait(rst_ni.posedge_event());

        // load instructions AFTER reset so resetValues() in SRAM doesn't wipe them
        dut->loadFromJson(json_path);
        loadReference();   // build flat PC-indexed reference from banks

        // one idle cycle to let everything settle
        wait(clk.posedge_event());

        int total  = dut->loadedCount;
        int groups = (total + TB_NUM_PORTS - 1) / TB_NUM_PORTS;
        int pass   = 0, fail = 0;

        std::cout << "\n[TB] Starting reads — " << total
                  << " instructions in " << groups << " groups\n";

        // Issue first request
        pc.write(0);
        addr_i.write(DUT::addr_t(0));
        req_i.write(SC_LOGIC_1);
        wait(clk.posedge_event());   // posedge N+1: SRAM latches group 0

        for (int g = 0; g < groups; g++) {
            int base = g * TB_NUM_PORTS;

            // Pipeline: immediately update addr for next group (req stays high)
            // or deassert if this is the last group.
            if (g + 1 < groups) {
                int next_base = (g + 1) * TB_NUM_PORTS;
                pc.write(next_base);
                addr_i.write(DUT::addr_t(next_base));
                // req_i stays SC_LOGIC_1
            } else {
                req_i.write(SC_LOGIC_0);
                pc.write(-1);
            }

            // posedge N+2+g: bank_rdata for group g valid (written in delta N+1+g)
            wait(clk.posedge_event());
            output_pc.write(base);  // aligns with r_data_o in VCD (both settle in this delta)

            // check all 4 parallel outputs against the PC-indexed reference
            for (int p = 0; p < TB_NUM_PORTS; p++) {
                int pc_val = base + p;
                if (pc_val >= total) break;

                Instruction got      = r_data_o[p].read();
                Instruction expected = reference[pc_val];   // independent of bank layout

                if (got == expected) {
                    std::cout << "  [PASS] PC=" << pc_val << "  " << got << "\n";
                    pass++;
                } else {
                    std::cout << "  [FAIL] PC=" << pc_val
                              << "  got: "      << got
                              << "  expected: " << expected << "\n";
                    fail++;
                }
            }
        }

        std::cout << "\n[TB] Done — PASS: " << pass << "  FAIL: " << fail << "\n";
        sc_stop();
    }
};

#endif
