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

"$PYTHON_BIN" "$ROOT_DIR/hw/cpu.py" "$INPUT_JSON" "$OUTPUT_JSON"
