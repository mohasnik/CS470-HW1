# json_io.py — OoO470 JSON I/O Utility

Helper module for the OoO470 cycle-accurate simulator. Handles input parsing, binary encoding, output serialization, and basic debugging.

---

## CLI Usage

**Parse input instructions (print only):**
```bash
python3 json_io.py parse <input.json>
```

**Parse + emit a `$readmemh` hex `.mem` file:**
```bash
python3 json_io.py parse <input.json> --mem <out.mem>
```

**Parse + emit a raw little-endian binary file:**
```bash
python3 json_io.py parse <input.json> --bin <out.bin>
```

**Parse + emit both at once:**
```bash
python3 json_io.py parse <input.json> --mem <out.mem> --bin <out.bin>
```

**Validate structure of your output file:**
```bash
python3 json_io.py validate <output.json>
```

**Inspect a specific cycle:**
```bash
python3 json_io.py inspect <output.json> --cycle 3
```

---

## Binary Encoding Reference

Instructions are encoded as standard 32-bit RISC-V words (RV32I / RV64M subset):

| Opcode | Type | opcode | funct3 | funct7 |
|--------|------|--------|--------|--------|
| `add`  | R    | 0x33   | 000    | 0000000 |
| `sub`  | R    | 0x33   | 000    | 0100000 |
| `mulu` | R    | 0x33   | 000    | 0000001 (RV64M `mul`) |
| `divu` | R    | 0x33   | 101    | 0000001 |
| `remu` | R    | 0x33   | 111    | 0000001 |
| `addi` | I    | 0x13   | 000    | — (imm masked to 12 bits) |

- `.mem` format: one 8-digit hex word per line → load with Verilog `$readmemh`
- `.bin` format: raw `uint32` little-endian words → load directly into hardware sim

---

## Using as a Module in Your Simulator

```python
from util.json_io import InputParser, OutputWriter, CycleSnapshot, ActiveListEntry, IQEntry
from util.json_io import InstructionEncoder, MemFileWriter

# 1. Parse input
instructions = InputParser().parse_file("input.json")

# 2. (Optional) encode to binary
MemFileWriter().write_hex(instructions, "prog.mem")
MemFileWriter().write_bin(instructions, "prog.bin")

# 3. Set up writer and record reset state
writer = OutputWriter()
writer.record(OutputWriter.initial_snapshot())

# 4. Each cycle: build a CycleSnapshot and record it
snapshot = CycleSnapshot(
    pc=4,
    exception=False,
    exception_pc=0,
    decoded_pcs=[0, 1, 2, 3],
    physical_register_file=[0] * 64,
    register_map_table=list(range(32)),
    free_list=list(range(36, 64)),
    busy_bit_table=[False] * 64,
    active_list=[
        ActiveListEntry(done=False, exception=False,
                        logical_destination=1, old_destination=1, pc=0)
    ],
    integer_queue=[
        IQEntry(dest_register=32, op_a_is_ready=True, op_a_reg_tag=0,
                op_a_value=0, op_b_is_ready=True, op_b_reg_tag=0,
                op_b_value=1, opcode="addi", pc=0)
    ],
)
writer.record(snapshot)

# 5. Write output
writer.write_file("output.json")
```

---

## Data Classes Reference

| Class | Key fields |
|---|---|
| `Instruction` | `pc`, `opcode`, `dest`, `op_a`, `op_b` (or `imm` for `addi`) |
| `ActiveListEntry` | `done`, `exception`, `logical_destination`, `old_destination`, `pc` |
| `IQEntry` | `dest_register`, `op_a_is_ready`, `op_a_reg_tag`, `op_a_value`, `op_b_*`, `opcode`, `pc` |
| `CycleSnapshot` | all 10 processor state fields |
| `InstructionEncoder` | `.encode(instr)` → 32-bit int |
| `MemFileWriter` | `.write_hex(instrs, path)`, `.write_bin(instrs, path)` |
