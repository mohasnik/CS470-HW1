import json
import sys
import re
from collections import deque
from copy import deepcopy


# =============================================================================
# Instruction
# =============================================================================

class Instruction:
    """Decoded instruction representation."""

    # Regex patterns for parsing
    _RE_REG_REG = re.compile(
        r"^(add|sub|mulu|divu|remu)\s+x(\d+),\s*x(\d+),\s*x(\d+)$"
    )
    _RE_IMM = re.compile(
        r"^(addi)\s+x(\d+),\s*x(\d+),\s*(-?\d+)$"
    )

    def __init__(self, pc: int, opcode: str, dest: int, src_a: int,
                 src_b: int | None = None, imm: int | None = None):
        self.pc = pc
        self.opcode = opcode      # "add", "sub", "mulu", "divu", "remu"
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


# =============================================================================
# Active List Entry
# =============================================================================

class ActiveListEntry:
    def __init__(self, pc: int, done: bool, exception: bool,
                 logical_dest: int, old_dest: int):
        self.pc = pc
        self.done = done
        self.exception = exception
        self.logical_dest = logical_dest  # architectural register id
        self.old_dest = old_dest          # previous physical register for that arch reg

    def to_dict(self) -> dict:
        return {
            "Done": self.done,
            "Exception": self.exception,
            "LogicalDestination": self.logical_dest,
            "OldDestination": self.old_dest,
            "PC": self.pc,
        }


# =============================================================================
# Integer Queue Entry
# =============================================================================

class IQEntry:
    def __init__(self, pc: int, opcode: str, dest_preg: int,
                 op_a_ready: bool, op_a_tag: int, op_a_val: int,
                 op_b_ready: bool, op_b_tag: int, op_b_val: int):
        self.pc = pc
        self.opcode = opcode
        self.dest_preg = dest_preg
        self.op_a_ready = op_a_ready
        self.op_a_tag = op_a_tag      # physical register tag for operand A
        self.op_a_val = op_a_val      # value of operand A (valid when ready)
        self.op_b_ready = op_b_ready
        self.op_b_tag = op_b_tag
        self.op_b_val = op_b_val

    def to_dict(self) -> dict:
        return {
            "DestRegister": self.dest_preg,
            "OpAIsReady": self.op_a_ready,
            "OpARegTag": self.op_a_tag,
            "OpAValue": self.op_a_val,
            "OpBIsReady": self.op_b_ready,
            "OpBRegTag": self.op_b_tag,
            "OpBValue": self.op_b_val,
            "OpCode": self.opcode,
            "PC": self.pc,
        }


# =============================================================================
# Processor State
# =============================================================================

class ProcessorState:
    """All clocked state of the OoO470 processor."""

    def __init__(self):
        # Program Counter
        self.pc: int = 0

        # Physical Register File: 64 x 64-bit unsigned
        self.phys_reg_file: list[int] = [0] * 64

        # Decoded Instruction Register (buffer between F&D and R&D)
        self.decoded_insts: list[Instruction] = []

        # Exception state
        self.exception: bool = False
        self.exception_pc: int = 0

        # Register Map Table: arch_reg -> phys_reg  (32 entries)
        self.reg_map: list[int] = list(range(32))

        # Free List: FIFO of available physical registers
        self.free_list: deque[int] = deque(range(32, 64))

        # Busy Bit Table: 64 booleans
        self.busy_bit: list[bool] = [False] * 64

        # Active List (in program order)
        self.active_list: list[ActiveListEntry] = []

        # Integer Queue
        self.int_queue: list[IQEntry] = []

    def snapshot(self) -> dict:
        """Produce the JSON-serialisable dict for one cycle."""
        return {
            "ActiveList": [e.to_dict() for e in self.active_list],
            "BusyBitTable": list(self.busy_bit),
            "DecodedPCs": [inst.pc for inst in self.decoded_insts],
            "Exception": self.exception,
            "ExceptionPC": self.exception_pc,
            "FreeList": list(self.free_list),
            "IntegerQueue": [e.to_dict() for e in self.int_queue],
            "PC": self.pc,
            "PhysicalRegisterFile": list(self.phys_reg_file),
            "RegisterMapTable": list(self.reg_map),
        }


# =============================================================================
# ALU Pipeline Entry (models the 2-cycle execution latency)
# =============================================================================

class ALUPipeEntry:
    """One instruction in the ALU pipeline."""
    def __init__(self, pc: int, opcode: str, dest_preg: int,
                 op_a_val: int, op_b_val: int, cycles_left: int = 2):
        self.pc = pc
        self.opcode = opcode
        self.dest_preg = dest_preg
        self.op_a_val = op_a_val
        self.op_b_val = op_b_val
        self.cycles_left = cycles_left   # counts down: 2 -> 1 -> 0 (result ready)
        self.result: int | None = None
        self.exception: bool = False


# =============================================================================
# Simulator
# =============================================================================

class Simulator:
    NUM_PHYS_REGS = 64
    NUM_ARCH_REGS = 32
    ACTIVE_LIST_SIZE = 32
    IQ_SIZE = 32
    FETCH_WIDTH = 4
    COMMIT_WIDTH = 4
    NUM_ALUS = 4
    ALU_LATENCY = 2

    def __init__(self, program: list[Instruction]):
        self.program = program
        self.state = ProcessorState()
        self.log: list[dict] = []

        # ALU pipelines: list of in-flight ALU operations
        # Each ALU slot holds a list representing 2 pipeline stages
        # We model it as a flat list; at most NUM_ALUS * ALU_LATENCY entries
        self.alu_pipeline: list[ALUPipeEntry] = []

        # Forwarding paths: results available this cycle (dest_preg -> (value, exception))
        self.forwarding: dict[int, tuple[int, bool]] = {}

    def run(self):
        # Dump initial (reset) state
        self.log.append(self.state.snapshot())

        while not self._is_done():
            self._cycle()
            self.log.append(self.state.snapshot())

    def _is_done(self) -> bool:
        """Simulation ends when all instructions committed and no exception recovery pending."""
        all_fetched = self.state.pc >= len(self.program)
        no_decoded = len(self.state.decoded_insts) == 0
        no_active = len(self.state.active_list) == 0
        no_iq = len(self.state.int_queue) == 0
        no_alu = len(self.alu_pipeline) == 0
        return all_fetched and no_decoded and no_active and no_iq and no_alu

    def _cycle(self):
        # === Propagate phase ===
        # Order matters: we compute the *next* state from the *current* state.
        # We process stages in reverse pipeline order so that downstream
        # results (forwarding, commits) are available for upstream decisions.

        # TODO: implement each stage
        # self._propagate_commit()
        # self._propagate_execute()
        # self._propagate_issue()
        # self._propagate_rename_dispatch()
        # self._propagate_fetch_decode()

        # === Latch phase ===
        # Replace current state with next state (done inside each propagate call)
        pass

    # ------------------------------------------------------------------
    # JSON output
    # ------------------------------------------------------------------
    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.log, f, indent=2)


# =============================================================================
# Entry point
# =============================================================================

def load_program(path: str) -> list[Instruction]:
    with open(path) as f:
        lines = json.load(f)
    return [Instruction.from_string(line, pc) for pc, line in enumerate(lines)]


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.json> <output.json>")
        sys.exit(1)

    program = load_program(sys.argv[1])
    sim = Simulator(program)
    sim.run()
    sim.save(sys.argv[2])


if __name__ == "__main__":
    main()
