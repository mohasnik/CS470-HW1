import json
import sys
from collections import deque
from copy import deepcopy

from hw.common.instruction import Instruction


# =============================================================================
# Active List Entry
# =============================================================================

class ActiveListEntry:
    def __init__(self, pc: int, done: bool, exception: bool,
                 logical_dest: int, old_dest: int):
        self.pc = pc
        self.done = done
        self.exception = exception
        self.logical_dest = logical_dest
        self.old_dest = old_dest

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
        self.op_a_tag = op_a_tag
        self.op_a_val = op_a_val
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
# ALU Pipeline Entry (models the 2-cycle execution latency)
# =============================================================================

class ALUPipeEntry:
    def __init__(self, pc: int, opcode: str, dest_preg: int,
                 op_a_val: int, op_b_val: int):
        self.pc = pc
        self.opcode = opcode
        self.dest_preg = dest_preg
        self.op_a_val = op_a_val
        self.op_b_val = op_b_val
        self.cycles_left: int = 2  # 2 -> 1 -> 0 (broadcast on transition 1->0)
        self.result: int = 0
        self.exception: bool = False


# =============================================================================
# Processor State  (all clocked / architecturally visible storage)
# =============================================================================

class ProcessorState:
    def __init__(self):
        self.pc: int = 0
        self.phys_reg_file: list[int] = [0] * 64
        self.decoded_insts: list[tuple[int, Instruction]] = []   # (pc, Instruction)
        self.exception: bool = False
        self.exception_pc: int = 0
        self.reg_map: list[int] = list(range(32))
        self.free_list: deque[int] = deque(range(32, 64))
        self.busy_bit: list[bool] = [False] * 64
        self.active_list: list[ActiveListEntry] = []
        self.int_queue: list[IQEntry] = []

    def snapshot(self) -> dict:
        return {
            "ActiveList": [e.to_dict() for e in self.active_list],
            "BusyBitTable": list(self.busy_bit),
            "DecodedPCs": [pc for pc, _ in self.decoded_insts],
            "Exception": self.exception,
            "ExceptionPC": self.exception_pc,
            "FreeList": list(self.free_list),
            "IntegerQueue": [e.to_dict() for e in self.int_queue],
            "PC": self.pc,
            "PhysicalRegisterFile": list(self.phys_reg_file),
            "RegisterMapTable": list(self.reg_map),
        }


# =============================================================================
# Unsigned 64-bit arithmetic helpers
# =============================================================================

MASK64 = (1 << 64) - 1


def _sign_extend_imm(imm: int) -> int:
    """Sign-extend a small immediate to 64-bit unsigned representation."""
    return imm & MASK64


def _compute(opcode: str, a: int, b: int) -> tuple[int, bool]:
    """Return (result, exception).  All values are 64-bit unsigned."""
    a &= MASK64
    b &= MASK64
    if opcode == "add":
        return (a + b) & MASK64, False
    elif opcode == "sub":
        return (a - b) & MASK64, False
    elif opcode == "mulu":
        return (a * b) & MASK64, False
    elif opcode == "divu":
        if b == 0:
            return 0, True
        return (a // b) & MASK64, True if False else False  # no exception when b!=0
    elif opcode == "remu":
        if b == 0:
            return 0, True
        return (a % b) & MASK64, False
    raise ValueError(f"Unknown opcode: {opcode}")


def _compute_alu(opcode: str, a: int, b: int) -> tuple[int, bool]:
    """Return (result, is_exception)."""
    a &= MASK64
    b &= MASK64
    if opcode == "add":
        return (a + b) & MASK64, False
    if opcode == "sub":
        return (a - b) & MASK64, False
    if opcode == "mulu":
        return (a * b) & MASK64, False
    if opcode == "divu":
        if b == 0:
            return 0, True
        return (a // b) & MASK64, False
    if opcode == "remu":
        if b == 0:
            return 0, True
        return (a % b) & MASK64, False
    raise ValueError(f"Unknown opcode: {opcode}")


# =============================================================================
# Simulator
# =============================================================================

class Simulator:
    FETCH_WIDTH = 4
    COMMIT_WIDTH = 4
    NUM_ALUS = 4
    ALU_LATENCY = 2
    ACTIVE_LIST_SIZE = 32
    IQ_SIZE = 32

    def __init__(self, program: list[tuple[int, Instruction]]):
        """program is a list of (pc, Instruction) pairs."""
        self.program = program                    # indexed by PC
        self.state = ProcessorState()
        self.log: list[dict] = []

        # ALU pipeline stages (not part of architecturally visible state)
        # stage1: first cycle of ALU, stage2: second cycle (results broadcast)
        self.alu_stage1: list[ALUPipeEntry] = []  # entered this cycle
        self.alu_stage2: list[ALUPipeEntry] = []  # will broadcast at end of this cycle

    # ------------------------------------------------------------------
    def run(self):
        self.log.append(self.state.snapshot())
        while not self._is_done():
            self._cycle()
            self.log.append(self.state.snapshot())

    def _is_done(self) -> bool:
        all_fetched = self.state.pc >= len(self.program)
        no_decoded = len(self.state.decoded_insts) == 0
        no_active = len(self.state.active_list) == 0
        no_iq = len(self.state.int_queue) == 0
        no_alu = len(self.alu_stage1) == 0 and len(self.alu_stage2) == 0
        return all_fetched and no_decoded and no_active and no_iq and no_alu

    # ------------------------------------------------------------------
    # Main cycle: propagate then latch
    #
    # The propagate phase computes the NEXT state from the CURRENT state.
    # We work on copies of data structures ("next_*") and swap at latch.
    #
    # Processing order within one cycle (conceptually simultaneous, but
    # we resolve dependencies by processing in a careful order):
    #
    #   1) Compute forwarding results from ALU stage2
    #   2) Commit  — retire instructions, free old phys regs, detect exceptions
    #   3) Exception recovery (if in exception mode)
    #   4) Execute — advance ALU pipelines, compute results
    #   5) Issue   — pick ready IQ entries, send to ALU stage1
    #   6) Update IQ entries with forwarding (snoop)
    #   7) Rename & Dispatch — rename decoded insts, allocate AL & IQ entries
    #   8) Fetch & Decode — fetch next instructions into DIR
    # ------------------------------------------------------------------

    def _cycle(self):
        s = self.state

        # --- Next-state copies (we modify these, then latch) ---
        next_pc = s.pc
        next_phys_reg = list(s.phys_reg_file)
        next_decoded: list[tuple[int, Instruction]] = list(s.decoded_insts)
        next_exception = s.exception
        next_exception_pc = s.exception_pc
        next_reg_map = list(s.reg_map)
        next_free_list = deque(s.free_list)
        next_busy_bit = list(s.busy_bit)
        next_active_list: list[ActiveListEntry] = list(s.active_list)
        next_int_queue: list[IQEntry] = list(s.int_queue)

        next_alu_stage1: list[ALUPipeEntry] = []
        next_alu_stage2: list[ALUPipeEntry] = []

        # ============================================================
        # STEP 1: Compute forwarding from ALU stage2
        # These are the results becoming available THIS cycle.
        # dict: dest_preg -> (value, is_exception)
        # ============================================================
        forwarding: dict[int, tuple[int, bool]] = {}
        for entry in self.alu_stage2:
            result, exc = _compute_alu(entry.opcode, entry.op_a_val, entry.op_b_val)
            entry.result = result
            entry.exception = exc
            forwarding[entry.dest_preg] = (result, exc)

        # Write forwarding results into physical register file and clear busy bits
        for preg, (val, _exc) in forwarding.items():
            next_phys_reg[preg] = val
            next_busy_bit[preg] = False

        # Mark Active List entries as Done / Exception based on forwarding
        for al_entry in next_active_list:
            if not al_entry.done:
                # Find if this instruction's dest preg produced a result
                # We need to match by PC — find the ALU entry
                pass
        # Actually, we match by checking all forwarding results against AL.
        # The AL doesn't directly store dest_preg, but we can match via the
        # alu_stage2 entries which have both pc and dest_preg.
        for alu_entry in self.alu_stage2:
            for al_entry in next_active_list:
                if al_entry.pc == alu_entry.pc and not al_entry.done:
                    al_entry.done = True
                    al_entry.exception = alu_entry.exception
                    break

        # ============================================================
        # STEP 2: Commit stage (normal mode — not exception)
        # ============================================================
        committed_count = 0
        enter_exception = False
        exception_trigger_pc = 0

        if not s.exception:
            # Scan active list head in program order, retire up to 4
            while committed_count < self.COMMIT_WIDTH and len(next_active_list) > 0:
                head = next_active_list[0]
                if not head.done:
                    break
                if head.exception:
                    # This instruction triggers exception — enter exception mode NEXT cycle
                    enter_exception = True
                    exception_trigger_pc = head.pc
                    break
                # Normal commit: free old destination register
                next_free_list.append(head.old_dest)
                next_active_list.pop(0)
                committed_count += 1

        # ============================================================
        # STEP 3: Exception handling
        # ============================================================
        if s.exception:
            # We are in exception recovery mode.
            # Roll back up to 4 instructions from the BOTTOM of active list
            # (reverse program order).
            rollback_count = 0
            while rollback_count < self.COMMIT_WIDTH and len(next_active_list) > 0:
                tail = next_active_list.pop()  # remove from end (highest PC)
                # Restore: reg_map[logical_dest] = old_dest
                # The "old_dest" was the physical reg mapped BEFORE this instruction
                # was renamed. So to undo: map the logical_dest back to old_dest,
                # and free the NEW physical reg that was allocated.
                #
                # The new physical reg is whatever reg_map currently points to
                # for this logical dest — but during rollback we process in reverse,
                # so we need to track the current mapping as we unwind.
                #
                # Actually: the new phys reg = the one that was allocated for this
                # instruction's dest. It's currently in reg_map[logical_dest] only
                # if no later instruction overwrote it. Since we unwind from the
                # bottom (latest first), reg_map[logical_dest] IS the new phys reg
                # for the latest instruction writing to that logical dest.
                new_preg = next_reg_map[tail.logical_dest]
                next_reg_map[tail.logical_dest] = tail.old_dest
                next_free_list.append(new_preg)
                next_busy_bit[new_preg] = False
                rollback_count += 1

            # Clear IQ and ALU pipelines (done once when entering exception mode,
            # but we keep them clear every cycle during exception)
            next_int_queue = []
            next_alu_stage1 = []
            next_alu_stage2 = []
            next_decoded = []
            next_pc = 0x10000

            if len(next_active_list) == 0:
                # Exception recovery done — exit exception mode
                next_exception = False

        elif enter_exception:
            # Entering exception mode THIS cycle
            next_exception = True
            next_exception_pc = exception_trigger_pc
            next_pc = 0x10000
            next_decoded = []
            next_int_queue = []
            next_alu_stage1 = []
            next_alu_stage2 = []
            # The excepting instruction itself stays in active list (will be rolled back)
            # Actually: per the spec, the excepting instruction is being committed,
            # so we remove it from the active list head as well? Let me re-read...
            #
            # "an instruction is met that is completed but triggers an exception.
            #  In this case, the processor will enter the Exception mode in the next cycle."
            # So the excepting instruction is NOT retired — it stays, and we enter
            # exception mode next cycle. But we already set next_exception = True.
            #
            # "Record the PC of the instruction with the exception in the Exception PC register"
            # "pick (up to) 4 instructions in reverse program order from the Active list bottom"
            #
            # So the excepting instruction and everything after it stays in AL.
            # They will be rolled back starting next cycle from the bottom.

        # ============================================================
        # STEP 4: Advance ALU pipeline (not in exception mode)
        # ============================================================
        if not s.exception and not enter_exception:
            # stage1 -> stage2 (advance)
            next_alu_stage2 = list(self.alu_stage1)
            # stage2 results already consumed above (forwarding), clear
            # (new stage1 will be filled by Issue)
        else:
            next_alu_stage1 = []
            next_alu_stage2 = []

        # ============================================================
        # STEP 5 & 6: Update IQ with forwarding, then Issue
        # ============================================================
        if not s.exception and not enter_exception:
            # Snoop forwarding paths to update IQ operand readiness
            for iq_entry in next_int_queue:
                if not iq_entry.op_a_ready and iq_entry.op_a_tag in forwarding:
                    iq_entry.op_a_ready = True
                    iq_entry.op_a_val = forwarding[iq_entry.op_a_tag][0]
                if not iq_entry.op_b_ready and iq_entry.op_b_tag in forwarding:
                    iq_entry.op_b_ready = True
                    iq_entry.op_b_val = forwarding[iq_entry.op_b_tag][0]

            # Issue: pick up to 4 ready instructions (oldest first = smallest PC)
            ready = [e for e in next_int_queue if e.op_a_ready and e.op_b_ready]
            ready.sort(key=lambda e: e.pc)
            issued = ready[:self.NUM_ALUS]

            issued_set = set(id(e) for e in issued)
            next_int_queue = [e for e in next_int_queue if id(e) not in issued_set]

            for iq_entry in issued:
                alu_entry = ALUPipeEntry(
                    pc=iq_entry.pc,
                    opcode=iq_entry.opcode,
                    dest_preg=iq_entry.dest_preg,
                    op_a_val=iq_entry.op_a_val,
                    op_b_val=iq_entry.op_b_val,
                )
                next_alu_stage1.append(alu_entry)

        # ============================================================
        # STEP 7: Rename & Dispatch
        # ============================================================
        if not s.exception and not enter_exception and len(next_decoded) > 0:
            num_insts = len(next_decoded)
            # Check resources: free regs, active list slots, IQ slots
            free_regs_available = len(next_free_list)
            al_slots = self.ACTIVE_LIST_SIZE - len(next_active_list)
            iq_slots = self.IQ_SIZE - len(next_int_queue)

            if free_regs_available >= num_insts and al_slots >= num_insts and iq_slots >= num_insts:
                # Rename all instructions in the DIR
                for pc, inst in next_decoded:
                    # Allocate new physical register for destination
                    new_preg = next_free_list.popleft()
                    old_preg = next_reg_map[inst.dest]

                    # Update register map
                    next_reg_map[inst.dest] = new_preg

                    # Mark new preg as busy
                    next_busy_bit[new_preg] = True

                    # Resolve operand A
                    preg_a = next_reg_map[inst.src_a]
                    # Check: is it available in phys reg file (not busy) OR via forwarding?
                    if not next_busy_bit[preg_a]:
                        op_a_ready = True
                        op_a_val = next_phys_reg[preg_a]
                        op_a_tag = preg_a
                    elif preg_a in forwarding:
                        op_a_ready = True
                        op_a_val = forwarding[preg_a][0]
                        op_a_tag = preg_a
                    else:
                        op_a_ready = False
                        op_a_val = 0
                        op_a_tag = preg_a

                    # Resolve operand B
                    if inst.isImmediate():
                        op_b_ready = True
                        op_b_val = _sign_extend_imm(inst.imm)
                        op_b_tag = 0
                    else:
                        preg_b = next_reg_map[inst.src_b]
                        if not next_busy_bit[preg_b]:
                            op_b_ready = True
                            op_b_val = next_phys_reg[preg_b]
                            op_b_tag = preg_b
                        elif preg_b in forwarding:
                            op_b_ready = True
                            op_b_val = forwarding[preg_b][0]
                            op_b_tag = preg_b
                        else:
                            op_b_ready = False
                            op_b_val = 0
                            op_b_tag = preg_b

                    # Allocate Active List entry
                    al_entry = ActiveListEntry(
                        pc=pc,
                        done=False,
                        exception=False,
                        logical_dest=inst.dest,
                        old_dest=old_preg,
                    )
                    next_active_list.append(al_entry)

                    # Allocate IQ entry
                    iq_entry = IQEntry(
                        pc=pc,
                        opcode=inst.opcode,
                        dest_preg=new_preg,
                        op_a_ready=op_a_ready,
                        op_a_tag=op_a_tag,
                        op_a_val=op_a_val,
                        op_b_ready=op_b_ready,
                        op_b_tag=op_b_tag,
                        op_b_val=op_b_val,
                    )
                    next_int_queue.append(iq_entry)

                # Clear the decoded instruction register (consumed)
                next_decoded = []
            # else: stall — decoded_insts stay, no fetch

        # ============================================================
        # STEP 8: Fetch & Decode
        # ============================================================
        if not s.exception and not enter_exception:
            if len(next_decoded) == 0:
                # DIR is empty (was consumed by R&D or was already empty) — fetch
                fetch_count = min(self.FETCH_WIDTH, len(self.program) - next_pc)
                if fetch_count > 0:
                    new_decoded = []
                    for i in range(fetch_count):
                        pc_val = next_pc + i
                        new_decoded.append(self.program[pc_val])
                    next_decoded = new_decoded
                    next_pc = next_pc + fetch_count
            # else: DIR still has instructions (backpressure) — don't fetch

        # ============================================================
        # LATCH: apply next state
        # ============================================================
        s.pc = next_pc
        s.phys_reg_file = next_phys_reg
        s.decoded_insts = next_decoded
        s.exception = next_exception
        s.exception_pc = next_exception_pc
        s.reg_map = next_reg_map
        s.free_list = next_free_list
        s.busy_bit = next_busy_bit
        s.active_list = next_active_list
        s.int_queue = next_int_queue
        self.alu_stage1 = next_alu_stage1
        self.alu_stage2 = next_alu_stage2

    # ------------------------------------------------------------------
    def save(self, path: str):
        with open(path, "w") as f:
            json.dump(self.log, f, indent=2)


# =============================================================================
# Entry point
# =============================================================================

def load_program(path: str) -> list[tuple[int, Instruction]]:
    with open(path) as f:
        lines = json.load(f)
    return [(pc, Instruction.from_string(line)) for pc, line in enumerate(lines)]


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
