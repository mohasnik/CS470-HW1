#ifndef __COUNTER_H__
#define __COUNTER_H__

#include <systemc.h>
#include "../utils.h"

template<int MAX_COUNT>
SC_MODULE(Counter) {

    static constexpr int WIDTH = clog2(MAX_COUNT);

    sc_in<sc_logic>      clk_i;
    sc_in<sc_logic>      rst_ni;

    sc_out<sc_lv<WIDTH>> count_o;

    sc_signal<sc_uint<WIDTH>> count_r;

    SC_CTOR(Counter) {
        SC_METHOD(update);
        sensitive << clk_i.pos();
    }

    void update() {
        if (rst_ni.read() == SC_LOGIC_0) {
            count_r.write(0);
        } else {
            sc_uint<WIDTH> next = count_r.read() + 1;
            if (next >= MAX_COUNT)
                next = 0;
            count_r.write(next);
        }
        count_o.write(count_r.read());
    }
};

#endif