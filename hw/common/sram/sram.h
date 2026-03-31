#ifndef __SRAM_H__
#define __SRAM_H__

#include <systemc.h>
#include "../utils.h"

template<int LATENCY, int NUM_WORDS, typename data_t>
SC_MODULE(Sram) {

    static constexpr int address_size = clog2(NUM_WORDS);
    typedef sc_lv<address_size> sram_address_t;

    sc_in<sc_logic> clk_i;
    sc_in<sc_logic> rst_ni;
    

    // interface
    sc_in<sc_logic> req_i;
    sc_in<sc_logic> we_i;
    sc_in<sram_address_t> addr_i;
    sc_in<data_t> wdata_i;
    sc_out<data_t> rdata_o;


    data_t mem[NUM_WORDS];


    SC_CTOR(Sram) {
        SC_THREAD(eval);
            sensitive << clk_i.pos();
    }

    void eval();
    void resetValues();
};


template<int LATENCY, int NUM_WORDS, typename data_t>
void Sram<LATENCY, NUM_WORDS, data_t>::eval() {
    bool write_en;
    uint32_t address;
    data_t write_data;

    while (true)
    {
        
        if(rst_ni == '0') {
            rdata_o = data_t();
            resetValues();
        } else {
            if(req_i == '1') {
                write_en = (bool)( we_i == '1');
                address = addr_i.read().to_uint();
                write_data = wdata_i.read();
                
                // wait for latency
                for(int i = 0; i < LATENCY-1; i++)
                    wait(clk_i.posedge_event());

                    if (write_en) { // write
                        mem[address] = write_data;
                    }   
                    else {  // read

                        rdata_o = mem[address];
                    }
            }
        }    

        wait();
    }
    
    
}


template<int LATENCY, int NUM_WORDS, typename data_t>
void Sram<LATENCY, NUM_WORDS, data_t>::resetValues() {
    for(int i = 0; i < NUM_WORDS; i++) {
        mem[i] = data_t();  // initialize data_t with default constructor
    }
}

#endif