#ifndef __COUNTER_H__
#define __COUNTER_H__

#include <systemc.h>
#include "../utils.h"

template<int MAX_COUNT>
SC_MODULE(Counter) {

    static constexpr int WIDTH = clog2(MAX_COUNT);

    sc_in<sc_logic>      clk_i;
    sc_in<sc_logic>      rst_ni;
    sc_in<sc_logic>     cen_ni;

    sc_out<sc_lv<WIDTH>> count_o;
    sc_out<sc_logic>    cout_o;

    sc_signal<sc_uint<WIDTH>> count_r;

    SC_CTOR(Counter) {
        SC_METHOD(update);
            sensitive << clk_i.pos();


        SC_METHOD(coutUpdate);
            sensitive << count_r;

        SC_METHOD(countOutUpdateComb);
            sensitive << count_r;
    
    }

    void coutUpdate(); 

    void update();

    void countOutUpdateComb();
};

template<int MAX_COUNT>
void Counter<MAX_COUNT>::update()
{
    if (rst_ni.read() == SC_LOGIC_0) {
        count_r.write(0);
    } else if(cen_ni == '0') {
        sc_uint<WIDTH> next = count_r.read() + 1;
        if (next >= MAX_COUNT)
            next = 0;
        count_r.write(next);
    }
}


template<int MAX_COUNT>
void Counter<MAX_COUNT>::coutUpdate() {
    cout_o = (sc_logic)(count_r.read() == (sc_uint<WIDTH>)(MAX_COUNT - 1));
}


template<int MAX_COUNT>
void Counter<MAX_COUNT>::countOutUpdateComb() {

    count_o.write(count_r.read());
}

#endif