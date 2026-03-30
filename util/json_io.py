#!/usr/bin/env python3
"""
json_io.py  —  JSON I/O utilities for the OoO470 cycle-accurate simulator.

Usage
-----
Parse input (print only):
    python3 json_io.py parse <input.json>

Parse + emit $readmemh hex file:
    python3 json_io.py parse <input.json> --mem <out.mem>

Parse + emit raw binary file:
    python3 json_io.py parse <input.json> --bin <out.bin>

Parse + emit both:
    python3 json_io.py parse <input.json> --mem <out.mem> --bin <out.bin>

Validate output against reference:
    python3 json_io.py validate <output.json>

Inspect a single cycle from an output file:
    python3 json_io.py inspect <output.json> --cycle 3
"""

import json
import argparse
import re
import struct
import sys
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes (used by the simulator — import this module)
# ---------------------------------------------------------------------------

@dataclass
class Instruction:
    pc:    int
    opcode: str          # "add" | "addi" | "sub" | "mulu" | "divu" | "remu"
    dest:  int           # architectural register index
    op_a:  int           # architectural register index
    op_b:  Optional[int] # architectural register index (None for addi)
    imm:   Optional[int] # sign-extended immediate (None unless addi)


@dataclass
class ActiveListEntry:
    done:                bool
    exception:           bool
    logical_destination: int
    old_destination:     int
    pc:                  int

    def to_dict(self) -> dict:
        return {
            "Done":               self.done,
            "Exception":          self.exception,
            "LogicalDestination": self.logical_destination,
            "OldDestination":     self.old_destination,
            "PC":                 self.pc,
        }


@dataclass
class IQEntry:
    dest_register: int
    op_a_is_ready: bool
    op_a_reg_tag:  int
    op_a_value:    int
    op_b_is_ready: bool
    op_b_reg_tag:  int
    op_b_value:    int
    opcode:        str
    pc:            int

    def to_dict(self) -> dict:
        return {
            "DestRegister": self.dest_register,
            "OpAIsReady":   self.op_a_is_ready,
            "OpARegTag":    self.op_a_reg_tag,
            "OpAValue":     self.op_a_value,
            "OpBIsReady":   self.op_b_is_ready,
            "OpBRegTag":    self.op_b_reg_tag,
            "OpBValue":     self.op_b_value,
            "OpCode":       self.opcode,
            "PC":           self.pc,
        }


@dataclass
class CycleSnapshot:
    pc:                    int
    exception:             bool
    exception_pc:          int
    decoded_pcs:           list[int]
    physical_register_file: list[int]    # 64 elements
    register_map_table:    list[int]     # 32 elements
    free_list:             list[int]
    busy_bit_table:        list[bool]    # 64 elements
    active_list:           list[ActiveListEntry]
    integer_queue:         list[IQEntry]

    def to_dict(self) -> dict:
        return {
            "ActiveList":           [e.to_dict() for e in self.active_list],
            "BusyBitTable":         self.busy_bit_table,
            "DecodedPCs":           self.decoded_pcs,
            "Exception":            self.exception,
            "ExceptionPC":          self.exception_pc,
            "FreeList":             self.free_list,
            "IntegerQueue":         [e.to_dict() for e in self.integer_queue],
            "PC":                   self.pc,
            "PhysicalRegisterFile": self.physical_register_file,
            "RegisterMapTable":     self.register_map_table,
        }


# ---------------------------------------------------------------------------
# Parser  —  reads input.json → list[Instruction]
# ---------------------------------------------------------------------------

_REG = r'x(\d+)'
_IMM = r'(-?\d+)'

_PATTERNS = {
    "add":  re.compile(rf'add\s+{_REG}\s*,\s*{_REG}\s*,\s*{_REG}'),
    "addi": re.compile(rf'addi\s+{_REG}\s*,\s*{_REG}\s*,\s*{_IMM}'),
    "sub":  re.compile(rf'sub\s+{_REG}\s*,\s*{_REG}\s*,\s*{_REG}'),
    "mulu": re.compile(rf'mulu\s+{_REG}\s*,\s*{_REG}\s*,\s*{_REG}'),
    "divu": re.compile(rf'divu\s+{_REG}\s*,\s*{_REG}\s*,\s*{_REG}'),
    "remu": re.compile(rf'remu\s+{_REG}\s*,\s*{_REG}\s*,\s*{_REG}'),
}


class InputParser:
    """Reads input.json and returns a list of Instruction objects."""

    def parse_file(self, path: str) -> list[Instruction]:
        with open(path) as f:
            raw = json.load(f)
        if not isinstance(raw, list):
            raise ValueError("Input JSON must be a list of instruction strings.")
        return [self._parse_line(line.strip(), pc) for pc, line in enumerate(raw)]

    def _parse_line(self, line: str, pc: int) -> Instruction:
        opcode = line.split()[0]
        if opcode not in _PATTERNS:
            raise ValueError(f"Unknown opcode '{opcode}' at PC={pc}: {line!r}")
        m = _PATTERNS[opcode].match(line)
        if not m:
            raise ValueError(f"Cannot parse instruction at PC={pc}: {line!r}")
        groups = [int(x) for x in m.groups()]
        dest, a = groups[0], groups[1]
        if opcode == "addi":
            return Instruction(pc, opcode, dest, a, op_b=None, imm=groups[2])
        else:
            return Instruction(pc, opcode, dest, a, op_b=groups[2], imm=None)


# ---------------------------------------------------------------------------
# Output writer  —  accumulates CycleSnapshots, writes output.json
# ---------------------------------------------------------------------------

class OutputWriter:
    """Collects per-cycle snapshots and serialises them to JSON."""

    def __init__(self):
        self._cycles: list[CycleSnapshot] = []

    def record(self, snapshot: CycleSnapshot):
        self._cycles.append(snapshot)

    def write_file(self, path: str):
        with open(path, "w") as f:
            json.dump([s.to_dict() for s in self._cycles], f, indent=2)

    # Convenience: initial (reset) snapshot
    @staticmethod
    def initial_snapshot() -> CycleSnapshot:
        return CycleSnapshot(
            pc=0,
            exception=False,
            exception_pc=0,
            decoded_pcs=[],
            physical_register_file=[0] * 64,
            register_map_table=list(range(32)),
            free_list=list(range(32, 64)),
            busy_bit_table=[False] * 64,
            active_list=[],
            integer_queue=[],
        )


# ---------------------------------------------------------------------------
# Instruction encoder  —  Instruction → 32-bit RISC-V binary word
# ---------------------------------------------------------------------------
#
# Encoding reference (standard RV32I / RV64M subset used by OoO470):
#
#   R-type  [31:25 funct7][24:20 rs2][19:15 rs1][14:12 funct3][11:7 rd][6:0 opcode]
#   I-type  [31:20 imm12 ][19:15 rs1][14:12 funct3][11:7 rd][6:0 opcode]
#
#   opcode  funct3  funct7    mnemonic
#   0x33    000     0000000   add
#   0x33    000     0100000   sub
#   0x33    000     0000001   mulu   (maps to RV64M mul)
#   0x33    101     0000001   divu   (RV64M divu)
#   0x33    111     0000001   remu   (RV64M remu)
#   0x13    000     —         addi   (I-type, imm sign-extended to 12 bits)

_RTYPE = {
    #          opcode   funct3  funct7
    "add":  (0x33,    0b000,  0b0000000),
    "sub":  (0x33,    0b000,  0b0100000),
    "mulu": (0x33,    0b000,  0b0000001),
    "divu": (0x33,    0b101,  0b0000001),
    "remu": (0x33,    0b111,  0b0000001),
}


class InstructionEncoder:
    """Encodes an Instruction into a 32-bit RISC-V integer."""

    def encode(self, instr: Instruction) -> int:
        if instr.opcode == "addi":
            return self._encode_itype(instr)
        return self._encode_rtype(instr)

    def _encode_rtype(self, instr: Instruction) -> int:
        opcode, funct3, funct7 = _RTYPE[instr.opcode]
        return (
            (funct7          << 25) |
            (instr.op_b      << 20) |
            (instr.op_a      << 15) |
            (funct3          << 12) |
            (instr.dest      <<  7) |
            opcode
        )

    def _encode_itype(self, instr: Instruction) -> int:
        opcode, funct3 = 0x13, 0b000
        imm12 = instr.imm & 0xFFF   # keep lower 12 bits (handles negatives)
        return (
            (imm12       << 20) |
            (instr.op_a  << 15) |
            (funct3      << 12) |
            (instr.dest  <<  7) |
            opcode
        )


# ---------------------------------------------------------------------------
# .mem file writer
# ---------------------------------------------------------------------------

class MemFileWriter:
    """
    Writes encoded instructions to disk.

    Formats
    -------
    hex  (.mem)  — one 8-digit hex word per line, suitable for Verilog $readmemh
    bin  (.bin)  — raw little-endian 32-bit words, one per instruction
    """

    def __init__(self):
        self._encoder = InstructionEncoder()

    def write_hex(self, instructions: list[Instruction], path: str):
        words = [self._encoder.encode(i) for i in instructions]
        with open(path, "w") as f:
            for w in words:
                f.write(f"{w:08x}\n")
        print(f"Wrote {len(words)} words → {path}  (hex / $readmemh)")

    def write_bin(self, instructions: list[Instruction], path: str):
        words = [self._encoder.encode(i) for i in instructions]
        with open(path, "wb") as f:
            for w in words:
                f.write(struct.pack("<I", w))   # little-endian uint32
        print(f"Wrote {len(words)} words → {path}  (binary little-endian)")


# ---------------------------------------------------------------------------
# CLI actions
# ---------------------------------------------------------------------------

def _cmd_parse(args):
    instructions = InputParser().parse_file(args.input)
    print(f"Parsed {len(instructions)} instructions:")
    encoder = InstructionEncoder()
    for instr in instructions:
        word = encoder.encode(instr)
        if instr.opcode == "addi":
            desc = f"dest=x{instr.dest}  opA=x{instr.op_a}  imm={instr.imm}"
        else:
            desc = f"dest=x{instr.dest}  opA=x{instr.op_a}  opB=x{instr.op_b}"
        print(f"  PC={instr.pc:2d}  {instr.opcode:<4}  {desc:<35}  -> 0x{word:08x}")

    writer = MemFileWriter()
    if args.mem:
        writer.write_hex(instructions, args.mem)
    if args.bin:
        writer.write_bin(instructions, args.bin)


def _cmd_inspect(args):
    with open(args.output) as f:
        cycles = json.load(f)
    if args.cycle >= len(cycles):
        print(f"Error: only {len(cycles)} cycles in file (requested cycle {args.cycle}).")
        sys.exit(1)
    c = cycles[args.cycle]
    print(f"=== Cycle {args.cycle} ===")
    print(f"  PC            : {c['PC']}")
    print(f"  Exception     : {c['Exception']}  ExceptionPC={c['ExceptionPC']}")
    print(f"  DecodedPCs    : {c['DecodedPCs']}")
    print(f"  FreeList      : {c['FreeList']}")
    print(f"  ActiveList    : {len(c['ActiveList'])} entries")
    for e in c['ActiveList']:
        print(f"    {e}")
    print(f"  IntegerQueue  : {len(c['IntegerQueue'])} entries")
    for e in c['IntegerQueue']:
        print(f"    {e}")
    busy = [i for i, b in enumerate(c['BusyBitTable']) if b]
    print(f"  Busy phys regs: {busy}")


def _cmd_validate(args):
    """Lightweight structural check (not a full compare — use compare.py for grading)."""
    with open(args.output) as f:
        cycles = json.load(f)
    required_keys = {
        "ActiveList", "BusyBitTable", "DecodedPCs", "Exception",
        "ExceptionPC", "FreeList", "IntegerQueue", "PC",
        "PhysicalRegisterFile", "RegisterMapTable",
    }
    errors = 0
    for i, c in enumerate(cycles):
        missing = required_keys - c.keys()
        if missing:
            print(f"Cycle {i}: missing keys {missing}")
            errors += 1
        if len(c.get("PhysicalRegisterFile", [])) != 64:
            print(f"Cycle {i}: PhysicalRegisterFile must have 64 elements")
            errors += 1
        if len(c.get("BusyBitTable", [])) != 64:
            print(f"Cycle {i}: BusyBitTable must have 64 elements")
            errors += 1
        if len(c.get("RegisterMapTable", [])) != 32:
            print(f"Cycle {i}: RegisterMapTable must have 32 elements")
            errors += 1
    if errors == 0:
        print(f"OK — {len(cycles)} cycles, structure looks valid.")
    else:
        print(f"{errors} error(s) found.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="OoO470 JSON I/O utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_parse = sub.add_parser("parse", help="Parse input.json, print instructions, optionally emit .mem/.bin")
    p_parse.add_argument("input", help="Path to input.json")
    p_parse.add_argument("--mem", metavar="OUT.mem", default=None,
                         help="Write $readmemh hex file to this path")
    p_parse.add_argument("--bin", metavar="OUT.bin", default=None,
                         help="Write raw little-endian binary file to this path")

    p_inspect = sub.add_parser("inspect", help="Pretty-print one cycle from output.json")
    p_inspect.add_argument("output", help="Path to output.json")
    p_inspect.add_argument("--cycle", "-c", type=int, default=0, help="Cycle index (default: 0)")

    p_val = sub.add_parser("validate", help="Structural validation of output.json")
    p_val.add_argument("output", help="Path to output.json")

    args = parser.parse_args()
    {"parse": _cmd_parse, "inspect": _cmd_inspect, "validate": _cmd_validate}[args.cmd](args)


if __name__ == "__main__":
    main()
