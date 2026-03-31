import re

# =============================================================================
# Instruction
# =============================================================================

class Instruction:
    # Regex patterns for parsing
    _RE_REG_REG = re.compile(
        r"^(add|sub|mulu|divu|remu)\s+x(\d+),\s*x(\d+),\s*x(\d+)$"
    )
    _RE_IMM = re.compile(
        r"^(addi)\s+x(\d+),\s*x(\d+),\s*(-?\d+)$"
    )

    def __init__(self, opcode: str, dest: int, src_a: int,
                 src_b: int | None = None, imm: int | None = None):
        self.opcode = opcode      
        self.dest = dest           # architectural dest register (0-31)
        self.src_a = src_a         # architectural source A register (0-31)
        self.src_b = src_b         # architectural source B register (0-31), None for addi
        self.imm = imm             # immediate value (only for addi), None otherwise
        self.is_imm = imm is not None

    @classmethod
    def from_string(cls, s: str, pc: int) -> "Instruction":
        """Parse an instruction string like 'addi x1, x2, 10' or 'add x0, x1, x2'."""
        s = s.strip()

        m = cls._RE_IMM.match(s)
        if m:
            opcode = m.group(1)       # "addi"
            dest = int(m.group(2))
            src_a = int(m.group(3))
            imm = int(m.group(4))
            # addi is treated as "add" in the pipeline (opcode stored as "add")
            return cls(pc, "add", dest, src_a, src_b=None, imm=imm)

        m = cls._RE_REG_REG.match(s)
        if m:
            opcode = m.group(1)
            dest = int(m.group(2))
            src_a = int(m.group(3))
            src_b = int(m.group(4))
            return cls(pc, opcode, dest, src_a, src_b=src_b, imm=None)

        raise ValueError(f"Cannot parse instruction: '{s}'")

    @property
    def opcode_json(self) -> str:
        """OpCode string for JSON output."""
        return self.opcode

    def __repr__(self):
        if self.is_imm:
            return f"Instruction(PC={self.pc}, addi x{self.dest}, x{self.src_a}, {self.imm})"
        return f"Instruction(PC={self.pc}, {self.opcode} x{self.dest}, x{self.src_a}, x{self.src_b})"


