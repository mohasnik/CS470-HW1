#ifndef __COUNTER_TB_H__
#define __COUNTER_TB_H__

#include <systemc.h>
#include <iostream>
#include <cstdlib>
#include "counter.h"

#define TB_MAX_COUNT  10
#define TB_RUN_CYCLES 200   // total cycles to run the random test

using DUT = Counter<TB_MAX_COUNT>;

SC_MODULE(CounterTB) {

    sc_signal<sc_logic>              clk;
    sc_signal<sc_logic>              rst_ni;
    sc_signal<sc_logic>              cen_ni;
    sc_signal<sc_lv<DUT::WIDTH>>     count_o;
    sc_signal<sc_logic>              cout_o;

    DUT *dut;

    SC_CTOR(CounterTB) {
        dut = new DUT("counter");
        dut->clk_i  (clk);
        dut->rst_ni (rst_ni);
        dut->cen_ni (cen_ni);
        dut->count_o(count_o);
        dut->cout_o (cout_o);

        rst_ni.write(SC_LOGIC_0);
        cen_ni.write(SC_LOGIC_1);

        SC_THREAD(gen_clock);
        SC_THREAD(stimulus);
    }

    // Advance one posedge and let all delta-cycle updates settle
    void posedge_and_settle() {
        wait(clk.posedge_event());
        wait(SC_ZERO_TIME);
        wait(SC_ZERO_TIME);
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

    void check(const char* tag, unsigned int got, unsigned int expected,
               int& pass, int& fail) {
        if (got == expected) {
            pass++;
        } else {
            std::cout << "[FAIL] " << tag
                      << "  got=" << got << "  expected=" << expected << "\n";
            fail++;
        }
    }

    void stimulus() {
        std::srand(42);
        int pass = 0, fail = 0;

        // ── 1. Reset check ────────────────────────────────────────────────────
        rst_ni.write(SC_LOGIC_0);
        cen_ni.write(SC_LOGIC_0);
        posedge_and_settle();
        posedge_and_settle();
        check("reset", count_o.read().to_uint(), 0, pass, fail);

        // ── 2. Release reset ──────────────────────────────────────────────────
        rst_ni.write(SC_LOGIC_1);

        // model tracks what the counter *should* be
        int model = 0;

        // ── 3. Random-stall run ───────────────────────────────────────────────
        // Each iteration: randomly decide to stall for 1-3 cycles, then count,
        // checking count_o and cout_o every cycle.
        int stall_countdown = 0;

        for (int cycle = 0; cycle < TB_RUN_CYCLES; cycle++) {

            // Decide enable/stall at negedge (between posedges) so the signal
            // is stable before the next rising edge.
            bool enabled;
            if (stall_countdown > 0) {
                cen_ni.write(SC_LOGIC_1);   // stall
                enabled = false;
                stall_countdown--;
            } else {
                cen_ni.write(SC_LOGIC_0);   // count
                enabled = true;
                // 30% chance to insert a stall next cycle
                if ((std::rand() % 10) < 3)
                    stall_countdown = 1 + (std::rand() % 3);  // 1-3 stall cycles
            }

            posedge_and_settle();

            // Update model: only advance when enabled
            if (enabled) {
                model = (model + 1) % TB_MAX_COUNT;
            }

            unsigned int got_count = count_o.read().to_uint();
            sc_logic     got_cout  = cout_o.read();
            sc_logic     exp_cout  = (model == TB_MAX_COUNT - 1) ? SC_LOGIC_1 : SC_LOGIC_0;

            check("count_o", got_count, (unsigned int)model, pass, fail);

            if (got_cout == exp_cout) {
                pass++;
            } else {
                std::cout << "[FAIL] cout_o=" << got_cout
                          << "  expected=" << exp_cout
                          << "  at model=" << model
                          << "  cycle=" << cycle << "\n";
                fail++;
            }
        }

        // ── 4. Mid-run reset ──────────────────────────────────────────────────
        cen_ni.write(SC_LOGIC_0);
        posedge_and_settle();
        posedge_and_settle();   // advance a couple cycles first

        rst_ni.write(SC_LOGIC_0);
        posedge_and_settle();
        model = 0;

        check("mid-run reset", count_o.read().to_uint(), 0, pass, fail);

        std::cout << "\n[TB] Done — PASS: " << pass << "  FAIL: " << fail << "\n";
        sc_stop();
    }
};

#endif
