#ifndef __INST_MEM__
#define  __INST_MEM__

#include "instruction.h"
#include <systemc.h>
#include <iostream>
#include <fstream>
#include <sstream>
#include <cstdint>






template<int MEM_SIZE>
SC_MODULE(InstructionMemory) {

    sc_in<sc_logic> clk, rst;
    sc_in<sc_logic> r_req_i;
    sc_in<sc_uint<32>> r_addr_i;
    sc_out<sc_logic> r_ack_i;

    sc_out<Instruction> r_data_o[4];


    Instruction mem[MEM_SIZE]; // abstraction for now.
    int loadedCount = 0;       // number of instructions loaded from JSON


    SC_CTOR(InstructionMemory) {

        SC_THREAD(run);
            sensitive << clk.pos();
    }


    // used only for debugging purposes. 
    // Initializes every cell to 0xffff_ffff
    void initValues();

    void run();

    // TODO : support bianry in future
    // void loadBinFromFile(std::string filePath); 

    void loadFromJson(std::string filePath);

};


template<int MEM_SIZE>
void InstructionMemory<MEM_SIZE>::loadFromJson(std::string filePath) {
    std::ifstream f(filePath);
    if (!f) {
        std::cerr << "[InstructionMemory] Cannot open JSON file: " << filePath << "\n";
        return;
    }

    int count = 0;
    std::string line;
    while (count < MEM_SIZE && std::getline(f, line)) {
        // Strip leading/trailing whitespace
        size_t lo = line.find_first_not_of(" \t\r\n");
        if (lo == std::string::npos) continue;
        size_t hi = line.find_last_not_of(" \t\r\n");
        line = line.substr(lo, hi - lo + 1);

        // Skip JSON array brackets
        if (line == "[" || line == "]") continue;

        // Strip surrounding double-quotes and optional trailing comma
        if (line.back() == ',') line.pop_back();
        if (line.front() == '"') line = line.substr(1);
        if (line.back()  == '"') line.pop_back();

        if (line.empty()) continue;

        mem[count++] = Instruction(line);
    }

    loadedCount = count;
    std::cout << "[InstructionMemory] Loaded " << count
              << " instructions from " << filePath << "\n";
}

template<int MEM_SIZE>
void InstructionMemory<MEM_SIZE>::initValues() {
    for (int i = 0; i < MEM_SIZE; i++)
        mem[i] = NOP_INSTRUCTION;
}

template<int MEM_SIZE>
void InstructionMemory<MEM_SIZE>::run() {
    while (true)
    {   
        r_ack_i = SC_LOGIC_0;

        if (rst.read() == SC_LOGIC_1) {
            r_ack_i = SC_LOGIC_0;
        }
        else if (clk.posedge()) {
            if (r_req_i.read() == SC_LOGIC_1) {
                // CHECK : enables unaligned read. unfavorable.
                wait(clk.posedge_event());
    
                for(int i = 0; i < 4; i ++ )
                    r_data_o[i] = mem[(int)(r_addr_i.read()) + i];
                
                r_ack_i = SC_LOGIC_1;
            }
        }

        wait();
    }
    
}

#endif