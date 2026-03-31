#ifndef __INST_MEM__
#define  __INST_MEM__

#include "instruction.h"
#include "sram.h"
#include <systemc.h>
#include <iostream>
#include <fstream>

template<int MEM_SIZE, int NUM_PORTS>
SC_MODULE(instruction_memory) {

    static_assert((NUM_PORTS & (NUM_PORTS - 1)) == 0 && NUM_PORTS > 0,
              "NUM_PORTS must be a power of 2");

    static_assert((MEM_SIZE & (MEM_SIZE - 1)) == 0 && MEM_SIZE > 0,
              "MEM_SIZE must be a power of 2");

    // ── Bank configuration ────────────────────────────────────────────────────
    // Each bank holds MEM_SIZE/NUM_PORTS instructions, round-robin distributed.
    static constexpr int BANK_WORDS          = MEM_SIZE / NUM_PORTS;
    static constexpr int BANK_LATENCY        = 1;
    static constexpr int ADDRESS_WIDTH       = clog2(MEM_SIZE);
    static constexpr int BANK_ADDRESS_WIDTH  = clog2(BANK_WORDS);

    using Bank        = Sram<BANK_LATENCY, BANK_WORDS, Instruction>;
    using addr_t      = sc_lv<ADDRESS_WIDTH>;
    using bank_addr_t = sc_lv<BANK_ADDRESS_WIDTH>;

    // ── Ports ─────────────────────────────────────────────────────────────────
    sc_in<sc_logic>     clk;
    sc_in<sc_logic>     rst_ni;
    sc_in<sc_logic>     req_i;
    sc_in<addr_t>       addr_i;       // full instruction address (lower bits = port offset)
    sc_out<sc_logic>    r_ack_o;
    sc_out<Instruction> r_data_o[NUM_PORTS];

    // ── Internal signals connecting to SRAM banks ─────────────────────────────
    sc_signal<sc_logic>     bank_req  [NUM_PORTS];
    sc_signal<sc_logic>     bank_we   [NUM_PORTS];   // always 0 (read-only)
    sc_signal<bank_addr_t>  bank_addr [NUM_PORTS];
    sc_signal<Instruction>  bank_wdata[NUM_PORTS];   // unused
    sc_signal<Instruction>  bank_rdata[NUM_PORTS];
    

    sc_signal<uint32_t> delay_counter;

    Bank* banks[NUM_PORTS];
    int   loadedCount = 0;

    SC_CTOR(instruction_memory) {
        initModules();

        SC_METHOD(delayCount);
        sensitive << clk.pos();

        SC_METHOD(combinationalAssignments);
        sensitive << req_i << rst_ni << addr_i << delay_counter;
        for (int i = 0; i < NUM_PORTS; i++)
            sensitive << bank_rdata[i];
    }

    void combinationalAssignments();

    void initModules();

    // ── Main synchronous thread ───────────────────────────────────────────────
    // With combinational bank_req, SRAM sees req at posedge N.
    // SRAM writes rdata_o at posedge N (delta-delayed → bank_rdata valid at posedge N+1).
    // So we wait BANK_LATENCY posedges before reading bank_rdata.
    // Total latency: BANK_LATENCY cycles (vs BANK_LATENCY+1 without combinational req).

    void delayCount();

    // ── Load instructions from JSON, distributed round-robin across banks ─────
    // Instruction i → bank[i % NUM_PORTS], address i / NUM_PORTS
    void loadFromJson(std::string filePath) {
        std::ifstream f(filePath);
        if (!f) {
            std::cerr << "[instruction_memory] Cannot open: " << filePath << "\n";
            return;
        }

        int count = 0;
        std::string line;
        while (count < MEM_SIZE && std::getline(f, line)) {
            size_t lo = line.find_first_not_of(" \t\r\n");
            if (lo == std::string::npos) continue;
            size_t hi = line.find_last_not_of(" \t\r\n");
            line = line.substr(lo, hi - lo + 1);

            if (line == "[" || line == "]") continue;
            if (line.back()  == ',') line.pop_back();
            if (line.front() == '"') line = line.substr(1);
            if (line.back()  == '"') line.pop_back();
            if (line.empty()) continue;

            banks[count % NUM_PORTS]->mem[count / NUM_PORTS] = Instruction(line);
            count++;
        }

        loadedCount = count;
        std::cout << "[instruction_memory] Loaded " << count
                  << " instructions across " << NUM_PORTS << " banks ("
                  << BANK_WORDS << " words/bank) from " << filePath << "\n";
    }

    // ── Initialize all banks to NOP ───────────────────────────────────────────
    void initValues() {
        for (int i = 0; i < NUM_PORTS; i++)
            for (int j = 0; j < BANK_WORDS; j++)
                banks[i]->mem[j] = Instruction();
    }

};


template<int MEM_SIZE, int NUM_PORTS>
void instruction_memory<MEM_SIZE, NUM_PORTS>::delayCount() {
    if (rst_ni == SC_LOGIC_0 || req_i == SC_LOGIC_0)
        delay_counter.write(0);
    else
        delay_counter.write((delay_counter.read() + 1) % BANK_LATENCY);
}


template<int MEM_SIZE, int NUM_PORTS>
void instruction_memory<MEM_SIZE, NUM_PORTS>::combinationalAssignments()
{
    sc_logic req_value = (rst_ni == SC_LOGIC_0) ? SC_LOGIC_0 : req_i.read();

    for (int i = 0; i < NUM_PORTS; i++)
        bank_req[i].write(req_value);

    // upper BANK_ADDRESS_WIDTH bits of addr_i select the row within each bank
    bank_addr_t baddr = addr_i.read().range(ADDRESS_WIDTH - 1, ADDRESS_WIDTH - BANK_ADDRESS_WIDTH);

    std::cout << "baddr : " << baddr.to_uint() << std::endl;

    for (int i = 0; i < NUM_PORTS; i++) {
        bank_addr[i].write(baddr);
        r_data_o[i].write(bank_rdata[i].read());

    }

    r_ack_o.write((delay_counter == BANK_LATENCY-1) && req_i.read().to_bool() ? SC_LOGIC_1 : SC_LOGIC_0);


}

template<int MEM_SIZE, int NUM_PORTS>
void instruction_memory<MEM_SIZE, NUM_PORTS>::initModules() {

    for (int i = 0; i < NUM_PORTS; i++) {
        banks[i] = new Bank(sc_gen_unique_name("bank"));
        banks[i]->clk_i  (clk);
        banks[i]->rst_ni (rst_ni);
        banks[i]->req_i  (bank_req  [i]);
        banks[i]->we_i   (bank_we   [i]);
        banks[i]->addr_i (bank_addr [i]);
        banks[i]->wdata_i(bank_wdata[i]);
        banks[i]->rdata_o(bank_rdata[i]);

        bank_we[i].write(SC_LOGIC_0);
    }
}


#endif