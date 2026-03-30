// MODULE : fetch_stage
#ifndef __FETCH_STAGE_H__
#define __FETCH_STAGE_H__

#include <systemc.h>
#include "sram.h"
#include "instruction.h"


const uint32_t instruction_memory_size = 256;
typedef Sram<1, instruction_memory_size, Instruction> fetch_inst_mem;

SC_MODULE(fetch_stage) {
    sc_in<sc_logic> backp_stall;
    sc_in<sc_logic> clk;
    sc_in<sc_logic> rst;

    sc_out<uint32_t> pc;

    sc_out<Instruction> inst_o[4];


    fetch_inst_mem* inst_mem;

    SC_CTOR(fetch_stage) {
        initialize();


        SC_METHOD(eval);
            sensitive << clk;
    }

    void initialize();
    void eval();

    void fetch_instructins();


};


void fetch_stage::initialize() {
    inst_mem = new fetch_inst_mem("inst_mem");
    pc.write(0);
}


void fetch_stage::eval() {
    if(rst == '1' ) {
        pc = 0;
    }
    else if (backp_stall == '0') {

        pc = (int)(pc.read()) + 4;
    }
}


void fetch_stage::fetch_instructins() {
    
}


#endif
