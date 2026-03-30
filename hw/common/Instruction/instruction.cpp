#include "instruction.h"

Instruction::Instruction() 
    : dest(-1), op_a(-1), op_b(-1), imm(0), is_imm(false) 
{
    parseInstruction(NOP_INSTRUCTION);
}

Instruction::Instruction(std::string inst_str)
    : dest(-1), op_a(-1), op_b(-1), imm(0), is_imm(false)
{
    parseInstruction(inst_str);
}

Instruction::~Instruction()
{
}

void Instruction::parseInstruction(std::string inst)
{
    // R-type: add|sub|mulu|divu|remu  xDEST, xOPA, xOPB
    static const std::regex r_rtype(
        R"((add|sub|mulu|divu|remu)\s+x(\d+)\s*,\s*x(\d+)\s*,\s*x(\d+))");
    // I-type: addi  xDEST, xOPA, IMM
    static const std::regex r_itype(
        R"(addi\s+x(\d+)\s*,\s*x(\d+)\s*,\s*(-?\d+))");

    std::smatch m;
    if (std::regex_match(inst, m, r_rtype)) {
        opcode_str = m[1].str();
        dest       = std::stoi(m[2].str());
        op_a       = std::stoi(m[3].str());
        op_b       = std::stoi(m[4].str());
        imm        = 0;
        is_imm     = false;

        if      (opcode_str == "add")  opcode_id = OP_ADD;
        else if (opcode_str == "sub")  opcode_id = OP_SUB;
        else if (opcode_str == "mulu") opcode_id = OP_MULU;
        else if (opcode_str == "divu") opcode_id = OP_DIVU;
        else                           opcode_id = OP_REMU;

        dest_str  = "x" + m[2].str();
        op_str[0] = "x" + m[3].str();
        op_str[1] = "x" + m[4].str();

    } else if (std::regex_match(inst, m, r_itype)) {
        opcode_str = "addi";
        dest       = std::stoi(m[1].str());
        op_a       = std::stoi(m[2].str());
        op_b       = -1;
        imm        = std::stoi(m[3].str());
        is_imm     = true;
        opcode_id  = OP_ADDI;

        dest_str  = "x" + m[1].str();
        op_str[0] = "x" + m[2].str();
        op_str[1] = m[3].str();   // immediate kept as string too

    } else {
        throw std::invalid_argument("Cannot parse instruction: \"" + inst + "\"");
    }
}


Instruction& Instruction::operator=(const std::string& inst_str) {
    parseInstruction(inst_str);
    return *this;
}
