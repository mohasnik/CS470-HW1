// MODULE : fetch_stage
#ifndef __FETCH_DECODE_STAGE_H__
#define __FETCH_DECODE_STAGE_H__

#include <systemc.h>
#include "instruction_memory.h"
#include "instruction.h"
#include "custom_counter.h"



SC_MODULE(fetch_decode_stage) {
    static constexpr uint32_t instruction_memory_size = 256;
    static constexpr uint32_t pc_width = clog2(instruction_memory_size);

    sc_in<sc_logic> backp_stall;
    sc_in<sc_logic> clk_i;
    sc_in<sc_logic> rst_ni;

    sc_out<uint32_t> pc_o;

    sc_signal<sc_lv<pc_width>> pc;

    sc_out<Instruction> inst_o[4];


    
    // TODO: make the instruction memory size configurable 
    custom_counter<instruction_memory_size>* pc_counter; 
    instruction_memory<instruction_memory_size, 4>* inst_mem;
    


    SC_CTOR(fetch_decode_stage) {
        initialize();


        // SC_METHOD(eval);
        //     sensitive << clk_i << backp_stall;
    }

    void initialize();
    void eval();

};


void fetch_decode_stage::initialize() {
    inst_mem = new instruction_memory<instruction_memory_size, 4>("inst_mem");
    inst_mem->clk(clk_i);
    inst_mem->rst_ni(rst_ni);
    inst_mem->req_i();
    inst_mem->addr_i();
    inst_mem->r_ack_o();
    
    for(int i =0 ; i < 4; i++)
        inst_mem->r_data_o[i](inst_o[i]);
    
    
    // Counter instance
    pc_counter = new custom_counter<instruction_memory_size>("pc_counter");
    sc_signal<sc_logic> cout;
    pc_counter->clk_i(clk_i);
    pc_counter->rst_ni(rst_ni);
    pc_counter->cen_ni(backp_stall);
    pc_counter->count_o(pc);
    pc_counter->cout_o(cout);
    // pc_counter->count_step_i(); // TODO : add this!

    

}




#endif
