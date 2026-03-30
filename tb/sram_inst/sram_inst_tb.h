#ifndef __SRAM_INST_TB_H__
#define __SRAM_INST_TB_H__

#include <systemc.h>
#include <iostream>
#include <iomanip>
#include <vector>
#include <string>
#include <cstdlib>
#include "sram.h"
#include "instruction.h"

// Testbench parameters
#define SRAM_LATENCY   2
#define SRAM_WORDS     32

enum class OpType { READ, WRITE };

struct Op {
    OpType      type;
    int         addr;
    Instruction data;   // only used for WRITE
};

// Generate a random valid Instruction
static Instruction random_instruction() {
    static const char* r_ops[] = { "add", "sub", "mulu", "divu", "remu" };
    int rd  = rand() % 32;
    int rs1 = rand() % 32;
    if (rand() % 2 == 0) {
        int imm = (rand() % 4096) - 2048;  // 12-bit signed
        return Instruction("addi x" + std::to_string(rd) +
                           ", x"   + std::to_string(rs1) +
                           ", "    + std::to_string(imm));
    } else {
        int rs2 = rand() % 32;
        const char* op = r_ops[rand() % 5];
        return Instruction(std::string(op) +
                           " x"  + std::to_string(rd)  +
                           ", x" + std::to_string(rs1) +
                           ", x" + std::to_string(rs2));
    }
}

// Generate a random mixed sequence of reads and writes
static std::vector<Op> gen_mixed_seq(int size, float write_ratio = 0.5f) {
    std::vector<Op> seq(size);
    for (auto& op : seq) {
        op.type = ((rand() / (float)RAND_MAX) < write_ratio) ? OpType::WRITE : OpType::READ;
        op.addr = rand() % SRAM_WORDS;
        op.data = random_instruction();
    }
    return seq;
}

SC_MODULE(SramInstTB) {

    sc_signal<sc_logic>                    clk;
    sc_signal<sc_logic>                    rst_ni;
    sc_signal<sc_logic>                    req_i;
    sc_signal<sc_logic>                    we_i;
    sc_signal<sc_lv<clog2<SRAM_WORDS>()>> addr_i;
    sc_signal<Instruction>                 wdata_i;
    sc_signal<Instruction>                 rdata_o;

    InstructionTracer wdata_tracer;
    InstructionTracer rdata_tracer;

    Sram<SRAM_LATENCY, SRAM_WORDS, Instruction> *dut;

    SC_CTOR(SramInstTB) {
        dut = new Sram<SRAM_LATENCY, SRAM_WORDS, Instruction>("sram_dut");
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
        wdata_i.write(Instruction());

        SC_THREAD(gen_clock);
        SC_THREAD(gen_reset);
        SC_THREAD(stimulus);

        SC_METHOD(update_tracers);
        sensitive << wdata_i << rdata_o;
    }

    void update_tracers() {
        wdata_tracer.update(wdata_i.read());
        rdata_tracer.update(rdata_o.read());
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

    void do_write(int addr, const Instruction& inst) {
        addr_i.write(addr);
        wdata_i.write(inst);
        we_i.write(SC_LOGIC_1);
        req_i.write(SC_LOGIC_1);
        wait(clk.posedge_event());
        req_i.write(SC_LOGIC_0);
        we_i.write(SC_LOGIC_0);
        for (int i = 1; i < SRAM_LATENCY; i++)
            wait(clk.posedge_event());
    }

    Instruction do_read(int addr) {
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
        srand(42);

        wait(rst_ni.posedge_event());
        wait(clk.posedge_event());

        // shadow memory: tracks expected SRAM state (Instruction() = NOP = reset value)
        Instruction shadow[SRAM_WORDS];
        bool        ever_written[SRAM_WORDS] = {};

        const auto seq = gen_mixed_seq(40, 0.5f);

        int pass = 0, fail = 0;
        std::cout << "\n[TB] === Mixed read/write sequence (data_t = Instruction) ===\n";

        for (const auto& op : seq) {
            idle_random(3);

            if (op.type == OpType::WRITE) {
                do_write(op.addr, op.data);
                shadow[op.addr]       = op.data;
                ever_written[op.addr] = true;
                std::cout << "[TB] WRITE addr=0x" << std::hex << std::setw(2) << std::setfill('0')
                          << op.addr << std::dec << "  inst=[ " << op.data << " ]\n";

            } else {
                Instruction expected = shadow[op.addr];
                Instruction got      = do_read(op.addr);
                bool ok = (got == expected);

                std::cout << "[TB] READ  addr=0x" << std::hex << std::setw(2) << std::setfill('0')
                          << op.addr << std::dec
                          << "  expected=[ " << expected << " ]"
                          << "  got=[ "      << got      << " ]"
                          << "  " << (ok ? "PASS" : "FAIL");
                if (!ever_written[op.addr]) std::cout << " (uninitialized)";
                std::cout << "\n";

                ok ? pass++ : fail++;
            }
        }

        std::cout << "\n[TB] === Result: " << pass << " PASS, " << fail << " FAIL ===\n";
        sc_stop();
    }
};

#endif
