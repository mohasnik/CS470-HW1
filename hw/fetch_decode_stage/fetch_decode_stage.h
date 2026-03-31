// MODULE : fetch_stage
#ifndef __FETCH_DECODE_STAGE_H__
#define __FETCH_DECODE_STAGE_H__

#include <systemc.h>
#include "sram.h"
#include "instruction.h"


const uint32_t instruction_memory_size = 256;
typedef Sram<1, instruction_memory_size, Instruction> fetch_inst_mem;

SC_MODULE(fetch_decode_stage) {
    sc_in<sc_logic> backp_stall;
    sc_in<sc_logic> clk_i;
    sc_in<sc_logic> rst_ni;

    sc_out<uint32_t> pc_o;

    sc_signal<uint32_t> pc;

    sc_out<Instruction> inst_o[4];


    fetch_inst_mem* inst_mem;

    SC_CTOR(fetch_decode_stage) {
        initialize();


        SC_METHOD(eval);
            sensitive << clk_i << backp_stall;
    }

    void initialize();
    void eval();

    void fetch_instructins();


};


void fetch_decode_stage::initialize() {
    inst_mem = new fetch_inst_mem("inst_mem");
    pc.write(0);
}


void fetch_decode_stage::eval() {
    if(rst_ni == '1' ) {
        pc = 0;
    }
    else if (backp_stall == '0') {

        pc = (int)(pc.read()) + 4;
    }
}


void fetch_decode_stage::fetch_instructins() {
    
}


#endif
