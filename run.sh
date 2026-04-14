#!/bin/bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "Usage: ./run.sh </path/to/input.json> </path/to/output.json>" >&2
  exit 1
fi

INPUT_JSON="$1"
OUTPUT_JSON="$2"
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

PYTHON_BIN="python3"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

"$PYTHON_BIN" - "$ROOT_DIR" "$INPUT_JSON" "$OUTPUT_JSON" <<'PY'
import os
import sys

root_dir, input_json, output_json = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, os.path.join(root_dir, "hw"))

from cpu import CPU

out_dir = os.path.dirname(output_json)
if out_dir:
    os.makedirs(out_dir, exist_ok=True)

cpu = CPU(numALUs=4, numPhysicalRegisters=64, numLogicalRegisters=32)
cpu.reset()
cpu.parseInstructions(input_json)
cpu.dumpStateIntoLog(output_json)

max_cycles = 1_000_000
cycle = 0

while not (cpu.noInstructionsLeft() and cpu.activeListIsEmpty() and (not cpu.currentState.exceptionFlag)):
    cycle += 1
    if cycle > max_cycles:
        raise RuntimeError(f"Simulation exceeded max cycles ({max_cycles})")

    cpu.propagate()
    cpu.latch()
    cpu.dumpStateIntoLog(output_json)
PY
