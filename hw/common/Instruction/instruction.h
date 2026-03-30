#ifndef __INSTRUCTION_H__
#define __INSTRUCTION_H__

#include <systemc.h>
#include <string>
#include <regex>
#include <stdexcept>

#define NOP_INSTRUCTION "addi x0, x0, 0"

enum OpcodeID {
    OP_ADD  = 0,
    OP_ADDI = 1,
    OP_SUB  = 2,
    OP_MULU = 3,
    OP_DIVU = 4,
    OP_REMU = 5,
};

class Instruction
{
private:
    // String fields (original)
    std::string opcode_str;
    std::string op_str[2];  // [0] = op_a ("xN"), [1] = op_b ("xN") or immediate string
    std::string dest_str;   // e.g. "x3"

    // Integer fields for hardware use
    int      dest;      // destination register index
    int      op_a;      // source register A index
    int      op_b;      // source register B index (-1 for addi)
    int      imm;       // sign-extended immediate (0 for R-type)
    bool     is_imm;    // true for addi (I-type), false for R-type
    OpcodeID opcode_id; // integer opcode, traceable in VCD

public:
    Instruction(std::string inst_str);
    Instruction();
    ~Instruction();

    void parseInstruction(std::string inst);


    std::string getOpcode() const { return opcode_str; }
    int getDest()           const { return dest; }
    int getOpA()            const { return op_a; }
    int getOpB()            const { return op_b; }
    int getImm()            const { return imm; }
    bool     isImmediate()  const { return is_imm; }
    OpcodeID getOpcodeID()  const { return opcode_id; }

    Instruction& operator=(const std::string& inst_str);

    bool operator==(const Instruction& other) const {
        return opcode_str == other.opcode_str &&
               dest == other.dest &&
               op_a == other.op_a &&
               op_b == other.op_b &&
               imm  == other.imm;
    }

    friend std::ostream& operator<<(std::ostream& os, const Instruction& ins) {
        os << ins.opcode_str << " x" << ins.dest
           << ", x" << ins.op_a;
        if (ins.is_imm) os << ", " << ins.imm;
        else            os << ", x" << ins.op_b;
        return os;
    }
};

// Holds stable sc_signal<int> shadows for one sc_signal<Instruction>.
// Usage in any SC_MODULE testbench:
//
//   InstructionTracer tr[4];
//
//   // in SC_METHOD sensitive to r_data_o[i]:
//   tr[i].update(r_data_o[i].read());
//
//   // in sc_main, after module construction:
//   tr[i].trace(tf, "r_data_o_0");
//
struct InstructionTracer {
    sc_signal<int> opcode, dest, op_a, op_b, imm;

    // call from an SC_METHOD whenever the watched sc_signal<Instruction> changes
    void update(const Instruction& ins) {
        opcode.write((int)ins.getOpcodeID());
        dest.write(ins.getDest());
        op_a.write(ins.getOpA());
        op_b.write(ins.getOpB());
        imm.write(ins.getImm());
    }

    // call once in sc_main to register all fields with the VCD trace file
    void trace(sc_trace_file* tf, const std::string& name) {
        sc_trace(tf, opcode, name + ".opcode");
        sc_trace(tf, dest,   name + ".dest");
        sc_trace(tf, op_a,   name + ".op_a");
        sc_trace(tf, op_b,   name + ".op_b");
        sc_trace(tf, imm,    name + ".imm");
    }
};

// sc_out<Instruction> internally compiles sc_trace(tf, iface->read(), name) from within
// the sc_core namespace. Placing the overload here makes it findable by that lookup.
// InstructionTracer is the right way to actually trace; this overload is a no-op stub.
namespace sc_core {
inline void sc_trace(sc_trace_file*, const Instruction&, const std::string&) {}
}

#endif
